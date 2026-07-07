"""Teardown ring (sub-spec shm-ring-epoch-switchover) — quyết định B + H2.

_Requirements: 4.1, 4.2, 4.3, 6.1_

H2 (K-012, đảo D-010): supervisor KHÔNG còn close ring cũ per-migrate; POOL giữ ring suốt phiên, teardown =
`pool.close_all()` lúc shutdown (test ở `test_switchover_ring_pool.py::test_close_all_frees_segments`).
File này giữ test PRIMITIVE `ShmRingBuffer.close()` (OS ref-count handle) — nền của teardown pool.

Hành vi "mọi handle đóng → segment free" là của Windows (verify LOG #126); POSIX cần unlink → guard skip
non-win32, verify ở Task 7 (T-C, K-003) → KHÔNG claim sai.
"""
from __future__ import annotations

import sys
import uuid

import pytest

from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer
from vision_platform.kernel.shm_layout import SlotState


def _ring_name() -> str:
    return "vp_ring_" + uuid.uuid4().hex


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="teardown-by-close là hành vi Windows (OS ref-count handle); POSIX cần unlink → verify ở T-C (K-003)",
)
def test_real_ring_freed_when_all_handles_closed():
    name = _ring_name()
    creator = ShmRingBuffer(name, 2, 4, 4, 3, create=True)
    locks = creator.slot_locks_for_children
    consumer = ShmRingBuffer(name, 2, 4, 4, 3, create=False, slot_locks=locks)

    consumer.close()          # 1 handle đóng — ring vẫn sống nhờ handle creator
    assert creator.peek_state(0) == SlotState.FREE

    creator.close()           # handle CUỐI đóng → OS giải phóng segment (Windows)
    with pytest.raises(FileNotFoundError):
        ShmRingBuffer(name, 2, 4, 4, 3, create=False, slot_locks=locks)   # attach lại → đã giải phóng


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="ràng buộc handle-count là hành vi Windows; POSIX verify ở T-C (K-003)",
)
def test_real_ring_alive_while_one_handle_open():
    name = _ring_name()
    creator = ShmRingBuffer(name, 2, 4, 4, 3, create=True)
    locks = creator.slot_locks_for_children
    try:
        consumer = ShmRingBuffer(name, 2, 4, 4, 3, create=False, slot_locks=locks)
        consumer.close()                                   # consumer rời
        # creator còn giữ handle → attach mới VẪN được (ring còn sống, không bị chặn)
        again = ShmRingBuffer(name, 2, 4, 4, 3, create=False, slot_locks=locks)
        assert again.peek_state(0) == SlotState.FREE
        again.close()
    finally:
        creator.cleanup_all()
