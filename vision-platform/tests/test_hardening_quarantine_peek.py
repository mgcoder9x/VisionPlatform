"""Test Task 3 (spec shm-production-hardening): lock-free peek + skip QUARANTINED (chưa active recovery).

QUARANTINED được set THỦ CÔNG (mô phỏng recovery sẽ làm ở Task 4) để kiểm writer/reader BỎ QUA slot
terminal qua lock-free peek, KHÔNG đụng lock. Recovery thật (điều kiện owner-chết + lease) là Task 4.
"""
from __future__ import annotations

import struct
import uuid

import numpy as np

from vision_platform.kernel.shm_layout import STATE_FMT, OFFSET_STATE, SlotState
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader,
)


def _ring(n_slots: int = 4):
    return ShmRingBuffer(
        name=f"q_{uuid.uuid4().hex[:8]}", n_slots=n_slots,
        height=8, width=8, channels=3, create=True,
    )


def _frame(v: int):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def _force_quarantine(ring: ShmRingBuffer, slot_idx: int) -> None:
    """Set state=QUARANTINED trực tiếp (atomic 4B store) — mô phỏng recovery."""
    struct.pack_into(STATE_FMT, ring._meta_shms[slot_idx].buf, OFFSET_STATE, int(SlotState.QUARANTINED))


# ============ peek phản ánh đúng state ============

def test_peek_state_reflects_lifecycle():
    ring = _ring()
    try:
        assert ring.peek_state(0) == SlotState.FREE
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(7))
        assert ring.peek_state(ref.slot) == SlotState.READY
        reader.read(ref.slot, ref.generation)
        assert ring.peek_state(ref.slot) == SlotState.DONE
    finally:
        ring.cleanup_all()


# ============ writer/reader bỏ qua QUARANTINED ============

def test_writer_skips_quarantined_slot():
    ring = _ring()
    try:
        _force_quarantine(ring, 0)        # slot 0 terminal
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(1))     # phải nhảy sang slot khác
        assert ref is not None
        assert ref.slot != 0
        # slot 0 vẫn QUARANTINED (sticky) — writer KHÔNG đụng tới
        assert ring.peek_state(0) == SlotState.QUARANTINED
    finally:
        ring.cleanup_all()


def test_reader_returns_none_for_quarantined_slot():
    ring = _ring()
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(5))          # slot 0 READY
        _force_quarantine(ring, ref.slot)      # rồi bị quarantine
        assert reader.read(ref.slot, ref.generation) is None
        assert ring.peek_state(ref.slot) == SlotState.QUARANTINED  # sticky
    finally:
        ring.cleanup_all()


def test_quarantined_sticky_through_writer_scan():
    ring = _ring()
    try:
        _force_quarantine(ring, 0)
        writer = ShmFrameWriter(ring)
        for v in range(3):
            writer.write(_frame(v))   # lấp các slot khỏe
        assert ring.peek_state(0) == SlotState.QUARANTINED  # không bao giờ revert
    finally:
        ring.cleanup_all()


def test_writer_returns_none_when_all_quarantined():
    ring = _ring(n_slots=4)
    try:
        for i in range(4):
            _force_quarantine(ring, i)
        writer = ShmFrameWriter(ring)
        assert writer.write(_frame(9)) is None   # hết slot khỏe → None (không deadlock)
    finally:
        ring.cleanup_all()
