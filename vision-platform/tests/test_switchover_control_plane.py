"""RingControlPlane publish/read + fail-fast attach (sub-spec shm-ring-epoch-switchover).

_Requirements: 2.1, 2.2, 2.3, 2.4, 6.2_
"""
from __future__ import annotations

import uuid
from multiprocessing import shared_memory

import pytest

from vision_platform.kernel.shm_control_plane_layout import CP_SEGMENT_BYTES
from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane


def _uniq() -> str:
    return f"vp_cp_test_{uuid.uuid4().hex}"


def test_publish_read_roundtrip():
    cp = RingControlPlane(_uniq(), create=True)
    try:
        assert cp.read_current() == (0, "")   # chưa publish
        cp.publish(1, "vp_ring_abc123")
        assert cp.read_current() == (1, "vp_ring_abc123")
    finally:
        cp.close()
        cp.unlink()


def test_publish_monotonic_overwrite():
    cp = RingControlPlane(_uniq(), create=True)
    try:
        cp.publish(1, "vp_ring_one")
        cp.publish(2, "vp_ring_two")
        assert cp.read_current() == (2, "vp_ring_two")
    finally:
        cp.close()
        cp.unlink()


def test_cross_handle_attach_reads_published():
    name = _uniq()
    creator = RingControlPlane(name, create=True)
    try:
        creator.publish(7, "vp_ring_" + "d" * 32)
        attached = RingControlPlane(name, create=False)   # attach handle thứ 2 (chỉ-đọc)
        try:
            assert attached.read_current() == (7, "vp_ring_" + "d" * 32)
        finally:
            attached.close()
    finally:
        creator.close()
        creator.unlink()


def test_attach_wrong_magic_fail_fast():
    name = _uniq()
    # Tạo segment THÔ không có header hợp lệ (zero-init → magic=0)
    raw = shared_memory.SharedMemory(name=name, create=True, size=CP_SEGMENT_BYTES)
    try:
        with pytest.raises(ValueError):
            RingControlPlane(name, create=False)
    finally:
        raw.close()
        raw.unlink()
