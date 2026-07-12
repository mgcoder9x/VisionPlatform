# 13.01 — PULL vs PUSH + `IPipelineObserver` port (@kernel, thuần) — lõi KHÔNG phụ thuộc Prometheus

## 1. Thuộc về đâu
Layer **kernel** — `kernel/observability_port.py`. Port (Protocol) để lõi phát số liệu mà không biết công cụ giám sát cụ thể.

## 2. Cần biết trước
"Protocol" (structural typing, bài port). "Scrape" = hệ giám sát tự GỌI `/metrics` lấy số liệu. PULL = bị-kéo; PUSH = tự-đẩy.

## 3. Code thật (quote nguyên văn — `kernel/observability_port.py`)
```python
@runtime_checkable
class IPipelineObserver(Protocol):
    """Nhận snapshot số liệu định kỳ từ `PipelineRunner`. Impl PHẢI non-blocking (chạy trong thread run() —
    I/O chậm sẽ backpressure pipeline; adapter nặng tự buffer async)."""

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None: ...
```

## 4. Giải thích từng mẩu nhỏ nhất
- `IPipelineObserver` = HỢP ĐỒNG: "ai muốn nhận số liệu pipeline thì implement `on_snapshot`".
- `Protocol` (structural) → observer không cần kế thừa, chỉ cần có method đúng chữ ký.
- Docstring nhấn: impl PHẢI **non-blocking** — vì `on_snapshot` chạy TRONG thread `run()` của pipeline; nếu observer
  làm I/O chậm (gửi mạng) sẽ làm CHẬM cả pipeline (backpressure ngược). Adapter nặng phải tự buffer async.

## 5. Là gì
Cổng thuần để lõi "phát snapshot ra ngoài" mà không dính công cụ giám sát nào.

## 6. Tại sao tồn tại / PULL vs PUSH
- **PUSH** (lõi tự gửi tới Prometheus/StatsD): lõi phải biết địa chỉ + giao thức + import client của server → phụ
  thuộc công cụ + kéo dep vào runtime.
- **PULL** (Prometheus tự đến scrape `/metrics`): lõi chỉ phơi endpoint text; ai scrape, bao lâu 1 lần là việc của
  server giám sát. Lõi TÁCH RỜI. → dự án chọn PULL (chuẩn Prometheus).
- Port `IPipelineObserver` @kernel: lõi (`PipelineRunner`) chỉ gọi `observer.on_snapshot(...)` — KHÔNG biết
  observer là Logging/Metrics/Prometheus gì. Đổi công cụ = thêm observer/adapter ở rìa, KHÔNG đụng lõi.

## 7. Dùng ở đâu
`PipelineRunner.__init__(observer: IPipelineObserver)` + `emit()` gọi `self._observer.on_snapshot(snap)`. Impl:
`NoopObserver`/`LoggingObserver`/`MetricsObserver` (mẩu 04, @runtime).

## 8. Không có nó thì sao
Lõi import Prometheus client → runtime phụ thuộc lib giám sát (đảo hướng, kéo dep). Đổi Prometheus→StatsD = sửa lõi.
Port cắt đứt phụ thuộc đó (hexagonal).

## 9. Ví von
Lõi như nhà máy có "cổng công-tơ" tiêu chuẩn; công ty điện (Prometheus) tự đến đọc số (PULL). Nhà máy không cần
biết công ty điện dùng phần mềm gì.

## 10. Liên kết bức tranh lớn
Khâu ĐO của chuỗi đo→render→serve. Cùng triết lý port với IFrameSource/IDetector/ISink (bài #03/#06) — lõi nói
qua Protocol, adapter ở rìa.

## 11. Cạm bẫy
- Observer BLOCKING (I/O chậm) trong `on_snapshot` → backpressure ngược pipeline. Phải non-blocking (chỉ ghi bộ nhớ/log).
- PULL cần endpoint HTTP sống (mẩu 08); nếu process chết thì scrape fail = tín hiệu "camera chết" (đúng ý).

## 12. Tự kiểm (Feynman)
- PULL vs PUSH khác gì? Vì sao PULL giúp lõi tách rời Prometheus?
- Vì sao `on_snapshot` PHẢI non-blocking? Chậm thì hại gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/observability_port.py` (đọc thật phiên này) · `docs/ARCHITECTURE.md` §8. Độ chắc: cao (quote trực tiếp).
