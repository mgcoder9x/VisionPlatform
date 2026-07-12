# 13.10 — Wiring: 1 `InMemoryMetrics` + 1 exporter DÙNG CHUNG → aggregate theo `source_id`

## 1. Thuộc về đâu
Layer **profiles** — `vision_slice_app._build_config_observability`. Ráp ĐO→GOM→SERVE thành 1 hệ observability cho lần chạy.

## 2. Cần biết trước
mẩu 04 (MetricsObserver), 06 (iter_metrics), 08 (exporter). #11.15 (`_CompositeObserver`, `extra_sinks`).

## 3. Code thật (quote nguyên văn — `vision_slice_app.py`)
```python
def _build_config_observability(observe, metrics_port, metrics_host):
    metrics_host = metrics_host or "127.0.0.1"   # #310/K-076
    observers_list = []
    if observe:
        from vision_platform.runtime.observers import LoggingObserver
        observers_list.append(LoggingObserver())
    exporter = None
    if metrics_port is not None:
        from vision_platform.runtime.observability import InMemoryMetrics
        from vision_platform.runtime.observers import MetricsObserver
        from vision_platform.adapters.metrics_http_server import MetricsHttpExporter, is_loopback
        metrics = InMemoryMetrics()
        observers_list.append(MetricsObserver(metrics))
        if not is_loopback(metrics_host):
            print(f"[metrics] CẢNH BÁO: /metrics bind {metrics_host} KHÔNG xác thực — chỉ dùng mạng nội bộ tin cậy", file=sys.stderr)
        exporter = MetricsHttpExporter(metrics.iter_metrics, host=metrics_host, port=metrics_port)
        _p = exporter.start()
        print(f"[metrics] phục vụ http://{metrics_host}:{_p}/metrics", file=sys.stderr)
    if len(observers_list) == 1: observer = observers_list[0]
    elif len(observers_list) >= 2: observer = _CompositeObserver(observers_list)
    else: observer = None
    return observer, exporter
```

## 4. Giải thích từng mẩu nhỏ nhất
- `metrics = InMemoryMetrics()` — **1** kho metric; `MetricsObserver(metrics)` ghi vào nó; `exporter =
  MetricsHttpExporter(metrics.iter_metrics, ...)` đọc từ CHÍNH nó. → 1 InMemoryMetrics + 1 exporter DÙNG CHUNG.
- **Aggregate theo `source_id`**: mọi pipeline (camera) cùng process gọi `MetricsObserver.on_snapshot` với nhãn
  `source=source_id` (mẩu 04) → cùng ghi vào 1 InMemoryMetrics → `/metrics` có 1 series gauge/camera (aggregate tự nhiên theo nhãn).
- `is_loopback` → cảnh báo khi bind non-localhost (K-072).
- `exporter.start()` in cổng thực. `observer` = 1 cái / `_CompositeObserver` fan-out (observe + metrics) / None.
- `metrics_host or "127.0.0.1"` — resolve sentinel None → localhost (K-076, tránh crash ThreadingHTTPServer((None,port))).

## 5. Là gì
Hàm dựng (observer, exporter) DÙNG CHUNG cho cả đường CLI-direct lẫn `--config` — ráp toàn chuỗi observability.

## 6. Tại sao tồn tại / vấn đề nó giải
Mô hình deploy: "1 process = 1 hoặc nhiều camera, 1 endpoint `/metrics`". Dùng CHUNG 1 InMemoryMetrics → Prometheus
scrape 1 target thấy TẤT CẢ camera trong process (mỗi camera 1 series theo `source`). Không dùng chung → mỗi camera
1 kho → phải nhiều endpoint. Đây là điểm nối ĐO (observer)→GOM(metrics)→SERVE(exporter).

## 7. Dùng ở đâu
CLI-direct (`main`) + `_run_from_config` (đường config) đều gọi hàm này (DRY, #298). `exporter.stop()` trong finally
(mẩu 09). Bật qua `--observe`/`--metrics-port` hoặc `[observability]` TOML (#11.07).

## 8. Không có nó thì sao
Ráp tay ở 2 đường → phân kỳ (như F1). Không dùng chung metrics → aggregate sai/nhiều endpoint. Không cảnh báo
non-loopback → phơi mạng âm thầm. Hàm này gom 1 chỗ + an toàn.

## 9. Ví von
1 bảng điện tử trung tâm (InMemoryMetrics) hiện số liệu MỌI camera (mỗi camera 1 dòng theo tên); 1 cửa sổ (exporter)
cho người ngoài xem bảng đó.

## 10. Liên kết bức tranh lớn — CỔNG ĐÓNG #13
Ráp trọn: emit snapshot (03) → MetricsObserver (04) → InMemoryMetrics (06) → iter_metrics → render (07) → exporter
`/metrics` (08) + stop an toàn (09). Aggregate theo source_id = mô hình "1 process/camera → scrape".

## 11. Cạm bẫy
- Non-loopback bind PHẢI cảnh báo (K-072). `metrics_host=None` sentinel → resolve localhost (K-076).
- Dùng CHUNG metrics là CHỦ ĐÍCH (aggregate); đừng tạo nhiều InMemoryMetrics cho cùng process.

## 12. Tự kiểm (Feynman — cổng đóng #13)
- Vì sao 1 InMemoryMetrics DÙNG CHUNG → aggregate theo `source_id`? Mô hình deploy nào?
- **Tổng hợp #13:** kể chuỗi đo→gom→render→serve, chỉ rõ mỗi khâu tầng nào (kernel/runtime/adapters/profiles) + vì sao lõi tách Prometheus.

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`vision_slice_app::_build_config_observability` (đọc thật #324) · K-072/K-076 · #298/#299. Độ chắc: cao (quote trực tiếp).
