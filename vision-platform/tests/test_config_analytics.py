"""Mở rộng config-declarative: khai báo analytics (track/line_crossing) + sink crossing_events qua config.

Test build_runner dựng đúng chuỗi stage từ config + validate_config + strict-key (K-046) + required params.
Deploy-by-config cho chuỗi analytics — additive vào registry (Req 3.3), KHÔNG sửa lõi factory.
"""
import pytest

from vision_platform.kernel.config import (
    AppConfig, PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
)
from vision_platform.profiles.pipeline_factory import build_runner, validate_config, ConfigError
from vision_platform.runtime.stages.detect_stage import DetectStage
from vision_platform.runtime.stages.tracking_stage import TrackingStage
from vision_platform.runtime.stages.line_crossing_stage import LineCrossingStage


def _pcfg(tmp_path, stages, sinks=()):
    return PipelineConfig(
        id="cam0",
        source=SourceConfig("fake", {"max_frames": 3}),
        detector=DetectorConfig("fake", {"model_size": 64}),
        stages=stages,
        sinks=sinks,
    )


def test_build_runner_with_full_analytics_chain(tmp_path):
    out = tmp_path / "ev.jsonl"
    pcfg = _pcfg(
        tmp_path,
        stages=[
            StageConfig("detect"),
            StageConfig("track", {"iou_threshold": 0.3, "max_age": 30}),
            StageConfig("line_crossing", {"ax": 50, "ay": 0, "bx": 50, "by": 100}),
        ],
        sinks=[SinkConfig("crossing_events", {"path": str(out)})],
    )
    runner = build_runner(pcfg)
    stages = runner._executor._stages
    assert [type(s) for s in stages] == [DetectStage, TrackingStage, LineCrossingStage]
    stats = runner.run(max_frames=3)         # chạy thật (fake source) — không crash
    assert stats.frames_read == 3 and stats.processed == 3
    assert out.exists()                       # sink crossing_events đã mở file (append)


def test_validate_config_accepts_analytics(tmp_path):
    app = AppConfig([_pcfg(
        tmp_path,
        stages=[StageConfig("detect"), StageConfig("track"),
                StageConfig("line_crossing", {"ax": 1, "ay": 2, "bx": 3, "by": 4})],
        sinks=[SinkConfig("crossing_events", {"path": "x.jsonl"})],
    )])
    validate_config(app)                      # không raise = hợp lệ


def test_strict_key_rejects_typo_in_track(tmp_path):
    app = AppConfig([_pcfg(tmp_path, stages=[StageConfig("track", {"iou_thresh": 0.5})])])  # typo
    with pytest.raises(ConfigError) as ei:
        validate_config(app)
    assert "iou_thresh" in str(ei.value)


def test_line_crossing_missing_coords_errors(tmp_path):
    pcfg = _pcfg(tmp_path, stages=[
        StageConfig("detect"),
        StageConfig("track"),
        StageConfig("line_crossing", {"ax": 50, "ay": 0}),   # thiếu bx,by
    ])
    with pytest.raises(ConfigError):
        build_runner(pcfg)
