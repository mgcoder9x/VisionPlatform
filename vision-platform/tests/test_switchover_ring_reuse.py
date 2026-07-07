"""Task 6 nền (H2 ring-pool, K-012): ShmRingBuffer.reset_for_reuse() — tái dùng ring cho epoch mới.

Giải K-012 bằng NÉ cấp-phát-động: pool ring tạo 1 lần, lock thừa kế; switchover = reset + bump epoch (KHÔNG
tạo SHM/lock mới). Test in-process (deterministic), CHƯA đụng spawn cross-process (Task 6 T-B).
_Requirements: 2.1, 3.1, 4.x (H2 variant)_
"""
from __future__ import annotations

import struct
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameWriter, ShmFrameReader
from vision_platform.kernel.shm_layout import SlotState, OFFSET_STATE, STATE_FMT


def _ring(epoch=1):
    return ShmRingBuffer(name=f"reuse_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
                         create=True, ring_epoch=epoch)


def _frame(v=1):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def test_reset_bumps_epoch_and_clears_slots():
    ring = _ring(epoch=1)
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(7))                       # slot → READY
        assert ref is not None and ring.peek_state(ref.slot) == SlotState.READY

        ring.reset_for_reuse(2)
        assert ring.ring_epoch == 2
        for s in range(ring.n_slots):
            assert ring.peek_state(s) == SlotState.FREE     # mọi slot về FREE
    finally:
        ring.cleanup_all()


def test_reset_clears_quarantined_slot():
    ring = _ring(epoch=1)
    try:
        # Ép slot 0 sang QUARANTINED (terminal) — mô phỏng poison cần rebuild.
        struct.pack_into(STATE_FMT, ring._meta_shms[0].buf, OFFSET_STATE, int(SlotState.QUARANTINED))
        assert ring.peek_state(0) == SlotState.QUARANTINED
        ring.reset_for_reuse(2)
        assert ring.peek_state(0) == SlotState.FREE         # rebuild xoá được QUARANTINED
    finally:
        ring.cleanup_all()


def test_reset_requires_monotonic_epoch():
    ring = _ring(epoch=5)
    try:
        with pytest.raises(ValueError):
            ring.reset_for_reuse(5)                          # == hiện tại
        with pytest.raises(ValueError):
            ring.reset_for_reuse(3)                          # < hiện tại
    finally:
        ring.cleanup_all()


def test_reset_allows_new_writer_registration():
    ring = _ring(epoch=1)
    try:
        ring.register_writer()                               # writer đầu
        ring.reset_for_reuse(2)
        ring.register_writer()                               # sau reset: registry sạch → claim lại được
    finally:
        ring.cleanup_all()


def test_stale_ref_after_reset_returns_none():
    ring = _ring(epoch=2)
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(9))                        # ref.ring_epoch == 2
        assert ref.ring_epoch == 2

        ring.reset_for_reuse(3)                              # tái dùng → epoch 3
        reader = ShmFrameReader(ring)
        assert reader.read_ref(ref) is None                  # ref epoch 2 (cũ) → stale → None
    finally:
        ring.cleanup_all()
