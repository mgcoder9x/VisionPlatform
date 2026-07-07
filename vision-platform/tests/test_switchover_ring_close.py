"""Task 4.2 nền (sub-spec shm-ring-epoch-switchover): ShmRingBuffer.close() chỉ-đóng (KHÔNG unlink).

Teardown quyết định B: consumer rời ring epoch cũ → close() handle; OS giải phóng ở handle cuối.
_Requirements: 4.1, 4.2_
"""
from __future__ import annotations

import uuid

from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer
from vision_platform.kernel.shm_layout import SlotState


def _ring_name() -> str:
    return "vp_ring_" + uuid.uuid4().hex


def test_consumer_close_does_not_unlink():
    name = _ring_name()
    creator = ShmRingBuffer(name, 2, 4, 4, 3, create=True)
    try:
        consumer = ShmRingBuffer(name, 2, 4, 4, 3, create=False,
                                 slot_locks=creator.slot_locks_for_children)
        consumer.close()   # đóng handle consumer — KHÔNG unlink
        # creator VẪN đọc được → segment chưa bị giải phóng (close không unlink)
        assert creator.peek_state(0) == SlotState.FREE
    finally:
        creator.cleanup_all()


def test_close_twice_is_safe():
    name = _ring_name()
    creator = ShmRingBuffer(name, 2, 4, 4, 3, create=True)
    try:
        consumer = ShmRingBuffer(name, 2, 4, 4, 3, create=False,
                                 slot_locks=creator.slot_locks_for_children)
        consumer.close()
        consumer.close()   # gọi lần 2 không nổ (handle list đã clear)
    finally:
        creator.cleanup_all()
