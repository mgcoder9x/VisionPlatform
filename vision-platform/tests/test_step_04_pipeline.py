"""Step 04: stage + executor."""
import numpy as np
import pytest
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import (
    StageStatus, StageResult, SkipFrameSignal, ExecutionResult,
)
from vision_platform.runtime.base_stage import BaseStage
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.stages.brightness_stage import BrightnessStage
from vision_platform.runtime.stages.dark_filter_stage import DarkFilterStage


def _make_packet(value: int = 0) -> MediaPacket:
    """Frame uniform với value."""
    arr = np.full((50, 50, 3), fill_value=value, dtype=np.uint8)
    return MediaPacket(
        packet_id=f"p_{value}",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=0,
    )


# ============ Stage individual ============

def test_brightness_stage_computes_mean():
    stage = BrightnessStage()
    packet = _make_packet(value=100)
    result = stage.process(packet)
    assert result.status == StageStatus.SUCCESS
    assert result.packet.artifacts["brightness"] == pytest.approx(100.0)


def test_brightness_stage_does_not_mutate_input():
    """CoW invariant — input packet unchanged."""
    stage = BrightnessStage()
    packet = _make_packet(value=50)
    result = stage.process(packet)
    assert "brightness" not in packet.artifacts
    assert "brightness" in result.packet.artifacts


def test_dark_filter_skips_below_threshold():
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=10).with_artifact("brightness", 10.0)
    result = stage.process(packet)
    assert result.status == StageStatus.SKIPPED
    assert "too_dark" in result.skip_reason


def test_dark_filter_passes_above_threshold():
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=200).with_artifact("brightness", 200.0)
    result = stage.process(packet)
    assert result.status == StageStatus.SUCCESS


def test_dark_filter_errors_without_brightness():
    """Stage explicitly errors instead of silently passing."""
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=200)
    result = stage.process(packet)
    assert result.status == StageStatus.ERROR
    assert "brightness" in result.error_message.lower()
    assert isinstance(result.error_message, str)


def test_stage_error_does_not_retain_exception_object():
    """R5-CRITICAL-02: StageResult must NOT retain live Exception."""
    from dataclasses import fields
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=100)
    result = stage.process(packet)
    assert isinstance(result.error_type, str)
    assert isinstance(result.error_message, str)
    field_names = {f.name for f in fields(StageResult)}
    assert "error" not in field_names


# ============ Executor ============

def test_executor_runs_stages_in_order():
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    executor.setup_all()
    packet = _make_packet(value=200)
    result = executor.execute(packet)
    assert result.status == StageStatus.SUCCESS
    assert result.is_processed
    assert result.packet.artifacts["brightness"] == pytest.approx(200.0)
    executor.teardown_all()


def test_executor_stops_on_skip():
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    executor.setup_all()
    packet = _make_packet(value=10)
    result = executor.execute(packet)
    assert result.status == StageStatus.SKIPPED
    assert result.packet is None
    assert result.failed_stage == "dark_filter"
    assert "too_dark" in (result.reason or "")
    executor.teardown_all()


def test_executor_stops_on_error():
    executor = SyncLinearExecutor([
        DarkFilterStage(threshold=50.0),
    ])
    executor.setup_all()
    packet = _make_packet(value=100)
    result = executor.execute(packet)
    assert result.status == StageStatus.ERROR
    assert result.packet is None
    assert result.failed_stage == "dark_filter"
    assert isinstance(result.error_message, str)
    assert "brightness" in result.error_message.lower()
    executor.teardown_all()


def test_executor_skip_and_error_are_distinguishable():
    """Invariant chính của ExecutionResult: skip ≠ error."""
    skip_exec = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    skip_exec.setup_all()
    skip_result = skip_exec.execute(_make_packet(value=10))
    skip_exec.teardown_all()

    err_exec = SyncLinearExecutor([DarkFilterStage(threshold=50.0)])
    err_exec.setup_all()
    err_result = err_exec.execute(_make_packet(value=100))
    err_exec.teardown_all()

    assert skip_result.status == StageStatus.SKIPPED
    assert err_result.status == StageStatus.ERROR
    assert skip_result.status != err_result.status


