"""adapters/security_headers.py — WSGI middleware thêm HTTP security headers (spec web-production-hardening Wave 3).

Bọc NGOÀI CÙNG (ngoài cả auth) → mọi response (kể cả 401) đều có header an toàn. Leaf adapter: chỉ stdlib.

Header (mặc định, an toàn — KHÔNG phá app camera nội bộ):
- `X-Content-Type-Options: nosniff` — cấm trình duyệt đoán MIME (chống chèn nội dung sai kiểu).
- `X-Frame-Options: DENY` — cấm nhúng vào <iframe> → chống clickjacking feed camera.
- `Referrer-Policy: no-referrer` — không rò URL (có thể chứa token/host) sang site khác.

KHÔNG thêm CSP (app dùng inline <script> trong _PAGE → CSP cần nonce, dễ vỡ; để Wave sau nếu cần) và KHÔNG HSTS
(chỉ có nghĩa trên HTTPS → thuộc lớp TLS reverse-proxy, xem deploy/README-tls-reverse-proxy.md).
"""
from __future__ import annotations

from typing import Iterable, Optional

_DEFAULT_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
)


class SecurityHeadersMiddleware:
    """Thêm security headers vào MỌI response. Không đè header đã có (idempotent theo tên, case-insensitive)."""

    def __init__(self, app, headers: Optional[Iterable[tuple[str, str]]] = None):
        self._app = app
        self._headers = tuple(headers) if headers is not None else _DEFAULT_HEADERS

    def __call__(self, environ, start_response):
        def _start(status, response_headers, exc_info=None):
            existing = {h.lower() for h, _ in response_headers}
            for name, value in self._headers:
                if name.lower() not in existing:      # tôn trọng header app đã đặt (không đè)
                    response_headers.append((name, value))
            return start_response(status, response_headers, exc_info)

        return self._app(environ, _start)
