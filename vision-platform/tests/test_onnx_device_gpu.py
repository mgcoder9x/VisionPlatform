"""ONNX device policy — capability-aware, HỢP NHẤT 1 chính sách device mọi đường ONNX (F3.2/D-139).

`onnx_providers_for(requested, caps)` (adapters, THUẦN) dùng `resolve_device` @kernel: hỗ trợ 'auto',
FAIL-FAST `CapabilityError` khi 'cuda' mà máy KHÔNG CUDA (KHÔNG fallback CPU âm thầm — đối xứng `_det_pt`).
`_det_onnx` (config) đi qua helper + probe + LOG. Test tiêm `MachineCapabilities` giả → không cần GPU/onnxruntime-gpu.
"""
from __future__ import annotations

import pytest

from vision_platform.profiles import pipeline_factory as pf
from vision_platform.kernel.capabilities import MachineCapabilities, CapabilityError
from vision_platform.adapters.onnx_detector import onnx_providers_for

_GPU = MachineCapabilities(has_torch=True, has_cuda=True, cuda_device_count=1, gpu_name="RTX", has_cv2=True)
_CPU = MachineCapabilities(has_torch=False, has_cuda=False)

_CUDA = ["CUDAExecutionProvider", "CPUExecutionProvider"]
_CPUONLY = ["CPUExecutionProvider"]


# ---------- helper THUẦN (tiêm caps, không cần GPU) ----------

def test_helper_gpu_cuda():
    assert onnx_providers_for("cuda", _GPU) == (_CUDA, "cuda")


def test_helper_gpu_auto_picks_cuda():
    assert onnx_providers_for("auto", _GPU) == (_CUDA, "cuda")


def test_helper_cpu_explicit():
    assert onnx_providers_for("cpu", _GPU) == (_CPUONLY, "cpu")


def test_helper_nocuda_auto_falls_cpu():
    assert onnx_providers_for("auto", _CPU) == (_CPUONLY, "cpu")


def test_helper_nocuda_cuda_fail_fast():
    # ESSENCE (F3.2): 'cuda' trên máy không CUDA → FAIL-FAST, KHÔNG fallback CPU âm thầm.
    with pytest.raises(CapabilityError):
        onnx_providers_for("cuda", _CPU)


def test_helper_bad_device_raises():
    with pytest.raises(CapabilityError):
        onnx_providers_for("tpu", _CPU)


# ---------- _det_onnx wiring (monkeypatch probe + OnnxDetector spy) ----------

class _SpyOnnx:
    last: dict = {}

    def __init__(self, weights, *, preprocess_fn, postprocess_fn, providers, **kw):
        _SpyOnnx.last = {"weights": weights, "providers": list(providers)}


def _build(params, monkeypatch, caps=_CPU):
    import vision_platform.adapters.onnx_detector as od
    monkeypatch.setattr(od, "OnnxDetector", _SpyOnnx)     # _det_onnx import OnnxDetector trong hàm → lấy bản patch
    monkeypatch.setattr(pf, "probe_capabilities", lambda: caps)   # tiêm năng lực máy giả (xác định)
    return pf._det_onnx(params)


def test_device_cuda_sets_cuda_provider(monkeypatch):
    _build({"weights": "m.onnx", "device": "cuda"}, monkeypatch, caps=_GPU)
    assert _SpyOnnx.last["providers"] == _CUDA


def test_device_default_is_cpu(monkeypatch):
    _build({"weights": "m.onnx"}, monkeypatch, caps=_CPU)
    assert _SpyOnnx.last["providers"] == _CPUONLY


def test_device_auto_no_gpu_is_cpu(monkeypatch):
    # 'auto' MỚI được hỗ trợ (trước là ConfigError) → không GPU thì về CPU.
    _build({"weights": "m.onnx", "device": "auto"}, monkeypatch, caps=_CPU)
    assert _SpyOnnx.last["providers"] == _CPUONLY


def test_device_cuda_no_gpu_fail_fast(monkeypatch):
    # ESSENCE (F3.2): config yêu cầu cuda trên máy CPU → CapabilityError (không chạy CPU âm thầm).
    with pytest.raises(CapabilityError):
        _build({"weights": "m.onnx", "device": "cuda"}, monkeypatch, caps=_CPU)


def test_device_bad_raises(monkeypatch):
    with pytest.raises(CapabilityError):
        _build({"weights": "m.onnx", "device": "tpu"}, monkeypatch, caps=_CPU)


def test_device_in_allowed_params_strict_key():
    assert "device" in pf._det_onnx.allowed_params