def test_executor_idempotent_setup():
    executor = SyncLinearExecutor([BrightnessStage()])
    executor.setup_all()
    executor.setup_all()
    executor.teardown_all()
    executor.teardown_all()


def test_custom_stage_via_subclass():
    """Subclass BaseStage works for custom logic."""
    class CountStage(BaseStage):
        def __init__(self):
            super().__init__("count")
            self.count = 0

        def _do_process(self, packet):
            self.count += 1
            return packet.with_artifact("count", self.count)

    s = CountStage()
    p = _make_packet()
    r1 = s.process(p)
    r2 = s.process(p)
    assert r1.packet.artifacts["count"] == 1
    assert r2.packet.artifacts["count"] == 2
    assert "count" not in p.artifacts


def test_executor_context_manager_setup_teardown():
    """ERRATA E-14 (Risk 4): `with` tự gọi setup_all lúc vào, teardown_all lúc ra
    (kể cả khi thân with raise)."""
    calls = []

    class TrackStage(BaseStage):
        def __init__(self):
            super().__init__("track")

        def setup(self):
            calls.append("setup")

        def teardown(self):
            calls.append("teardown")

        def _do_process(self, packet):
            return packet

    with SyncLinearExecutor([TrackStage()]) as ex:
        assert calls == ["setup"]
        ex.execute(_make_packet(0))
    assert calls == ["setup", "teardown"]

    # teardown vẫn chạy dù thân with raise:
    calls.clear()
    with pytest.raises(RuntimeError):
        with SyncLinearExecutor([TrackStage()]):
            raise RuntimeError("boom")
    assert calls == ["setup", "teardown"]


# ============ Review #04 fixes (ERRATA E-16) ============

def test_stage_error_keeps_traceback_string():
    """R1: ERROR result giữ traceback DẠNG CHUỖI (debug) — vẫn KHÔNG giữ Exception object."""
    stage = DarkFilterStage(threshold=50.0)
    result = stage.process(_make_packet(value=100))  # thiếu brightness -> ValueError
    assert result.status == StageStatus.ERROR
    assert isinstance(result.error_traceback, str)
    assert "Traceback" in result.error_traceback
    assert "ValueError" in result.error_traceback
    # vẫn không có trường giữ Exception
    from dataclasses import fields
    assert "error" not in {f.name for f in fields(StageResult)}


def test_stage_wrong_return_type_becomes_error():
    """R6: _do_process trả sai kiểu (None) -> ERROR fail-fast, không lọt downstream."""
    class BadStage(BaseStage):
        def __init__(self):
            super().__init__("bad")

        def _do_process(self, packet):
            return None  # SAI — phải trả MediaPacket

    result = BadStage().process(_make_packet(value=10))
    assert result.status == StageStatus.ERROR
    assert "MediaPacket" in result.error_message


def test_executor_setup_failure_rolls_back_only_setup_stages():
    """R3: setup lỗi nửa chừng -> chỉ teardown stage đã setup THÀNH CÔNG, rồi raise."""
    calls = []

    class OkStage(BaseStage):
        def setup(self):
            calls.append(f"setup_{self._name}")

        def teardown(self):
            calls.append(f"teardown_{self._name}")

        def _do_process(self, packet):
            return packet

    class FailSetupStage(BaseStage):
        def setup(self):
            raise RuntimeError("setup boom")

        def teardown(self):
            calls.append("teardown_fail")  # KHÔNG được gọi (chưa setup xong)

        def _do_process(self, packet):
            return packet

    ex = SyncLinearExecutor([OkStage("a"), FailSetupStage("fail"), OkStage("b")])
    with pytest.raises(RuntimeError):
        ex.setup_all()
    assert "setup_a" in calls
    assert "teardown_a" in calls        # rollback teardown stage đã setup
    assert "teardown_fail" not in calls  # chưa setup -> không teardown
    assert "setup_b" not in calls        # chưa tới
