"""Task 1 (sub-spec config-declarative): schema frozen dataclass THUẦN.

_Requirements: 1.2, 4.1_
Kiểm: khởi tạo đúng · frozen (không gán lại) · params bất biến (MappingProxyType) · list→tuple.
"""
from __future__ import annotations

import dataclasses

import pytest

from vision_platform.kernel.config import (
    SourceConfig, StageConfig, SinkConfig, DetectorConfig, PipelineConfig, AppConfig,
)


def test_source_config_fields_and_params():
    s = SourceConfig("video", {"path": "clips/a.mp4"})
    assert s.type == "video"
    assert s.params["path"] == "clips/a.mp4"


def test_configs_are_frozen():
    s = SourceConfig("fake")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.type = "noise"   # type: ignore[misc]


def test_params_immutable_mappingproxy():
    s = StageConfig("detect", {"k": 1})
    with pytest.raises(TypeError):
        s.params["k"] = 2   # MappingProxyType → read-only


def test_default_params_empty_and_readonly():
    d = DetectorConfig("fake")
    assert dict(d.params) == {}
    with pytest.raises(TypeError):
        d.params["x"] = 1


def test_pipeline_normalizes_lists_to_tuple():
    p = PipelineConfig(
        id="cam-01",
        source=SourceConfig("noise"),
        stages=[StageConfig("detect"), StageConfig("count")],
        sinks=[SinkConfig("jsonl", {"path": "e.jsonl"})],
        detector=DetectorConfig("fake", {"model_size": 640}),
        max_frames=100,
    )
    assert isinstance(p.stages, tuple) and len(p.stages) == 2
    assert p.stages[0].type == "detect" and p.stages[1].type == "count"
    assert isinstance(p.sinks, tuple) and p.sinks[0].type == "jsonl"
    assert p.detector is not None and p.detector.params["model_size"] == 640
    assert p.max_frames == 100


def test_pipeline_optional_detector_and_empty_sinks():
    p = PipelineConfig(id="c", source=SourceConfig("fake"))
    assert p.detector is None
    assert p.sinks == ()
    assert p.stages == ()


def test_appconfig_normalizes_pipelines_to_tuple():
    app = AppConfig(pipelines=[PipelineConfig(id="a", source=SourceConfig("fake"))])
    assert isinstance(app.pipelines, tuple) and app.pipelines[0].id == "a"
