"""Test Task 2.2 (spec shm-production-hardening): ring control segment + fail-fast attach.

Phủ phần MỚI của migration v2: ring-level control segment self-describing + attach mismatch → raise.
(Attach-OK với control khớp đã được `test_step_05_shm.py::test_writer_in_subprocess_reader_in_parent`
phủ qua đường create=False thật.)
"""
from __future__ import annotations

import struct
import uuid

import pytest

from vision_platform.kernel.shm_layout import (
    RING_CONTROL_FMT, RING_MAGIC, HEADER_VERSION, SLOT_HEADER_V2_BYTES, MAX_READERS,
    check_ring_control,
)
from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer


def _make_creator(name: str) -> ShmRingBuffer:
    return ShmRingBuffer(name=name, n_slots=4, height=8, width=8, channels=3, create=True)


def test_creator_writes_valid_control():
    name = f"v2ctl_{uuid.uuid4().hex[:8]}"
    ring = _make_creator(name)
    try:
        raw = bytes(ring._ctrl_shm.buf[:struct.calcsize(RING_CONTROL_FMT)])
        check_ring_control(raw)  # không raise
        magic, version, header_size, max_readers = struct.unpack(RING_CONTROL_FMT, raw)
        assert magic == RING_MAGIC
        assert version == HEADER_VERSION
        assert header_size == SLOT_HEADER_V2_BYTES == 256
        assert max_readers == MAX_READERS
    finally:
        ring.cleanup_all()


def test_attach_with_bad_magic_fails_fast():
    """Corrupt magic trong ctrl segment sống → attach (create=False) RAISE ngay, không đụng slot."""
    name = f"v2bad_{uuid.uuid4().hex[:8]}"
    creator = _make_creator(name)
    try:
        n = struct.calcsize(RING_CONTROL_FMT)
        creator._ctrl_shm.buf[:n] = struct.pack(
            RING_CONTROL_FMT, 0xDEADBEEF, HEADER_VERSION, SLOT_HEADER_V2_BYTES, MAX_READERS,
        )
        with pytest.raises(ValueError):
            ShmRingBuffer(
                name=name, n_slots=4, height=8, width=8, channels=3,
                create=False, slot_locks=creator.slot_locks_for_children,
            )
    finally:
        creator.cleanup_all()


def test_attach_with_bad_version_fails_fast():
    name = f"v2ver_{uuid.uuid4().hex[:8]}"
    creator = _make_creator(name)
    try:
        n = struct.calcsize(RING_CONTROL_FMT)
        creator._ctrl_shm.buf[:n] = struct.pack(
            RING_CONTROL_FMT, RING_MAGIC, 1, SLOT_HEADER_V2_BYTES, MAX_READERS,  # version 1 (cũ)
        )
        with pytest.raises(ValueError):
            ShmRingBuffer(
                name=name, n_slots=4, height=8, width=8, channels=3,
                create=False, slot_locks=creator.slot_locks_for_children,
            )
    finally:
        creator.cleanup_all()


def test_meta_segment_holds_v2_header():
    """Meta segment đủ chỗ cho header v2 256B (buf length >= 256)."""
    name = f"v2sz_{uuid.uuid4().hex[:8]}"
    ring = _make_creator(name)
    try:
        assert len(ring._meta_shms[0].buf) >= SLOT_HEADER_V2_BYTES
    finally:
        ring.cleanup_all()
