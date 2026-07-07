# Mẩu 02 — Control-plane layout: 1 segment tên CỐ ĐỊNH chứa {epoch, tên-ring}

> Bám code thật `kernel/shm_control_plane_layout.py` (đọc nguyên văn khi viết mẩu này). Đây là "hợp đồng
> nhị phân" của vùng SHM điều khiển — nơi hai process tra "ring hiện tại là cái nào".

## 1. Thuộc về đâu
- **Tầng:** `kernel` — THUẦN (chỉ `struct`; KHÔNG import `multiprocessing`/`shared_memory` — import-linter ép).
- **Vai:** định nghĩa **bố cục byte** của control-plane segment. Việc tạo/đọc vùng SHM thật ở `runtime/ipc` (mẩu 03).

## 2. Cần biết trước
- Mẩu 01 (#05b): đã có tín hiệu rebuild → cần dựng ring mới → cần **nơi công bố "ring hiện tại"**.
- Gloss: **offset** = vị trí byte trong vùng nhớ · **magic** = số "chữ ký" để nhận diện đúng loại segment ·
  **aligned (căn lề)** = đặt field 8 byte ở vị trí chia hết 8 → CPU đọc/ghi **atomic** (không nửa vời) ·
  **fail-fast** = sai là báo lỗi NGAY, không đoán mò. (Ôn `kernel/shm_layout.py` #05/04 về atomic nếu quên.)

## 3. Code thật (quote nguyên văn — `kernel/shm_control_plane_layout.py`)

**(a) Magic + offsets:**
```python
CP_MAGIC = 0x53484D43        # uint32 sentinel ("SHMC" — khác RING_MAGIC 0x53484D52 "SHMR")
CP_VERSION = 1               # version control-plane segment

OFFSET_CP_MAGIC = 0            # <I (4B)
OFFSET_CP_VERSION = 4          # <I (4B)
OFFSET_CP_ATTACH_COUNT = 8     # <I (4B) — RESERVED (quyết định B: teardown dựa OS handle ref-count, không đếm tường minh)
OFFSET_CP_EPOCH = 16           # <Q (8B) — AUTHORITY, ghi CUỐI
OFFSET_CP_RING_NAME = 24       # bytes[CP_RING_NAME_BYTES] — tên ring hiện tại (utf-8, null-pad)
```

**(b) Kích thước segment (pad về bội cache-line):**
```python
CP_RING_NAME_BYTES = 96
CACHE_LINE_BYTES = 64
_CP_END = OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES  # 24 + 96 = 120
...
CP_SEGMENT_BYTES = _round_up(_CP_END, CACHE_LINE_BYTES)  # 128
```

**(c) Fail-fast khi attach:**
```python
def check_cp_header(raw: bytes) -> None:
    magic = struct.unpack_from(CP_MAGIC_FMT, raw, OFFSET_CP_MAGIC)[0]
    version = struct.unpack_from(CP_VERSION_FMT, raw, OFFSET_CP_VERSION)[0]
    if magic != CP_MAGIC:
        raise ValueError(f"control-plane magic mismatch: got {magic:#x}, expected {CP_MAGIC:#x}")
    if version != CP_VERSION:
        raise ValueError(f"control-plane version mismatch: got {version}, expected {CP_VERSION}")
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `CP_MAGIC = 0x53484D43` — "chữ ký" của control-plane segment. **Khác** magic của ring data (`SHMR`) → attach
  nhầm loại segment là phát hiện được ngay.
- `OFFSET_CP_MAGIC = 0`, `OFFSET_CP_VERSION = 4` — 2 field 4 byte đầu = phần **tự mô tả** (self-describing).
- `OFFSET_CP_ATTACH_COUNT = 8 ... RESERVED` — chỗ này **để trống có chủ đích**: từng định dùng làm biến đếm
  handle (phương án cũ), nhưng **quyết định B** bỏ đếm thủ công (dựa OS tự đếm handle). Giữ chỗ, không dùng.
- `OFFSET_CP_EPOCH = 16 ... AUTHORITY, ghi CUỐI` — số epoch (8 byte) đặt ở vị trí **chia hết 8** → ghi atomic.
  Đây là "công tắc chính": chỉ khi epoch đổi thì bản ghi mới được coi là hợp lệ.
- `OFFSET_CP_RING_NAME = 24` — tên ring hiện tại, 96 byte (đủ chứa `vp_ring_<32 hex>` = 40B + dư).
- `_CP_END = 120` rồi `_round_up(..., 64)` → **128 byte** — pad lên bội **cache-line** (64B) để tránh
  "false sharing" (2 lõi CPU tranh nhau 1 dòng cache).
- `check_cp_header`: đọc magic + version; **sai → `raise ValueError` ngay** (không diễn dịch byte rác thành
  trạng thái hợp lệ) = fail-fast.

## 5. Là gì (1–2 câu)
Đây là **bản thiết kế byte** của vùng nhớ điều khiển: 4B magic + 4B version + (8B reserved) + 8B epoch +
96B tên-ring, pad thành 128B. Kèm hàm `check_cp_header` để từ chối segment lạ ngay khi attach.

## 6. Tại sao tồn tại / vấn đề nó giải
Vì tên ring sinh bằng `uuid4().hex` (ngẫu nhiên) → **không suy ra được** từ epoch (mẩu 01/03). Phải có **1 nơi
cố định** ghi rõ "epoch hiện tại + tên ring hiện tại" để writer/reader tra. Layout này chính là hợp đồng của nơi đó.

## 7. Dùng ở đâu trong project
- `RingControlPlane` (`runtime/ipc/ring_control_plane.py`, mẩu 03) tạo/đọc segment theo đúng offsets này +
  gọi `check_cp_header` khi attach.
- `encode_ring_name`/`decode_ring_name` dùng để nhét/lấy tên ring vào 96 byte.

## 8. Không có nó thì sao
Không có layout cố định + magic → attach nhầm vùng nhớ rác mà **không biết** → đọc epoch/tên bậy → writer/reader
mở nhầm ring → hỏng toàn hệ. Không có "epoch ghi cuối" → có thể đọc **tên mới nhưng epoch cũ** (bản ghi nửa vời).

## 9. Ví von
Như **bảng tin ở sảnh toà nhà**: 1 chỗ **cố định ai cũng biết**, ghi "phòng họp hôm nay ở tầng mấy". `magic` =
dấu mộc xác nhận "đây đúng là bảng tin chính thức" (không phải tờ giấy dán bậy). `epoch ghi cuối` = chỉ khi
**đổi số thứ tự thông báo** thì người đọc mới tin nội dung mới (tránh đọc thông báo dán dở).

## 10. Liên kết bức tranh lớn
kernel (layout THUẦN này) ← runtime/ipc `RingControlPlane` (transport, mẩu 03) ← application `RingSupervisor`
(publish, mẩu 08) + coordinator (đọc, mẩu 09/10). Tách **control-plane** (điều khiển, tên cố định) khỏi
**data-plane** (ring chứa frame, tên uuid) — 2 mặt phẳng khác nhau.

## 11. Cạm bẫy (+errata)
- **Đặt epoch ở offset không chia hết 8** → mất tính atomic → đọc epoch nửa vời. (Ở đây @16, an toàn.)
- **Quên `check_cp_header` khi attach** → diễn dịch byte rác thành trạng thái "hợp lệ" giả. Luôn fail-fast.
- **ATTACH_COUNT @8 là RESERVED** — đừng "tiện tay" dùng lại làm biến đếm (đã bỏ theo quyết định B; xem journal C-002/D-004).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao `current_epoch` phải đặt ở offset chia hết 8 và **ghi CUỐI**? (nối atomic + "authority".)
- `check_cp_header` bảo vệ khỏi điều gì? Nếu bỏ nó thì hỏng ra sao?
- Vì sao tên ring cần 96 byte, và vì sao segment pad lên 128 (không phải 120)?

## 13. Mốc ôn
- 1 ngày: nhắc lại 5 field + kích thước 128B + lý do pad cache-line.
- 1 tuần: giải thích "epoch ghi cuối = authority atomic" không nhìn code.
- 1 tháng: tự vẽ lại layout byte + vai control-plane vs data-plane.

## 14. Nguồn
- Code: `kernel/shm_control_plane_layout.py` — **đọc nguyên văn khi viết mẩu này** (quote khớp từng ký tự).
- Hành vi fail-fast (magic sai → ValueError): **đã có test** `tests/test_switchover_control_plane.py::test_attach_wrong_magic_fail_fast`
  + `test_switchover_control_plane_layout.py` (8 test offset/size/encode) — **pass** (full 242 passed/1 skipped). → đã verify.
- Atomicity 8B aligned: Intel SDM Vol 3A §8.1.1 (nêu trong docstring code). Bối cảnh Q1: `.kiro/specs/shm-ring-epoch-switchover/design.md`.
- Độ chắc: cao (code + test chạy thật).
