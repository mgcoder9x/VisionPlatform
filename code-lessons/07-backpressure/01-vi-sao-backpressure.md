# Mẩu 01 — Vì sao cần backpressure

**(1) Thuộc về đâu:** bức tranh tổng bài #07 — hàng đợi giữa producer (camera) và consumer (detector).
Chưa vào 1 dòng cụ thể; đây là "móc treo".

**(2) Cần biết trước:** thread (glossary `#thread` — luồng chạy trong 1 tiến trình); queue/hàng đợi
(vào trước ra trước — FIFO); producer/consumer (nơi sản xuất / nơi tiêu thụ).

**(3) Code thật (quote docstring `kernel/backpressure.py`):**
```python
"""Backpressure — BoundedQueue thread-safe với 4 policy khi hàng đợi đầy.
...
4 policy (Module 02 có 6; bỏ SAMPLE/DEGRADE_QUALITY vì là quyết định source-side, không phải queue):
    DROP_OLDEST · DROP_NEWEST · BLOCK · REJECT.
"""
```

**(4) Giải thích từng ý nhỏ:**
- "backpressure ... khi hàng đợi đầy" → vấn đề trọng tâm: **đầy thì làm gì**.
- "4 policy" → có 4 cách xử lý, chọn lúc tạo queue.
- "bỏ SAMPLE/DEGRADE ... source-side" → 2 chính sách kia thuộc *nguồn*, không phải queue (SRP — mẩu 02).

**(5) Là gì:** backpressure = cơ chế "đẩy lùi" khi nơi tiêu thụ không theo kịp nơi sản xuất, để hệ
không vỡ (hết RAM/nghẽn).

**(6) Tại sao tồn tại / vấn đề nó giải:** camera phát ~30–60 khung/giây; detector (AI) chậm hơn. Nếu
để hàng đợi *không giới hạn*, nó phình vô hạn → **hết RAM → crash**. Backpressure ép ra quyết định:
bỏ frame nào / chặn / từ chối — có kiểm soát.

**(7) Dùng ở đâu trong project:** `BoundedQueue` (kernel) — các tầng trên đặt giữa thread capture và
thread submit-inference (trong 1 tiến trình). Cross-process thì dùng SHM ring #05 (mẩu 07).

**(8) Không có nó thì sao:** hàng đợi vô hạn → phình RAM → sập; hoặc chặn sai cách (RTSP) → nghẽn mạng.

**(9) Ví von:** bồn rửa có vòi chảy mạnh (producer) nhưng lỗ thoát nhỏ (consumer). Không có cơ chế →
nước tràn (crash). Backpressure = quyết định: khoá bớt vòi (BLOCK) / xả nước cũ (DROP_OLDEST) / từ
chối thêm nước (REJECT).

**(10) Liên kết bức tranh lớn:** nằm ở `kernel` như "công cụ nền" thread-safe. Là mảnh chống quá tải
trong hệ real-time nhiều camera — nối với shutdown (#09) + observability (#08).

**(11) Cạm bẫy:** đừng nghĩ "cứ tăng maxsize là xong" — chỉ trì hoãn crash. Phải chọn *policy* đúng
với bản chất nguồn.

**(12) Tự kiểm (retrieval + Feynman):**
- Vì sao hàng đợi không giới hạn là nguy hiểm?
- Nói bằng lời của bạn: backpressure giải quyết mâu thuẫn gì giữa producer và consumer?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (docstring) · Design step-07 (Mục tiêu). Độ chắc: cao (quote
thật + 11 test pass).
