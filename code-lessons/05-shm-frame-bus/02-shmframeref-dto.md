# Mẩu 02 — `ShmFrameRefData`: con trỏ nhẹ tới frame trong SHM

> Bám file: `vision-platform/src/vision_platform/kernel/shm_frame_ref.py` (đọc nguyên văn khi viết mẩu).

## 1. Thuộc về đâu
Tầng **kernel** — DỮ LIỆU THUẦN (DTO). KHÔNG import `multiprocessing`/`shared_memory` (import-linter ép).
Transport thật ở `runtime/ipc/shm_frame_ring.py`; DTO này chỉ **mô tả** frame nằm ở đâu.

## 2. Cần biết trước
- [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) · [frozen](../../knowledge-base/00-GLOSSARY.md#frozen-bất-biến) · [DTO](../../knowledge-base/00-GLOSSARY.md#dto-data-transfer-object) (đã học ở #02).
- Mẩu 01 (vì sao "con trỏ nhẹ" đi qua ống thay vì ảnh 6 MB).

## 3. Code thật (quote nguyên văn)
```python
@dataclass(frozen=True)
class ShmFrameRefData:
    """Pure data carried by MediaPacket pointing to SHM slot."""
    ring_name: str        # ShmRingBuffer.name
    slot: int             # slot index
    generation: int       # ABA-prevention counter
    height: int
    width: int
    channels: int
    ring_epoch: int = 0   # P0-3: phiên bản ring; reader cầm ref epoch cũ sau switchover → trả None (stale).
```
(Nguồn: `kernel/shm_frame_ref.py` — quote nguyên văn.)

## 4. Giải thích từng ý nhỏ nhất
- `@dataclass(frozen=True)` → class dữ liệu **bất biến** (tạo xong không sửa được) → an toàn khi đi qua nhiều process/thread.
- `ring_name: str` → tên ring buffer chứa frame (để tìm đúng vùng SHM). Khớp `ShmRingBuffer.name`.
- `slot: int` → **ô thứ mấy** trong ring chứa frame này.
- `generation: int` → **số đếm chống ABA**: mỗi lần 1 slot được ghi mới, generation tăng. Reader so khớp để biết slot **chưa bị ghi đè** (mẩu 06).
- `height/width/channels` → kích thước ảnh để dựng lại `numpy.ndarray` từ vùng byte thô.
- `ring_epoch: int = 0` → **phiên bản ring** (mặc định 0). Sau khi ring bị dựng lại (switchover), epoch đổi → reader cầm ref epoch cũ biết là **stale** → trả `None`, không đọc nhầm ring mới (mẩu 12). Có default `=0` → code cũ tạo ref không cần truyền vẫn chạy (backward-compat).

## 5. Là gì (1–2 câu)
Một "tấm vé" bất biến, nhẹ (vài chục byte) mô tả: frame nằm ở **ring nào, ô nào, đời thứ mấy, kích thước
bao nhiêu, thuộc epoch nào**. Đi qua wire thay cho ảnh nặng.

## 6. Tại sao tồn tại / vấn đề nó giải
Tách "mô tả frame" (nhẹ, thuần, đi qua ống) khỏi "dữ liệu frame" (nặng, nằm im trong SHM). Nhờ DTO thuần ở
kernel, nó có thể serialize (ZMQ msgpack) hoặc gắn vào `MediaPacket` mà không kéo theo phụ thuộc I/O.

## 7. Dùng ở đâu trong project
- `ShmFrameWriter.write()` trả về `ShmFrameRefData` sau khi ghi frame (mẩu 06).
- `ShmFrameReader.read(slot, generation)` / `read_ref(ref)` dùng nó để đọc + kiểm epoch (mẩu 07/12).

## 8. Không có nó thì sao
Phải gửi cả ảnh 6 MB qua ống (chậm), hoặc reader không có cách biết "frame ở đâu + còn đúng đời không" →
đọc nhầm frame cũ (ABA).

## 9. Ví von
Như **vé gửi xe**: vé ghi "bãi X, ô 12, lượt gửi #7". Bạn cầm vé (nhẹ) đi, xe (nặng) nằm im ở bãi. Đưa vé
đúng → lấy đúng xe; vé sai đời (ô đã cho xe khác) → không lấy nhầm.

## 10. Liên kết bức tranh lớn
kernel (thuần) chứa **hợp đồng dữ liệu**; runtime/ipc chứa **máy móc** đọc/ghi. `ShmFrameRefData` là cầu
nối: sinh ra ở writer (runtime), đi qua wire, dùng ở reader (runtime) — nhưng bản thân nó thuần kernel.

## 11. Cạm bẫy (+errata)
- `generation` là **writer-local** (mỗi writer đếm riêng từ 1) → **1 ring chỉ 1 writer** (F-4), nếu 2 writer thì trùng generation → vỡ ABA (ép bằng single-writer, mẩu 10).
- Quên `ring_epoch` → sau switchover reader đọc nhầm ring mới (giải ở mẩu 12).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao DTO này để ở kernel mà KHÔNG import shared_memory? Cái gì thật sự chứa ảnh?
- `generation` và `ring_epoch` chống 2 loại "đọc nhầm" khác nhau như thế nào?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `kernel/shm_frame_ref.py` (quote nguyên văn). · Spec: `.kiro/specs/shm-production-hardening/`
  (ring_epoch = Task 8 / P0-3). · Độ chắc: cao (đọc file + test 180 passed).
