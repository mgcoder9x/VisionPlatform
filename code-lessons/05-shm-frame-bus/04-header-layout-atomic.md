# Mẩu 04 — Header layout v2: vì sao `state` @offset 0, 4-byte (atomic lock-free)

> Bám file: `vision-platform/src/vision_platform/kernel/shm_layout.py` (đọc nguyên văn khi viết mẩu).

## 1. Thuộc về đâu
Tầng **kernel** — "hợp đồng nhị phân": mỗi slot có 1 vùng **header** (metadata) bố trí theo offset cố định.
Writer/reader/recovery đọc-ghi header theo đúng các offset này.

## 2. Cần biết trước
- byte / offset = vị trí (tính từ 0) trong vùng nhớ.
- **aligned (căn chỉnh):** field 8-byte đặt ở offset chia hết 8; 4-byte ở offset chia hết 4.
- **atomic:** đọc/ghi "ăn cả hoặc mất cả" (mẩu 01). CPU x86-64 đảm bảo atomic **chỉ khi** field ≤8 byte VÀ aligned.
- `struct` = thư viện Python đóng/mở gói byte theo format (vd `<I` = uint32 little-endian).

## 3. Code thật (quote nguyên văn — offsets + size)
```python
OFFSET_STATE = 0                      # <I (4B) — atomic lock-free peek/quarantine
OFFSET_GENERATION = 8                 # <Q (8B) — ABA counter
OFFSET_OWNER_PID = 16                 # <Q (8B)
OFFSET_OWNER_CREATE_TIME_NS = 24      # <Q (8B) — định danh chống PID reuse
OFFSET_LEASE_DEADLINE_NS = 32         # <Q (8B)
OFFSET_READER_COUNT = 40              # <I (4B) — số reader pin (dẫn xuất từ registry)
OFFSET_READER_REGISTRY = 48           # mảng MAX_READERS ô, mỗi ô READER_ENTRY_FMT
```
```python
STATE_FMT = "<I"   # 4B @ OFFSET_STATE
U64_FMT = "<Q"     # 8B: generation / owner_pid / owner_create_time_ns / lease_deadline_ns
...
_REGISTRY_END = OFFSET_READER_REGISTRY + MAX_READERS * READER_ENTRY_BYTES  # 48 + 8*24 = 240
CACHE_LINE_BYTES = 64
...
SLOT_HEADER_V2_BYTES = _round_up(_REGISTRY_END, CACHE_LINE_BYTES)  # 256
```
(Nguồn: `kernel/shm_layout.py` — quote nguyên văn.)

## 4. Giải thích từng ý nhỏ nhất
- `OFFSET_STATE = 0` → trường `state` nằm **đầu tiên**, 4 byte (`<I`), offset 0 chia hết 4 → **aligned** → **đọc/ghi ATOMIC không cần lock**. Đây là điểm mấu chốt.
- Các field 8-byte (`generation`@8, `owner_pid`@16, `owner_create_time`@24, `lease_deadline`@32) đều ở offset **chia hết 8** → aligned.
- `reader_count`@40 (4B) chia hết 4.
- `reader_registry`@48 → mảng 8 ô (mẩu 07).
- `_REGISTRY_END = 240` → cuối vùng dữ liệu; `_round_up(240, 64) = 256` → pad lên **bội 64 byte (1 cache-line)** để tránh **false sharing** (2 slot cạnh nhau không chia chung dòng cache → không "đá" nhau).

## 5. Là gì (1–2 câu)
Bản đồ byte của 1 slot header (256 byte): mỗi trường ở 1 offset cố định, căn chỉnh để CPU truy cập atomic
được với trường ≤8 byte.

## 6. Tại sao tồn tại / vấn đề nó giải
Header nhiều byte (256B) đọc/ghi cả cụm thì **KHÔNG atomic** → phải dưới lock. NHƯNG nếu để riêng `state`
4-byte aligned @0 thì đọc/ghi nó atomic **không cần lock** → cho phép **peek lock-free**: nhìn nhanh trạng
thái slot mà không đụng khoá (nền của recovery — không bao giờ chạm khoá của process đã chết).

## 7. Dùng ở đâu trong project
- `peek_state()` đọc `<I`@0 lock-free (mẩu 09).
- `_read_header`/`_write_header` đọc/ghi các trường theo offset DƯỚI lock (mẩu 06/07).
- `quarantine_poisoned_slot` ghi `state=QUARANTINED` bằng 1 lệnh atomic 4-byte (mẩu 09).

## 8. Không có nó thì sao
Nếu `state` không aligned/không ở riêng → không thể peek lock-free → recovery buộc phải acquire lock → mà
khoá của process chết thì kẹt → **đứng bus**. Layout này chính là thứ cho phép "né khoá chết".

## 9. Ví von
Như **ô "TÌNH TRẠNG" in to ngoài bìa hồ sơ**: liếc qua là biết (không cần mở hồ sơ = không cần lock). Chi
tiết bên trong (owner, lease...) mới cần "mở khoá tủ" để đọc cho khớp.

## 10. Liên kết bức tranh lớn
Layout (kernel, thuần) là hợp đồng dùng chung; `runtime/ipc` là máy móc đọc-ghi theo hợp đồng đó. Việc đặt
`state`@0 atomic là nền tảng kiến trúc cho toàn bộ cơ chế recovery lock-free (mẩu 09).

## 11. Cạm bẫy (+errata)
- Sai alignment (vd để field 8-byte ở offset lẻ) → mất đảm bảo atomic → torn read. Test `test_hardening_slot_layout` kiểm mọi field 8B ở offset chia hết 8 + tổng = 256B.
- Đọc **nhiều trường** header (không chỉ `state`) mà không có lock → torn → recovery dùng **double-snapshot** (đọc 2 lần phải khớp — mẩu 09).
- Atomicity aligned là đảm bảo **x86-64**; ARM ordering yếu hơn → chỉ claim x86-64 (mẩu 12 / ARM gate).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao `state` để 4-byte @offset 0? "peek lock-free" nghĩa là gì và giải quyết điều gì?
- Vì sao pad header lên 256B (bội 64)? "false sharing" là gì?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `kernel/shm_layout.py` (quote nguyên văn). · Deep-dive: `Design/module-04-deep-dives/02-shm-atomicity-explained.md` + Intel SDM Vol 3A §8.1.1. · Độ chắc: cao (đọc file + test layout pass).
