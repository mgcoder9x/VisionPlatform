"""Bootstrap ring hiện tại qua control-plane (sub-spec shm-ring-epoch-switchover, Task 4.1).

_Requirements: 2.2, 4.1_
Additive — KHÔNG sửa ShmFrameWriter/ShmFrameReader hiện có (dùng ring_opener tiêm ngoài).
Teardown ring cũ dựa OS handle ref-count (quyết định B) — không có biến đếm tường minh.
"""
from __future__ import annotations

import uuid

import pytest

from vision_platform.runtime.ipc.ring_control_plane import (
    RingControlPlane, bootstrap_current_ring,
)


def _uniq() -> str:
    return f"vp_cp_test_{uuid.uuid4().hex}"


def test_bootstrap_reads_current_ring():
    creator = RingControlPlane(_uniq(), create=True)
    try:
        ring_name = "vp_ring_" + "b" * 32
        creator.publish(1, ring_name)
        opened: list[str] = []
        ring, epoch = bootstrap_current_ring(creator, ring_opener=lambda n: opened.append(n) or n)
        assert epoch == 1
        assert ring == ring_name
        assert opened == [ring_name]
    finally:
        creator.close()
        creator.unlink()


def test_two_consumers_bootstrap_same_ring():
    name = _uniq()
    creator = RingControlPlane(name, create=True)
    try:
        ring_name = "vp_ring_" + "c" * 32
        creator.publish(3, ring_name)
        c1 = RingControlPlane(name, create=False)   # attach chỉ-đọc
        c2 = RingControlPlane(name, create=False)
        try:
            r1, e1 = bootstrap_current_ring(c1, ring_opener=lambda n: n)
            r2, e2 = bootstrap_current_ring(c2, ring_opener=lambda n: n)
            assert (e1, r1) == (3, ring_name)
            assert (e2, r2) == (3, ring_name)
        finally:
            c1.close()
            c2.close()
    finally:
        creator.close()
        creator.unlink()


def test_bootstrap_before_publish_raises():
    creator = RingControlPlane(_uniq(), create=True)
    try:
        with pytest.raises(RuntimeError):
            bootstrap_current_ring(creator, ring_opener=lambda n: n)   # epoch=0 chưa publish
    finally:
        creator.close()
        creator.unlink()
