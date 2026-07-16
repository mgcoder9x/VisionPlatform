"""Spec web-production-hardening Wave 3 — test SecurityHeadersMiddleware (WSGI env giả)."""
from vision_platform.adapters.security_headers import SecurityHeadersMiddleware


class _Capture:
    def __init__(self):
        self.status = None
        self.headers = None

    def __call__(self, status, headers, exc_info=None):
        self.status = status
        self.headers = headers


def _app_factory(status="200 OK", headers=None):
    hdrs = headers if headers is not None else [("Content-Type", "text/plain")]

    def app(environ, start_response):
        start_response(status, list(hdrs))
        return [b"body"]

    return app


def _hdr_dict(pairs):
    return {h.lower(): v for h, v in pairs}


def test_adds_security_headers():
    mw = SecurityHeadersMiddleware(_app_factory())
    cap = _Capture()
    mw({"PATH_INFO": "/"}, cap)
    d = _hdr_dict(cap.headers)
    assert d["x-content-type-options"] == "nosniff"
    assert d["x-frame-options"] == "DENY"
    assert d["referrer-policy"] == "no-referrer"
    assert d["content-type"] == "text/plain"   # header gốc giữ nguyên


def test_headers_present_on_401():
    # response lỗi (vd 401 từ auth ở tầng trong) vẫn phải có security headers
    mw = SecurityHeadersMiddleware(_app_factory(status="401 Unauthorized",
                                                headers=[("WWW-Authenticate", "Basic")]))
    cap = _Capture()
    mw({"PATH_INFO": "/overlay"}, cap)
    assert cap.status == "401 Unauthorized"
    d = _hdr_dict(cap.headers)
    assert d["x-frame-options"] == "DENY"
    assert d["www-authenticate"] == "Basic"    # header của tầng trong giữ nguyên


def test_does_not_override_existing():
    # nếu app đã đặt X-Frame-Options khác → KHÔNG đè
    mw = SecurityHeadersMiddleware(_app_factory(headers=[("X-Frame-Options", "SAMEORIGIN")]))
    cap = _Capture()
    mw({"PATH_INFO": "/"}, cap)
    xfo = [v for h, v in cap.headers if h.lower() == "x-frame-options"]
    assert xfo == ["SAMEORIGIN"]               # đúng 1, không nhân đôi
