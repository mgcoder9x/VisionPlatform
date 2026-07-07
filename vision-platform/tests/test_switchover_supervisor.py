"""RingSupervisor (sub-spec shm-ring-epoch-switchover) — H2: switchover qua RingPool.activate.

_Requirements: 2.1, 5.1, 5.2, 6.1_
H2 (K-012): supervisor KHÔNG tạo/đóng ring (đảo D-002/D-010) — dùng pool.activate (reset+bump). Test bằng
FakePool (deterministic) + 1 test tích hợp RingPool THẬT.
"""
from __future__ import annotations

import uuid

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook
from vision_platform.application.ring_supervisor import RingSupervisor


def _uniq() -> str:
    return f"vp_cp_test_{uuid.uuid4().hex}"


class FakePool:
    """Giả RingPool: activate ghi lại epoch + trả tên xác định."""

    def __init__(self):
        self.activated: list[int] = []

    def activate(self, epoch: int) -> str:
        self.activated.append(epoch)
        return f"vp_pool_ring_ep{epoch}"


def test_switchover_activates_pool_and_publishes_monotonic():
    cp = RingControlPlane(_uniq(), create=True)
    pool = FakePool()
    try:
        sup = RingSupervisor(cp, pool)
        e1 = sup.switchover()
        assert e1 == 1
        ep, nm = cp.read_current()
        assert ep == 1 and nm == "vp_pool_ring_ep1"
        assert pool.activated == [1]                       # pool.activate(1) được gọi
        e2 = sup.switchover()
        assert e2 == 2 and cp.read_current()[0] == 2       # đơn điệu tăng
        assert pool.activated == [1, 2]
    finally:
        cp.close(); cp.unlink()


def test_on_event_triggers_only_for_rebuild_requested():
    cp = RingControlPlane(_uniq(), create=True)
    pool = FakePool()
    try:
        sup = RingSupervisor(cp, pool)
        assert sup.on_event("shm_slot_quarantined", slot=0) is None   # sự kiện khác → bỏ qua
        assert cp.read_current()[0] == 0 and pool.activated == []
        assert sup.on_event("shm_ring_rebuild_requested", reason="threshold") == 1
        assert cp.read_current()[0] == 1 and pool.activated == [1]
    finally:
        cp.close(); cp.unlink()


def test_switchover_emits_observability_events():
    cp = RingControlPlane(_uniq(), create=True)
    events: list[str] = []

    class Rec(ObservabilityHook):
        def emit(self, event, **fields):
            events.append(event)

    try:
        sup = RingSupervisor(cp, FakePool(), obs=Rec())
        sup.switchover()
        assert "shm_switchover_started" in events
        assert "shm_switchover_completed" in events
    finally:
        cp.close(); cp.unlink()


def test_switchover_with_real_pool_bumps_ring_epoch():
    """Tích hợp: RingSupervisor + RingPool THẬT → switchover reset+bump epoch pool ring + publish đúng tên."""
    cp = RingControlPlane(_uniq(), create=True)
    pool = RingPool(n_slots=4, height=8, width=8, channels=3, pool_size=3,
                    session_prefix=f"suptest_{uuid.uuid4().hex[:8]}")
    try:
        sup = RingSupervisor(cp, pool)
        e1 = sup.switchover()                              # epoch 1 → pool[1%3]
        assert e1 == 1
        ep, name = cp.read_current()
        assert ep == 1 and name == pool.name_for_epoch(1)
        assert pool.ring_for_epoch(1).ring_epoch == 1      # pool ring đã bump epoch 1
        sup.switchover()                                   # epoch 2 → pool[2%3]
        assert cp.read_current()[0] == 2
        assert pool.ring_for_epoch(2).ring_epoch == 2
    finally:
        pool.close_all()
        cp.close(); cp.unlink()
