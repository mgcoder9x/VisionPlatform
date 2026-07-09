"""Validate PHỤ THUỘC ARTIFACT theo thứ tự stage tại lúc config (fail-fast, không đợi runtime).

count/track cần detections (từ detect); line_crossing cần tracks (từ track). Sai thứ tự → ConfigError NGAY.
"""
import pytest

from vision_platform.kernel.config import (
    AppConfig, PipelineConfig, SourceConfig, StageConfig, DetectorConfig,
)
from vision_platform.profiles.pipeline_factory import build_runner, validate_config, ConfigError


def _p(stages):
    return PipelineConfig(
        id="cam0",
        source=SourceConfig("fake", {"max_frames": 2}),
        detector=DetectorConfig("fake", {"model_size": 64}),
        stages=stages,
    )


def test_correct_order_ok():
    validate_config(AppConfig([_p([
        StageConfig("motion_gate"), StageConfig("detect"), StageConfig("track"),
        StageConfig("line_crossing", {"ax": 1, "ay": 2, "bx": 3, "by": 4}), StageConfig("count"),
    ])]))  # không raise


def test_line_crossing_before_track_rejected():
    with pytest.raises(ConfigError) as ei:
        validate_config(AppConfig([_p([
            StageConfig("detect"),
            StageConfig("line_crossing", {"ax": 1, "ay": 2, "bx": 3, "by": 4}),  # thiếu track trước
        ])]))
    assert "tracks" in str(ei.value)


def test_count_before_detect_rejected():
    with pytest.raises(ConfigError) as ei:
        validate_config(AppConfig([_p([StageConfig("count"), StageConfig("detect")])]))
    assert "detections" in str(ei.value)


def test_track_before_detect_rejected():
    with pytest.raises(ConfigError) as ei:
        validate_config(AppConfig([_p([StageConfig("track"), StageConfig("detect")])]))
    assert "detections" in str(ei.value)


def test_build_runner_also_fails_fast_on_bad_order():
    # _run_from_config gọi build_runner KHÔNG qua validate_config → build_runner cũng phải chặn.
    with pytest.raises(ConfigError):
        build_runner(_p([
            StageConfig("detect"),
            StageConfig("line_crossing", {"ax": 1, "ay": 2, "bx": 3, "by": 4}),  # thiếu track
        ]))


def test_motion_gate_anywhere_ok():
    # motion_gate requires ∅ → đặt đâu cũng hợp lệ về phụ thuộc.
    validate_config(AppConfig([_p([StageConfig("detect"), StageConfig("motion_gate"), StageConfig("count")])]))
