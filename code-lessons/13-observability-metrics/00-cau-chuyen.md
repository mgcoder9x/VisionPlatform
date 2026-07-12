# 13 — Observability đo→render→serve `/metrics` — CÂU CHUYỆN

> Bám code THẬT (đã đọc): `kernel/observability_port.py`·`kernel/metric_sample.py` · `runtime/observers.py`·
> `runtime/observability.py`(InMemoryMetrics.iter_metrics) · `adapters/metrics_exposition.py`·`adapters/metrics_http_server.py` · `runtime/pipeline_runner.py`(emit).
> Người học: đã qua #08 (structlog + InMemoryMetrics cơ bản). #13 dạy phần MỚI: quan-sát-pipeline → Prometheus `/metrics`.
> Thuật ngữ lạ → `knowledge-base/00-GLOSSARY.md`.

---

## Nhịp 1 — Tổng quan (nằm ĐÂU, phục vụ GÌ)

Service chạy 24/7 cho N camera. Vận hành cần biết SỐNG: camera nào còn chạy? fps bao nhiêu? tỉ lệ bỏ khung
(skip) cao bất thường không? Đó là **observability**. Chuỗi 3 khâu (mỗi khâu 1 tầng — điểm mấu chốt):

```
PipelineRunner ──emit(PipelineSnapshot)──► IPipelineObserver          [ĐO]   kernel port + runtime observer
                                              └► MetricsObserver → InMemoryMetrics
InMemoryMetrics.iter_metrics() ─► list[MetricSample] ─► render_prometheus() ─► text 0.0.4   [RENDER]  adapters
render text ◄── MetricsHttpExporter  GET /metrics  ◄── Prometheus scrape (PULL)             [SERVE]   adapters
```
Một câu: **đo (snapshot) → gom (InMemoryMetrics) → render (text Prometheus) → phục vụ (`/metrics` HTTP)**.

---

## Nhịp 2 — VẤN ĐỀ & tại sao (Forces)

**Vấn đề:** lõi pipeline (runtime) KHÔNG được phụ thuộc Prometheus/StatsD (lib giám sát cụ thể) — nếu nhúng
thẳng thì đổi hệ giám sát = sửa lõi + lõi kéo dep nặng. Nhưng vẫn phải phát số liệu ra được.
- *Forces:* quan sát được ↔ lõi không phụ thuộc công cụ giám sát; đo LIÊN TỤC ↔ không làm chậm/sập pipeline
  (observer chậm/lỗi không được kéo sập xử lý frame).

**Vấn đề 2 — số liệu "trung thực":** fps trung bình tích luỹ CHE sự cố (camera đang rớt nhưng trung bình vẫn đẹp).
Cần fps phản ánh nhịp GẦN ĐÂY.

**Vấn đề 3 — render đúng chuẩn:** Prometheus text 0.0.4 có luật (escape nhãn, `+Inf`/`NaN`, 1 tên 1 type); parse
key nội bộ `name{k=v}` để render lại thì LOSSY khi value chứa `,`/`=`/`}`.

**Vấn đề 4 — phục vụ an toàn:** mở cổng HTTP không được sập pipeline + không phơi mạng bừa + `stop()` không deadlock.

> ✋ Đoán thử: làm sao lõi "phát số liệu" mà KHÔNG biết Prometheus là gì? (đáp nhịp 4)

---

## Nhịp 3 — Khám phá NHIỀU hướng

- **Đẩy (PUSH) vs Kéo (PULL):** push (lõi tự gửi tới server giám sát) — lõi phải biết địa chỉ/giao thức server;
  pull (server tự đến scrape `/metrics`) — lõi chỉ phơi endpoint, không biết ai scrape. → chọn **PULL** (chuẩn Prometheus, lõi tách rời).
- **Coupling lõi↔Prometheus:** (a) nhúng client Prometheus vào runtime — kéo dep + đảo hướng; (b) **port thuần**
  (`IPipelineObserver` @kernel) + adapter ở rìa. → chọn (b).
- **fps:** trung bình tích luỹ (che sự cố) vs **interval** (frame kể từ lần emit trước / thời gian trôi). → chọn interval.

---

## Nhịp 4 — CHỐT giải pháp + tại sao thắng

- **ĐO:** `IPipelineObserver` (port @kernel, thuần) + `PipelineSnapshot` (frozen, fps INTERVAL). `PipelineRunner`
  `emit()` snapshot định kỳ (theo-giờ ở ĐẦU loop → mất-camera vẫn phát) + **cô lập lỗi observer** (try/except,
  đếm `_observer_errors`, không sập). Observer: `Noop` (default, opt-in), `Logging` (structlog), `Metrics` (gauge).
- **GOM:** `MetricsObserver` ghi gauge vào `InMemoryMetrics` (nhãn CHỈ `source` — bounded cardinality K-019).
  `iter_metrics()` xuất `list[MetricSample]` CÓ CẤU TRÚC (name+labels tách) → renderer khỏi parse-ngược (fix lossy).
- **RENDER:** `render_prometheus` THUẦN @adapters: `# TYPE`, escape nhãn, `+Inf`/`NaN`, SORT xác định, raise khi
  1 tên có 2 type. `MetricSample` @kernel = DTO dùng chung runtime↔adapters (không đảo hướng).
- **SERVE:** `MetricsHttpExporter` (`http.server` daemon, PULL `/metrics`), **secure-default localhost**, 500-không-sập,
  `_serving` Event chống deadlock `stop()` (K-071). Vì sao thắng: lõi chỉ phụ thuộc PORT; đổi Prometheus→StatsD = thêm observer, không đụng lõi.

---

## Nhịp 5 — Dạy TRIỂN KHAI (qua mẩu nhỏ nhất)
Xem `00-muc-luc.md`: port+snapshot (kernel) → observers (runtime) → MetricSample+iter_metrics → render_prometheus →
MetricsHttpExporter + `_serving` chống deadlock → wiring (1 InMemoryMetrics dùng chung aggregate theo source_id).

---

## Nhịp 6 — NÊN LÀM / NÊN TRÁNH
**Nên:** port thuần @kernel (lõi không phụ thuộc Prometheus) · fps INTERVAL (không che sự cố) · emit theo-giờ đầu
loop (mất-camera vẫn phát) · cô lập lỗi observer · nhãn bounded (`source`) · MetricSample có cấu trúc (không parse
key) · secure-default localhost · `_serving` Event trước `shutdown()`.
**Tránh:** nhúng Prometheus vào runtime (đảo hướng + dep nặng) · fps trung-bình-tích-luỹ (che sự cố) · nhãn
high-cardinality (packet_id/bbox → nổ series, Prometheus OOM — K-019) · bind 0.0.0.0 không cảnh báo · `shutdown()`
khi serve_forever chưa chạy (deadlock K-071).

## Tự kiểm (retrieval)
1. Vì sao PULL (scrape) chứ không PUSH? Lõi tách rời thế nào?
2. Vì sao fps INTERVAL chứ không trung-bình-tích-luỹ?
3. Vì sao `MetricSample` giữ (name, labels) tách rời thay vì chuỗi `name{k=v}`?
4. `_serving` Event giải deadlock gì khi `stop()`?

**Mốc ôn:** 1 ngày / 1 tuần / 1 tháng. **Nguồn:** 6 file trên · D (pipeline-observability/metrics-exposition/http-endpoint) · `docs/ARCHITECTURE.md` §8 · K-019/K-071.
