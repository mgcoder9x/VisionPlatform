# Design Document — metrics-http-endpoint (phục vụ /metrics cho Prometheus scrape, no-GPU)

## Overview

Hoàn tất chuỗi observability: `MetricsObserver`→`InMemoryMetrics` (đo) → `render_prometheus` (#284, render) →
**exporter HTTP `/metrics`** (phục vụ để Prometheus PULL). Thêm một exporter TỐI GIẢN, NON-BLOCKING (daemon
thread), zero-dep (`http.server` stdlib), phơi `render_prometheus(provider())` mỗi lần scrape.

**Nguyên tắc gốc:** exporter là NGƯỜI-PHỤC-VỤ, tách khỏi nguồn dữ liệu (nhận `provider` callable tiêm) → adapters
KHÔNG import runtime (leaf) + test được với provider giả (no-GPU). An toàn mặc định: BIND localhost; phơi-mạng =
opt-in tường minh + cảnh báo (chuẩn Prometheus KHÔNG auth).

## Bằng chứng code đã đọc (chống bịa)
- `adapters/metrics_exposition.py::render_prometheus(samples: Iterable[MetricSample]) -> str` (THUẦN, 0.0.4).
- `kernel/metric_sample.py::MetricSample` (DTO thuần).
- `runtime/observability.py::InMemoryMetrics.iter_metrics() -> list[MetricSample]` (dùng làm provider qua composition).
- Import contract (verify #288 lint 5/0): "Adapters là leaf — không import runtime/application/profiles".
- `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` (stdlib) — server đa-luồng nhẹ.

## Nguồn chuẩn (kiến thức — độ chắc chắn CAO, xác nhận lúc code)
- Prometheus scrape: HTTP GET path `/metrics`, Content-Type `text/plain; version=0.0.4; charset=utf-8` (prometheus.io).
- `http.server.ThreadingHTTPServer((host, port), Handler)`; `server.server_address[1]` = cổng thực (khi port=0 → OS cấp ephemeral); `serve_forever()` (chạy trong thread) / `shutdown()` + `server_close()` để dừng sạch. (stdlib docs — ổn định.)

## Architecture

Thêm 1 exporter @adapters. KHÔNG layer mới, KHÔNG đảo hướng. Nguồn dữ liệu tiêm qua callable.

```
Prometheus server ──scrape GET /metrics──►  adapters/metrics_http_server.py
                                              MetricsHttpExporter(provider, host="127.0.0.1", port=0)
                                                • ThreadingHTTPServer + Handler (daemon thread)
                                                • GET /metrics → 200 render_prometheus(provider())
                                                • GET khác → 404 ; /healthz → 200 ("ok")
                                                • handler lỗi → 500 (server không sập)
                                                • start()/stop() (daemon serve_forever / shutdown+close)
                                                   ▲ provider: () -> Iterable[MetricSample]  (TIÊM)
                                                   │
profiles (composition): MetricsHttpExporter(metrics.iter_metrics, host, port).start()
                        (host="0.0.0.0" opt-in → LOG cảnh báo không-auth)
                                                   │ đọc
                                              runtime/observability.py InMemoryMetrics (ghi bởi MetricsObserver)
```

- **Hướng phụ thuộc:** `adapters` (exporter) → gọi `render_prometheus` (adapters) + `provider()` (callable thuần,
  KHÔNG import runtime) → adapters=leaf giữ. `profiles` wire `metrics.iter_metrics` làm provider.
- **Vì sao provider callable (không truyền InMemoryMetrics):** để exporter (adapters) KHÔNG import kiểu runtime →
  giữ leaf + test bằng provider giả (list MetricSample) không cần InMemoryMetrics/pipeline.
- **Vì sao http.server stdlib:** zero-dep, đủ cho 1 endpoint /metrics; `prometheus_client` cũng dùng http.server/WSGI.

## Components and Interfaces

### 1. adapters/metrics_http_server.py — MetricsHttpExporter (stdlib, non-blocking)
```
class MetricsHttpExporter:
    def __init__(self, provider, host="127.0.0.1", port=0, *, enable_healthz=True):
        # provider: () -> Iterable[MetricSample]. host="0.0.0.0" → cảnh báo (nơi gọi log; xem An toàn).
        self._serving = threading.Event()   # set NGAY TRƯỚC serve_forever (chống deadlock stop-sớm)

    def start(self) -> int:
        # dựng ThreadingHTTPServer (server_bind trong __init__ → port thực có ngay; port đã-dùng → OSError raise)
        self._srv = ThreadingHTTPServer((host, port), _Handler); self._srv.daemon_threads = True
        self._srv._vp_provider = self._provider; self._srv._vp_healthz = self._enable_healthz
        def _serve():
            self._serving.set()              # báo "sắp serve_forever" cho stop() (fix Lỗ-A #290)
            self._srv.serve_forever(poll_interval=0.2)
        self._thread = threading.Thread(target=_serve, daemon=True); self._thread.start()
        return self._srv.server_address[1]   # cổng thực (ephemeral khi port=0)

    def stop(self):
        if self._srv is None: return         # idempotent (chưa start / 2 lần)
        self._serving.wait(timeout=5.0)      # CHỜ serve_forever đã vào (BaseServer.shutdown yêu cầu) — chống deadlock
        self._srv.shutdown(); self._srv.server_close()
        self._thread.join(timeout=5.0); self._srv = None

    @property
    def port(self) -> int: ...               # cổng thực (hữu ích khi port=0 ephemeral cho test)
```
- **Fix Lỗ-A (#290, bản chất — chống deadlock):** `BaseServer.shutdown()` (stdlib) PHẢI gọi khi `serve_forever()` ĐANG chạy ở thread khác, nếu không **DEADLOCK**. `start()` return ngay → nếu `stop()` gọi TRƯỚC khi thread vào serve_forever (test start→stop nhanh, P5) → treo. Guard: `_serving` Event set ngay trước `serve_forever`; `stop()` `wait()` nó (bounded 5s) rồi mới `shutdown()`.
- `poll_interval=0.2` để `serve_forever` phản hồi `shutdown()` nhanh (≤0.2s).
Handler (BaseHTTPRequestHandler) — chỉ GET:
```
def do_GET(self):
    if self.path == "/metrics":
        try:
            body = render_prometheus(self.server._vp_provider()).encode("utf-8")
        except Exception:
            self.send_error(500); return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    elif self.path == "/healthz" and <enabled>:
        <200 "ok">
    else:
        self.send_error(404)
def log_message(self, *a): pass   # không spam stderr mỗi scrape
```
- `provider` gắn vào server instance (`server._vp_provider`) để handler (class) truy cập.
- ThreadingHTTPServer → mỗi scrape 1 thread → scrape song song/chậm không chặn nhau. daemon_threads=True.

### 2. profiles / CLI — wire (composition)
- Optional CLI `--metrics-port N` (+ `--metrics-host`, default 127.0.0.1) ở `vision_slice_app`/`camera_worker`:
  `exp = MetricsHttpExporter(metrics.iter_metrics, host, port); exp.start()`; `exp.stop()` lúc teardown.
- Nếu `host` không phải loopback (127.0.0.1/localhost/::1) → `logger.warning("/metrics KHÔNG xác thực — chỉ dùng mạng nội bộ tin cậy", host=...)` (R3.2). Quyết định cảnh-báo ở COMPOSITION (biết ý định vận hành).

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `MetricsHttpExporter` | class | provider callable; host/port; start()/stop()/port | adapters | composition |
| `provider` | `() -> Iterable[MetricSample]` | thuần; gọi mỗi scrape | (tiêm) | handler /metrics |
| bind host | str | default "127.0.0.1"; "0.0.0.0"=opt-in+cảnh báo | adapters/profiles | server |

- KHÔNG đổi `render_prometheus`/`MetricSample`/`InMemoryMetrics`. Exporter chỉ TIÊU THỤ.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| provider()/render ném lỗi | handler bắt → HTTP 500; server thread KHÔNG sập (scrape sau vẫn phục vụ) | R2.3, P4 |
| GET path lạ | 404 | R1.2 |
| port=0 | OS cấp ephemeral; `start()` trả cổng thực (đọc server_address[1]) — test dùng | R5.1 |
| host phi-loopback | composition LOG cảnh báo không-auth (không chặn — vận hành tự quyết) | R3.2 |
| stop() gọi khi chưa start / 2 lần | idempotent (guard None) — không raise | R2.2 |
| **stop() gọi NGAY sau start (serve_forever chưa vào)** | `_serving` Event: stop() `wait()` tới khi serve_forever bắt đầu rồi mới `shutdown()` → KHÔNG deadlock (Lỗ-A #290) | R2.2, P5 |
| **port cố định đã bị dùng** | `ThreadingHTTPServer.__init__` (server_bind) ném `OSError` → `start()` raise (fail-fast, thông báo cổng bận) | R2.1 |
| scrape đồng thời | ThreadingHTTPServer mỗi request 1 thread (daemon_threads=True) → không chặn | R2.1 |

- Exporter là phụ trợ → lỗi scrape KHÔNG được ảnh hưởng pipeline (chạy thread riêng; provider chỉ đọc snapshot).

## Correctness Properties

### Property 1: GET /metrics trả Prometheus text đúng
Provider giả (vài MetricSample) → `GET /metrics` → 200, body == `render_prometheus(provider())`, Content-Type `text/plain; version=0.0.4; charset=utf-8`.
**Validates: Requirements 1.1**

### Property 2: path lạ → 404 ; /healthz → 200
`GET /` → 404; `GET /healthz` (bật) → 200 "ok".
**Validates: Requirements 1.2**

### Property 3: số liệu cập-nhật mỗi scrape
provider trả giá trị khác nhau giữa 2 lần gọi → 2 scrape cho body khác nhau (không cache).
**Validates: Requirements 1.3**

### Property 4: handler lỗi → 500, server sống
provider ném lỗi → `GET /metrics` → 500; scrape kế (provider ok) → 200 (server không sập).
**Validates: Requirements 2.3**

### Property 5: non-blocking + start/stop sạch (kể cả stop NGAY sau start — fix Lỗ-A #290)
`start()` không chặn (trả ngay + cổng thực); sau `stop()` → cổng đóng (connect refused) + thread joined (không rò). `start()` rồi `stop()` NGAY (serve_forever có thể chưa vào) → KHÔNG deadlock (nhờ `_serving` Event).
**Validates: Requirements 2.1, 2.2, 5.3**

### Property 6: an toàn bind mặc định localhost
Default host == "127.0.0.1" (không phơi mạng); host phi-loopback → cảnh báo được phát (kiểm qua composition/log).
**Validates: Requirements 3.1, 3.2**

### Property 7: layer + zero-dep + additive
Exporter @adapters chỉ import stdlib + adapters(render)+kernel(MetricSample) qua provider — KHÔNG runtime/application/profiles; import-linter 5 kept/0 broken; baseline 591/2 giữ.
**Validates: Requirements 4.1, 4.2, 4.3**

## Testing Strategy

- **Endpoint (P1,P2,P3):** `exp = MetricsHttpExporter(provider=lambda: [MetricSample("gauge","g",1.0,{"source":"cam0"})], host="127.0.0.1", port=0)`; `port=exp.start()`; `urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics")` → assert 200 + `g{source="cam0"} 1.0` + Content-Type. `/`→404, `/healthz`→200. provider đổi giá trị → body đổi.
- **Lỗi (P4):** provider ném → GET 500; đổi provider ok → 200. (Dùng provider mutable/flag.)
- **start/stop (P5):** sau `exp.stop()`, `urlopen` → `URLError`/ConnectionRefused (cổng đóng); thread không alive.
- **Layer (P7):** lint importlinter.api 5/0; kiểm module chỉ import stdlib+kernel+adapters.render.
- **An toàn (P6):** default host "127.0.0.1"; test hàm cảnh-báo (composition) phát warning khi host="0.0.0.0" (tiêm logger giả / caplog).
- **Đối chiếu:** không cần GPU/mạng-ngoài (dùng 127.0.0.1 ephemeral). Chạy được ngay máy dev.

## Review đối kháng vòng 2 (đọc-lại-valid #290 — đối chiếu ngữ nghĩa stdlib, trước khi code)
Đối chiếu design với hợp đồng `socketserver.BaseServer` thật → tìm 1 lỗ bản chất + 1 note:
- **Lỗ-A (deadlock tiềm ẩn):** `BaseServer.shutdown()` PHẢI gọi khi `serve_forever()` đang chạy ở thread khác,
  nếu không DEADLOCK (shutdown chờ event chỉ serve_forever set). `start()` return ngay → `stop()` gọi TRƯỚC khi
  thread vào serve_forever (test start→stop nhanh P5 / teardown nhanh) → treo. Fix: `_serving` Event set ngay
  trước `serve_forever`; `stop()` `wait()` (bounded 5s) rồi mới `shutdown()`. +Property 5 + Error-Handling row.
- **Note:** port cố định đã dùng → `server_bind` ném OSError trong `__init__` → `start()` raise (fail-fast, thông báo rõ). render trong try TRƯỚC send_response → 500 sạch (headers chưa gửi).
> Bài học (K-071, củng cố K-069): review adapter I/O phải trace HỢP ĐỒNG THƯ VIỆN THẬT (thread/lifecycle của
> http.server), không chỉ logic ứng dụng — deadlock start/stop chỉ lộ khi biết shutdown() cần serve_forever đang chạy.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** phục-vụ-chuẩn (Prometheus scrape) ⟂ non-blocking (không cản pipeline) ⟂ an-toàn (không vô tình phơi
  mạng) ⟂ layer sạch (adapters leaf, provider tiêm) ⟂ zero-dep. Cân được: http.server daemon + provider callable +
  localhost default.
- **What varies?** NGUỒN metrics (InMemoryMetrics giờ; Prometheus registry sau) → provider callable trừu tượng hoá.
  ĐỊNH DẠNG (render) tái dùng #284. GIAO VẬN (HTTP pull) = 1 exporter; push-gateway = adapter khác sau.
- **Which way deps point?** adapters(exporter)→adapters(render)+kernel(MetricSample); provider callable (thuần) do
  profiles cấp = `runtime.iter_metrics`. adapters KHÔNG import runtime → leaf giữ.
- **Cái GIÁ:** +1 class exporter (http.server) + wire. Nhỏ. Đổi lấy: metrics DÙNG ĐƯỢC THẬT (scrape/dashboard).
- **An toàn (nhấn):** `/metrics` KHÔNG auth (chuẩn Prometheus). Rủi ro = rò thông tin vận hành nếu phơi mạng công
  cộng. GIẢM THIỂU: default localhost + opt-in mạng phải cảnh báo + metric bounded (không secret/PII). Auth/TLS =
  sub-spec nếu triển khai qua mạng không tin cậy (KHÔNG mặc định — tránh over-engineer khi thường scrape nội bộ).
- **Khi nào KHÔNG dùng:** (a) đã có prometheus_client toàn hệ → dùng exporter của nó. (b) scrape qua Internet công
  cộng → CẦN reverse-proxy auth/TLS (ngoài phạm vi; cảnh báo). (c) cross-process gộp → push-gateway (sau).
- **Recognize:** "render được metrics nhưng Prometheus không kéo được" = thiếu exporter HTTP.

## Non-Goals (nhắc lại)
Auth/TLS cho /metrics · push-gateway/federation/gộp cross-process · framework nặng (Flask/aiohttp) cho exporter
headless · đổi render_prometheus/InMemoryMetrics/MetricsObserver · nhiều route ngoài /metrics(+/healthz).
