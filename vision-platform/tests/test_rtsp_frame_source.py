"""Test RtspFrameSource — logic reconnect deterministic bằng capture GIẢ (DI, KHÔNG cần camera thật)."""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.kernel.read_result import ReadStatus
from vision_platform.adapters.rtsp_frame_source import RtspFrameSource, mask_rtsp


class FakeCapture:
    """Giả cv2.VideoCapture: opened cố định + danh sách kết quả read (ok, frame)."""
    def __init__(self, opened=True, reads=None):
        self._opened = opened
        self._reads = list(reads or [])
        self.released = False

    def isOpened(self):
        return self._opened and not self.released

    def read(self):
        if self._reads:
            return self._reads.pop(0)
        return (False, None)

    def release(self):
        self.released = True


def _factory(captures):
    """Factory trả lần lượt các capture đã dựng; hết → capture không mở được."""
    it = iter(captures)

    def factory(url):
        try:
            return next(it)
        except StopIteration:
            return FakeCapture(opened=False)
    return factory


_URL = "rtsp://admin:secret@10.0.0.9:554/cam"


def test_mask_rtsp_hides_password():
    assert mask_rtsp(_URL) == "rtsp://admin:***@10.0.0.9:554/cam"
    assert "secret" not in RtspFrameSource(_URL).source_id


def test_setup_required():
    src = RtspFrameSource(_URL, capture_factory=_factory([FakeCapture()]))
    with pytest.raises(RuntimeError, match="setup"):
        src.read()


def test_read_returns_frame():
    frame = np.ones((4, 4, 3), dtype=np.uint8)
    cap = FakeCapture(opened=True, reads=[(True, frame)])
    src = RtspFrameSource(_URL, capture_factory=_factory([cap]))
    src.setup()
    r = src.read()
    src.teardown()
    assert r.status == ReadStatus.FRAME
    assert r.has_data and r.data is frame


def test_reconnect_when_initial_open_fails():
    """setup mở hỏng (cap not opened) → read#1 RECONNECTING (mở lại thành công) → read#2 FRAME."""
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    bad = FakeCapture(opened=False)
    good = FakeCapture(opened=True, reads=[(True, frame)])
    src = RtspFrameSource(_URL, capture_factory=_factory([bad, good]))
    src.setup()                       # dùng `bad` → cap None
    r1 = src.read()                   # reconnect → good → RECONNECTING
    r2 = src.read()                   # good.read → FRAME
    src.teardown()
    assert r1.status == ReadStatus.RECONNECTING
    assert r2.status == ReadStatus.FRAME


def test_drop_midstream_triggers_reconnect():
    """Đang chạy thì rớt (read trả False) → RECONNECTING + release → mở lại → FRAME lại."""
    f1 = np.ones((2, 2, 3), dtype=np.uint8)
    f2 = np.full((2, 2, 3), 2, dtype=np.uint8)
    cap1 = FakeCapture(opened=True, reads=[(True, f1), (False, None)])   # frame rồi rớt
    cap2 = FakeCapture(opened=True, reads=[(True, f2)])
    src = RtspFrameSource(_URL, capture_factory=_factory([cap1, cap2]))
    src.setup()
    assert src.read().status == ReadStatus.FRAME          # f1
    assert src.read().status == ReadStatus.RECONNECTING   # rớt → release cap1
    assert cap1.released
    assert src.read().status == ReadStatus.RECONNECTING   # mở lại cap2
    assert src.read().status == ReadStatus.FRAME          # f2
    src.teardown()


def test_max_reconnect_gives_error():
    """Mở mãi không được + vượt max_reconnect → ERROR (không thử vô ích)."""
    src = RtspFrameSource(_URL, capture_factory=_factory([]), max_reconnect=2)  # factory luôn not-opened
    src.setup()
    assert src.read().status == ReadStatus.RECONNECTING   # attempt 1
    assert src.read().status == ReadStatus.RECONNECTING   # attempt 2
    r = src.read()                                        # vượt hạn
    src.teardown()
    assert r.status == ReadStatus.ERROR
    assert isinstance(r.error, RuntimeError)


def test_is_finite_false_and_context_manager():
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    cap = FakeCapture(opened=True, reads=[(True, frame)])
    src = RtspFrameSource(_URL, capture_factory=_factory([cap]))
    assert src.is_finite is False
    with src as s:
        assert s.read().status == ReadStatus.FRAME
    assert cap.released                                    # __exit__ → teardown → release
