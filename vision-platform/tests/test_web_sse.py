"""Test SSE transport `/events` (spec overlay-sse-transport #448) — header WSGI-safe + khung SSE hợp lệ.

BỐI CẢNH (fix gốc "cực nhiều lỗi" browser K-119): overlay đổi transport poll→SSE server-push → khi mất kết
nối, trình duyệt chỉ log ~1 lỗi + `EventSource` tự reconnect (thay vì flood mỗi fetch `/overlay` hỏng).
Property 2 (giảm lỗi outage) + freshness + fallback đã VERIFY bằng browser MCP dưới waitress (LOG #454).
Test này = regression THUẦN (không cần server thật):
- Route `/events`: `text/event-stream` + `X-Accel-Buffering:no` + **KHÔNG** header `Connection`
  (hop-by-hop, PEP 3333 CẤM trong WSGI app — bug đã lộ dưới waitress `AssertionError`; guard chống tái diễn).
- Generator `_sse_overlay_stream`: yield `retry:` trước, rồi khung `event: overlay\ndata: {json}\n\n` parse
  được = CÙNG dict `project_overlay` mà `/overlay` trả (Property 1 freshness, không đổi schema).
"""
from __future__ import annotations

import json

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome
from vision_platform.runtime.overlay_state_store import OverlayStateStore
from vision_platform.profiles import vision_web_app as web

MS = 1_000_000


def _nbox(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _store_with_box():
    s = OverlayStateStore("proc-1", 1, OverlayConfig(minHits=1, displayLeaseMs=500, ghostSlaMs=1500),
                          clock=lambda: 0)
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.2), 0.87)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    return s


def test_events_route_headers_wsgi_safe(monkeypatch):
    """Route `/events`: streaming header đúng + KHÔNG set `Connection` (hop-by-hop → waitress reject PEP 3333)."""
    monkeypatch.setattr(web, "_store", _store_with_box())
    with web.app.test_request_context("/events"):
        resp = web.events()
    assert resp.mimetype == "text/event-stream"
    assert resp.headers.get("X-Accel-Buffering") == "no"
    assert "no-cache" in resp.headers.get("Cache-Control", "")
    # BUG GUARD: 'Connection' là hop-by-hop → WSGI app KHÔNG được set (waitress raise AssertionError nếu có).
    assert "Connection" not in resp.headers


def test_sse_stream_emits_retry_then_overlay_event(monkeypatch):
    """Generator: `retry:` trước, rồi khung `event: overlay\\ndata: {json}\\n\\n` parse được = project_overlay."""
    monkeypatch.setattr(web, "_store", _store_with_box())
    monkeypatch.setattr(web, "_cfg", OverlayConfig(minHits=1, displayLeaseMs=500, ghostSlaMs=1500))
    monkeypatch.setattr(web.time, "monotonic_ns", lambda: 100 * MS)   # box (clock=0, lease 500ms) còn tươi
    gen = web._sse_overlay_stream()
    try:
        first = next(gen)
        assert first.startswith("retry:")
        frame = next(gen)          # snapshot có box + rev != last_rev(None) → phát event ngay (trước sleep)
    finally:
        gen.close()
    assert frame.startswith("event: overlay\ndata: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("event: overlay\ndata: "):].strip())
    assert payload["schemaVersion"] == 1
    assert payload["processEpoch"] == "proc-1"
    assert "eventRevision" in payload
    assert payload["display"]["boxes"][0]["label"] == "person"   # box chảy qua SSE (Property 1 freshness)
