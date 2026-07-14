"""WebcamFrameSource — nguồn webcam cục bộ theo index (DI capture, test KHÔNG cần webcam thật)."""
from __future__ import annotations

import numpy as np

from vision_platform.adapters.webcam_frame_source import WebcamFrameSource
from vision_platform.kernel.read_result import ReadStatus


class _FakeCap:
    """Giả cv2.VideoCapture: kịch bản đọc điều khiển được."""
    def __init__(self, frames, opened=True):
        self._frames = list(frames)   # mỗi phần tử: np.ndarray (ok) hoặc None (đọc lỗi)
        self._opened = opened
        self.released = 0

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        f = self._frames.pop(0)
        return (f is not None), f

    def release(self):
        self.released += 1
        self._opened = False


def _frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_read_returns_frame_when_capture_ok():
    cap = _FakeCap([_frame(), _frame()])
    src = WebcamFrameSource(0, capture_factory=lambda idx: cap)
    src.setup()
    r = src.read()
    assert r.status == ReadStatus.FRAME
    assert r.data is not None and r.data.shape == (480, 640, 3)
    src.teardown()


def test_factory_receives_index():
    seen = {}
    def factory(idx):
        seen["idx"] = idx
        return _FakeCap([_frame()])
    src = WebcamFrameSource(2, capture_factory=factory)
    src.setup()
    assert seen["idx"] == 2
    src.teardown()


def test_not_opened_returns_reconnecting():
    cap = _FakeCap([], opened=False)
    src = WebcamFrameSource(0, capture_factory=lambda idx: cap)
    src.setup()
    r = src.read()
    assert r.status == ReadStatus.RECONNECTING


def test_read_failure_self_heals_next_read():
    # Contract (mirror RtspFrameSource): đọc lỗi → release + RECONNECTING; cycle sau cap=None → MỞ LẠI +
    # RECONNECTING (chưa đọc); cycle sau nữa → đọc được → FRAME. Self-heal 2 nhịp (nhất quán RTSP).
    caps = [_FakeCap([None]), _FakeCap([_frame()])]
    src = WebcamFrameSource(0, capture_factory=lambda idx: caps.pop(0))
    src.setup()
    r1 = src.read()
    assert r1.status == ReadStatus.RECONNECTING     # đọc lỗi → release
    r2 = src.read()
    assert r2.status == ReadStatus.RECONNECTING     # cap=None → mở lại (chưa đọc cycle này)
    r3 = src.read()
    assert r3.status == ReadStatus.FRAME            # đã mở → đọc được
    src.teardown()


def test_is_finite_false_and_source_id():
    src = WebcamFrameSource(1, capture_factory=lambda idx: _FakeCap([_frame()]))
    assert src.is_finite is False
    assert src.source_id == "webcam:1"


def test_read_before_setup_raises():
    src = WebcamFrameSource(0, capture_factory=lambda idx: _FakeCap([_frame()]))
    try:
        src.read()
        assert False, "phải raise khi chưa setup"
    except RuntimeError:
        pass


def test_teardown_releases_capture():
    cap = _FakeCap([_frame()])
    src = WebcamFrameSource(0, capture_factory=lambda idx: cap)
    src.setup()
    src.teardown()
    assert cap.released >= 1
