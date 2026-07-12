# 13 — Observability đo→render→serve — MỤC LỤC (các mẩu nhỏ nhất)

> Đọc `00-cau-chuyen.md` trước. Mỗi mẩu = 1 ý nhỏ nhất, quote code thật + cite path. Tạo DẦN (không hàng loạt).
> #13 dạy phần MỚI sau #08 (structlog+InMemoryMetrics cơ bản). Trạng thái: ⬜/🔵/✅.

| # | Mẩu (ý nhỏ nhất) | File code thật | Trạng thái |
|---|---|---|---|
| 01 | PULL vs PUSH + `IPipelineObserver` port (@kernel, thuần, non-blocking) — lõi không phụ thuộc Prometheus | `kernel/observability_port.py` | ✅ `01-pull-vs-push-port.md` |
| 02 | `PipelineSnapshot` (frozen) — fps INTERVAL (không che sự cố) vs trung-bình-tích-luỹ | `kernel/observability_port.py` | ✅ `02-pipeline-snapshot-fps-interval.md` |
| 03 | `PipelineRunner.emit()` — emit theo-giờ ở ĐẦU loop (mất-camera vẫn phát) + cô lập lỗi observer | `runtime/pipeline_runner.py` | ✅ `03-emit-interval-isolation.md` |
| 04 | Observers: `Noop` (default opt-in) · `Logging` (structlog) · `Metrics` (gauge, nhãn bounded `source`) | `runtime/observers.py` | ✅ `04-observers.md` |
| 05 | `MetricSample` DTO — vì sao CÓ CẤU TRÚC (name+labels tách) thay chuỗi `name{k=v}` (lossy parse) | `kernel/metric_sample.py` | ✅ `05-metric-sample-dto.md` |
| 06 | `InMemoryMetrics.iter_metrics()` — snapshot có cấu trúc + `_labelsets` (ghi lúc write, khỏi parse ngược) | `runtime/observability.py` | ✅ `06-iter-metrics-labelsets.md` |
| 07 | `render_prometheus` — `# TYPE`, escape nhãn, `+Inf`/`NaN`, SORT xác định, raise name↔type xung đột | `adapters/metrics_exposition.py` | ✅ `07-render-prometheus.md` |
| 08 | `MetricsHttpExporter` — `http.server` daemon PULL `/metrics`, secure-default localhost, 500-không-sập | `adapters/metrics_http_server.py` | ✅ `08-metrics-http-exporter.md` |
| 09 | `_serving` Event chống DEADLOCK `stop()` (K-071: shutdown cần serve_forever đang chạy) | `adapters/metrics_http_server.py` | ✅ `09-serving-event-deadlock.md` |
| 10 | Wiring: 1 `InMemoryMetrics` + 1 exporter DÙNG CHUNG → aggregate theo `source_id` (1 process/camera → 1 scrape target) | `vision_slice_app::_build_config_observability` | ✅ `10-wiring-shared-metrics-aggregate.md` |

**Ghi chú:** #13 = observability metrics (spec pipeline-observability · metrics-exposition · metrics-http-endpoint,
sau #10). Đọc kèm #08 (structlog/InMemoryMetrics nền) + #11.07 (`_parse_observability` config).
