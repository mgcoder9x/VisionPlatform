"""Spec pipeline-observability — test XÁC ĐỊNH (clock TIÊM + observer spy), KHÔNG GPU.

Phủ Correctness Properties:
- P1 emit định kỳ (emit_every_n) · P2 snapshot cuối luôn phát (kể cả should_stop / thân raise)
- P3 số học + per-camera (skip_rate/source_id) · P4 isolation lỗi observer · P5 backward-compat
- P7 emit khi camera MẤT-KẾT-NỐI (no-data) — fix Lỗ-review-A (mù-lúc-outage).
"""
import numpy as np
import pytest

from vision_platform.kernel.read_result import ReadResult, ReadStatus
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.composite_sink import CompositeSink
from vision_platform.runtime.base_stage import BaseStage
from vision_platform.runtime.stages.motion_gate_stage import MotionGateStage
from vision_platform.runtime.observers import CollectingObserver, NoopObserver, MetricsObserver
from vision_platform.runtime.observability import InMemoryMetrics


# ============ test doubles ============

class _DataSource:
    """Yield N frame FRAME (val = i%256 → khung liên tiếp chênh 1/pixel → 'tĩnh' cho motion-gate) rồi EOF."""
    def __init__(self, n, source_id="cam0"):
        self._n = n
        self.source_id = source_id
        self.is_finite = True
        self._i = 0

    def setup(self): self._i = 0
    def teardown(self): pass

    def read(self, timeout_ms=100):
        if self._i < self._n:
            f = np.full((8, 8, 3), self._i % 256, dtype=np.uint8)
            self._i += 1
            return ReadResult(status=ReadStatus.FRAME, data=f)
        return ReadResult(status=ReadStatus.EOF)


class _OutageSource:
    """LUÔN trả TIMEOUT (no-data) — mô phỏng camera mất kết nối. is_finite=False (không EOF-break)."""
    def __init__(self, source_id="cam0"):
        self.source_id = source_id
        self.is_finite = False

    def setup(self): pass
    def teardown(self): pass

    def read(self, timeout_ms=100):
        return ReadResult(status=ReadStatus.TIMEOUT)


class _PassStage(BaseStage):
    def __init__(self): super().__init__("pass")
    def _do_process(self, packet): return packet


class _RaisingObserver:
    def on_snapshot(self, snapshot): raise RuntimeError("boom observer")


def _clock_stepper(step_ns):
    """Clock TIÊM: mỗi lần gọi tăng cố định step_ns → dt xác định, không phụ thuộc thời gian thực."""
    t = {"v": 0}
    def clock():
        t["v"] += step_ns
        return t["v"]
    return clock


def _runner(source, stages, **kw):
    return PipelineRunner(source, SyncLinearExecutor(stages), CompositeSink([]), **kw)


# ============ P1: emit định kỳ ============

def test_emits_every_n_plus_final():
    obs = CollectingObserver()
    r = _runner(_DataSource(10), [_PassStage()], observer=obs, emit_every_n=3)
    stats = r.run(max_frames=10)
    periodic = [s for s in obs.snapshots if not s.is_final]
    finals = [s for s in obs.snapshots if s.is_final]
    assert [s.frames_read for s in periodic] == [3, 6, 9]     # emit tại bội số 3, KHÔNG đợi kết thúc
    assert len(finals) == 1 and finals[0].frames_read == 10   # đúng 1 snapshot cuối
    assert stats.frames_read == 10 and stats.processed == 10


def test_no_periodic_emit_when_disabled():
    obs = CollectingObserver()
    _runner(_DataSource(5), [_PassStage()], observer=obs).run(max_frames=5)  # emit_every_n=0, interval=0
    assert [s.is_final for s in obs.snapshots] == [True]       # CHỈ snapshot cuối


# ============ P2: snapshot cuối LUÔN phát ============

def test_final_emitted_on_should_stop():
    obs = CollectingObserver()
    stop = {"n": 0}
    def should_stop():
        stop["n"] += 1
        return stop["n"] > 3
    _runner(_DataSource(100), [_PassStage()], observer=obs).run(should_stop=should_stop)
    assert sum(1 for s in obs.snapshots if s.is_final) == 1


