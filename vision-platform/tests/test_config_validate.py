"""validate_config + cờ --validate: kiểm config hợp lệ KHÔNG dựng object (no-GPU/no-torch).

Cho phép validate cả config GPU (pt/cuda) trên máy dev TRƯỚC khi chạy trên máy GPU.
_Requirements (config-declarative): 2.1, 2.2, 3.1_
"""
from __future__ import annotations

import pathlib

import pytest

from vision_platform.kernel.config import (
    PipelineConfig, SourceConfig, StageConfig, DetectorConfig, AppConfig,
)
from vision_platform.application.config_loader import ConfigError, load_app_config
from vision_platform.profiles.pipeline_factory import validate_config
from vision_platform.profiles.vision_slice_app import main

CONFIGS = pathlib.Path(__file__).resolve().parents[1] / "configs"


def test_validate_ok_for_valid_app():
    app = AppConfig(pipelines=[PipelineConfig(
        id="a", source=SourceConfig("fake"),
        stages=[StageConfig("detect"), StageConfig("count")],
        detector=DetectorConfig("fake"),
    )])
    validate_config(app)   # không raise


def test_validate_unknown_type_raises_with_id():
    app = AppConfig(pipelines=[PipelineConfig(id="cam-x", source=SourceConfig("bogus"))])
    with pytest.raises(ConfigError) as ei:
        validate_config(app)
    assert "cam-x" in str(ei.value)


def test_validate_detect_without_detector_raises():
    app = AppConfig(pipelines=[PipelineConfig(
        id="a", source=SourceConfig("fake"), stages=[StageConfig("detect")], detector=None,
    )])
    with pytest.raises(ConfigError):
        validate_config(app)


def test_validate_gpu_config_on_dev_machine_no_torch():
    # KEY: config GPU (pt/cuda) validate ĐƯỢC trên máy dev (không import torch/không dựng detector)
    app = load_app_config(str(CONFIGS / "example_video_gpu.toml"))
    validate_config(app)   # không raise, không cần GPU
    app2 = load_app_config(str(CONFIGS / "example_rtsp_gpu.toml"))
    validate_config(app2)


def _write(tmp_path, body):
    p = tmp_path / "c.toml"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_cli_validate_ok_returns_0(tmp_path):
    cfg = _write(tmp_path, (
        '[[pipelines]]\nid = "a"\n[pipelines.source]\ntype = "fake"\n'
        '[[pipelines.stages]]\ntype = "count"\n'
    ))
    assert main(["--config", cfg, "--validate"]) == 0


def test_cli_validate_bad_returns_2(tmp_path):
    cfg = _write(tmp_path, (
        '[[pipelines]]\nid = "a"\n[pipelines.source]\ntype = "khong_co_type"\n'
    ))
    assert main(["--config", cfg, "--validate"]) == 2


def test_cli_validate_gpu_config_returns_0():
    assert main(["--config", str(CONFIGS / "example_video_gpu.toml"), "--validate"]) == 0


def test_cli_validate_requires_config():
    with pytest.raises(SystemExit):   # argparse parser.error → SystemExit
        main(["--validate"])


# --- K-046: strict-key — params typo KHÔNG được nuốt im lặng ---

def test_validate_rejects_unknown_param_key():
    """Typo key trong params (vd 'max_frame' thay 'max_frames') → ConfigError kèm pipeline id + key lạ."""
    app = AppConfig(pipelines=[PipelineConfig(
        id="cam-typo", source=SourceConfig("fake", {"max_frame": 5}),  # thiếu 's'
        stages=[StageConfig("count")],
    )])
    with pytest.raises(ConfigError) as ei:
        validate_config(app)
    msg = str(ei.value)
    assert "cam-typo" in msg and "max_frame" in msg


def test_validate_accepts_correct_param_key():
    """Key đúng → không raise (không siết nhầm cái hợp lệ)."""
    app = AppConfig(pipelines=[PipelineConfig(
        id="ok", source=SourceConfig("fake", {"max_frames": 5}),
        stages=[StageConfig("count")],
    )])
    validate_config(app)   # không raise


def test_build_runner_rejects_unknown_detector_param_before_torch():
    """Typo 'wieghts' ở detector pt → ConfigError TRƯỚC khi import torch (chạy được máy no-GPU)."""
    from vision_platform.profiles.pipeline_factory import build_runner
    pcfg = PipelineConfig(
        id="x", source=SourceConfig("fake"),
        stages=[StageConfig("detect")],
        detector=DetectorConfig("pt", {"wieghts": "m.pt", "device": "cuda"}),  # typo weights
    )
    with pytest.raises(ConfigError) as ei:
        build_runner(pcfg)
    assert "wieghts" in str(ei.value)


def test_cli_validate_unknown_param_returns_2(tmp_path):
    """--validate bắt được typo params trên máy dev (return 2)."""
    cfg = _write(tmp_path, (
        '[[pipelines]]\nid = "a"\n[pipelines.source]\ntype = "fake"\n'
        'params = { maxframes = 5 }\n'   # typo
        '[[pipelines.stages]]\ntype = "count"\n'
    ))
    assert main(["--config", cfg, "--validate"]) == 2
