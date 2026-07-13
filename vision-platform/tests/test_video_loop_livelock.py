"""Săn bug V1 (#349): VideoFileFrameSource(loop=True) trên video RỖNG/không-seek-được → LIVELOCK trong runner.

Runner: EOF trên source is_finite=False → `continue` (giả định EOF transient). Nhưng loop-video bất-khả-loop
trả EOF lặp lại → busy-loop vô hạn (peg CPU + treo _run_from_config tuần tự). Root fix: video không loop được
= THỰC CHẤT finite → source báo is_finite=True sau khi loop thất bại → runner break. Test deterministic (fake
capture, KHÔNG cần file/codec thật). Safety-stop chống treo test nếu bug còn.
"""
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.composite_sink import CompositeSink


class _UnloopableCapture:
    """isOpened=True nhưng read() LUÔN (False, None) + set() không tác dụng — video rỗng/không-seek-được."""
    def isOpened(self):
        return True

    def read(self):
        return (False, None)

    def set(self, *_a):
        return False          # seek KHÔNG có tác dụng (một số codec/container)

    def release(self):
        pass


def test_loop_video_that_cannot_loop_does_not_livelock():
    src = VideoFileFrameSource("empty.mp4", capture_factory=lambda _p: _UnloopableCapture(), loop=True)
    runner = PipelineRunner(src, SyncLinearExecutor([]), CompositeSink([]))
    calls = {"n": 0}

    def safety_stop():
        calls["n"] += 1
        return calls["n"] > 50   # lưới an toàn: nếu LIVELOCK thì dừng ở 50 (test không treo vô hạn)

    stats = runner.run(should_stop=safety_stop)

    assert stats.frames_read == 0
    # Fixed: source thành finite sau khi loop thất bại → runner break NGAY (eof nhỏ).
    # Buggy: eof tăng tới lưới an toàn (~50) = LIVELOCK.
    assert stats.eof <= 2, f"LIVELOCK: EOF lặp {stats.eof} lần — loop-video bất-khả KHÔNG thành finite"


def test_loop_video_still_loops_when_seekable():
    """Regression: video HỢP LỆ + loop=True vẫn loop (không bị fix làm thành finite oan)."""
    class _Loopable:
        def __init__(self):
            self.pos = 0
        def isOpened(self):
            return True
        def read(self):
            # 2 frame rồi hết; sau seek(pos=0) đọc lại được.
            if self.pos < 2:
                self.pos += 1
                import numpy as np
                return (True, np.zeros((4, 4, 3), np.uint8))
            return (False, None)
        def set(self, *_a):
            self.pos = 0          # seek THÀNH CÔNG
            return True
        def release(self):
            pass

    src = VideoFileFrameSource("ok.mp4", capture_factory=lambda _p: _Loopable(), loop=True)
    assert src.is_finite is False
    src.setup()
    try:
        # đọc 5 frame liên tục (2 + loop + 2 + loop...) → luôn có data, KHÔNG EOF (loop thật hoạt động)
        from vision_platform.kernel.read_result import ReadStatus
        got = [src.read().status for _ in range(5)]
        assert all(s == ReadStatus.FRAME for s in got), got
        assert src.is_finite is False   # vẫn non-finite (loop OK, không bị flip oan)
    finally:
        src.teardown()