def test_final_emitted_even_when_body_raises():
    obs = CollectingObserver()

    class _BoomSource(_DataSource):
        def read(self, timeout_ms=100):
            if self._i >= 2:
                raise RuntimeError("boom source")
            return super().read(timeout_ms)

    r = _runner(_BoomSource(10), [_PassStage()], observer=obs)
    with pytest.raises(RuntimeError):
        r.run(max_frames=10)
    assert any(s.is_final for s in obs.snapshots)              # cuối vẫn phát dù thân raise (finally)


# ============ P3: số học + per-camera ============

def test_skip_rate_and_source_id_exact():
    obs = CollectingObserver()
    r = _runner(_DataSource(5, source_id="camX"), [MotionGateStage()], observer=obs, emit_every_n=5)
    stats = r.run(max_frames=5)
    # frame0 pass; frame1..4 chênh 1/pixel (<25) → SKIP → processed=1, skipped=4
    assert stats.processed == 1 and stats.skipped == 4
    final = [s for s in obs.snapshots if s.is_final][0]
    assert final.source_id == "camX"
    assert final.frames_read == 5 and final.skipped == 4
    assert abs(final.skip_rate - 4 / 5) < 1e-9                 # skip_rate = skipped/frames_read (clock-independent)


def test_fps_interval_positive_when_frames_flow():
    obs = CollectingObserver()
    r = _runner(_DataSource(6), [_PassStage()], observer=obs,
                emit_every_n=3, clock_ns=_clock_stepper(10_000_000))  # 10ms/call
    r.run(max_frames=6)
    periodic = [s for s in obs.snapshots if not s.is_final]
    assert periodic and all(s.frames_per_second > 0.0 for s in periodic)  # có frame chảy → throughput > 0


# ============ P7: emit khi MẤT-KẾT-NỐI (fix Lỗ-review-A) ============

def test_emits_during_outage_no_data():
    obs = CollectingObserver()
    # clock nhảy 1s/call → interval 0.5s luôn thoả ở đầu loop dù KHÔNG có frame.
    r = _runner(_OutageSource(), [_PassStage()], observer=obs,
                emit_interval_s=0.5, clock_ns=_clock_stepper(1_000_000_000))
    def should_stop():
        return len(obs.snapshots) >= 3
    r.run(should_stop=should_stop)
    non_final = [s for s in obs.snapshots if not s.is_final]
    assert len(non_final) >= 2                        # PHÁT snapshot DÙ không có frame (thấy sự cố live)
    assert all(s.frames_read == 0 for s in non_final) # frames_read đứng yên (camera chết)
    assert all(s.frames_per_second == 0.0 for s in non_final)  # idle → interval-fps = 0 (không che sự cố)


# ============ P4: isolation lỗi observer ============

def test_observer_error_isolated_from_pipeline():
    base = _runner(_DataSource(5), [_PassStage()]).run(max_frames=5)   # baseline no-op
    r = _runner(_DataSource(5), [_PassStage()], observer=_RaisingObserver(), emit_every_n=2)
    stats = r.run(max_frames=5)
    assert stats == base                              # RunStats Y HỆT dù observer raise mỗi lần
    assert r._observer_errors > 0                     # lỗi observer bị đếm (không nuốt im lặng)


# ============ P5: backward-compat ============

def test_backward_compat_no_observer_vs_noop():
    a = _runner(_DataSource(7), [MotionGateStage()]).run(max_frames=7)
    b = _runner(_DataSource(7), [MotionGateStage()], observer=NoopObserver()).run(max_frames=7)
    assert a == b                                     # default (no-op) không đổi RunStats/hành vi


# ============ MetricsObserver integration ============

def test_metrics_observer_updates_gauges():
    m = InMemoryMetrics()
    r = _runner(_DataSource(5, source_id="cam9"), [MotionGateStage()],
                observer=MetricsObserver(m), emit_every_n=5)
    r.run(max_frames=5)
    assert m.get_gauge("pipeline_frames_read", source="cam9") == 5.0
    assert m.get_gauge("pipeline_skip_rate", source="cam9") is not None
    assert m.get_gauge("pipeline_fps", source="cam9") is not None


# ============ CLI smoke (wire vào vision_slice_app) ============

def test_cli_observe_smoke():
    from vision_platform.profiles.vision_slice_app import main
    rc = main(["--source", "fake", "--frames", "6", "--observe", "--observe-every", "2"])
    assert rc == 0
