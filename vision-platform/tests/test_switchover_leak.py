"""Task 7 (sub-spec shm-ring-epoch-switchover): T-C — không leak ring cũ.

BẢN CHẤT no-leak dưới H2 (khác spec gốc "tạo ring mới + free ring cũ"): switchover TÁI DÙNG pool ring →
số segment KHÔNG tăng theo số lần switchover (luôn = K ring). Đây là tính no-leak cốt lõi, verify được
KHÔNG phụ thuộc nền tảng. Phần "OS thực sự giải phóng khi close_all" là Windows-specific (OS ref-count
handle) → guard skip non-win32; POSIX resource_tracker/`/dev/shm` verify sau (🔴 K-003).
_Requirements: 4.2, 4.3_
"""
from __future__ import annotations

import sys
import uuid

import pytest

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener

_H = _W = _C = 4
_N = 4


def _cp():
    return RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)


def test_no_segment_accumulation_across_many_switchovers():
    """H2 no-leak (platform-independent): 20 switchover → tập segment KHÔNG đổi (bounded = K ring)."""
    from vision_platform.application.ring_supervisor import RingSupervisor
    cp = _cp()
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"leak_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    names_before = set(pool.names())
    try:
        for _ in range(20):
            sup.switchover()                         # activate = reset+bump (TÁI DÙNG, không tạo segment mới)
        names_after = set(pool.names())
        assert names_after == names_before           # KHÔNG segment mới sau 20 switchover → bounded, no leak-by-growth
        assert len(names_after) == 3                 # đúng K ring

        # Mọi pool ring VẪN sống (attach được) tại epoch hiện tại của nó.
        opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
        for nm in names_after:
            ring = opener(nm)
            try:
                assert ring.ring_epoch >= 1
            finally:
                ring.close()
    finally:
        pool.close_all()
        cp.close(); cp.unlink()


def test_switchover_memory_bounded_by_pool_size():
    """Số ring sống = pool_size dù switchover nhiều — chứng minh bộ nhớ đoán trước (không tăng)."""
    from vision_platform.application.ring_supervisor import RingSupervisor
    for k in (2, 3, 5):
        cp = _cp()
        pool = RingPool(_N, _H, _W, _C, pool_size=k, session_prefix=f"leak_{uuid.uuid4().hex[:8]}")
        sup = RingSupervisor(cp, pool)
        try:
            for _ in range(3 * k + 2):
                sup.switchover()
            assert pool.size == k
            assert len(set(pool.names())) == k       # vẫn đúng k ring, không phình
        finally:
            pool.close_all()
            cp.close(); cp.unlink()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="OS giải phóng khi close_all là hành vi Windows (ref-count handle); POSIX resource_tracker → T-C Linux (K-003)",
)
def test_pool_close_all_frees_all_segments():
    """Sau close_all + không còn handle → mọi pool ring được OS giải phóng (attach lại → FileNotFoundError)."""
    from vision_platform.application.ring_supervisor import RingSupervisor
    cp = _cp()
    pool = RingPool(_N, _H, _W, _C, pool_size=2, session_prefix=f"leak_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    names = pool.names()
    locks_map = pool.slot_locks_map()
    try:
        sup.switchover(); sup.switchover()           # dùng cả 2 pool ring
        pool.close_all()                              # teardown shutdown → đóng+unlink mọi segment
        opener = make_pool_opener(locks_map, _N, _H, _W, _C)
        for nm in names:
            with pytest.raises(FileNotFoundError):
                opener(nm)                            # đã giải phóng — không leak
    finally:
        cp.close(); cp.unlink()
