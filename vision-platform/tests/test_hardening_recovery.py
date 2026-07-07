"""Test Task 4.2 (spec shm-production-hardening): crash-recovery + terminal quarantine.

Deterministic: tiêm `liveness_fn` vào ring (không phụ thuộc process thật) + dựng state slot thủ công.
Subprocess kill THẬT là Task 4.3.
"""
from __future__ import annotations

import time
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc import shm_frame_ring as R
from vision_platform.runtime.ipc._process_identity import Liveness
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader,
    _write_header, SlotState, LOCK_ACQUIRE_TIMEOUT_S,
)


def _ring(liveness: Liveness):
    return ShmRingBuffer(
        name=f"rec_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
        create=True, liveness_fn=lambda pid, ct: liveness,
    )


def _set_slot(ring, idx, state, *, pid=999, ct=111, lease_offset_ns=-1_000_000):
    """Dựng header slot: state + owner(pid,ct) + lease = now + offset (mặc định quá hạn 1ms)."""
    _write_header(
        ring._meta_shms[idx].buf, state, 5, pid, ct,
        time.monotonic_ns() + lease_offset_ns,
    )


def _set_reader(ring, slot_idx, reg_idx, *, pid=999, ct=111, lease_offset_ns=-1_000_000):
    """Ghi 1 ô reader_registry + cập nhật reader_count (mô phỏng reader đã pin)."""
    from vision_platform.runtime.ipc.shm_frame_ring import (
        _registry_set, _registry_count, _write_reader_count,
    )
    buf = ring._meta_shms[slot_idx].buf
    _registry_set(buf, reg_idx, pid, ct, time.monotonic_ns() + lease_offset_ns)
    _write_reader_count(buf, _registry_count(buf))


def _frame(v: int):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def test_lock_acquire_timeout_constant():
    assert LOCK_ACQUIRE_TIMEOUT_S == 0.1


# ============ quarantine_poisoned_slot — bảng quyết định ============

def test_quarantine_when_dead_and_lease_expired():
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.WRITING)          # lease quá hạn
        assert ring.quarantine_poisoned_slot(0) is True
        assert ring.peek_state(0) == SlotState.QUARANTINED
    finally:
        ring.cleanup_all()


def test_no_quarantine_when_lease_not_expired():
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.WRITING, lease_offset_ns=5_000_000_000)  # còn 5s
        assert ring.quarantine_poisoned_slot(0) is False
        assert ring.peek_state(0) == SlotState.WRITING
    finally:
        ring.cleanup_all()


def test_no_quarantine_when_owner_alive():
    ring = _ring(Liveness.ALIVE)
    try:
        _set_slot(ring, 0, SlotState.WRITING)
        assert ring.quarantine_poisoned_slot(0) is False
        assert ring.peek_state(0) == SlotState.WRITING
    finally:
        ring.cleanup_all()


def test_no_quarantine_when_owner_unknown():
    ring = _ring(Liveness.UNKNOWN)
    try:
        _set_slot(ring, 0, SlotState.READING)
        _set_reader(ring, 0, 0)                         # 1 reader trong registry, lease quá hạn, liveness UNKNOWN
        assert ring.quarantine_poisoned_slot(0) is False   # UNKNOWN → bảo vệ slot (R-2.2)
        assert ring.peek_state(0) == SlotState.READING
    finally:
        ring.cleanup_all()


@pytest.mark.parametrize("state", [SlotState.FREE, SlotState.DONE])
def test_no_quarantine_for_free_or_done(state):
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, state)
        assert ring.quarantine_poisoned_slot(0) is False
    finally:
        ring.cleanup_all()


def test_no_quarantine_when_already_quarantined():
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.QUARANTINED)
        assert ring.quarantine_poisoned_slot(0) is False
    finally:
        ring.cleanup_all()


def test_double_snapshot_torn_skips(monkeypatch):
    """2 snapshot KHÁC nhau (torn/đang đổi) → KHÔNG quarantine (P1-1)."""
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.WRITING)
        seq = iter([b"\x00" * 256, b"\x01" * 256])   # 2 snapshot bytes KHÁC nhau → torn
        monkeypatch.setattr(R, "_full_snapshot", lambda buf: next(seq))
        assert ring.quarantine_poisoned_slot(0) is False
        assert ring.peek_state(0) == SlotState.WRITING
    finally:
        ring.cleanup_all()


# ============ Integration: lock bị giữ → writer/reader recovery ============

def test_writer_recovers_when_slot_lock_held_by_dead_owner():
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.WRITING)          # slot0 đang WRITING, owner DEAD, lease quá hạn
        held = ring.slot_lock(0)
        assert held.acquire(timeout=1.0)               # giữ lock slot0 (mô phỏng owner chết còn giữ lock)
        try:
            writer = ShmFrameWriter(ring)
            ref = writer.write(_frame(7))              # không acquire được slot0 → quarantine → ghi slot khác
            assert ref is not None
            assert ref.slot != 0
            assert ring.peek_state(0) == SlotState.QUARANTINED
        finally:
            held.release()
    finally:
        ring.cleanup_all()


def test_reader_recovers_when_slot_lock_held():
    ring = _ring(Liveness.DEAD)
    try:
        _set_slot(ring, 0, SlotState.READY)            # slot0 READY nhưng lock bị giữ + owner DEAD + lease quá hạn
        held = ring.slot_lock(0)
        assert held.acquire(timeout=1.0)
        try:
            reader = ShmFrameReader(ring)
            assert reader.read(0, 5) is None           # không pin được → quarantine → None
            assert ring.peek_state(0) == SlotState.QUARANTINED
        finally:
            held.release()
    finally:
        ring.cleanup_all()
