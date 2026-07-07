# Bài #08 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung: log-không-biết-của-ai → contextvars + processor). Rồi mẩu dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + code verify. Cột Feynman = riêng (user học sau).
> Bám code thật: `runtime/observability.py` + `tests/test_step_08_observability.py` — **12 passed**,
> full **284 passed/1 skipped** · lint **5 kept/0 broken**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-observability.md` | 3 trụ (logs/metrics/traces); vấn đề "log không biết của ai" | `runtime/observability.py` (docstring) | ✅ |
| 02 | `02-contextvars-vs-threadlocal.md` | 3 ContextVar (camera/packet/request); vì sao contextvars không threading.local | `runtime/observability.py` (_*_var) | ✅ |
| 03 | `03-log-context.md` | `log_context` __enter__/__exit__: set token, reset LIFO nested-safe | `runtime/observability.py` (log_context) | ✅ |
| 04 | `04-processor-add-context-vars.md` | `_add_context_vars` processor + chuỗi processor structlog | `runtime/observability.py` (_add_context_vars) | ✅ |
| 05 | `05-setup-logging.md` | `setup_logging`: JSONRenderer + filtering bound logger + cache | `runtime/observability.py` (setup_logging) | ✅ |
| 06 | `06-inmemory-metrics-3-loai.md` | counter/gauge/histogram + Lock (3 loại số đo khác nhau) | `runtime/observability.py` (InMemoryMetrics) | ✅ |
| 07 | `07-labels-cardinality.md` | `_key` (label sorted) + ngân sách cardinality (K-019 bounded) | `runtime/observability.py` (_key) | ✅ |
| 08 | `08-snapshot-thread-safe.md` | `snapshot` copy độc lập + get_histogram copy under-lock; thread-safe | `runtime/observability.py` (snapshot/get_*) | ✅ |
| 09 | `09-tests-12.md` | 12 test: 6 metrics (gồm thread-safe 10×100) + 4 log_context + 2 logger integration | `tests/test_step_08_observability.py` | ✅ |

> ✅ **ĐỦ 9/9 MẨU** — quote nguyên văn code + neo test đã pass (12 passed, full 284/1). Template 14 mục.
> **Cổng Feynman:** user tự giải thích lại (học sau). AI KHÔNG tự chấm. Không dán lesson vào chat.
