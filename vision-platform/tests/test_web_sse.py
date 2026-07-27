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


# --- Wave 2 (bulkhead, ĐO #456): vượt trần → 503 + Retry-After NGAY, KHÔNG treo (P9); release trả slot (P10) ---
def test_stream_and_events_return_503_when_admission_full(monkeypatch):
    """Đạt trần kết nối streaming → route trả 503 + Retry-After (client suy giảm: SSE→poll, ảnh→retry)."""
    from vision_platform.runtime.stream_admission import StreamAdmission

    adm = StreamAdmission(1)
    assert adm.try_acquire() is True          # slot duy nhất đã bị chiếm
    monkeypatch.setattr(web, "_admission", adm)
    monkeypatch.setattr(web, "_store", _store_with_box())

    with web.app.test_request_context("/events"):
        r_events = web.events()
    with web.app.test_request_context("/stream"):
        r_stream = web.stream()

    for r in (r_events, r_stream):
        assert r.status_code == 503
        assert r.headers.get("Retry-After") == "5"


def test_streaming_releases_slot_when_generator_closed(monkeypatch):
    """Generator streaming đóng (client rời) → slot ĐƯỢC TRẢ (nếu không, trần rò rỉ dần → treo lại)."""
    from vision_platform.runtime.stream_admission import StreamAdmission

    adm = StreamAdmission(1)
    monkeypatch.setattr(web, "_admission", adm)
    monkeypatch.setattr(web, "_store", _store_with_box())

    with web.app.test_request_context("/events"):
        resp = web.events()
    assert resp.status_code == 200 and adm.active == 1        # đã chiếm slot
    gen = resp.response
    next(iter(gen))                                          # lấy 1 chunk (retry:) rồi đóng
    resp.close()                                             # client rời → generator close → finally release
    assert adm.active == 0
    assert adm.try_acquire() is True                         # slot dùng lại được


# --- K-124 GUARD: client PHẢI dùng URL tuyệt đối `BASE=location.origin`, KHÔNG path tương đối ---
def test_client_uses_absolute_urls_not_relative_paths():
    """Mở UI bằng URL http://user:pass@host/ → `document.baseURI` GIỮ credential ⇒ path tương đối resolve thành
    URL-có-credential ⇒ MỌI `fetch()` NÉM LỖI (Fetch spec) ⇒ `/stats` + đường lui poll chết ÂM THẦM (SSE/<img>
    vẫn chạy nên trông như bình thường). `location.origin` không bao giờ chứa credential ⇒ miễn nhiễm.
    Test này chặn việc ai đó (kể cả AI) vô tình viết lại thành path tương đối."""
    page = web._PAGE
    assert "const BASE=location.origin;" in page
    for absolute in ("BASE+'/overlay'", "BASE+'/stats'", "BASE+'/events'", "BASE+'/stream?t='"):
        assert absolute in page, f"thiếu URL tuyệt đối: {absolute}"
    for relative in ("fetch('/", "new EventSource('/", "img.src='/"):
        assert relative not in page, f"còn URL tương đối (bẫy K-124): {relative}"
    assert 'src="/stream"' not in page          # <img> nạp qua reloadStream() dùng BASE


# --- Observability bulkhead: /stats phơi `streams=active/max` (phát hiện bão hoà + RÒ RỈ slot trong soak) ---
def test_stats_exposes_stream_admission_saturation(monkeypatch):
    """Tài nguyên CÓ TRẦN mà không quan sát được thì vận hành chỉ biết khi nó ĐÃ từ chối (503).
    `streams=a/b` là cách đo RÒ RỈ slot trực tiếp (a phải về 0 khi không còn viewer) — đã dùng ở churn probe #458."""
    from vision_platform.runtime.stream_admission import StreamAdmission

    adm = StreamAdmission(6)
    assert adm.try_acquire() is True and adm.try_acquire() is True
    monkeypatch.setattr(web, "_admission", adm)
    monkeypatch.setattr(web, "_store", _store_with_box())
    with web.app.test_request_context("/stats"):
        body = web.stats()
    assert "streams=2/6" in body

    adm.release()
    adm.release()
    with web.app.test_request_context("/stats"):
        body2 = web.stats()
    assert "streams=0/6" in body2          # slot trả lại → operator thấy ngay, không phải suy đoán


def test_stats_omits_streams_when_admission_absent(monkeypatch):
    """Không bật bulkhead (đường test/legacy) → KHÔNG bịa số liệu."""
    monkeypatch.setattr(web, "_admission", None)
    monkeypatch.setattr(web, "_store", _store_with_box())
    with web.app.test_request_context("/stats"):
        body = web.stats()
    assert "streams=" not in body
