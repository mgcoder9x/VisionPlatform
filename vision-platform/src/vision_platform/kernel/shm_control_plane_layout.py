"""Layout của CONTROL-PLANE segment cho ring-epoch switchover (sub-spec shm-ring-epoch-switchover, Task 1.1).

Layer: kernel — THUẦN (chỉ `struct`; KHÔNG import multiprocessing/shared_memory — import-linter ép).
Đây là "hợp đồng nhị phân" của MỘT segment tên CỐ ĐỊNH (well-known) trỏ tới ring dữ liệu hiện tại.

VÌ SAO cần control-plane tên cố định (design §Overview Q1): `new_ring_name()` sinh tên bằng `uuid4().hex`
(NGẪU NHIÊN) → writer/reader KHÔNG thể suy ra tên ring hiện tại từ số epoch. Do đó cần 1 điểm hội tụ tên
cố định chứa {epoch, tên-ring-hiện-tại} để hai bên bootstrap + phát hiện switchover. (Chính docstring
`new_ring_name` cũng chỉ hướng này.)

ATOMICITY (kế thừa `shm_layout.py`, Intel SDM Vol 3A §8.1.1): x86-64 store atomic khi field ≤8B VÀ aligned.
`current_epoch` (u64 @16, 8-aligned) là AUTHORITY: publish ghi tên TRƯỚC, ghi `current_epoch` CUỐI → reader
chỉ tin cả bản ghi khi thấy epoch tăng (không đọc tên "nửa vời"). Transport thật ở `runtime/ipc`.
"""
from __future__ import annotations

import struct

# ---- Magic/version (self-describing, fail-fast attach) ----
CP_MAGIC = 0x53484D43        # uint32 sentinel ("SHMC" — khác RING_MAGIC 0x53484D52 "SHMR")
CP_VERSION = 1               # version control-plane segment

# ---- Offsets (byte). Field 8B ở offset chia hết 8; field 4B ở offset chia hết 4 ----
OFFSET_CP_MAGIC = 0            # <I (4B)
OFFSET_CP_VERSION = 4          # <I (4B)
OFFSET_CP_ATTACH_COUNT = 8     # <I (4B) — RESERVED (quyết định B: teardown dựa OS handle ref-count, không đếm tường minh)
OFFSET_CP_EPOCH = 16           # <Q (8B) — AUTHORITY, ghi CUỐI
OFFSET_CP_RING_NAME = 24       # bytes[CP_RING_NAME_BYTES] — tên ring hiện tại (utf-8, null-pad)

CP_MAGIC_FMT = "<I"
CP_VERSION_FMT = "<I"
CP_ATTACH_COUNT_FMT = "<I"
CP_EPOCH_FMT = "<Q"

# Tên ring: `vp_ring_<32 hex>` = 40 byte; chừa dư cho prefix khác → 96 byte cố định.
CP_RING_NAME_BYTES = 96

CACHE_LINE_BYTES = 64
_CP_END = OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES  # 24 + 96 = 120


def _round_up(n: int, multiple: int) -> int:
    """Làm tròn LÊN bội của `multiple` (pad về bội cache-line, tránh false sharing)."""
    return ((n + multiple - 1) // multiple) * multiple


# Tổng kích thước control-plane segment = pad _CP_END lên bội cache-line → 128B (≥128 theo design).
CP_SEGMENT_BYTES = _round_up(_CP_END, CACHE_LINE_BYTES)  # 128


def pack_cp_header() -> bytes:
    """Bytes phần self-describing (magic + version) để ghi lúc create control-plane segment."""
    return struct.pack(CP_MAGIC_FMT + "I", CP_MAGIC, CP_VERSION)


def check_cp_header(raw: bytes) -> None:
    """Kiểm magic + version khi attach (fail-fast). Mismatch → ValueError.

    KHÔNG diễn dịch bytes rác thành trạng thái hợp lệ: sai magic/version ⇒ raise ngay.
    """
    magic = struct.unpack_from(CP_MAGIC_FMT, raw, OFFSET_CP_MAGIC)[0]
    version = struct.unpack_from(CP_VERSION_FMT, raw, OFFSET_CP_VERSION)[0]
    if magic != CP_MAGIC:
        raise ValueError(f"control-plane magic mismatch: got {magic:#x}, expected {CP_MAGIC:#x}")
    if version != CP_VERSION:
        raise ValueError(f"control-plane version mismatch: got {version}, expected {CP_VERSION}")


def encode_ring_name(name: str) -> bytes:
    """Mã hoá tên ring thành đúng CP_RING_NAME_BYTES byte (utf-8, null-pad). Quá dài → ValueError."""
    raw = name.encode("utf-8")
    if len(raw) > CP_RING_NAME_BYTES:
        raise ValueError(f"ring name dài {len(raw)}B > {CP_RING_NAME_BYTES}B")
    return raw.ljust(CP_RING_NAME_BYTES, b"\x00")


def decode_ring_name(raw: bytes) -> str:
    """Giải mã tên ring từ vùng CP_RING_NAME_BYTES byte (bỏ null-pad)."""
    return raw[:CP_RING_NAME_BYTES].rstrip(b"\x00").decode("utf-8")
