"""ReaderEpochCoordinator — reader chuyển ring an toàn qua epoch (sub-spec shm-ring-epoch-switchover, Task 4.3).

Layer: application. ADDITIVE — KHÔNG sửa `ShmFrameReader`/`ShmRingBuffer` (giữ baseline #05 xanh). Đối xứng
`WriterEpochCoordinator` nhưng phía đọc: reader KHÔNG `register_writer` (không có bất biến 1-writer) → đơn giản hơn.

BẢN CHẤT (Req 1.1/1.2/1.3, 4.1): reader nhận các `ShmFrameRefData` (mang `ring_epoch`) và đọc frame. Khi
`RingSupervisor` switchover sang epoch N+1, reader phải chuyển sang ring mới. Chiến lược **check-on-read**
(đối xứng check-on-write): mỗi `read_ref()` đọc `RingControlPlane.read_current()`; epoch đổi thì:
  1. mở ring mới qua `ring_opener` (DI),
  2. đổi con trỏ reader sang ring mới,
  3. `close()` handle ring cũ (TEARDOWN quyết định B: OS ref-count handle, KHÔNG `detach`/biến đếm — LOG #126).
Rồi delegate `self._reader.read_ref(ref)`.

Bất biến đúng (không cần code thêm — dùng stale-check sẵn có của `ShmFrameReader`):
- ref cầm `ring_epoch` CŨ (đến muộn sau switchover) → `read_ref` trả `None` (stale, P0-3 L~600) → DROP an toàn.
- Supervisor publish epoch N+1 TRƯỚC khi tồn tại ref N+1 bất kỳ (writer chỉ ghi ring N+1 sau khi thấy publish)
  → reader poll control-plane luôn thấy N+1 kịp lúc → không đọc nhầm ring cũ, không mất frame vì thứ tự.

DI `ring_opener(name)->ring` + `reader_factory(ring)->reader` (mặc định `ShmFrameReader`) để test deterministic.

🔴 NGOÀI PHẠM VI Task 4.3 (chung với writer, xem K-012): cấp phát `slot_locks` cho ring mới ở process reader
đang chạy = CHƯA giải (mp.Lock không attach theo tên) → Task 6 (T-B). Trong process (test 4.3) `ring_opener`
cấp ring có sẵn lock.
"""
from __future__ import annotations

from typing import Callable, Optional

from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane, bootstrap_current_ring
from vision_platform.runtime.ipc.shm_frame_ring import ShmFrameReader, ObservabilityHook


class ReaderEpochCoordinator:
    def __init__(
        self,
        control_plane: RingControlPlane,
        ring_opener: Callable[[str], object],
        *,
        reader_factory: Callable[[object], object] = ShmFrameReader,
        obs: Optional[ObservabilityHook] = None,
    ):
        self._cp = control_plane
        self._ring_opener = ring_opener
        self._reader_factory = reader_factory
        self._obs = obs if obs is not None else ObservabilityHook()
        self._ring: object = None
        self._reader: object = None
        self._epoch: int = 0

    def bootstrap(self) -> int:
        """Mở ring hiện tại từ control-plane + dựng reader. Trả epoch hiện tại."""
        ring, epoch = bootstrap_current_ring(self._cp, self._ring_opener)
        self._ring = ring
        self._epoch = epoch
        self._reader = self._reader_factory(ring)
        return epoch

    def _maybe_switch(self) -> Optional[int]:
        """Phát hiện epoch đổi → chuyển ring. Trả epoch mới nếu có chuyển, ngược lại None."""
        cur_epoch, name = self._cp.read_current()
        if cur_epoch == self._epoch:
            return None

        new_ring = self._ring_opener(name)
        old_ring = self._ring
        old_epoch = self._epoch
        self._ring = new_ring
        self._epoch = cur_epoch
        self._reader = self._reader_factory(new_ring)
        self._obs.emit("shm_reader_switched", old_epoch=old_epoch, new_epoch=cur_epoch, new_ring_name=name)

        if old_ring is not None:
            old_ring.close()                        # teardown B: đóng handle ring cũ (KHÔNG unlink/detach)
            self._obs.emit("shm_ring_teardown_pending", epoch=old_epoch)
        return cur_epoch

    def read_ref(self, ref: ShmFrameRefData):
        """Kiểm switchover TRƯỚC rồi đọc ref. ref epoch cũ → None (stale). Trả frame copy hoặc None."""
        if self._reader is None:
            raise RuntimeError("ReaderEpochCoordinator.read_ref() gọi trước bootstrap()")
        self._maybe_switch()
        return self._reader.read_ref(ref)

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def current_ring(self) -> object:
        return self._ring
