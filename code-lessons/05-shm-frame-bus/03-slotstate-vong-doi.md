# Mẩu 03 — `SlotState`: vòng đời một slot (+ QUARANTINED terminal)

> Bám file: `vision-platform/src/vision_platform/kernel/shm_layout.py` (đọc nguyên văn khi viết mẩu).

## 1. Thuộc về đâu
Tầng **kernel** (`shm_layout.py` — "hợp đồng nhị phân" thuần, chỉ `struct`+`enum`). Định nghĩa các trạng thái
mà 1 slot có thể ở. Writer/reader/recovery (nhiều process) dùng CHUNG 1 nguồn này.

## 2. Cần biết trước
- [Enum / IntEnum](../../knowledge-base/00-GLOSSARY.md#enum) (đã học #02) — tập giá trị có tên.
- slot = 1 ô chứa frame (mẩu 01). Mỗi slot có 1 trường `state` cho biết đang ở giai đoạn nào.

## 3. Code thật (quote nguyên văn)
```python
class SlotState(IntEnum):
    """Trạng thái 1 slot. Giá trị ghi vào trường `state` 4-byte @offset 0 (atomic)."""
    FREE = 0          # trống, writer ghi được
    WRITING = 1       # writer đang giữ, dở
    READY = 2         # sẵn sàng đọc
    READING = 3       # có ≥1 reader đang pin
    DONE = 4          # đọc xong, tái dùng được
    QUARANTINED = 0xFFFFFFFF  # TERMINAL: slot bị loại vĩnh viễn (owner chết + lease quá hạn) — KHÔNG tái dùng
```
(Nguồn: `kernel/shm_layout.py` — quote nguyên văn.)

## 4. Giải thích từng ý nhỏ nhất
- `IntEnum` → mỗi trạng thái là 1 **số nguyên** (ghi được vào bộ nhớ nhị phân dễ dàng).
- `FREE = 0` → ô trống, writer được phép ghi.
- `WRITING = 1` → writer đang ghi dở (chưa xong) — reader KHÔNG được đọc.
- `READY = 2` → ghi xong, sẵn sàng cho reader.
- `READING = 3` → có **≥1** reader đang "pin" (giữ) để đọc (đa reader — mẩu 07).
- `DONE = 4` → mọi reader đọc xong → writer được tái dùng ô.
- `QUARANTINED = 0xFFFFFFFF` → **cách ly VĨNH VIỄN** (terminal): khi owner của slot chết + lease quá hạn. Giá trị `0xFFFFFFFF` = max uint32, tách biệt hẳn 0–4 để không lẫn.

## 5. Là gì (1–2 câu)
Máy trạng thái (state machine) của 1 slot: `FREE → WRITING → READY → READING → DONE → (tái dùng)`, cộng
nhánh sự cố `→ QUARANTINED` (loại vĩnh viễn).

## 6. Tại sao tồn tại / vấn đề nó giải
Nhiều process cùng động 1 slot → phải có "biển báo" chung để biết ai được làm gì lúc nào (writer chỉ ghi
FREE/DONE; reader chỉ đọc READY/READING). QUARANTINED giải nỗi đau **process chết giữ khoá** (mẩu 09).

## 7. Dùng ở đâu trong project
- Writer đọc `state`, chỉ ghi khi FREE/DONE; mark WRITING→READY (mẩu 06).
- Reader chỉ pin khi READY/READING; unpin → DONE (mẩu 07).
- Recovery ghi QUARANTINED khi phát hiện owner chết (mẩu 09).

## 8. Không có nó thì sao
Không có "biển báo" → reader đọc trúng lúc writer đang ghi (WRITING) → ảnh rách; hoặc writer đè slot đang có
reader đọc → hỏng.

## 9. Ví von
Như **biển trên phòng thử đồ**: TRỐNG (FREE) · ĐANG THAY (WRITING) · XONG-CHỜ-KHÁCH (READY) · KHÁCH ĐANG
DÙNG (READING) · TRẢ PHÒNG (DONE) · HỎNG-KHÓA-NIÊM-PHONG (QUARANTINED, không ai vào nữa).

## 10. Liên kết bức tranh lớn
`state` là trường ĐẦU TIÊN của header (offset 0, 4-byte) → đọc/ghi **atomic không cần lock** (mẩu 04). Nhờ
vậy peek nhanh trạng thái slot trước khi đụng khoá (nền của recovery mẩu 09).

## 11. Cạm bẫy (+errata)
- QUARANTINED là **terminal** — KHÔNG bao giờ quay lại FREE. Vì khoá của OS (semaphore) không "robust": owner chết thì khoá kẹt ở mức OS, không giải được → tái dùng = chờ khoá chết mãi. (Review R-1.1; mẩu 09.)
- Đừng thêm giá trị state ≥ 5 trùng vùng khác — QUARANTINED cố ý ở tận `0xFFFFFFFF`.

## 12. Tự kiểm (retrieval + Feynman)
- Kể vòng đời 1 slot bằng lời mình. Writer ghi ở trạng thái nào? Reader đọc ở trạng thái nào?
- Vì sao QUARANTINED phải là "terminal", không quay lại FREE?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `kernel/shm_layout.py` (quote nguyên văn). · Spec: QUARANTINED = Task 3/4 (R-1.1 terminal). ·
  Độ chắc: cao (đọc file + test 180 passed).
