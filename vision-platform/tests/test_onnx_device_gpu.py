"""ONNX device policy — capability-aware, HỢP NHẤT 1 chính sách device mọi đường ONNX (F3.2/D-139).

`onnx_providers_for(requested, caps)` (adapters, THUẦN) dùng `resolve_onnx_device` @kernel: gate CUDA theo
`caps.has_onnx_cuda` (onnxruntime providers, ĐỘC LẬP torch — K-109); hỗ trợ 'auto', FAIL-FAST `CapabilityError`
khi 'cuda' mà onnxruntime KHÔNG CUDA. `_det_onnx`/`_build_detector` đi qua helper + probe + LOG. Test tiêm
`MachineCapabilities` giả → không cần GPU/onnxruntime-gpu.
"""
from __future__ import annotations

import pytest

from vision_platform.profiles import pipeline_factory as pf
from vision_platform.kernel.capabilities import MachineCapabilities, CapabilityError
from vision_platform.adapters.onnx_detector import onnx_providers_for

# GPU đầy đủ (torch + onnxruntime đều thấy CUDA)
_GPU = MachineCapabilities(has_torch=True, has_cuda=True, cuda_device_count=1, gpu_name="RTX",
                           has_cv2=True, has_onnx_cuda=True)
_CPU = MachineCapabilities(has_torch=False, has_cuda=False)   # has_onnx_cuda default False
# KỊCH BẢN BUG (#nnn) — máy GPU CÓ onnxruntime-gpu NHƯNG KHÔNG cài torch: has_cuda(torch)=False,
# has_onnx_cuda=True. Đường ONNX PHẢI dùng được GPU (đây là kịch bản CPU-first-no-torch của onnx).
_GPU_NOTORCH = MachineCapabilities(has_torch=False, has_cuda=False, has_onnx_cuda=True)
# Ngược lại: có torch-CUDA nhưng onnxruntime KHÔNG có CUDA provider (onnxruntime CPU-only) → onnx PHẢI về/chặn CPU.
_TORCHCUDA_NO_ONNXCUDA = MachineCapabilities(has_torch=True, has_cuda=True, cuda_device_count=1,
                                             gpu_name="RTX", has_onnx_cuda=False)

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


# ---------- REGRESSION (bug #nnn): onnx gate theo has_onnx_cuda, KHÔNG theo has_cuda(torch) ----------

def test_onnx_cuda_without_torch_auto_picks_cuda():
    # GỐC: máy GPU-KHÔNG-torch (onnxruntime-gpu thấy CUDA) → auto PHẢI chọn CUDA (trước bug: về CPU oan).
    assert onnx_providers_for("auto", _GPU_NOTORCH) == (_CUDA, "cuda")


def test_onnx_cuda_without_torch_cuda_ok():
    # GỐC: 'cuda' trên máy GPU-không-torch → CUDA (trước bug: CapabilityError oan vì has_cuda(torch)=False).
    assert onnx_providers_for("cuda", _GPU_NOTORCH) == (_CUDA, "cuda")


def test_onnx_ignores_torch_cuda_when_onnxruntime_has_no_cuda():
    # ĐỐI XỨNG: có torch-CUDA nhưng onnxruntime CPU-only → onnx 'auto' về CPU, 'cuda' fail-fast
    # (onnx KHÔNG mượn được CUDA của torch).
    assert onnx_providers_for("auto", _TORCHCUDA_NO_ONNXCUDA) == (_CPUONLY, "cpu")
    with pytest.raises(CapabilityError):
        onnx_providers_for("cuda", _TORCHCUDA_NO_ONNXCUDA)


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
