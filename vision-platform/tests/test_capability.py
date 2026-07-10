"""Spec capability-aware-execution — test XÁC ĐỊNH (tiêm MachineCapabilities), KHÔNG cần GPU.

Phủ Correctness Properties:
- P1 auto→theo năng lực · P2 cuda-thiếu→CapabilityError · P3 cpu luôn được · P5 thuần/xác định
- P4 probe an toàn (máy no-torch không raise) · P6 gate test skip · P8 ordinal cuda:N · P9 chuẩn hoá lower
- Wire: _det_pt (đường config) resolve device (fail-fast cuda / auto→cpu).
"""
import pytest

from vision_platform.kernel.capabilities import (
    MachineCapabilities, CapabilityError, resolve_device,
)
from vision_platform.adapters.capability_probe import probe_capabilities


_CUDA1 = MachineCapabilities(has_torch=True, has_cuda=True, cuda_device_count=1, gpu_name="FakeGPU")
_CUDA2 = MachineCapabilities(has_torch=True, has_cuda=True, cuda_device_count=2, gpu_name="FakeGPU")
_NOCUDA = MachineCapabilities(has_torch=True, has_cuda=False, cuda_device_count=0)
_NOTORCH = MachineCapabilities(has_torch=False, has_cuda=False, cuda_device_count=0)


# ============ P1: auto chọn theo năng lực ============

def test_auto_picks_cuda_when_available():
    assert resolve_device("auto", _CUDA1) == "cuda"


def test_auto_falls_back_cpu_when_no_cuda():
    assert resolve_device("auto", _NOCUDA) == "cpu"
    assert resolve_device("auto", _NOTORCH) == "cpu"


# ============ P2: cuda tường minh thiếu CUDA → fail-fast ============

def test_explicit_cuda_without_cuda_raises():
    for req in ("cuda", "gpu", "cuda:0"):
        with pytest.raises(CapabilityError) as ei:
            resolve_device(req, _NOCUDA)
        msg = str(ei.value)
        assert "CUDA" in msg and ("auto" in msg or "cpu" in msg)  # thông báo có gợi ý


# ============ P3: cpu luôn được ============

def test_cpu_always():
    assert resolve_device("cpu", _CUDA1) == "cpu"
    assert resolve_device("cpu", _NOCUDA) == "cpu"
    assert resolve_device("cpu", _NOTORCH) == "cpu"


# ============ P5: thuần / xác định ============

def test_deterministic_pure():
    a = resolve_device("auto", _CUDA1)
    b = resolve_device("auto", _CUDA1)
    assert a == b == "cuda"
    # default requested rỗng/None → coi như auto
    assert resolve_device("", _NOCUDA) == "cpu"
    assert resolve_device(None, _CUDA1) == "cuda"  # type: ignore[arg-type]


# ============ P8: ordinal cuda:N vs số GPU ============

def test_ordinal_out_of_range_raises():
    with pytest.raises(CapabilityError) as ei:
        resolve_device("cuda:3", _CUDA1)          # máy 1 GPU
    assert "1 GPU" in str(ei.value) or "cuda:0" in str(ei.value)


def test_ordinal_in_range_ok():
    assert resolve_device("cuda:0", _CUDA1) == "cuda:0"
    assert resolve_device("cuda:1", _CUDA2) == "cuda:1"


def test_ordinal_non_numeric_raises():
    for bad in ("cuda:x", "cuda:", "cuda:-1"):
        with pytest.raises(CapabilityError):
            resolve_device(bad, _CUDA2)


def test_unknown_device_raises():
    with pytest.raises(CapabilityError):
        resolve_device("tpu", _CUDA1)


# ============ P9: chuẩn hoá về lower 1 dạng ============

def test_normalize_to_lower():
    assert resolve_device("CUDA:0", _CUDA1) == "cuda:0"
    assert resolve_device("GPU", _CUDA1) == "cuda"
    assert resolve_device("  Auto  ", _NOCUDA) == "cpu"
    assert resolve_device("CPU", _CUDA1) == "cpu"


# ============ P4: probe an toàn (máy no-torch không raise) ============

def test_probe_never_raises_and_reports_no_torch_on_this_machine():
    caps = probe_capabilities()               # máy dev hiện tại: KHÔNG cài torch
    assert isinstance(caps, MachineCapabilities)
    assert caps.has_torch is False            # venv không có extra 'pt' (torch)
    assert caps.has_cuda is False             # không torch ⇒ không CUDA
    assert caps.cuda_device_count == 0
    assert caps.gpu_name is None
    # has_cv2 tuỳ máy (extra cv2) → không assert cứng


# ============ Wire: _det_pt (đường config) resolve device ============

def test_config_pt_cuda_fails_fast_on_no_cuda(monkeypatch):
    """Đường config-declarative: detector pt device=cuda trên máy KHÔNG CUDA → build_runner raise CapabilityError
    (resolve TRƯỚC khi import torch). Tiêm caps no-cuda → xác định trên MỌI máy."""
    from vision_platform.profiles import pipeline_factory
    from vision_platform.kernel.config import PipelineConfig, SourceConfig, DetectorConfig, StageConfig

    monkeypatch.setattr(pipeline_factory, "probe_capabilities", lambda: _NOCUDA)
    pcfg = PipelineConfig(
        id="camPt",
        source=SourceConfig("fake", {"max_frames": 2}),
        detector=DetectorConfig("pt", {"weights": "dummy.pt", "device": "cuda"}),
        stages=[StageConfig("count")],
        sinks=(),
    )
    with pytest.raises(CapabilityError):
        pipeline_factory.build_runner(pcfg)


def test_config_pt_auto_resolves_cpu_on_no_cuda(monkeypatch):
    """device=auto trên máy không CUDA → resolve "cpu" → build OK (construct không import torch)."""
    from vision_platform.profiles import pipeline_factory
    from vision_platform.kernel.config import PipelineConfig, SourceConfig, DetectorConfig, StageConfig

    monkeypatch.setattr(pipeline_factory, "probe_capabilities", lambda: _NOCUDA)
    pcfg = PipelineConfig(
        id="camPt",
        source=SourceConfig("fake", {"max_frames": 2}),
        detector=DetectorConfig("pt", {"weights": "dummy.pt", "device": "auto"}),
        stages=[StageConfig("count")],
        sinks=(),
    )
    runner = pipeline_factory.build_runner(pcfg)   # KHÔNG raise (auto→cpu)
    assert runner is not None


# ============ P6: gate test theo năng lực (conftest autoskip) ============

@pytest.mark.gpu
def test_gpu_marked_is_skipped_without_cuda():
    """Test này CỐ Ý fail nếu chạy. Trên máy KHÔNG CUDA, conftest phải SKIP nó (nếu chạy = gate hỏng)."""
    pytest.fail("test @gpu phải bị conftest SKIP trên máy không CUDA — nếu thấy fail này, gate hỏng")
