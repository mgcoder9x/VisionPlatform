"""Config-declarative hỗ trợ detector ONNX (deploy-by-config detector NN THẬT chạy được CPU).

Không cần file .onnx thật: `OnnxDetector` nạp model ở setup() (không phải __init__) → build_runner CONSTRUCT
được mà không load → test CI-safe (không phụ thuộc weight gitignored). Chỉ kiểm WIRING + fail-fast params.
"""
from __future__ import annotations

import pytest

from vision_platform.kernel.config import (
    PipelineConfig, SourceConfig, StageConfig, DetectorConfig,
)
from vision_platform.application.config_loader import ConfigError
from vision_platform.profiles.pipeline_factory import build_runner, DEFAULT_REGISTRY
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.adapters.detector_pipeline import DetectorPipeline
from vision_platform.adapters.onnx_detector import OnnxDetector


def _onnx_pcfg(det_params):
    return PipelineConfig(
        id="cam-onnx",
        source=SourceConfig("fake", {"max_frames": 3}),
        stages=[StageConfig("detect"), StageConfig("count")],
        detector=DetectorConfig("onnx", det_params),
        max_frames=3,
    )


def test_onnx_registered_in_registry():
    assert "onnx" in DEFAULT_REGISTRY["detectors"]


def test_build_onnx_detector_v8_constructs_without_weight_file():
    # Construct KHÔNG load (setup() mới load) → dựng runner OK dù file chưa tồn tại.
    runner = build_runner(_onnx_pcfg({"weights": "khong_ton_tai.onnx", "yolo": "v8"}))
    assert isinstance(runner, PipelineRunner)


def test_build_onnx_wraps_detector_pipeline_over_onnx():
    # Kiểm WIRING đúng: DetectorPipeline bọc OnnxDetector (đường sản phẩm letterbox/NMS/inverse).
    runner = build_runner(_onnx_pcfg({"weights": "m.onnx", "yolo": "v8", "model_size": 640}))
    # detector nằm trong DetectStage của executor — tìm qua stages.
    det = None
    for st in runner._executor._stages:  # type: ignore[attr-defined]
        if hasattr(st, "_detector"):
            det = st._detector
    assert isinstance(det, DetectorPipeline)
    assert isinstance(det._inner, OnnxDetector)  # type: ignore[attr-defined]


def test_onnx_labels_accepts_comma_string_and_list():
    assert isinstance(build_runner(_onnx_pcfg({"weights": "m.onnx", "labels": "person,car,bus"})), PipelineRunner)
    assert isinstance(build_runner(_onnx_pcfg({"weights": "m.onnx", "labels": ["person", "car"]})), PipelineRunner)


def test_onnx_missing_weights_raises():
    with pytest.raises(ConfigError):
        build_runner(_onnx_pcfg({"yolo": "v8"}))


def test_onnx_bad_yolo_version_raises():
    with pytest.raises(ConfigError):
        build_runner(_onnx_pcfg({"weights": "m.onnx", "yolo": "v99"}))


def test_onnx_bad_layout_raises():
    with pytest.raises(ConfigError):
        build_runner(_onnx_pcfg({"weights": "m.onnx", "yolo": "v8", "layout": "xyz"}))


def test_onnx_unknown_param_raises_strict_key():
    # K-046 strict-key: key lạ → fail-fast (không âm thầm bỏ qua).
    with pytest.raises(ConfigError):
        build_runner(_onnx_pcfg({"weights": "m.onnx", "khong_hop_le": 1}))
