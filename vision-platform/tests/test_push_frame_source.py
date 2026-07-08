"""Task 2.2 — PushFrameSource (nguồn đẩy nhịp cố định, R7.1/R7.2).

- Phát đúng M frame FRAME + 1 EOF (interval_s=0).
- interval_s>0 + mô phỏng đồng hồ tiêm (time_fn) → nhịp KHÔNG phụ thuộc tốc độ gọi read():
  chưa tới hạn → TIMEOUT; tới hạn → FRAME.
- Frame value tăng dần (deterministic, dùng kiểm recency).
"""
from vision_platform.adapters.push_frame_source import PushFrameSource
from vision_platform.kernel.read_result import ReadStatus


def test_emits_exactly_max_frames_then_eof():
    src = PushFrameSource(width=8, height=8, max_frames=3, interval_s=0.0)
    src.setup()
    try:
        statuses = [src.read().status for _ in range(4)]
    finally:
        src.teardown()
    assert statuses == [
        ReadStatus.FRAME,
        ReadStatus.FRAME,
        ReadStatus.FRAME,
        ReadStatus.EOF,
    ]


def test_frame_value_increases_deterministic():
    src = PushFrameSource(width=4, height=4, max_frames=3, interval_s=0.0)
    src.setup()
    try:
        f0 = src.read().data
        f1 = src.read().data
        f2 = src.read().data
    finally:
        src.teardown()
    # mọi pixel = chỉ số frame → value tăng dần 0,1,2
    assert int(f0.flat[0]) == 0
    assert int(f1.flat[0]) == 1
    assert int(f2.flat[0]) == 2


def test_pacing_independent_of_call_rate():
    """interval_s>0: nhịp theo đồng hồ tiêm, không theo số lần gọi read()."""
    clock = {"t": 0.0}
    src = PushFrameSource(
        width=4, height=4, max_frames=2, interval_s=1.0,
        time_fn=lambda: clock["t"],
    )
    src.setup()  # _next_emit = 0.0
    try:
        # t=0: tới hạn → FRAME (frame 0)
        r = src.read()
        assert r.status == ReadStatus.FRAME
        # gọi nhiều lần khi đồng hồ chưa nhích → luôn TIMEOUT (nhịp độc lập tốc độ gọi)
        clock["t"] = 0.5
        assert src.read().status == ReadStatus.TIMEOUT
        assert src.read().status == ReadStatus.TIMEOUT
        # t=1.0: tới hạn kế → FRAME (frame 1)
        clock["t"] = 1.0
        assert src.read().status == ReadStatus.FRAME
        # đủ max_frames → EOF
        assert src.read().status == ReadStatus.EOF
    finally:
        src.teardown()
