"""Spec web-production-hardening Wave 1 — test serve_wsgi chọn server (P1, R1.1/1.2/1.3).

Không chạy server thật: tiêm module `waitress` giả vào sys.modules + app giả có .run spy → assert nhánh đúng.
"""
import sys
import types

import pytest

from vision_platform.adapters.wsgi_server import serve_wsgi


class _FakeApp:
    """WSGI app giả — ghi lại lời gọi .run (werkzeug dev-server path)."""
    def __init__(self):
        self.run_calls = []

    def run(self, **kwargs):
        self.run_calls.append(kwargs)


def _inject_fake_waitress(monkeypatch):
    """Đưa module `waitress` giả (có serve spy) vào sys.modules → import trong adapter nhặt bản giả."""
    calls = []
    mod = types.ModuleType("waitress")
    mod.serve = lambda app, **kwargs: calls.append((app, kwargs))  # noqa: E731
    monkeypatch.setitem(sys.modules, "waitress", mod)
    return calls


def _force_waitress_absent(monkeypatch):
    """sys.modules['waitress']=None → `import waitress` raise ImportError (giả lập chưa cài)."""
    monkeypatch.setitem(sys.modules, "waitress", None)


# --- server="dev": luôn dùng werkzeug app.run ---
def test_dev_mode_uses_app_run(monkeypatch):
    app = _FakeApp()
    serve_wsgi(app, "127.0.0.1", 8000, threads=4, server="dev")
    assert app.run_calls == [{"host": "127.0.0.1", "port": 8000, "threaded": True}]


# --- server="waitress": gọi waitress.serve, KHÔNG gọi app.run (P1) ---
def test_waitress_mode_calls_waitress_serve(monkeypatch):
    calls = _inject_fake_waitress(monkeypatch)
    app = _FakeApp()
    serve_wsgi(app, "0.0.0.0", 9000, threads=16, server="waitress")
    assert app.run_calls == []                       # KHÔNG rơi về dev
    assert len(calls) == 1
    served_app, kwargs = calls[0]
    assert served_app is app
    assert kwargs == {"host": "0.0.0.0", "port": 9000, "threads": 16}


# --- server="waitress" nhưng thiếu waitress → ImportError fail-fast (R1.2) ---
def test_waitress_mode_missing_raises(monkeypatch):
    _force_waitress_absent(monkeypatch)
    app = _FakeApp()
    with pytest.raises(ImportError):
        serve_wsgi(app, "127.0.0.1", 8000, server="waitress")
    assert app.run_calls == []                       # KHÔNG âm thầm rơi về dev


# --- server="auto" + waitress có → dùng waitress (P1) ---
def test_auto_uses_waitress_when_present(monkeypatch):
    calls = _inject_fake_waitress(monkeypatch)
    app = _FakeApp()
    serve_wsgi(app, "127.0.0.1", 8000, threads=8, server="auto")
    assert len(calls) == 1 and app.run_calls == []


# --- server="auto" + waitress vắng → fallback dev + CẢNH BÁO (R1.3) ---
def test_auto_fallback_dev_with_warning(monkeypatch, caplog):
    _force_waitress_absent(monkeypatch)
    app = _FakeApp()
    with caplog.at_level("WARNING"):
        serve_wsgi(app, "127.0.0.1", 8000, server="auto")
    assert app.run_calls == [{"host": "127.0.0.1", "port": 8000, "threaded": True}]
    assert any("dev-server" in r.message.lower() or "DEV-SERVER" in r.message for r in caplog.records)


# --- server không hợp lệ → ValueError ---
def test_invalid_server_raises():
    with pytest.raises(ValueError):
        serve_wsgi(_FakeApp(), "127.0.0.1", 8000, server="bogus")
