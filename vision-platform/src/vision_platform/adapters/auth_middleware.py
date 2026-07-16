"""adapters/auth_middleware.py — WSGI middleware HTTP Basic Auth (spec web-production-hardening Wave 2).

Bọc NGOÀI WSGI app → phủ MỌI route (kể cả `/stream` MJPEG) TRƯỚC khi vào Flask → không sót đường nào. Leaf adapter
(kiến trúc §4): chỉ stdlib + `verify_credential` TIÊM (thuần) → KHÔNG import runtime/application/profiles; test được
bằng WSGI env giả (không cần Flask/pipeline). Credential đọc từ env (`make_env_verifier`), so sánh HẰNG-THỜI-GIAN
(`hmac.compare_digest`), KHÔNG hard-code trong code/log.

An toàn (trung thực): Basic Auth trần = base64 (KHÔNG mã hoá) → chỉ an toàn SAU TLS (reverse-proxy = Wave 3).
Secure-default bind loopback (wire ở profiles) là lớp giảm-thiểu cho tới khi có TLS.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import os
from typing import Callable, Iterable, Optional

VerifyCredential = Callable[[str, str], bool]


class BasicAuthMiddleware:
    """WSGI middleware: 401 nếu thiếu/sai Basic credential; qua nếu đúng hoặc path được miễn (health-check)."""

    def __init__(self, app, verify_credential: VerifyCredential, *,
                 realm: str = "VisionPlatform", exempt_paths: Iterable[str] = ("/healthz",)):
        self._app = app
        self._verify = verify_credential
        self._realm = realm
        self._exempt = frozenset(exempt_paths)

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path in self._exempt:                       # health-check: cho reverse-proxy/monitor kiểm sống
            return self._app(environ, start_response)
        creds = _parse_basic(environ.get("HTTP_AUTHORIZATION"))
        if creds is not None and self._verify(creds[0], creds[1]):
            return self._app(environ, start_response)  # hợp lệ → vào app thật
        return self._unauthorized(start_response)      # thiếu/sai → 401 (không phân biệt user-sai/pass-sai)

    def _unauthorized(self, start_response):
        body = b"401 Unauthorized\n"
        start_response("401 Unauthorized", [
            ("WWW-Authenticate", f'Basic realm="{self._realm}", charset="UTF-8"'),
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]


def _parse_basic(header: Optional[str]) -> Optional[tuple[str, str]]:
    """'Basic base64(user:pass)' → (user, pass); None nếu thiếu/sai định dạng/base64 hỏng/không có ':'."""
    if not header or not header.startswith("Basic "):
        return None
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if ":" not in raw:
        return None
    user, _, pw = raw.partition(":")
    return user, pw


def make_env_verifier(user_var: str = "VP_WEB_USER",
                      pass_var: str = "VP_WEB_PASS") -> Optional[VerifyCredential]:
    """Dựng verify từ biến môi trường. None nếu CHƯA đặt (đủ) → profiles quyết định (loopback OK / non-loopback chặn).

    So sánh hằng-thời-gian cả user LẪN pass (không short-circuit → không lộ 'user có khớp không' qua thời gian).
    """
    expected_user = os.environ.get(user_var)
    expected_pw = os.environ.get(pass_var)
    if not expected_user or not expected_pw:
        return None
    eu = expected_user.encode("utf-8")
    ep = expected_pw.encode("utf-8")

    def verify(user: str, pw: str) -> bool:
        ok_u = hmac.compare_digest(user.encode("utf-8"), eu)
        ok_p = hmac.compare_digest(pw.encode("utf-8"), ep)
        return bool(ok_u & ok_p)   # bitwise & → cả hai LUÔN evaluate (constant-time, không short-circuit)

    return verify
