# 13.08 — `MetricsHttpExporter` — `http.server` daemon PULL `/metrics`, secure-default localhost, 500-không-sập

## 1. Thuộc về đâu
Layer **adapters** (leaf) — `adapters/metrics_http_server.py`. Phơi `/metrics` HTTP cho Prometheus scrape (PULL).

## 2. Cần biết trước
mẩu 01 (PULL), 07 (render_prometheus). `http.server` (stdlib). "daemon thread" = thread nền, tự chết khi process chết. `provider` = hàm trả metrics.

## 3. Code thật (quote nguyên văn — `metrics_http_server.py`)
```python
    def do_GET(self):
        if self.path == "/metrics":
            try:
                body = render_prometheus(self.server._vp_provider()).encode("utf-8")
            except Exception:  # provider/render lỗi → 500, KHÔNG sập thread server (R2.3)
                self.send_error(500, "metrics render error"); return
            self.send_response(200); self.send_header("Content-Type", _CONTENT_TYPE); ...
            self.wfile.write(body)
        elif self.path == "/healthz" and getattr(self.server, "_vp_healthz", False):
            ...
        else:
            self.send_error(404, "not found")

    def __init__(self, provider, host: str = "127.0.0.1", port: int = 0, *, enable_healthz: bool = True):
        ...
    def start(self) -> int:
        srv = ThreadingHTTPServer((self._host, self._port), _MetricsHandler)
        srv.daemon_threads = True
        srv._vp_provider = self._provider
        ...
        self._thread = threading.Thread(target=_serve, name="metrics-exporter", daemon=True); self._thread.start()
        return self._port
```
```python
def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")
```

## 4. Giải thích từng mẩu nhỏ nhất
- `ThreadingHTTPServer((host, port), _MetricsHandler)` — server HTTP đa-luồng stdlib; `provider` gắn lên `srv._vp_provider`.
- `daemon_threads=True` + thread `daemon=True` — NON-BLOCKING: chạy nền, không chặn pipeline; process chết → tự dọn.
- `port=0` → OS cấp cổng ephemeral (test); `start()` trả CỔNG THỰC (`server_address[1]`).
- `do_GET /metrics`: gọi `provider()` (= `iter_metrics`) → `render_prometheus` → 200 + body. Route `/healthz` (nếu bật) → "ok". Khác → 404.
- **500-không-sập**: provider/render raise → `send_error(500)` + return, KHÔNG cho exception thoát ra thread server (server sống tiếp, scrape sau vẫn được).
- **secure-default**: `host="127.0.0.1"` mặc định → localhost, KHÔNG phơi mạng. `is_loopback` để composition cảnh báo khi bind `0.0.0.0`.

## 5. Là gì
Server HTTP nhỏ, nền, phục vụ `/metrics` (+/healthz) cho Prometheus scrape.

## 6. Tại sao tồn tại / vấn đề nó giải
Hoàn tất chuỗi PULL: Prometheus cần endpoint HTTP để đến lấy. Dùng `http.server` stdlib (zero-dep). Non-blocking
(daemon) → không làm chậm pipeline. 500-không-sập → 1 lần render lỗi không giết endpoint (còn phục vụ scrape sau).
secure-default localhost → không vô tình phơi số liệu ra mạng.

## 7. Dùng ở đâu
`_build_config_observability` (mẩu 10): `MetricsHttpExporter(metrics.iter_metrics, host, port)`; `start()` in cổng;
`stop()` (mẩu 09) trong finally. Bật qua `--metrics-port`.

## 8. Không có nó thì sao
Không endpoint → Prometheus không scrape được (không có PULL). Blocking (không daemon) → chặn pipeline. Không
500-guard → 1 render lỗi giết thread server → mọi scrape sau fail. Bind 0.0.0.0 default → phơi số liệu ra mạng (rủi ro).

## 9. Ví von
Quầy "công-tơ" mở cửa nền cho công ty điện tới đọc; nếu 1 lần đọc lỗi thì báo "lỗi tạm" (500) chứ không ĐÓNG CỬA quầy; mặc định quầy chỉ mở trong nhà (localhost).

## 10. Liên kết bức tranh lớn
Khâu SERVE (cuối chuỗi). Nhận render (07) từ iter_metrics (06). An ninh: review §D.4/K-072 (0.0.0.0 chưa auth). `stop()` an toàn = mẩu 09.

## 11. Cạm bẫy
- Bind `0.0.0.0` phơi mạng KHÔNG auth (K-072) → composition PHẢI cảnh báo (mẩu 10 dùng `is_loopback`).
- `/metrics` gọi `provider()` MỖI scrape → provider phải nhanh + thread-safe (iter_metrics có lock, mẩu 06).

## 12. Tự kiểm (Feynman)
- Vì sao 500-không-sập quan trọng cho endpoint scrape?
- Vì sao default bind localhost? Bind 0.0.0.0 có rủi ro gì?
- Daemon thread giúp gì (blocking?)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`adapters/metrics_http_server.py` (đọc thật phiên này) · D-078/#290/#291 · K-072 (security). Độ chắc: cao (quote trực tiếp).
