"""Task 3 (sub-spec config-declarative): PipelineFactory registry + build_runner (NO-GPU).

_Requirements: 3.1, 3.3_
Dùng fake source + fake detector (xác định, không cần GPU/torch/onnx).
"""
from __future__ import annotations

import pytest

from vision_platform.kernel.config import (
    PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
)
from vision_platform.application.config_loader import ConfigError
from vision_platform.profiles.pipeline_factory import build_runner, DEFAULT_REGISTRY
from vision_platform.runtime.pipeline_runner import PipelineRunner


def _fake_detect_count_pcfg(max_frames=5):
    return PipelineConfig(
        id="cam-01",
        source=SourceConfig("fake", {"max_frames": max_frames}),
        stages=[StageConfig("detect"), StageConfig("count")],
        detector=DetectorConfig("fake", {"model_size": 640}),
        max_frames=max_frames,
    )


def test_build_runner_returns_runner_and_runs():
    runner = build_runner(_fake_detect_count_pcfg(max_frames=5))
    assert isinstance(runner, PipelineRunner)
    stats = runner.run(max_frames=5)
    assert stats.frames_read > 0
    assert stats.processed > 0          # pipeline chạy thật, không cần GPU


def test_unknown_source_type_raises():
    pcfg = PipelineConfig(id="a", source=SourceConfig("khong_co"))
    with pytest.raises(ConfigError):
        build_runner(pcfg)


def test_detect_stage_without_detector_raises():
    pcfg = PipelineConfig(
        id="a", source=SourceConfig("fake"),
        stages=[StageConfig("detect")], detector=None,
    )
    with pytest.raises(ConfigError):
        build_runner(pcfg)


def test_empty_sinks_and_no_detector_count_only():
    pcfg = PipelineConfig(
        id="a", source=SourceConfig("noise", {"max_frames": 3}),
        stages=[StageConfig("count")],
    )
    runner = build_runner(pcfg)
    stats = runner.run(max_frames=3)
    assert stats.frames_read > 0


def test_registry_extensible_without_editing_core():
    # Thêm loại source mới qua registry (không sửa lõi factory) — Req 3.3
    class _StubSource:
        source_id = "stub"
        is_finite = True
        def setup(self): pass
        def teardown(self): pass
        def read(self, timeout_ms):
            from vision_platform.kernel.read_result import ReadResult, ReadStatus
            return ReadResult(status=ReadStatus.EOF)

    custom = {
        "sources": {"stub": lambda params: _StubSource()},
        "detectors": {}, "stages": dict(DEFAULT_REGISTRY["stages"]), "sinks": {},
    }
    pcfg = PipelineConfig(id="a", source=SourceConfig("stub"), stages=[StageConfig("count")])
    runner = build_runner(pcfg, registry=custom)
    assert isinstance(runner, PipelineRunner)
    stats = runner.run(max_frames=1)
    assert stats.eof >= 1               # stub trả EOF → runner dừng sạch


def test_unknown_type_error_lists_valid():
    pcfg = PipelineConfig(id="a", source=SourceConfig("nope"))
    with pytest.raises(ConfigError) as ei:
        build_runner(pcfg)
    assert "fake" in str(ei.value)      # thông điệp liệt kê type hợp lệ (Req 2.2)
