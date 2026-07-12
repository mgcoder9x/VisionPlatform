"""R1 (review săn bug, #346): `_default_cv2_capture` phải set `CAP_PROP_OPEN_TIMEOUT_MSEC` TRƯỚC khi open.

Bản chất: `cv2.VideoCapture(url, ...)` MỞ NGAY trong constructor → set property SAU đó KHÔNG tác động cái open
đã hoàn tất → OPEN_TIMEOUT vô hiệu (host chết → treo lâu). Fix = construct RỖNG → set props → `cap.open(url)`.

Test bằng fake `cv2` ghi THỨ TỰ gọi (deterministic, KHÔNG cần camera/cv2 thật). RED trước fix (code cũ
truyền url vào constructor → không có `cap.open()` → contract sai); GREEN sau fix.
"""
from __future__ import annotations

import sys
import types

from vision_platform.adapters import rtsp_frame_source as R


class _FakeCap:
    def __init__(self):
        self.calls: list[tuple] = []

    def set(self, prop, val):
        self.calls.append(("set", prop, val))
        return True

    def open(self, url, api):
        self.calls.append(("open", url, api))
        return True

    def isOpened(self):
        return True


def _fake_cv2(cap):
    m = types.ModuleType("cv2")
    m.CAP_FFMPEG = 1900
    m.CAP_PROP_OPEN_TIMEOUT_MSEC = 53
    m.CAP_PROP_READ_TIMEOUT_MSEC = 54
    m.CAP_PROP_BUFFERSIZE = 38
    m.VideoCapture = lambda *a, **k: cap    # construct → luôn trả cùng instance để soi call order
    return m


def test_open_timeout_set_before_open(monkeypatch):
    cap = _FakeCap()
    monkeypatch.setitem(sys.modules, "cv2", _fake_cv2(cap))

    result = R._default_cv2_capture("rtsp://user:pw@host/stream")

    assert result is cap
    kinds = [c[0] for c in cap.calls]
    # open phải là thao tác CUỐI (mọi cấu hình timeout/buffer đã set TRƯỚC).
    assert "open" in kinds, f"code không gọi cap.open() rõ ràng (truyền url vào constructor?) — R1 bug: {cap.calls}"
    assert kinds[-1] == "open", f"open KHÔNG ở cuối (property set sau open = vô hiệu): {cap.calls}"

    set_open_idx = next(i for i, c in enumerate(cap.calls)
                        if c[0] == "set" and c[1] == 53)   # CAP_PROP_OPEN_TIMEOUT_MSEC
    open_idx = next(i for i, c in enumerate(cap.calls) if c[0] == "open")
    assert set_open_idx < open_idx, f"OPEN_TIMEOUT phải set TRƯỚC open: {cap.calls}"
    # open dùng đúng URL + backend FFMPEG.
    open_call = cap.calls[open_idx]
    assert open_call[1] == "rtsp://user:pw@host/stream"
    assert open_call[2] == 1900   # CAP_FFMPEG
