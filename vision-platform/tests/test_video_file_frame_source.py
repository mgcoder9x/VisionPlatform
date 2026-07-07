"""Test VideoFileFrameSource — logic bằng capture GIẢ (DI) + 1 round-trip video thật (guard cv2)."""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.kernel.read_result import ReadStatus
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource


class FakeCap:
    def __init__(self, opened=True, reads=None):
        self._opened = opened
        self._initial = list(reads or [])
        self._reads = list(self._initial)
        self.released = False

    def isOpened(self):
        return self._opened and not self.released

    def read(self):
        return self._reads.pop(0) if self._reads else (False, None)

    def set(self, prop, val):        # tua về đầu (loop) → nạp lại
        self._reads = list(self._initial)
        return True

    def release(self):
        self.released = True


def _factory(cap):
    return lambda path: cap


def test_reads_frames_then_eof():
    f = np.ones((4, 4, 3), dtype=np.uint8)
    cap = FakeCap(opened=True, reads=[(True, f), (True, f), (True, f)])
    src = VideoFileFrameSource("x.mp4", capture_factory=_factory(cap))
    src.setup()
    n = 0
    while True:
        r = src.read()
        if r.status == ReadStatus.EOF:
            break
        assert r.status == ReadStatus.FRAME
        n += 1
    src.teardown()
    assert n == 3
    assert cap.released


def test_missing_file_raises():
    src = VideoFileFrameSource("nope.mp4", capture_factory=_factory(FakeCap(opened=False)))
    with pytest.raises(RuntimeError, match="Không mở được"):
        src.setup()


def test_setup_required():
    src = VideoFileFrameSource("x.mp4", capture_factory=_factory(FakeCap()))
    with pytest.raises(RuntimeError, match="setup"):
        src.read()


def test_loop_reads_again():
    f = np.ones((2, 2, 3), dtype=np.uint8)
    cap = FakeCap(opened=True, reads=[(True, f)])
    src = VideoFileFrameSource("x.mp4", capture_factory=_factory(cap), loop=True)
    src.setup()
    assert src.read().status == ReadStatus.FRAME     # frame1
    assert src.read().status == ReadStatus.FRAME     # hết → loop (set nạp lại) → frame1 lần nữa
    src.teardown()


def test_is_finite():
    assert VideoFileFrameSource("x", capture_factory=_factory(FakeCap())).is_finite is True
    assert VideoFileFrameSource("x", capture_factory=_factory(FakeCap()), loop=True).is_finite is False


def test_real_video_round_trip(tmp_path):
    """Ghi video nhỏ bằng cv2 rồi đọc lại qua adapter (mặc định cv2). Skip nếu codec không ghi được."""
    cv2 = pytest.importorskip("cv2", reason="cần opencv-python (.[cv2])")
    path = str(tmp_path / "clip.avi")
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    wr = cv2.VideoWriter(path, fourcc, 10.0, (32, 32))
    if not wr.isOpened():
        pytest.skip("codec MJPG không khả dụng để ghi video test")
    for _ in range(5):
        wr.write(np.full((32, 32, 3), 128, dtype=np.uint8))
    wr.release()

    src = VideoFileFrameSource(path)
    src.setup()
    n = 0
    while True:
        r = src.read()
        if r.status == ReadStatus.EOF:
            break
        assert r.status == ReadStatus.FRAME and r.data.shape == (32, 32, 3)
        n += 1
        if n > 20:
            break            # an toàn chống vòng vô hạn
    src.teardown()
    assert n >= 1            # đọc được ít nhất 1 frame rồi tới EOF
