"""D-098: `_det_onnx` wire `device` → onnxruntime providers (cpu/cuda). KHÔNG cần GPU/onnxruntime-gpu thật
(spy OnnxDetector bắt providers khi build; build KHÔNG tạo session)."""
from __future__ import annotations

import pytest

from vision_platform.profiles import pipeline_factory as pf
from vision_platform.application.config_loader import ConfigError


class _SpyOnnx:
    last: dict = {}

    def __init__(self, weights, *, preprocess_fn, postprocess_fn, providers, **kw):
        _SpyOnnx.last = {"weights": weights, "providers": list(providers)}


def _build(params, monkeypatch):
    import vision_platform.adapters.onnx_detector as od
    monkeypatch.setattr(od, "OnnxDetector", _SpyOnnx)   # _det_onnx import OnnxDetector trong hàm → lấy bản patch
    return pf._det_onnx(params)


def test_device_cuda_sets_cuda_provider(monkeypatch):
    _build({"weights": "m.onnx", "device": "cuda"}, monkeypatch)
    assert _SpyOnnx.last["providers"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_device_default_is_cpu(monkeypatch):
    _build({"weights": "m.onnx"}, monkeypatch)
    assert _SpyOnnx.last["providers"] == ["CPUExecutionProvider"]


def test_device_bad_raises_configerror(monkeypatch):
    with pytest.raises(ConfigError):
        _build({"weights": "m.onnx", "device": "tpu"}, monkeypatch)


def test_device_in_allowed_params_strict_key():
    # 'device' phải được strict-key (K-046) chấp nhận (nếu không, config device=cuda sẽ bị từ chối oan).
    assert "device" in pf._det_onnx.allowed_params
