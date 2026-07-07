"""RingControlPlane — control-plane segment tên cố định (sub-spec shm-ring-epoch-switchover).

Layer: runtime/ipc (được phép import multiprocessing/shared_memory + kernel). Quản MỘT `SharedMemory`
segment tên CỐ ĐỊNH (well-known) chứa {current_epoch, current_ring_name} — điểm hội tụ để writer/reader
bootstrap ra ring dữ liệu hiện tại + phát hiện switchover (vì `new_ring_name()`=uuid4 không suy diễn được).

AUTHORITY atomic (design §Overview Q1): `publish` (CHỈ supervisor gọi) ghi TÊN trước, ghi `current_epoch`
(u64 @16 aligned) CUỐI. Reader/writer chỉ tin cả bản ghi khi thấy epoch đổi.

TEARDOWN ring cũ (design §Overview Q3, quyết định B — verify thật trên Windows `_shm_lifecycle_probe`):
KHÔNG cần biến đếm tường minh. OS ref-count handle: memory ring cũ sống tới khi HANDLE CUỐI đóng. Mỗi bên
`close()` handle ring cũ khi rời epoch; supervisor `close()` handle của nó sau switchover; OS giải phóng ở
handle cuối. POSIX có thể `unlink()` tên ring cũ ngay sau switchover (an toàn cho handle đang mở; tên mới
dùng cho ring mới). 🔴 hành vi `resource_tracker` trên Linux CHƯA verify (chỉ verify Windows) → kiểm ở T-C.
Layout thuần ở kernel: `kernel/shm_control_plane_layout.py`.
"""
from __future__ import annotations

import struct
from multiprocessing import shared_memory

from vision_platform.kernel.shm_control_plane_layout import (
    CP_SEGMENT_BYTES, CP_EPOCH_FMT, OFFSET_CP_EPOCH, OFFSET_CP_RING_NAME, CP_RING_NAME_BYTES,
    pack_cp_header, check_cp_header, encode_ring_name, decode_ring_name,
)

_HEADER_BYTES = len(pack_cp_header())  # 8 (magic + version)


class RingControlPlane:
    """Quản control-plane segment. `create=True` (supervisor tạo) / `False` (writer/reader attach chỉ-đọc)."""

    def __init__(self, name: str, *, create: bool):
        self.name = name
        if create:
            shm = shared_memory.SharedMemory(name=name, create=True, size=CP_SEGMENT_BYTES)
            shm.buf[:_HEADER_BYTES] = pack_cp_header()
            # current_epoch=0, current_ring_name="" (zero-init) → "chưa publish".
        else:
            shm = shared_memory.SharedMemory(name=name)
            check_cp_header(bytes(shm.buf[:_HEADER_BYTES]))   # fail-fast nếu magic/version sai
        self._shm = shm

    def publish(self, epoch: int, ring_name: str) -> None:
        """Công bố ring hiện tại (CHỈ supervisor gọi). Ghi TÊN trước, `current_epoch` CUỐI (authority atomic)."""
        encoded = encode_ring_name(ring_name)
        self._shm.buf[OFFSET_CP_RING_NAME:OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES] = encoded
        struct.pack_into(CP_EPOCH_FMT, self._shm.buf, OFFSET_CP_EPOCH, epoch)   # ghi CUỐI

    def read_current(self) -> tuple[int, str]:
        """Trả (current_epoch, current_ring_name) hiện tại. epoch=0 nghĩa là chưa publish."""
        epoch = struct.unpack_from(CP_EPOCH_FMT, self._shm.buf, OFFSET_CP_EPOCH)[0]
        raw = bytes(self._shm.buf[OFFSET_CP_RING_NAME:OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES])
        return epoch, decode_ring_name(raw)

    def close(self) -> None:
        """Đóng handle của process này (KHÔNG giải phóng segment nếu process khác còn attach)."""
        self._shm.close()

    def unlink(self) -> None:
        """Yêu cầu OS xoá segment (POSIX). Windows: block mất khi mọi handle đóng."""
        self._shm.unlink()


def bootstrap_current_ring(cp: "RingControlPlane", ring_opener):
    """Bootstrap ring hiện tại qua control-plane (additive — KHÔNG sửa Writer/Reader cũ).

    Đọc (epoch, ring_name) hiện tại từ control-plane → mở data ring bằng `ring_opener(name)` (tiêm ngoài, DI).
    Trả `(ring, epoch)`. Nếu chưa publish (epoch=0) → RuntimeError (không đoán ring).
    Teardown ring cũ dựa OS handle ref-count (caller `close()` ring cũ khi rời — xem docstring module).
    """
    epoch, name = cp.read_current()
    if epoch == 0:
        raise RuntimeError("control-plane chưa publish ring nào (epoch=0) — không thể bootstrap")
    ring = ring_opener(name)
    return ring, epoch
