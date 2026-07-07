"""Test Task 4.1 (spec shm-production-hardening): ghi owner identity + lease vào header.

4.1 = phần GHI (de-risk cho recovery 4.2): writer/reader ghi (pid, create_time, lease_deadline).
Recovery THẬT (đọc các field này để quyết quarantine) là Task 4.2.
"""
from __future__ import annotations

import time
import uuid

import numpy as np

from vision_platform.runtime.ipc._process_identity import current_identity
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader,
    _read_owner, _read_lease, WRITE_LEASE_NS, READ_LEASE_NS, SlotState,
)


def _ring():
    return ShmRingBuffer(
        name=f"ls_{uuid.uuid4().hex[:8]}", n_slots=4,
        height=8, width=8, channels=3, create=True,
    )


def _frame(v: int):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def test_lease_constants_are_2s():
    assert WRITE_LEASE_NS == 2_000_000_000
    assert READ_LEASE_NS == 2_000_000_000


def test_writer_sets_owner_identity_and_lease():
    ring = _ring()
    try:
        writer = ShmFrameWriter(ring)
        expect_pid, expect_ct = current_identity()
        t_before = time.monotonic_ns()
        ref = writer.write(_frame(7))
        t_after = time.monotonic_ns()

        pid, ct = _read_owner(ring._meta_shms[ref.slot].buf)
        assert pid == expect_pid
        assert ct == expect_ct

        lease = _read_lease(ring._meta_shms[ref.slot].buf)
        # lease = monotonic_ns()+WRITE_LEASE_NS tại lúc ghi → nằm trong [t_before+L, t_after+L].
        assert t_before + WRITE_LEASE_NS <= lease <= t_after + WRITE_LEASE_NS
    finally:
        ring.cleanup_all()


def test_done_clears_owner_and_lease():
    ring = _ring()
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(3))
        out = reader.read(ref.slot, ref.generation)
        assert out is not None
        assert ring.peek_state(ref.slot) == SlotState.DONE
        pid, ct = _read_owner(ring._meta_shms[ref.slot].buf)
        assert pid == 0 and ct == 0
        assert _read_lease(ring._meta_shms[ref.slot].buf) == 0
    finally:
        ring.cleanup_all()


def test_free_slot_has_zero_lease():
    ring = _ring()
    try:
        assert _read_lease(ring._meta_shms[0].buf) == 0
        pid, ct = _read_owner(ring._meta_shms[0].buf)
        assert pid == 0 and ct == 0
    finally:
        ring.cleanup_all()
