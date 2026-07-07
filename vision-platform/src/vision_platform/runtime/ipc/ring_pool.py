"""RingPool — pool K ring cố định cho switchover (H2, giải K-012). Layer: runtime/ipc.

VÌ SAO CÓ FILE NÀY (K-012, verify từ code): `ShmRingBuffer(create=False)` bắt buộc nhận `slot_locks` từ parent
(`mp.Lock` KHÔNG mở được theo tên) ⇒ ring sinh RUNTIME lúc switchover không thể cấp lock cho worker đang chạy.
H2 né vấn đề: tạo TRƯỚC K ring lúc startup, truyền TOÀN BỘ `slot_locks` cho mọi worker qua `Process(args=)`
(thừa kế — cơ chế đã verify ở `test_step_05_shm.py`). Switchover = TÁI DÙNG pool ring (`reset_for_reuse` +
bump epoch), KHÔNG cấp phát SHM/lock mới ⇒ hợp real-time (không jitter) + bộ nhớ đoán trước.

ĐÁNH ĐỔI (ghi rõ): pool giữ K ring suốt phiên (K× RAM); ring cũ phải DRAIN (reader_count==0) trước khi vòng
lại tái dùng — bất biến drain-before-reuse do CALLER (supervisor) giữ. Teardown = shutdown-only (moot K-003).
"""
from __future__ import annotations

import uuid
from typing import Callable, Optional

from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ObservabilityHook


class RingPool:
    """Sở hữu K ring cố định (creator handles) suốt phiên. Supervisor dùng để switchover không cấp-phát-động."""

    def __init__(
        self,
        n_slots: int,
        height: int,
        width: int,
        channels: int = 3,
        *,
        pool_size: int = 3,
        session_prefix: Optional[str] = None,
        obs: Optional[ObservabilityHook] = None,
    ):
        # ≥2 BẮT BUỘC: switchover N→N+1 có 2 thế hệ sống chồng (ring cũ drain + ring mới active).
        if pool_size < 2:
            raise ValueError(f"pool_size phải >=2 (old+new overlap khi switchover), got {pool_size}")
        self.n_slots = n_slots
        self.height = height
        self.width = width
        self.channels = channels
        # uuid mỗi phiên → không đụng segment sót phiên crash trước (cold-start, #05 Task 9);
        # hậu tố cố định _r{i} → tên ổn định trong phiên để worker attach-by-name bằng lock thừa kế.
        self._prefix = session_prefix if session_prefix is not None else f"vp_pool_{uuid.uuid4().hex}"
        self._rings: list[ShmRingBuffer] = [
            ShmRingBuffer(
                name=f"{self._prefix}_r{i}", n_slots=n_slots, height=height, width=width,
                channels=channels, create=True, ring_epoch=0, obs=obs,
            )
            for i in range(pool_size)
        ]

    @property
    def size(self) -> int:
        return len(self._rings)

    def ring_for_epoch(self, epoch: int) -> ShmRingBuffer:
        """Ring vật lý dùng cho epoch (vòng): pool[epoch % K]."""
        return self._rings[epoch % self.size]

    def name_for_epoch(self, epoch: int) -> str:
        return self.ring_for_epoch(epoch).name

    def activate(self, epoch: int) -> Optional[str]:
        """TÁI DÙNG pool ring cho epoch mới: reset + bump epoch (đơn điệu). Trả tên ring, hoặc None nếu ring
        CHƯA DRAIN (reset bị chặn vì còn reader hiệu lực — Fix A K-015; caller hoãn + thử lại sau).

        drain-before-reuse nay được `reset_for_reuse` CƯỠNG CHẾ (không còn dựa contract ngầm).
        """
        ring = self.ring_for_epoch(epoch)
        if not ring.reset_for_reuse(epoch):   # False = chưa drain (còn reader hiệu lực)
            return None
        return ring.name

    def slot_locks_map(self) -> dict[str, list]:
        """{tên ring → slot_locks} — truyền cho worker qua Process(args=) lúc spawn (giải K-012)."""
        return {r.name: r.slot_locks_for_children for r in self._rings}

    def names(self) -> list[str]:
        return [r.name for r in self._rings]

    def close_all(self) -> None:
        """Teardown TOÀN BỘ pool — CHỈ lúc shutdown (H2: không teardown giữa phiên)."""
        for r in self._rings:
            r.cleanup_all()


def make_pool_opener(
    locks_map: dict[str, list],
    n_slots: int,
    height: int,
    width: int,
    channels: int = 3,
    *,
    obs: Optional[ObservabilityHook] = None,
) -> Callable[[str], ShmRingBuffer]:
    """Tạo `ring_opener(name)` cho WORKER: attach pool ring theo tên bằng lock THỪA KẾ (locks_map từ spawn).

    Đây là mảnh ghép giải K-012 phía worker: coordinator dùng opener này; `ring_opener(name)` attach ring pool
    tương ứng (create=False) với đúng `slot_locks` đã thừa kế → khoá cross-process hoạt động cho ring mới.
    """
    def opener(name: str) -> ShmRingBuffer:
        if name not in locks_map:
            raise KeyError(f"ring '{name}' không có trong locks_map pool (worker chưa nhận lock qua spawn?)")
        return ShmRingBuffer(
            name=name, n_slots=n_slots, height=height, width=width, channels=channels,
            create=False, slot_locks=locks_map[name], obs=obs,
        )
    return opener
