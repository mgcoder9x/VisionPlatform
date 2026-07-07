"""Test Task 6 (spec shm-production-hardening): observability hook + taxonomy (P-2 / P2-2).

Tiêm RecordingHook để kiểm các sự kiện + field tối thiểu phát ra đúng. Hook mặc định = no-op (không vỡ).
"""
from __future__ import annotations

import time
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc._process_identity import Liveness
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader, ObservabilityHook, ReaderRegistryFull,
    _write_header, _registry_set, _registry_count, _write_reader_count, _reap_dead_readers,
    SlotState,
)


class RecordingHook(ObservabilityHook):
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append((event, fields))

    @property
    def names(self):
        return [e for e, _ in self.events]

    def fields_of(self, event):
        for e, f in self.events:
            if e == event:
                return f
        return None


def _ring(hook, liveness=Liveness.DEAD):
    return ShmRingBuffer(
        name=f"obs_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
        create=True, liveness_fn=lambda p, c: liveness, obs=hook,
    )


def _frame(v):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def test_quarantine_emits_quarantined_and_capacity():
    hook = RecordingHook()
    ring = _ring(hook, Liveness.DEAD)
    try:
        _write_header(ring._meta_shms[0].buf, SlotState.WRITING, 5, 999, 111, time.monotonic_ns() - 1)
        assert ring.quarantine_poisoned_slot(0) is True
        assert "shm_slot_quarantined" in hook.names
        assert "shm_ring_capacity_degraded" in hook.names
        f = hook.fields_of("shm_slot_quarantined")
        assert f["ring_name"] == ring.name
        assert f["slot"] == 0
        assert f["quarantined_count"] == 1
        assert f["healthy_slots"] == 3
    finally:
        ring.cleanup_all()


def test_owner_liveness_unknown_emits():
    hook = RecordingHook()
    ring = _ring(hook, Liveness.UNKNOWN)
    try:
        _write_header(ring._meta_shms[0].buf, SlotState.WRITING, 5, 999, 111, time.monotonic_ns() - 1)
        assert ring.quarantine_poisoned_slot(0) is False     # UNKNOWN → không quarantine
        assert "shm_owner_liveness_unknown" in hook.names
    finally:
        ring.cleanup_all()


def test_registry_full_emits():
    hook = RecordingHook()
    ring = _ring(hook, Liveness.ALIVE)
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(7))
        buf = ring._meta_shms[ref.slot].buf
        for i in range(8):
            _registry_set(buf, i, 1000 + i, 1, time.monotonic_ns() + 5_000_000_000)
        _write_reader_count(buf, _registry_count(buf))
        import struct as _s
        from vision_platform.kernel.shm_layout import STATE_FMT, OFFSET_STATE, OFFSET_GENERATION, U64_FMT
        _s.pack_into(U64_FMT, buf, OFFSET_GENERATION, ref.generation)
        _s.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.READING))

        reader = ShmFrameReader(ring)
        with pytest.raises(ReaderRegistryFull):
            reader.read(ref.slot, ref.generation)
        assert "shm_reader_registry_full" in hook.names
    finally:
        ring.cleanup_all()


def test_reap_emits_reader_reaped():
    hook = RecordingHook()
    ring = _ring(hook, Liveness.DEAD)
    try:
        buf = ring._meta_shms[0].buf
        _registry_set(buf, 0, 70001, 1, time.monotonic_ns() - 1_000_000)   # chết + lease quá hạn
        _write_reader_count(buf, 1)
        _reap_dead_readers(buf, ring._liveness_fn, ring._obs, ring.name, 0)
        assert "shm_reader_reaped" in hook.names
        f = hook.fields_of("shm_reader_reaped")
        assert f["owner_pid"] == 70001
    finally:
        ring.cleanup_all()


def test_lock_timeout_emits():
    hook = RecordingHook()
    ring = _ring(hook, Liveness.DEAD)
    try:
        _write_header(ring._meta_shms[0].buf, SlotState.WRITING, 5, 999, 111, time.monotonic_ns() - 1)
        held = ring.slot_lock(0)
        assert held.acquire(timeout=1.0)
        try:
            writer = ShmFrameWriter(ring)
            ref = writer.write(_frame(1))
            assert ref is not None and ref.slot != 0
            assert "shm_slot_lock_timeout" in hook.names
        finally:
            held.release()
    finally:
        ring.cleanup_all()


def test_default_hook_is_noop():
    """Ring KHÔNG truyền obs → default ObservabilityHook, emit không vỡ + hành vi không đổi."""
    ring = ShmRingBuffer(name=f"obsd_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
                         create=True, liveness_fn=lambda p, c: Liveness.DEAD)
    try:
        assert isinstance(ring._obs, ObservabilityHook)
        _write_header(ring._meta_shms[0].buf, SlotState.WRITING, 5, 999, 111, time.monotonic_ns() - 1)
        assert ring.quarantine_poisoned_slot(0) is True   # emit no-op, không raise
    finally:
        ring.cleanup_all()
