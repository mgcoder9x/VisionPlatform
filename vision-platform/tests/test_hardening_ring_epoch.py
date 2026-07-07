"""Test Task 8 (spec shm-production-hardening): DTO ring_epoch + stale-ref (P0-3)."""
from __future__ import annotations

import struct
import uuid

import numpy as np

from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.kernel.shm_layout import OFFSET_RING_EPOCH, U64_FMT
from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameWriter, ShmFrameReader


def _ring(epoch=1):
    return ShmRingBuffer(name=f"ep_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
                         create=True, ring_epoch=epoch)


def _frame(v):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def test_dto_has_ring_epoch_default_zero():
    ref = ShmFrameRefData(ring_name="r", slot=0, generation=1, height=8, width=8, channels=3)
    assert ref.ring_epoch == 0
    ref2 = ShmFrameRefData(ring_name="r", slot=0, generation=1, height=8, width=8, channels=3, ring_epoch=5)
    assert ref2.ring_epoch == 5


def test_ring_epoch_written_and_readable():
    ring = _ring(epoch=7)
    try:
        assert ring.ring_epoch == 7
    finally:
        ring.cleanup_all()


def test_writer_stamps_current_epoch_into_ref():
    ring = _ring(epoch=3)
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(1))
        assert ref.ring_epoch == 3
    finally:
        ring.cleanup_all()


def test_reader_returns_none_for_stale_epoch():
    ring = _ring(epoch=2)
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(9))
        # epoch khớp → đọc được
        assert np.array_equal(reader.read(ref.slot, ref.generation, ring_epoch=2), _frame(9))
    finally:
        ring.cleanup_all()


def test_read_ref_detects_stale_after_epoch_change():
    ring = _ring(epoch=2)
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(5))               # ref mang epoch=2
        assert np.array_equal(reader.read_ref(ref), _frame(5))   # epoch khớp

        # Mô phỏng switchover: đổi epoch ring sang 3 → ref cũ (epoch 2) thành stale.
        struct.pack_into(U64_FMT, ring._ctrl_shm.buf, OFFSET_RING_EPOCH, 3)
        assert ring.ring_epoch == 3
        assert reader.read_ref(ref) is None         # stale → None (không đọc nhầm ring mới)
    finally:
        ring.cleanup_all()
