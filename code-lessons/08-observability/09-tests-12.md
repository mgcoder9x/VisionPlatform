# Mẩu 09 — 12 test: metrics + log_context + logger integration

**(1) Thuộc về đâu:** `tests/test_step_08_observability.py`. Bằng chứng cho mẩu 01–08.

**(2) Cần biết trước:** `threading.Thread`; `structlog.testing.capture_logs`; contextvars (mẩu 02).

**(3) Code thật — hai test cốt lõi (quote `tests/test_step_08_observability.py`):**

Thread-safe metrics (chứng minh Lock):
```python
def test_metrics_thread_safe():
    m = InMemoryMetrics()
    n_threads, n_per = 10, 100
    def worker():
        for _ in range(n_per):
            m.counter("ops")
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert m.get_counter("ops") == n_threads * n_per   # 1000, không mất update
```

log_context nested (chứng minh reset LIFO):
```python
def test_log_context_nested_restores_outer():
    with log_context(camera_id="A"):
        with log_context(camera_id="B"):
            assert _add_context_vars(None, None, {})["camera_id"] == "B"
        assert _add_context_vars(None, None, {})["camera_id"] == "A"   # thoát B → A
    assert _camera_none()   # thoát A → None
```

**(4) Giải thích nhóm test:**
- **Metrics (6):** counter basic/labels · gauge overwrite · histogram append · **thread-safe 10×100** ·
  snapshot độc lập. Thread-safe: 1000 increment đồng thời → đúng 1000 (không mất) = Lock hoạt động.
- **log_context (4):** set/restore · nested (A→B→A) · multi-field · partial (chỉ set field truyền).
  Kiểm qua `_add_context_vars` (đọc contextvar thật) → deterministic.
- **Logger integration (2):** `setup_logging` + `capture_logs` (pipeline chạy, event bắt được) ·
  `_add_context_vars` inject trong `log_context`.

**(5) Là gì:** bộ 12 test phủ metrics + context + logging.

**(6) Tại sao tồn tại / vấn đề nó giải:** biến "Lock đúng", "reset LIFO đúng", "processor inject đúng"
thành **bằng chứng chạy được** (§5). Đặc biệt thread-safe test là chốt chặn race.

**(7) Dùng ở đâu / kết quả thật:** `pytest tests/test_step_08_observability.py -q` → **12 passed**
(0.62s); full **284 passed, 1 skipped**; `lint-imports` **5 kept, 0 broken** (structlog runtime KEPT).

**(8) Không có test thread-safe thì sao:** race mất-update chỉ lộ ngẫu nhiên lúc tải cao → metrics sai
âm thầm (đếm thiếu) → quyết định vận hành sai. Test ép lộ ngay.

**(9) Ví von:** cho 10 người cùng ghi 100 gạch vào một bảng, đếm cuối phải đúng 1000 — nếu thiếu tức
là có người ghi đè người khác (thiếu khoá).

**(10) Liên kết bức tranh lớn:** nối §5 (verify bằng chạy thật). Test contextvar dùng `_add_context_vars`
trực tiếp vì `capture_logs` bỏ qua processor chain (không kiểm được contextvar qua nó) — chi tiết quan trọng.

**(11) Cạm bẫy:** `capture_logs` KHÔNG chạy processor đã configure → đừng dùng nó để test contextvar
injection; test injection bằng cách gọi `_add_context_vars` trong `log_context`. Test thread-safe cần
đủ vòng lặp (10×100) để race lộ nếu thiếu lock.

**(12) Tự kiểm:**
- Test thread-safe phát hiện bug gì? Con số 1000 nghĩa là gì?
- Vì sao không dùng `capture_logs` để kiểm contextvar injection?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_step_08_observability.py` (12 test, đã chạy pass) · Design step-08 (Phần 4).
Độ chắc: cao (output pytest thật: 12 passed / full 284 passed, 1 skipped).
