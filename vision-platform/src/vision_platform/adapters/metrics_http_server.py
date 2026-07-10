"""Exporter HTTP `/metrics` cho Prometheus scrape (spec metrics-http-endpoint, D-078/#290). Layer: adapters (leaf).

Phơi `render_prometheus(provider())` qua `GET /metrics` (mô hình PULL). NON-BLOCKING (daemon thread), zero-dep
(`http.server` stdlib). Nhận `provider: () -> Iterable[MetricSample]` TIÊM → KHÔNG import runtime (giữ leaf) +
test được với provider giả (no-GPU).

An toàn: mặc định BIND `127.0.0.1` (localhost) — KHÔNG phơi ra mạng; bind mạng (0.0.0.0) là quyết định của
COMPOSITION (profiles) + phải cảnh báo "không auth". Endpoint này KHÔNG xác thực (chuẩn Prometheus, mạng nội bộ).

Chống deadlock (K-071): `BaseServer.shutdown()` PHẢI gọi khi `serve_forever()` đang chạy ở thread khác → dùng
`_serving` Event set NGAY TRƯỚC serve_forever; `stop()` chờ Event rồi mới shutdown.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Iterable

from vision_platform.kernel.metric_sample import MetricSample
from vision_platform.adapters.metrics_exposition import render_prometheus

_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


class _MetricsHandler(BaseHTTPRequestHandler):
    """Handler chỉ-GET: /metrics → Prometheus text; /healthz → ok (nếu bật); khác → 404."""

    def do_GET(self):  # noqa: N802 — tên do BaseHTTPRequestHandler quy định
        if self.path == "/metrics":
            try:
                body = render_prometheus(self.server._vp_provider()).encode("utf-8")  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 — provider/render lỗi → 500, KHÔNG sập thread server (R2.3)
                self.send_error(500, "metrics render error")
                return
            self.send_response(200)
            self.send_header("Content-Type", _CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/healthz" and getattr(self.server, "_vp_healthz", False):
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "not found")

    def log_message(self, *args) -> None:  # noqa: A003 — im lặng (không spam stderr mỗi scrape)
        return None


def is_loopback(host: str) -> bool:
    """True nếu host là loopback (không phơi ra mạng) — dùng để cảnh báo bind mạng ở composition."""
    return host in ("127.0.0.1", "localhost", "::1")


class MetricsHttpExporter:
    """Exporter `/metrics` non-blocking. `provider()` gọi mỗi scrape (số liệu tại-thời-điểm-scrape).

    Mặc định BIND localhost (an toàn). `port=0` → OS cấp cổng ephemeral (dùng cho test). start() trả cổng thực.
    """

    def __init__(self, provider: Callable[[], Iterable[MetricSample]],
                 host: str = "127.0.0.1", port: int = 0, *, enable_healthz: bool = True):
        self._provider = provider
        self._host = host
        self._port = port
        self._enable_healthz = enable_healthz
        self._srv: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._serving = threading.Event()   # set NGAY TRƯỚC serve_forever (chống deadlock stop-sớm, K-071)

    def start(self) -> int:
        """Dựng server + chạy serve_forever trong daemon thread. Trả CỔNG THỰC. Cổng bận → OSError (fail-fast)."""
        srv = ThreadingHTTPServer((self._host, self._port), _MetricsHandler)  # server_bind trong __init__
        srv.daemon_threads = True
        srv._vp_provider = self._provider      # type: ignore[attr-defined]  (handler đọc qua self.server)
        srv._vp_healthz = self._enable_healthz  # type: ignore[attr-defined]
        self._srv = srv
        self._port = srv.server_address[1]

        def _serve():
            self._serving.set()                # báo "sắp serve_forever" cho stop()
            srv.serve_forever(poll_interval=0.2)

        self._thread = threading.Thread(target=_serve, name="metrics-exporter", daemon=True)
        self._thread.start()
        return self._port

    def stop(self) -> None:
        """Dừng sạch (idempotent). Chờ serve_forever đã vào rồi mới shutdown → chống deadlock (K-071)."""
        if self._srv is None:
            return
        self._serving.wait(timeout=5.0)        # BaseServer.shutdown yêu cầu serve_forever ĐANG chạy
        self._srv.shutdown()
        self._srv.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._srv = None
        self._thread = None
        self._serving.clear()

    @property
    def port(self) -> int:
        return self._port
