# Mẩu 05 — `setup_logging`: cấu hình structlog (JSON + filter + cache)

**(1) Thuộc về đâu:** `runtime/observability.py`, hàm `setup_logging`.

**(2) Cần biết trước:** mẩu 04 (processor chain); JSON; log level (DEBUG/INFO/WARNING...); `logging` (thư viện chuẩn Python).

**(3) Code thật (quote `runtime/observability.py`):**
```python
def setup_logging(level: str = "INFO") -> None:
    """Cấu hình structlog. Gọi 1 lần mỗi tiến trình lúc khởi động."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context_vars,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO),
        ),
        cache_logger_on_first_use=True,
    )
```

**(4) Giải thích từng dòng:**
- `processors=[...]` → dây chuyền xử lý mỗi log, theo thứ tự:
  - `add_log_level` → thêm field mức log (info/warning...).
  - `TimeStamper(fmt="iso", utc=True)` → thêm mốc thời gian ISO, UTC.
  - `_add_context_vars` → chèn camera_id/packet_id/request_id (mẩu 04).
  - `JSONRenderer()` → biến `event_dict` thành **chuỗi JSON** (bước cuối).
- `wrapper_class=make_filtering_bound_logger(<level int>)` → logger **lọc theo mức sớm**: nếu mức là
  INFO thì message DEBUG bị bỏ NGAY (không tốn công format).
- `getattr(logging, level.upper(), logging.INFO)` → đổi "INFO" (chuỗi) → hằng số int của `logging`; không tìm thấy → INFO.
- `cache_logger_on_first_use=True` → cache logger theo tên → nhanh hơn (không dựng lại mỗi lần).

**(5) Là gì:** hàm cấu hình structlog một lần lúc khởi động tiến trình: định dạng JSON, gắn context, lọc theo mức.

**(6) Tại sao tồn tại / vấn đề nó giải:** structlog cần được "khai báo cách xử lý log" trước khi dùng.
Gom vào 1 hàm gọi-1-lần → mọi logger trong tiến trình nhất quán (JSON + context + level).

**(7) Dùng ở đâu trong project:** composition root gọi `setup_logging("INFO")` lúc start; sau đó
`structlog.get_logger()` ở mọi nơi. Test `test_setup_logging_and_log_capture`.

**(8) Không có nó thì sao:** structlog dùng cấu hình mặc định (không JSON, không context, không lọc) →
log không parse được, thiếu nhãn.

**(9) Ví von:** cài đặt dây chuyền đóng gói trước ca sản xuất: dán nhãn thời gian → dán nhãn camera →
đóng hộp JSON. Cài 1 lần, cả ca chạy theo.

**(10) Liên kết bức tranh lớn:** đây là nơi `_add_context_vars` (mẩu 04) được cắm vào chuỗi. JSON →
Loki/ELK parse được (nối vận hành 24/7). `make_filtering_bound_logger` = tối ưu hiệu năng hot path.

**(11) Cạm bẫy (K-018):** bản này CỐ Ý bỏ production handlers: non-blocking queue handler, xoay file
theo size, flush lúc shutdown. Sản phẩm thật cần thêm (đừng deploy bản này nguyên si cho 24/7). Gọi
`setup_logging` **một lần** — gọi nhiều lần cấu hình lại thừa.

**(12) Tự kiểm:**
- Thứ tự processor tại sao JSONRenderer cuối?
- `make_filtering_bound_logger` tiết kiệm gì khi message dưới mức?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (setup_logging) · Design step-08 (Phần 2 + Note vs production).
Độ chắc: cao (quote thật + test setup_logging pass, structlog 26.1.0).
