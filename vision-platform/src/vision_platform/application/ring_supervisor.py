"""RingSupervisor — authority điều phối ring-epoch switchover (sub-spec shm-ring-epoch-switchover).

Layer: application (phụ thuộc kernel + runtime). NƠI DUY NHẤT quyết định switchover — KHÔNG per-slot. Nhận
`shm_ring_rebuild_requested` (ShmRingBuffer phát khi `quarantined_count >= rebuild_threshold` hoặc writer cũ
DEAD) → chuyển epoch qua control-plane.

═══ THIẾT KẾ H2 (K-012) — ĐẢO D-002 + D-010 (xem journal C-006, LOG #136) ═══
Trước (D-002/D-010): switchover TẠO ring tên uuid mới + supervisor CLOSE ring cũ (close-on-migrate).
Nay (H2): `mp.Lock` KHÔNG cấp được cho worker đang chạy (không mở theo tên) ⇒ KHÔNG tạo ring runtime. Thay
vào đó dùng `RingPool` cấp sẵn K ring lúc startup (lock thừa kế qua spawn); switchover = `pool.activate(N)`
(reset_for_reuse + bump epoch — TÁI DÙNG, không cấp phát). Supervisor KHÔNG sở hữu/đóng ring nữa — POOL giữ
toàn bộ ring suốt phiên; teardown = `pool.close_all()` lúc shutdown (moot K-003 teardown-giữa-vận-hành).

`ring_pool` TIÊM ngoài (composition root sở hữu vòng đời pool) → supervisor thuần điều phối (SRP, test được).
Epoch tăng đơn điệu (Property 2) — `reset_for_reuse` trong `activate` tự ép.
"""
from __future__ import annotations

from typing import Optional

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook


class RingSupervisor:
    def __init__(
        self,
        control_plane: RingControlPlane,
        ring_pool: RingPool,
        obs: Optional[ObservabilityHook] = None,
    ):
        self._cp = control_plane
        self._pool = ring_pool                       # H2: pool sở hữu ring; supervisor chỉ điều phối
        self._obs = obs if obs is not None else ObservabilityHook()

    def on_event(self, event: str, **fields) -> Optional[int]:
        """Lọc sự kiện: chỉ `shm_ring_rebuild_requested` mới trigger switchover. Trả epoch mới hoặc None."""
        if event == "shm_ring_rebuild_requested":
            return self.switchover()
        return None

    def switchover(self) -> Optional[int]:
        """Chuyển sang epoch N+1: TÁI DÙNG pool ring (activate = reset+bump) + publish. Trả epoch mới, hoặc
        None nếu HOÃN vì ring chưa drain (Fix A K-015 — defer+retry).

        H2: KHÔNG tạo ring mới (đảo D-002), KHÔNG close ring cũ (đảo D-010 — pool giữ ring). Contract
        drain-before-reuse do pool/deployment đảm bảo (pool[N%K] đã drain khi tái dùng cho epoch N).
        """
        cur_epoch, _ = self._cp.read_current()
        new_epoch = cur_epoch + 1
        self._obs.emit("shm_switchover_started", new_epoch=new_epoch)
        name = self._pool.activate(new_epoch)        # reset_for_reuse + bump epoch trên pool[N%K]
        if name is None:
            # pool ring chưa drain (còn reader hiệu lực) → HOÃN switchover, thử lại lần rebuild sau
            # (defer+retry — Fix A K-015; KHÔNG publish, KHÔNG bump epoch → an toàn, không torn frame).
            self._obs.emit("shm_switchover_deferred", attempted_epoch=new_epoch, reason="ring_not_drained")
            return None
        self._cp.publish(new_epoch, name)            # publish CUỐI (hai bên poll thấy đổi)
        self._obs.emit("shm_switchover_completed", new_epoch=new_epoch, new_ring_name=name)
        return new_epoch
