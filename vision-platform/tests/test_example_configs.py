"""Xác nhận các file config mẫu trong configs/ HỢP LỆ trước khi chạy trên máy GPU.

Máy dev (no-GPU): các config `pt` chỉ kiểm PARSE (không dựng detector torch); config fake build+run thật.
_Requirements (config-declarative): 1.1, 2.3, 3.1_
"""
from __future__ import annotations

import pathlib

from vision_platform.application.config_loader import load_app_config
from vision_platform.profiles.pipeline_factory import build_runner, validate_config

CONFIGS = pathlib.Path(__file__).resolve().parents[1] / "configs"


def test_all_example_configs_parse_valid():
    files = sorted(CONFIGS.glob("*.toml"))
    assert files, "phải có file config mẫu trong configs/"
    for f in files:
        app = load_app_config(str(f))       # parse + validate cấu trúc (fail-fast nếu sai)
        # FULL validate (type∈registry + strict-key + detect-requires-detector) — KHỚP operator `--validate`.
        # TĨNH (T-014): không dựng detector/torch → chạy được no-GPU kể cả config `pt`. Bắt config ship rot.
        validate_config(app)
        assert len(app.pipelines) >= 1
        for p in app.pipelines:
            assert p.id and p.source.type    # tối thiểu id + source.type


def test_fake_config_builds_and_runs_no_gpu():
    app = load_app_config(str(CONFIGS / "example_fake.toml"))
    runner = build_runner(app.pipelines[0])
    stats = runner.run(max_frames=app.pipelines[0].max_frames)
    assert stats.processed > 0               # chạy thật, không cần GPU


def test_video_gpu_config_declares_pt_cuda():
    app = load_app_config(str(CONFIGS / "example_video_gpu.toml"))
    p = app.pipelines[0]
    assert p.source.type == "video" and p.source.params["path"]
    assert p.detector is not None and p.detector.type == "pt"
    assert p.detector.params["device"] == "cuda" and p.detector.params["weights"]
    assert [s.type for s in p.stages] == ["detect", "count"]


def test_rtsp_gpu_config_declares_rtsp_pt():
    app = load_app_config(str(CONFIGS / "example_rtsp_gpu.toml"))
    p = app.pipelines[0]
    assert p.source.type == "rtsp" and p.source.params["url"].startswith("rtsp://")
    assert p.detector is not None and p.detector.type == "pt"
