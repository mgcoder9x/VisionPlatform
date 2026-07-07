"""Test Task 9 (spec shm-production-hardening): cold-start sanitation — tên ring epoch/uuid (R-5.1, P1-4)."""
from __future__ import annotations

import numpy as np

from vision_platform.runtime.ipc.shm_frame_ring import (
    new_ring_name, ShmRingBuffer, ShmFrameWriter, ShmFrameReader,
)


def test_new_ring_name_is_unique():
    names = {new_ring_name() for _ in range(1000)}
    assert len(names) == 1000          # uuid → không trùng


def test_new_ring_name_respects_prefix():
    assert new_ring_name("cam0").startswith("cam0_")


def test_ring_with_fresh_name_works_end_to_end():
    ring = ShmRingBuffer(name=new_ring_name("vp_test"), n_slots=4, height=8, width=8, channels=3, create=True)
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(np.full((8, 8, 3), 5, dtype=np.uint8))
        assert np.array_equal(reader.read(ref.slot, ref.generation), np.full((8, 8, 3), 5, dtype=np.uint8))
    finally:
        ring.cleanup_all()


def test_two_sessions_get_different_ring_names():
    """Mỗi 'phiên' (mỗi lần dựng) tên khác → creator không attach segment phiên trước (cold-start)."""
    n1 = new_ring_name("session")
    n2 = new_ring_name("session")
    assert n1 != n2
