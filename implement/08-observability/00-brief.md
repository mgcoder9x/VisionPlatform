# Vấn đề #08 — Observability: structlog + log_context + InMemoryMetrics (PHA 1 valid)

> **Nguồn Design:** `Design/module-03-build-along/step-08-add-observability.md` (đọc nguyên văn).
> **Trạng thái:** PHA 1 valid — thiết kế SẠCH. 1 việc phải thêm: dependency `structlog` (C-008). Không có deviation logic.
> **Cập nhật lúc:** 2026-07-04.

## 1. Mục tiêu #08 (theo Design)
`runtime/observability.py` gồm:
- `setup_logging(level)` — cấu hình structlog (processors chain: add_log_level → TimeStamper(iso,utc) → _add_context_vars → JSONRenderer; filtering bound logger; cache).
- `log_context` (context manager) — bind `camera_id`/`packet_id`/`request_id` vào contextvars cho block; reset LIFO (nested đúng).
- `_add_context_vars` — structlog processor inject contextvars vào mỗi log line.
- `InMemoryMetrics` — thread-safe counter/gauge/histogram + labels (Prometheus-style key) + snapshot (copy độc lập).
- 12 test: 6 metrics (gồm thread-safe 10×100) + 4 log_context + 2 logger integration.

## 2. Đối chiếu Design ↔ CODE THẬT (chống bịa)
| Design giả định | Code THẬT | Kết luận |
|---|---|---|
| package `vision_demo` | `vision_platform` | đổi tên nhất quán |
| `runtime/observability.py` | CHƯA tồn tại (runtime/ có base_stage, sync_linear_executor, ipc/) | additive, 0 đụng độ |
| import `structlog` ở runtime | contract #3 runtime forbidden = application/adapters/profiles (KHÔNG cấm structlog) | ✅ hợp lệ layer |
| dùng `structlog` | **CHƯA cài** trong venv (`ModuleNotFoundError`) + CHƯA khai báo pyproject (deps=numpy,psutil) | ⚠️ phải thêm dep + cài (C-008) |
| `contextvars`, `collections.defaultdict`, `threading.Lock` | stdlib | ✅ |

## 3. C-008 — Thêm dependency `structlog` (chỗ phải thêm so với repo hiện tại)
- `observability.py` là code **production runtime** (không phải test) → `structlog` phải vào `[project] dependencies` (KHÔNG phải `[dev]`).
- Version: `structlog>=24.1` — theo convention repo (numpy>=1.26, psutil>=5.9 đều dùng `>=`), không over-constrain. structlog là thư viện logging cấu trúc nổi tiếng, actively maintained (không typosquat).
- `include_external_packages=true` → import-linter phân tích structlog; phải CÀI thật trước khi lint/test (nếu không → import error).

## 4. Đánh giá diện rộng (doubt-driven — thiết kế đúng chưa?)
- **contextvars (không threading.local):** đúng — hoạt động cho async + thread + process boundary; threading.local rò rỉ context khi async/thread-pool tái dùng thread. (Self-check #1.)
- **Token reset LIFO (`reversed`):** đúng — nested log_context khôi phục giá trị trước; reset xuôi sẽ dùng previous_value stale.
- **InMemoryMetrics Lock:** đúng — counter/gauge/histogram + get_* + snapshot đều under-lock; `get_histogram`/`snapshot` COPY under-lock (chống "deque/list mutated during iteration").
- **Cardinality budget:** Design cảnh báo đúng — KHÔNG để label unbounded (packet_id/bbox coords → Prometheus OOM). Đây là ràng buộc VẬN HÀNH (không enforce trong code, ghi K-mới).
- **snapshot copy độc lập:** đúng — caller mutate snapshot không đụng internal.
→ **Thiết kế production-minded, giữ nguyên logic.** Chỉ cải thiện style: thay `__import__("logging")` inline bằng `import logging` ở đầu file (không đổi hành vi).

## 5. Điều NÊN BIẾT (ghi journal)
- **K-018 (production hardening hoãn):** Design vision_demo CỐ Ý bỏ (so với production `08-observability.md`): `_BoundedQueueHandler` non-blocking enqueue (HI-OBS-01), `RotatingFileHandler` xoay theo size (HI-OBS-02), `LoggingHandle.shutdown()` flush lúc cascade. #08 chỉ dựng nền structlog+metrics. Sản phẩm thật cần bổ sung 3 cái này (sub-spec/ bước sau).
- **K-019 (cardinality):** label metrics PHẢI bounded (camera_id<100, status<10...); coords/packet_id → cho vào LOGS (high-cardinality OK), KHÔNG vào label metric. Ràng buộc vận hành, không enforce trong code.
- **Wiring nguồn→sink (LAW #1 — hoãn có chủ ý):** #08 dựng SINK (structlog + InMemoryMetrics). Các NGUỒN đã có — `ShmObservabilityHook.emit()` events (#05) + backpressure counters (#07/K-017) — nối vào sink này là **integration bước sau** (mỗi wiring nhỏ, không nhồi vào #08 để giữ một-vấn-đề-một-lần). Ghi rõ để không tưởng #08 đã "wire hết".

## 6. Kế hoạch PHA 2 (TDD)
1. Thêm `structlog>=24.1` vào `[project] dependencies` → `pip install structlog` (verify version).
2. `runtime/observability.py` theo Design (giữ logic, dùng `import logging` sạch).
3. `tests/test_step_08_observability.py`: 12 test (6 metrics + 4 log_context + 2 logger integration dùng structlog capture).
4. Chạy THẬT `pytest tests/test_step_08_observability.py` + full suite + `lint-imports` (kỳ vọng 5 kept/0 broken — structlog ở runtime hợp lệ).
