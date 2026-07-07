"""Task 2 (sub-spec config-declarative): ConfigLoader parse + validate + load TOML (fail-fast).

_Requirements: 1.1, 1.3, 1.4, 2.1, 2.2, 2.3, 4.3_
"""
from __future__ import annotations

import pytest

from vision_platform.application.config_loader import (
    parse_app_config, load_app_config, ConfigError,
)


def _valid_raw():
    return {
        "pipelines": [
            {
                "id": "cam-01",
                "max_frames": 100,
                "source": {"type": "video", "params": {"path": "clips/a.mp4"}},
                "detector": {"type": "fake", "params": {"model_size": 640}},
                "stages": [{"type": "detect"}, {"type": "count"}],
                "sinks": [{"type": "jsonl", "params": {"path": "e.jsonl"}}],
            }
        ]
    }


def test_parse_valid_roundtrip():
    app = parse_app_config(_valid_raw())
    assert len(app.pipelines) == 1
    p = app.pipelines[0]
    assert p.id == "cam-01" and p.max_frames == 100
    assert p.source.type == "video" and p.source.params["path"] == "clips/a.mp4"
    assert [s.type for s in p.stages] == ["detect", "count"]     # giữ THỨ TỰ
    assert p.sinks[0].type == "jsonl"
    assert p.detector is not None and p.detector.type == "fake"


def test_missing_pipelines_key():
    with pytest.raises(ConfigError):
        parse_app_config({})


def test_pipeline_missing_id():
    with pytest.raises(ConfigError):
        parse_app_config({"pipelines": [{"source": {"type": "fake"}}]})


def test_duplicate_id():
    raw = {"pipelines": [
        {"id": "x", "source": {"type": "fake"}},
        {"id": "x", "source": {"type": "noise"}},
    ]}
    with pytest.raises(ConfigError):
        parse_app_config(raw)


def test_source_missing_type():
    with pytest.raises(ConfigError):
        parse_app_config({"pipelines": [{"id": "a", "source": {"params": {}}}]})


def test_stage_missing_type():
    raw = {"pipelines": [{"id": "a", "source": {"type": "fake"}, "stages": [{"params": {}}]}]}
    with pytest.raises(ConfigError):
        parse_app_config(raw)


def test_detector_present_without_type():
    raw = {"pipelines": [{"id": "a", "source": {"type": "fake"}, "detector": {"params": {}}}]}
    with pytest.raises(ConfigError):
        parse_app_config(raw)


def test_max_frames_wrong_type():
    raw = {"pipelines": [{"id": "a", "source": {"type": "fake"}, "max_frames": "100"}]}
    with pytest.raises(ConfigError):
        parse_app_config(raw)


def test_optional_detector_and_empty_lists():
    app = parse_app_config({"pipelines": [{"id": "a", "source": {"type": "fake"}}]})
    p = app.pipelines[0]
    assert p.detector is None and p.stages == () and p.sinks == () and p.max_frames is None


def test_load_from_toml_file(tmp_path):
    toml_text = (
        '[[pipelines]]\n'
        'id = "cam-01"\n'
        'max_frames = 50\n'
        '[pipelines.source]\n'
        'type = "noise"\n'
        'params = { }\n'
        '[[pipelines.stages]]\n'
        'type = "detect"\n'
        '[[pipelines.stages]]\n'
        'type = "count"\n'
    )
    cfg = tmp_path / "app.toml"
    cfg.write_text(toml_text, encoding="utf-8")
    app = load_app_config(str(cfg))
    p = app.pipelines[0]
    assert p.id == "cam-01" and p.max_frames == 50
    assert p.source.type == "noise"
    assert [s.type for s in p.stages] == ["detect", "count"]


def test_load_missing_file():
    with pytest.raises(ConfigError):
        load_app_config("khong_ton_tai_12345.toml")


def test_load_bad_toml(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not valid toml [[[", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_app_config(str(bad))
