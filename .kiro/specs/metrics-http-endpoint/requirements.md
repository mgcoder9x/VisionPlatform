# Requirements Document

> **Spec:** metrics-http-endpoint (phục vụ `/metrics` HTTP cho Prometheus scrape — no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Hoàn tất:** chuỗi observability → metrics-exposition (#284, renderer Prometheus THUẦN) → **SCRAPE** (endpoint
> HTTP để Prometheus kéo). Renderer đã có nhưng chưa PHỤC VỤ ra ngoài → mảnh khoá cuối để dashboard/cảnh báo thật.
> **Nền tảng (đã ĐỌC CODE thật):**
> - `adapters/metrics_exposition.py::render_prometheus(samples) -> str` (THUẦN, 0.0.4, #284/D-074).
> - `runtime/observability.py::InMemoryMetrics.iter_metrics() -> list[MetricSample]` (#284).
> - `runtime/observers.py::MetricsObserver(metrics)` ghi gauge per-camera (nhãn `source`).
> - Import contract: **adapters = leaf** (KHÔNG import runtime/application/profiles). `vision_web_app` (Flask) đã có nhưng headless `camera_worker` KHÔNG có Flask.
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Sau #284, hệ RENDER được metrics ra Prometheus text (`render_prometheus`), nhưng CHƯA PHỤC VỤ ra ngoài → Prometheus
không kéo được → dashboard/cảnh báo vẫn chưa dùng được thật. Tính năng này thêm **endpoint HTTP `GET /metrics`**
phục vụ text đó theo mô hình PULL chuẩn (Prometheus scrape định kỳ).

Bối cảnh ~100 cam thương mại: nhiều tiến trình `camera_worker` HEADLESS (không Flask) → cần một **exporter HTTP
tối giản, độc lập, non-blocking** chạy TRONG mỗi tiến trình (giống `prometheus_client.start_http_server`), phơi
`InMemoryMetrics` của tiến trình đó.

**An toàn (BẮT BUỘC nêu):** `/metrics` theo chuẩn Prometheus **KHÔNG xác thực** (scrape trong mạng nội bộ tin cậy).
→ mặc định BIND `127.0.0.1` (localhost, an toàn — không phơi ra mạng); bind `0.0.0.0` (cho Prometheus scrape qua
mạng) là **OPT-IN tường minh** + phải cảnh báo rõ "endpoint không auth, chỉ để trong mạng nội bộ". KHÔNG bao giờ
mặc định phơi ra mạng.

**Ranh giới layer:** exporter ở `adapters` (I/O HTTP). Nó KHÔNG import `runtime` (adapters=leaf) → nhận **nguồn
dữ liệu qua callable tiêm** (`provider: () -> Iterable[MetricSample]`) → gọi `render_prometheus(provider())`.
Composition (profiles) wire `metrics.iter_metrics`. Server dùng `http.server` stdlib (zero-dep). KHÔNG cv2/torch.

**Kiểm chứng KHÔNG cần GPU:** start server trên `127.0.0.1:0` (cổng ephemeral) → `GET /metrics` qua urllib →
assert body chứa metrics + Content-Type đúng. Xác định, no-GPU/no-mạng-ngoài.

**Chống bịa:** `render_prometheus`/`iter_metrics`/`MetricsObserver`/adapters-leaf ĐÃ đọc code thật. Khẳng định về
`http.server.ThreadingHTTPServer` + Content-Type `text/plain; version=0.0.4` gắn độ-chắc-chắn CAO (stdlib + chuẩn công khai; đối chiếu docs lúc code).

### Goals
- Endpoint `GET /metrics` phục vụ `render_prometheus(provider())` với Content-Type Prometheus 0.0.4.
- Exporter NON-BLOCKING (chạy daemon thread) — KHÔNG cản pipeline chính; start/stop có kiểm soát.
- Mặc định BIND localhost (an toàn); bind mạng = opt-in + cảnh báo không-auth.
- Layer sạch: exporter @adapters nhận provider tiêm (không import runtime); zero-dep (http.server stdlib).
- Kiểm chứng no-GPU (start ephemeral port + GET + assert).

### Non-Goals
- KHÔNG thêm xác thực/TLS cho `/metrics` (chuẩn Prometheus không auth; mạng nội bộ lo bảo mật; TLS/auth = sub-spec sau nếu cần).
- KHÔNG push-gateway/federation/gộp cross-process (tầng cụm K-040 C1, sau).
- KHÔNG dùng framework nặng (Flask/aiohttp) cho exporter headless — http.server stdlib đủ (zero-dep).
- KHÔNG đổi `render_prometheus`/`InMemoryMetrics`/`MetricsObserver` (chỉ TIÊU THỤ qua provider).
- KHÔNG serving nhiều route (chỉ `/metrics`; health-check `/healthz` = tuỳ chọn nhỏ, có thể thêm).

## Glossary
- **Scrape (pull)** — Prometheus GET `/metrics` định kỳ để thu số liệu.
- **Exporter** — thành phần trong tiến trình phơi metrics qua HTTP `/metrics`.
- **provider** — callable `() -> Iterable[MetricSample]` tiêm vào exporter (nguồn dữ liệu; giữ adapters không import runtime).
- **Bind address** — địa chỉ server lắng nghe: `127.0.0.1` (localhost, an toàn) vs `0.0.0.0` (mọi interface, phơi mạng).
- **Non-blocking exporter** — server chạy daemon thread riêng, không chặn vòng pipeline.

## Requirements

### Requirement 1: Endpoint GET /metrics phục vụ Prometheus text
**User Story:** Là kỹ sư vận hành, tôi muốn Prometheus scrape `/metrics` của mỗi tiến trình để dashboard/cảnh báo, không cần bộ chuyển đổi riêng.
#### Acceptance Criteria
- 1.1 — WHEN nhận `GET /metrics`, THE exporter SHALL trả HTTP 200 với body = `render_prometheus(provider())` và Content-Type `text/plain; version=0.0.4; charset=utf-8`.
- 1.2 — WHEN nhận GET path khác (vd `/`), THE exporter SHALL trả 404 (hoặc `/healthz`→200 "ok" nếu bật) — KHÔNG phục vụ path lạ.
- 1.3 — THE mỗi lần scrape SHALL gọi `provider()` MỚI (số liệu cập-nhật-tại-thời-điểm-scrape), không cache cũ.

### Requirement 2: Non-blocking + start/stop có kiểm soát
**User Story:** Là kỹ sư, tôi muốn exporter KHÔNG cản pipeline chính và dừng sạch khi tắt.
#### Acceptance Criteria
- 2.1 — THE exporter SHALL chạy trong DAEMON THREAD riêng (`start()`), KHÔNG chặn luồng gọi.
- 2.2 — THE exporter SHALL có `stop()` dừng server + join thread sạch (không rò thread/cổng).
- 2.3 — IF handler `/metrics` ném lỗi (provider/render lỗi), THEN exporter SHALL trả HTTP 500 + KHÔNG sập thread server (scrape sau vẫn phục vụ).

### Requirement 3: An toàn — mặc định localhost, phơi-mạng là opt-in có cảnh báo
**User Story:** Là kiến trúc sư, tôi muốn endmetrics KHÔNG vô tình phơi ra mạng (rò thông tin), mà vẫn cho scrape mạng nội bộ khi cần.
#### Acceptance Criteria
- 3.1 — THE bind address mặc định SHALL là `127.0.0.1` (localhost) — KHÔNG phơi ra mạng ngoài theo mặc định.
- 3.2 — WHERE bind `0.0.0.0`/mạng được chọn (opt-in tường minh), THE hệ SHALL log CẢNH BÁO rõ "/metrics KHÔNG xác thực — chỉ dùng trong mạng nội bộ tin cậy".
- 3.3 — THE `/metrics` SHALL chỉ phơi metric bounded (source_id + tên cố định — K-019); KHÔNG phơi secret/PII (renderer chỉ nhận MetricSample bounded).

### Requirement 4: Ranh giới layer + zero-dep + additive
**User Story:** Là kiến trúc sư, tôi muốn exporter không kéo dep nặng, không đảo layer, không đụng code có sẵn.
#### Acceptance Criteria
- 4.1 — THE exporter SHALL ở `adapters`, nhận `provider: () -> Iterable[MetricSample]` TIÊM — KHÔNG import `runtime`/`application`/`profiles` (adapters=leaf); import-linter 5 kept/0 broken.
- 4.2 — THE exporter SHALL dùng `http.server` stdlib (zero-dep mới), KHÔNG Flask/aiohttp.
- 4.3 — THE thay đổi SHALL additive: KHÔNG đổi `render_prometheus`/`InMemoryMetrics`/`MetricsObserver`; baseline **591 passed/2 skipped · lint 5/0** giữ (+ test mới).

### Requirement 5: Kiểm chứng KHÔNG cần GPU
**User Story:** Là kỹ sư, tôi muốn test endpoint xác định trên máy dev.
#### Acceptance Criteria
- 5.1 — Test SHALL start exporter trên `127.0.0.1:0` (cổng ephemeral do OS cấp) với provider giả (vài MetricSample) → `GET /metrics` qua urllib → assert 200 + body chứa metric + Content-Type đúng.
- 5.2 — Test SHALL kiểm 404 cho path lạ + (nếu bật) `/healthz`→200.
- 5.3 — Test SHALL kiểm start/stop sạch (sau stop, cổng đóng — connect refused/không rò thread).
- 5.4 — Test SHALL kiểm provider ném lỗi → GET /metrics trả 500, server vẫn sống (scrape sau OK).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format) có: (a) `MetricsHttpExporter(provider, host, port)` @adapters
(http.server ThreadingHTTPServer + handler /metrics/404/500 + daemon start/stop) — nhận provider tiêm; (b) điểm wire
(profiles/CLI `--metrics-port`, `metrics.iter_metrics` làm provider) + cảnh báo bind-mạng; (c) an toàn (localhost
default, opt-in mạng + cảnh báo, bounded metric); (d) test no-GPU (ephemeral port + urllib GET); (e) layer + zero-dep
+ additive. **KHÔNG code ở PHA này** (chờ user valid thiết kế).
