"""Bước 1 H2 (K-012): RingPool — pool K ring cố định + opener attach-by-name bằng lock thừa kế.

Test in-process (deterministic). Chứng minh cơ chế giải K-012 mà KHÔNG spawn (T-B để bước cuối).
"""
from __future__ import annotations

import sys
import uuid

import pytest

from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.kernel.shm_layout import SlotState


def _pool(pool_size=3):
    return RingPool(n_slots=4, height=8, width=8, channels=3, pool_size=pool_size,
                    session_prefix=f"pooltest_{uuid.uuid4().hex[:8]}")


def test_pool_creates_k_distinct_rings_epoch_zero():
    pool = _pool(3)
    try:
        assert pool.size == 3
        names = pool.names()
        assert len(set(names)) == 3                       # tên phân biệt
        for i in range(3):
            assert pool.ring_for_epoch(i).ring_epoch == 0      # mọi ring mới tạo = epoch 0
    finally:
        pool.close_all()


def test_pool_size_min_two():
    with pytest.raises(ValueError):
        RingPool(4, 8, 8, 3, pool_size=1)


def test_name_for_epoch_is_cyclic():
    pool = _pool(3)
    try:
        assert pool.name_for_epoch(1) == pool.name_for_epoch(4)   # 1%3 == 4%3
        assert pool.name_for_epoch(3) == pool.name_for_epoch(0)   # 3%3 == 0
        assert pool.name_for_epoch(1) != pool.name_for_epoch(2)
    finally:
        pool.close_all()


def test_activate_resets_and_bumps_epoch():
    pool = _pool(3)
    try:
        name1 = pool.activate(1)
        assert pool.ring_for_epoch(1).ring_epoch == 1
        assert name1 == pool.name_for_epoch(1)
        # tái dùng cùng slot vật lý (epoch 4 → 4%3==1) sau khi thế hệ cũ drain:
        name4 = pool.activate(4)
        assert name4 == name1                              # cùng ring vật lý
        assert pool.ring_for_epoch(4).ring_epoch == 4      # đã bump lên 4
    finally:
        pool.close_all()


def test_activate_rejects_non_monotonic_reuse():
    pool = _pool(3)
    try:
        pool.activate(1)
        with pytest.raises(ValueError):
            pool.activate(1)                               # reset_for_reuse(1) khi ring đã ở epoch 1 → ValueError
    finally:
        pool.close_all()


def test_slot_locks_map_keys_and_lengths():
    pool = _pool(3)
    try:
        m = pool.slot_locks_map()
        assert set(m.keys()) == set(pool.names())
        for locks in m.values():
            assert len(locks) == pool.n_slots
    finally:
        pool.close_all()


def test_opener_attaches_pool_ring_with_inherited_locks():
    pool = _pool(3)
    try:
        pool.activate(1)
        name = pool.name_for_epoch(1)
        opener = make_pool_opener(pool.slot_locks_map(), pool.n_slots, pool.height, pool.width, pool.channels)
        ring = opener(name)                                # attach create=False bằng lock từ map
        try:
            assert ring.ring_epoch == 1
            assert ring.peek_state(0) == SlotState.FREE
        finally:
            ring.close()
    finally:
        pool.close_all()


def test_opener_unknown_name_raises():
    pool = _pool(2)
    try:
        opener = make_pool_opener(pool.slot_locks_map(), pool.n_slots, pool.height, pool.width, pool.channels)
        with pytest.raises(KeyError):
            opener("khong_ton_tai_trong_pool")
    finally:
        pool.close_all()


@pytest.mark.skipif(sys.platform != "win32", reason="close→free là hành vi Windows; POSIX verify ở T-C (K-003)")
def test_close_all_frees_segments():
    pool = _pool(2)
    names = pool.names()
    locks_map = pool.slot_locks_map()
    pool.close_all()
    opener = make_pool_opener(locks_map, 4, 8, 8, 3)
    with pytest.raises(FileNotFoundError):
        opener(names[0])                                   # segment đã giải phóng sau close_all
