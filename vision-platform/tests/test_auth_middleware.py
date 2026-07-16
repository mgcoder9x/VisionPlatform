"""Spec web-production-hardening Wave 2 — test BasicAuthMiddleware + make_env_verifier (P2, P3, P5).

Test bằng WSGI env giả (dict) + start_response bắt status — KHÔNG cần Flask/server thật.
"""
import base64

import pytest

from vision_platform.adapters.auth_middleware import BasicAuthMiddleware, make_env_verifier


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("ascii")


def _env(path="/overlay", auth=None):
    env = {"PATH_INFO": path, "REQUEST_METHOD": "GET"}
    if auth is not None:
        env["HTTP_AUTHORIZATION"] = auth
    return env


class _Capture:
    def __init__(self):
        self.status = None
        self.headers = None

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


def _downstream():
    """App WSGI giả — ghi lại path được gọi + trả 200."""
    calls = []

    def app(environ, start_response):
        calls.append(environ.get("PATH_INFO"))
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    app.calls = calls
    return app


_VERIFY = lambda u, p: u == "admin" and p == "s3cret"  # noqa: E731 (test verifier)


# --- P2: thiếu credential → 401 + WWW-Authenticate, downstream KHÔNG chạy ---
def test_missing_credential_401():
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY)
    cap = _Capture()
    body = mw(_env(auth=None), cap)
    assert cap.status == "401 Unauthorized"
    assert any(h.lower() == "www-authenticate" for h, _ in cap.headers)
    assert app.calls == []
    assert b"401" in b"".join(body)


# --- P2: sai credential → 401 ---
def test_wrong_credential_401():
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY)
    cap = _Capture()
    mw(_env(auth=_basic("admin", "WRONG")), cap)
    assert cap.status == "401 Unauthorized"
    assert app.calls == []


# --- P2: đúng credential → downstream chạy (200) ---
def test_correct_credential_passes():
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY)
    cap = _Capture()
    mw(_env(path="/stream", auth=_basic("admin", "s3cret")), cap)
    assert cap.status == "200 OK"
    assert app.calls == ["/stream"]


# --- P3: MỌI route nhạy cảm thiếu credential → 401 (không sót /stream) ---
@pytest.mark.parametrize("path", ["/", "/stream", "/overlay", "/boxes", "/stats"])
def test_all_routes_protected(path):
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY)
    cap = _Capture()
    mw(_env(path=path, auth=None), cap)
    assert cap.status == "401 Unauthorized"
    assert app.calls == []


# --- P3: path miễn (health-check) qua KHÔNG cần credential ---
def test_exempt_path_bypasses_auth():
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY, exempt_paths=("/healthz",))
    cap = _Capture()
    mw(_env(path="/healthz", auth=None), cap)
    assert cap.status == "200 OK"
    assert app.calls == ["/healthz"]


# --- header sai định dạng → 401 (Basic hỏng / base64 hỏng / thiếu ':') ---
@pytest.mark.parametrize("bad", ["Bearer xyz", "Basic !!!notbase64", "Basic " + base64.b64encode(b"nocolon").decode()])
def test_malformed_header_401(bad):
    app = _downstream()
    mw = BasicAuthMiddleware(app, _VERIFY)
    cap = _Capture()
    mw(_env(auth=bad), cap)
    assert cap.status == "401 Unauthorized"
    assert app.calls == []


# --- P5: make_env_verifier đọc env + so sánh; thiếu env → None ---
def test_make_env_verifier_reads_env(monkeypatch):
    monkeypatch.setenv("VP_WEB_USER", "admin")
    monkeypatch.setenv("VP_WEB_PASS", "s3cret")
    verify = make_env_verifier()
    assert verify is not None
    assert verify("admin", "s3cret") is True
    assert verify("admin", "nope") is False
    assert verify("root", "s3cret") is False


def test_make_env_verifier_none_when_unset(monkeypatch):
    monkeypatch.delenv("VP_WEB_USER", raising=False)
    monkeypatch.delenv("VP_WEB_PASS", raising=False)
    assert make_env_verifier() is None
    # chỉ đặt 1 nửa cũng None (không đủ credential)
    monkeypatch.setenv("VP_WEB_USER", "admin")
    assert make_env_verifier() is None
