# Mẩu 01 — Vì sao cần observability (3 trụ + "log không biết của ai")

**(1) Thuộc về đâu:** bức tranh tổng bài #08. Chưa vào dòng cụ thể; "móc treo".

**(2) Cần biết trước:** log (nhật ký sự kiện); tiến trình/thread (bài #05/#07); JSON (định dạng dữ liệu máy đọc được).

**(3) Code thật (quote docstring `runtime/observability.py`):**
```python
"""Observability: structlog setup + log_context (contextvars) + InMemoryMetrics.
...
3 trụ observability (vision_demo làm logs + metrics; traces để Module 04):
    Logs    → structlog (JSON, parse được bởi Loki/ELK/Datadog).
    Metrics → InMemoryMetrics (counter/gauge/histogram, thay bằng Prometheus/StatsD ở production).
"""
```

**(4) Giải thích từng ý nhỏ:**
- "Logs → structlog (JSON)" → nhật ký sự kiện dạng JSON, máy phân tích được.
- "Metrics → InMemoryMetrics" → số đo tổng hợp (đếm, mức, phân phối).
- "traces để Module 04" → trụ thứ 3 (dấu vết xuyên tiến trình) CHƯA làm ở bài này.

**(5) Là gì:** observability = khả năng nhìn vào bên trong hệ đang chạy qua dữ liệu nó phát ra (logs + metrics + traces).

**(6) Tại sao tồn tại / vấn đề nó giải:** hệ 24/7 nhiều camera/tiến trình — khi sự cố, không có
observability = "mù". Cụ thể vấn đề "**log không biết của ai**": nhiều frame/camera đổ log chung →
trộn lẫn → không truy được. Cần gắn `camera_id`/`request_id` vào log một cách sạch (mẩu 02–04).

**(7) Dùng ở đâu trong project:** `runtime/observability.py` là *nền* — code khắp hệ gọi `logger` +
`metrics`; bọc `log_context` quanh xử lý frame. Nguồn #05/#07 nối vào (bước sau).

**(8) Không có nó thì sao:** sản phẩm chạy nhưng không biết khoẻ/ốm; sự cố xảy ra mà không lần ra được — thảm hoạ vận hành 24/7.

**(9) Ví von:** bảng đồng hồ + hộp đen máy bay. Không có → bay trong sương mù, rơi mà không biết vì sao.

**(10) Liên kết bức tranh lớn:** trụ Logs/Metrics ở `runtime`; nối với backpressure metrics (#07),
sự kiện SHM (#05), shutdown (#09). Là hạ tầng vận hành xuyên suốt.

**(11) Cạm bẫy:** đừng nhầm observability với "chỉ in log". Log tự do (chuỗi) khó parse; cần JSON có
cấu trúc + metrics + context. Traces (trụ 3) chưa có ở bài này (đừng tưởng đủ 3 trụ).

**(12) Tự kiểm:**
- Kể 3 trụ observability + bài #08 làm những trụ nào?
- Vấn đề "log không biết của ai" là gì, vì sao nghiêm trọng khi nhiều camera?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (docstring) · Design step-08 (Recap concept). Độ chắc: cao (quote thật + 12 test pass).
