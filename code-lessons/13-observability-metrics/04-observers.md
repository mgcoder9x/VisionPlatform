# 13.04 — Observers: `Noop` (default opt-in) · `Logging` (structlog) · `Metrics` (gauge, nhãn bounded)

## 1. Thuộc về đâu
Layer **runtime** — `runtime/observers.py`. Các impl của `IPipelineObserver` (mẩu 01). Được import structlog (contract #3 cho phép).

## 2. Cần biết trước
mẩu 01 (port), 02 (snapshot), #08 (InMemoryMetrics gauge, cardinality K-019).

## 3. Code thật (quote nguyên văn — `runtime/observers.py`)
```python
class NoopObserver:
    """Mặc định của PipelineRunner — KHÔNG làm gì (backward-compat: bật observability = opt-in)."""
    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        return None

class LoggingObserver:
    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        self._log.info("pipeline_snapshot", source_id=snapshot.source_id, ..., fps=round(snapshot.frames_per_second, 2), ...)

class MetricsObserver:
    def __init__(self, metrics) -> None:
        self._m = metrics
    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        src = snapshot.source_id
        self._m.gauge("pipeline_fps", snapshot.frames_per_second, source=src)
        self._m.gauge("pipeline_skip_rate", snapshot.skip_rate, source=src)
        self._m.gauge("pipeline_frames_read", float(snapshot.frames_read), source=src)
        self._m.gauge("pipeline_stage_errors", float(snapshot.stage_errors), source=src)
```

## 4. Giải thích từng mẩu nhỏ nhất
- **`NoopObserver`** — default của `PipelineRunner`: không bật observability thì `_emit` gọi Noop (vô hại) → hành
  vi cũ giữ nguyên (opt-in, backward-compat).
- **`CollectingObserver`** (không quote đủ) — gom snapshot vào list (test/demo).
- **`LoggingObserver`** — mỗi snapshot 1 dòng structlog JSON (Loki/ELK/Datadog parse được).
- **`MetricsObserver`** — ghi 4 **gauge** vào `InMemoryMetrics`, nhãn CHỈ `source` (= source_id). Nhãn bounded
  (số camera hữu hạn) → không nổ cardinality (K-019). `_m` tiêm ngoài → production thay bằng adapter Prometheus/StatsD (cùng interface `gauge`).

## 5. Là gì
3 cách "tiêu thụ" snapshot: bỏ qua (Noop) · ghi log (Logging) · ghi metric gauge (Metrics).

## 6. Tại sao tồn tại / vấn đề nó giải
Cùng 1 port, nhiều cách dùng: dev muốn log đọc mắt (Logging); Prometheus muốn số (Metrics); mặc định không bật gì
(Noop, opt-in). Tách adapter khỏi lõi → thêm cách mới = thêm 1 class impl `on_snapshot`, không đụng runner.

## 7. Dùng ở đâu
`_build_config_observability` (mẩu 10): `--observe`→`LoggingObserver`; `--metrics-port`→`MetricsObserver(InMemoryMetrics)`;
cả hai → `_CompositeObserver` fan-out. Không bật gì → runner dùng `NoopObserver` (default).

## 8. Không có nó thì sao
Không có Noop-default → phải luôn truyền observer (mất backward-compat/opt-in). Không tách Logging/Metrics → nhồi
cả log lẫn metric vào runner (vi phạm SRP + khó thay).

## 9. Ví von
Cùng "bản tin thời tiết" (snapshot): người bỏ qua (Noop), người ghi nhật ký (Logging), người cắm vào bảng số liệu (Metrics).

## 10. Liên kết bức tranh lớn
Khâu ĐO (tiêu thụ snapshot). `MetricsObserver`→`InMemoryMetrics`→`iter_metrics`(mẩu 06)→render(07)→serve(08). Nhãn
`source` bounded = nối cardinality K-019 (#08).

## 11. Cạm bẫy
- Nhãn phải BOUNDED (chỉ `source`); đừng thêm packet_id/toạ độ → nổ series (Prometheus OOM, K-019).
- Observer phải non-blocking (mẩu 01); Logging/Metrics ở đây chỉ ghi bộ nhớ/log → OK.

## 12. Tự kiểm (Feynman)
- Vì sao default là `NoopObserver`? (opt-in/backward-compat)
- `MetricsObserver` dùng nhãn gì, vì sao KHÔNG dùng packet_id? (cardinality)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/observers.py` (đọc thật phiên này) · K-019 (cardinality). Độ chắc: cao (quote trực tiếp; excerpt có `...`).
