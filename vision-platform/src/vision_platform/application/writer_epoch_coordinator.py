"""WriterEpochCoordinator — writer chuyển ring an toàn qua epoch (sub-spec shm-ring-epoch-switchover, Task 4.2).

Layer: application (được phụ thuộc kernel + runtime). ADDITIVE — KHÔNG sửa `ShmFrameWriter`/`ShmRingBuffer`
(giữ toàn bộ baseline #05 xanh). Bọc quanh MỘT `ShmFrameWriter` + theo dõi control-plane để phát hiện switchover.

BẢN CHẤT (Req 3.1/3.2/3.3): writer đang ghi ring epoch N; khi `RingSupervisor` publish epoch N+1 (tên ring mới),
writer phải chuyển sang ring mới AN TOÀN, giữ bất biến 1-writer/ring. Chiến lược **check-on-write**: mỗi lần
`write()` đọc `RingControlPlane.read_current()` (rẻ — vài chục byte); nếu epoch đổi thì:
  1. mở ring mới qua `ring_opener` (DI),
  2. `register_writer()` ring mới TRƯỚC frame đầu (Req 3.2) — nếu ring mới đã có writer sống →
     `SingleWriterViolation` → **fail-fast** (đóng handle ring mới, GIỮ nguyên epoch cũ, ném lên caller),
  3. đổi con trỏ sang ring mới,
  4. `close()` handle ring cũ (TEARDOWN quyết định B: OS ref-count handle, KHÔNG `detach`/biến đếm — verify
     thật Windows `_shm_lifecycle_probe`, LOG Entry #126). OS giải phóng ring cũ ở handle cuối.

DI: `ring_opener(name) -> ring` và `writer_factory(ring) -> writer` được tiêm để test deterministic (fake ring/
writer) — cùng triết lý `liveness_fn`/`obs`/`ring_factory` sẵn có. Mặc định `writer_factory = ShmFrameWriter`.

🔴 NGOÀI PHẠM VI Task 4.2 (ghi rõ, KHÔNG claim đã giải): cấp phát `slot_locks` (mp.Lock) cho ring mới ở
process writer đang chạy (ring do supervisor tạo ở process khác) là bài toán CHƯA giải — mp.Lock không attach
theo tên. Kiểm/giải ở Task 6 (T-B cross-process). Trong process (test 4.2) `ring_opener` cấp ring có sẵn lock.
"""
from __future__ import annotations

from typing import Callable, Optional

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane, bootstrap_current_ring
from vision_platform.runtime.ipc.shm_frame_ring import ShmFrameWriter, ObservabilityHook


class WriterEpochCoordinator:
    def __init__(
        self,
        control_plane: RingControlPlane,
        ring_opener: Callable[[str], object],
        *,
        writer_factory: Callable[[object], object] = ShmFrameWriter,
        obs: Optional[ObservabilityHook] = None,
    ):
        self._cp = control_plane
        self._ring_opener = ring_opener
        self._writer_factory = writer_factory
        self._obs = obs if obs is not None else ObservabilityHook()
        self._ring: object = None
        self._writer: object = None
        self._epoch: int = 0

    def bootstrap(self) -> int:
        """Mở ring hiện tại từ control-plane + register_writer TRƯỚC frame đầu. Trả epoch hiện tại."""
        ring, epoch = bootstrap_current_ring(self._cp, self._ring_opener)
        ring.register_writer()                      # 1-writer/ring (Req 5) — trước khi ghi
        self._ring = ring
        self._epoch = epoch
        self._writer = self._writer_factory(ring)
        return epoch

    def _maybe_switch(self) -> Optional[int]:
        """Phát hiện epoch đổi → chuyển ring an toàn. Trả epoch mới nếu có chuyển, ngược lại None."""
        cur_epoch, name = self._cp.read_current()
        if cur_epoch == self._epoch:
            return None

        new_ring = self._ring_opener(name)
        try:
            new_ring.register_writer()              # register ring MỚI trước frame đầu (Req 3.2)
        except Exception:
            new_ring.close()                        # fail-fast vẫn dọn handle ring mới (không leak)
            raise                                   # single-writer/epoch giữ nguyên — caller xử lý

        old_ring = self._ring
        old_epoch = self._epoch
        self._ring = new_ring
        self._epoch = cur_epoch
        self._writer = self._writer_factory(new_ring)
        self._obs.emit("shm_writer_switched", old_epoch=old_epoch, new_epoch=cur_epoch, new_ring_name=name)

        if old_ring is not None:
            old_ring.close()                        # teardown B: đóng handle ring cũ (KHÔNG unlink/detach)
            self._obs.emit("shm_ring_teardown_pending", epoch=old_epoch)
        return cur_epoch

    def write(self, frame):
        """Kiểm switchover TRƯỚC (không bao giờ ghi ring lạc epoch) rồi ghi frame. Trả ref hoặc None."""
        if self._writer is None:
            raise RuntimeError("WriterEpochCoordinator.write() gọi trước bootstrap()")
        self._maybe_switch()
        return self._writer.write(frame)

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def current_ring(self) -> object:
        return self._ring
