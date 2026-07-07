# Mẩu 07 — K-016: THREAD-safe ≠ PROCESS-safe (đừng dùng cross-process)

**(1) Thuộc về đâu:** ranh giới thiết kế của `BoundedQueue` (`kernel/backpressure.py`). Đây là điểm
**sống còn cho sản phẩm thương mại** — dùng sai gây hỏng dữ liệu âm thầm.

**(2) Cần biết trước:** thread vs process (glossary `#thread`, `#process` — thread chia bộ nhớ trong 1
process; process là không gian nhớ riêng); `threading.Lock` vs `mp.Lock` (khoá luồng vs khoá liên tiến
trình — bài #05); SHM ring (#05).

**(3) Code thật (quote docstring cảnh báo `kernel/backpressure.py`):**
```python
⚠️ RANH GIỚI QUAN TRỌNG (K-016): BoundedQueue là **THREAD-safe** (dùng threading.Lock/Condition) —
KHÔNG process-safe. Chỉ dùng cho hàng đợi TRONG MỘT tiến trình (vd: thread capture → thread submit).
Truyền frame GIỮA các tiến trình vẫn phải qua SHM ring (bài #05) — threading.Lock không đồng bộ
được cross-process. Dùng nhầm cross-process = khoá vô hiệu → hỏng dữ liệu.
```

**(4) Giải thích từng ý nhỏ:**
- `threading.Lock` sống trong bộ nhớ của **một tiến trình**. Nhiều thread cùng process chia sẻ đúng
  một object lock → đồng bộ được.
- Nếu "gửi" `BoundedQueue` sang tiến trình khác (pickle qua `Process`/`mp.Queue`), **mỗi tiến trình
  nhận một bản sao lock RIÊNG** → hai bên khoá hai ổ khác nhau → **đồng bộ vô hiệu**.
- Hệ quả: 2 tiến trình cùng sửa "hàng đợi" mà không thật sự loại trừ nhau → mất item / hỏng dữ liệu,
  và **không báo lỗi** (im lặng — nguy hiểm nhất).

**(5) Là gì:** lời cảnh báo phạm vi: `BoundedQueue` chỉ an toàn giữa các **thread trong cùng 1 process**.

**(6) Tại sao tồn tại / vấn đề nó giải:** trong hệ Vision Platform có CẢ hai loại ranh giới: (a)
nhiều thread trong 1 process (dùng `BoundedQueue`); (b) nhiều process (camera process ↔ inference
process — dùng **SHM ring** + `mp.Lock` của #05). Nhầm lẫn hai cái → dùng công cụ sai chỗ → hỏng.

**(7) Dùng ở đâu ĐÚNG trong project:** hàng đợi giữa thread capture và thread submit-inference **trong
cùng một tiến trình camera**. KHÔNG dùng để đẩy frame sang tiến trình inference (đó là việc của SHM ring).

**(8) Nếu dùng nhầm cross-process thì sao:** như (4) — khoá vô hiệu, race, mất/rách dữ liệu âm thầm.
Đây chính là loại bug rất khó tìm trong sản phẩm 24/7.

**(9) Ví von:** `threading.Lock` như một cái chốt cửa **bên trong một căn phòng** — người cùng phòng
tôn trọng nó. Nhưng nếu photocopy cái chốt đưa sang phòng khác, mỗi phòng gài chốt riêng → hai phòng
tưởng đang khoá chung nhưng thực ra không liên quan gì nhau.

**(10) Liên kết bức tranh lớn:** phân định rõ 2 công cụ: `BoundedQueue` (in-process, #07) vs SHM ring
+ `mp.Lock` (cross-process, #05). Cùng phục vụ "chống quá tải / truyền frame" nhưng ở hai ranh giới khác nhau.

**(11) Cạm bẫy:** đừng "mở rộng" `BoundedQueue` để cross-process bằng cách nhét vào `mp.Queue` — sai
bản chất. Cần cross-process thì dùng cơ chế thiết kế cho việc đó (SHM ring / `mp.Queue` nguyên bản).

**(12) Tự kiểm:**
- Vì sao `BoundedQueue` không dùng được cross-process? Chuyện gì xảy ra với cái lock?
- Trong Vision Platform, truyền frame giữa 2 tiến trình thì dùng gì thay vì BoundedQueue?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (docstring K-016) · journal `04-things-to-know.md` K-016 ·
bài #05 (SHM ring + mp.Lock). Độ chắc: cao (nguyên lý threading.Lock — không đồng bộ cross-process).
