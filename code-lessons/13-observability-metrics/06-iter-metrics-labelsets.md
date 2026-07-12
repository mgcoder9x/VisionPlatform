# 13.06 — `InMemoryMetrics.iter_metrics()` + `_labelsets` — snapshot có cấu trúc (ghi lúc write, khỏi parse ngược)

## 1. Thuộc về đâu
Layer **runtime** — `runtime/observability.py` (phần MỚI so #08). Xuất metrics ra `list[MetricSample]` (mẩu 05) có cấu trúc.

## 2. Cần biết trước
#08 (InMemoryMetrics: counter/gauge lưu theo key chuỗi `_key(name,labels)`), mẩu 05 (MetricSample). Thread-safe (Lock).

## 3. Code thật (quote nguyên văn — `runtime/observability.py`)
```python
        self._labelsets: dict[str, tuple[str, dict]] = {}   # key → (name, labels) CÓ CẤU TRÚC

    def gauge(self, name: str, value: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value
            self._labelsets[key] = (name, dict(labels))     # GHI labelset lúc write

    def iter_metrics(self) -> "list[MetricSample]":
        from vision_platform.kernel.metric_sample import MetricSample
        out: list[MetricSample] = []
        with self._lock:
            for key, cval in self._counters.items():
                name, labels = self._labelsets[key]
                out.append(MetricSample("counter", name, float(cval), dict(labels)))
            for key, gval in self._gauges.items():
                name, labels = self._labelsets[key]
                out.append(MetricSample("gauge", name, float(gval), dict(labels)))
        out.sort(key=lambda s: (s.name, sorted(s.labels.items())))
        return out
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_labelsets[key] = (name, dict(labels))` — MỖI lần `counter`/`gauge`/`histogram` ghi, LƯU LUÔN (name, labels) có
  cấu trúc bên cạnh key chuỗi. → sau này lấy lại (name, labels) KHÔNG cần parse key.
- `iter_metrics` — duyệt counters + gauges, tra `_labelsets[key]` lấy (name, labels), dựng `MetricSample`.
- `with self._lock` — thread-safe (metrics ghi từ thread khác đồng thời).
- `out.sort(key=(name, sorted(labels)))` — sắp XÁC ĐỊNH → output renderer ổn định (test lặp-lại-được).
- histogram KHÔNG xuất (Non-Goal v1 — cần bucket).

## 5. Là gì
Hàm chụp toàn bộ counter+gauge thành `list[MetricSample]` có cấu trúc, sorted, thread-safe.

## 6. Tại sao tồn tại / vấn đề nó giải
Là cầu nối "kho metric nội bộ" (key chuỗi, #08) → "DTO có cấu trúc" (mẩu 05) cho renderer. `_labelsets` ghi-lúc-write
= fix GỐC lossy (mẩu 05): thay vì parse ngược key `name{k=v}` (mất thông tin), giữ cấu trúc từ đầu. Sort → xác định.

## 7. Dùng ở đâu
`MetricsHttpExporter` (mẩu 08) nhận `provider = metrics.iter_metrics`; mỗi scrape gọi `provider()` → `render_prometheus(...)` (mẩu 07).

## 8. Không có nó thì sao
Không `_labelsets` → renderer phải parse key chuỗi → lossy. Không sort → output đổi thứ tự giữa các scrape → khó test/diff.
Không lock → race khi ghi+đọc đồng thời.

## 9. Ví von
Kho hàng vừa dán mã vạch (key chuỗi để tra nhanh) VỪA ghi sổ chi tiết (name+labels) → xuất phiếu không cần "đọc ngược mã vạch" (dễ sai).

## 10. Liên kết bức tranh lớn
Khâu chuyển ĐO→RENDER: MetricsObserver ghi gauge (#08 API) → iter_metrics xuất MetricSample → render (07). `_labelsets` = mấu chốt chống lossy.

## 11. Cạm bẫy
- Getter `.get` (không tạo key) — giữ bất biến "key trong store ⟺ có labelset" (nếu getter tạo key rác thì `_labelsets[key]` KeyError).
- histogram không xuất iter_metrics (v1) — đừng kỳ vọng.

## 12. Tự kiểm (Feynman)
- `_labelsets` giải bài toán gì? Vì sao không parse key `name{k=v}`?
- Vì sao `iter_metrics` sort? Lợi gì cho render/test?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/observability.py::iter_metrics` (đọc thật phiên này) · D-071. Độ chắc: cao (quote trực tiếp).
