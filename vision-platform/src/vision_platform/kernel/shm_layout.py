"""Layout header v2 của SHM frame ring (spec shm-production-hardening, Task 2.1).

Layer: kernel — THUẦN (chỉ `struct` + `enum`; KHÔNG import multiprocessing/shared_memory — import-linter ép).
Đây là "hợp đồng nhị phân" mô tả byte-layout của metadata mỗi slot + control segment ring.
Transport thật (đọc/ghi buf) ở `runtime/ipc/shm_frame_ring.py`; module này CHỈ định nghĩa offsets/sizes/hằng.

VÌ SAO tách layout ra kernel (design §Sơ đồ thành phần): layout là dữ liệu/hợp đồng dùng chung cho
writer + reader + recovery (nhiều process). Đặt ở kernel để 1 nguồn sự thật, không lệch giữa các bên.

NGUYÊN TẮC ATOMICITY (design §Architecture, Intel SDM Vol 3A §8.1.1):
- x86-64 store atomic CHỈ khi field ≤8 byte VÀ aligned. Header đa-byte ⇒ đọc/ghi dưới lock.
- `state` đặt @offset 0, 4-byte aligned ⇒ peek/ghi lock-free atomic (sentinel QUARANTINED).

PHÂN TÁCH (design §Data Models + P0-3):
- Per-slot header (256B): CHỈ data fields (state/generation/owner/lease/reader_registry). KHÔNG chứa magic.
- Self-describing (magic/header_version/header_size/max_readers) nằm ở RING-LEVEL CONTROL segment riêng
  → attach mismatch fail-fast. Task 2 tạo ctrl tối thiểu; Task 10 mở rộng (ring_id/epoch/writer_registry).
"""
from __future__ import annotations

import struct
from enum import IntEnum


class SlotState(IntEnum):
    """Trạng thái 1 slot. Giá trị ghi vào trường `state` 4-byte @offset 0 (atomic)."""
    FREE = 0          # trống, writer ghi được
    WRITING = 1       # writer đang giữ, dở
    READY = 2         # sẵn sàng đọc
    READING = 3       # có ≥1 reader đang pin
    DONE = 4          # đọc xong, tái dùng được
    QUARANTINED = 0xFFFFFFFF  # TERMINAL: slot bị loại vĩnh viễn (owner chết + lease quá hạn) — KHÔNG tái dùng


# Số reader tối đa pin đồng thời 1 slot (chốt Codex Q3). Header pad → 256B với giá trị này.
MAX_READERS = 8

# ---- Offsets per-slot header v2 (byte). Mọi field 8B ở offset chia hết 8; state@0/reader_count@40 chia hết 4 ----
OFFSET_STATE = 0                      # <I (4B) — atomic lock-free peek/quarantine
OFFSET_GENERATION = 8                 # <Q (8B) — ABA counter
OFFSET_OWNER_PID = 16                 # <Q (8B)
OFFSET_OWNER_CREATE_TIME_NS = 24      # <Q (8B) — định danh chống PID reuse
OFFSET_LEASE_DEADLINE_NS = 32         # <Q (8B)
OFFSET_READER_COUNT = 40              # <I (4B) — số reader pin (dẫn xuất từ registry)
OFFSET_READER_REGISTRY = 48           # mảng MAX_READERS ô, mỗi ô READER_ENTRY_FMT

# struct format cho từng field (truy cập đơn-field atomic khi aligned)
STATE_FMT = "<I"   # 4B @ OFFSET_STATE
U64_FMT = "<Q"     # 8B: generation / owner_pid / owner_create_time_ns / lease_deadline_ns
COUNT_FMT = "<I"   # 4B @ OFFSET_READER_COUNT

# 1 ô reader registry = (reader_pid, reader_create_time_ns, reader_lease_ns)
READER_ENTRY_FMT = "<QQQ"
READER_ENTRY_BYTES = struct.calcsize(READER_ENTRY_FMT)  # 24

# Cuối vùng registry (chưa pad)
_REGISTRY_END = OFFSET_READER_REGISTRY + MAX_READERS * READER_ENTRY_BYTES  # 48 + 8*24 = 240

CACHE_LINE_BYTES = 64


def _round_up(n: int, multiple: int) -> int:
    """Làm tròn LÊN bội của `multiple` (tránh false sharing — pad header về bội cache-line)."""
    return ((n + multiple - 1) // multiple) * multiple


# Tổng kích thước per-slot header v2 = pad _REGISTRY_END lên bội cache-line → 256B.
SLOT_HEADER_V2_BYTES = _round_up(_REGISTRY_END, CACHE_LINE_BYTES)  # 256


def reader_entry_offset(index: int) -> int:
    """Offset (byte) của ô reader registry thứ `index` (0..MAX_READERS-1)."""
    if not 0 <= index < MAX_READERS:
        raise IndexError(f"reader index {index} ngoài [0, {MAX_READERS})")
    return OFFSET_READER_REGISTRY + index * READER_ENTRY_BYTES


# ---- Ring-level control segment (self-describing, fail-fast attach). Task 2 = tối thiểu 4 trường ----
# Magic là sentinel TÙY Ý để phát hiện attach nhầm segment / sai version (không cần spell chữ).
RING_MAGIC = 0x53484D52        # uint32 sentinel
HEADER_VERSION = 2             # v1 = demo `<IQQ`; v2 = layout này
RING_CONTROL_FMT = "<IIII"     # (magic, header_version, header_size, max_readers)
RING_CONTROL_BYTES = struct.calcsize(RING_CONTROL_FMT)  # 16

# Writer registry (P1-3): single-writer cross-process. Nằm SAU 16B self-describing trong segment ctrl.
OFFSET_WRITER_PID = 16              # <Q (8B)
OFFSET_WRITER_CREATE_TIME_NS = 24   # <Q (8B)
OFFSET_WRITER_LEASE_NS = 32         # <Q (8B)
OFFSET_RING_EPOCH = 40              # <Q (8B) — P0-3: phiên bản ring (switchover đổi epoch)
# Segment ctrl = 16B self-describing + 24B writer registry + 8B ring_epoch → pad 64B (1 cache-line).
CTRL_SEGMENT_BYTES = 64


def pack_ring_control() -> bytes:
    """Bytes control segment cho ring HIỆN TẠI (ghi lúc create)."""
    return struct.pack(RING_CONTROL_FMT, RING_MAGIC, HEADER_VERSION, SLOT_HEADER_V2_BYTES, MAX_READERS)


def check_ring_control(raw: bytes) -> None:
    """Đọc + kiểm control segment khi attach (create=False). Mismatch → ValueError (fail-fast).

    KHÔNG diễn dịch bytes rác thành state hợp lệ: sai magic/version/size/max_readers ⇒ raise ngay.
    """
    magic, version, header_size, max_readers = struct.unpack_from(RING_CONTROL_FMT, raw, 0)
    if magic != RING_MAGIC:
        raise ValueError(f"SHM ring magic mismatch: got {magic:#x}, expected {RING_MAGIC:#x}")
    if version != HEADER_VERSION:
        raise ValueError(f"SHM ring header_version mismatch: got {version}, expected {HEADER_VERSION}")
    if header_size != SLOT_HEADER_V2_BYTES:
        raise ValueError(f"SHM ring header_size mismatch: got {header_size}, expected {SLOT_HEADER_V2_BYTES}")
    if max_readers != MAX_READERS:
        raise ValueError(f"SHM ring max_readers mismatch: got {max_readers}, expected {MAX_READERS}")
