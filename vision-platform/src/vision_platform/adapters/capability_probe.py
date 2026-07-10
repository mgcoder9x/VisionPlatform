"""Probe năng lực máy THẬT (spec capability-aware-execution). Layer: adapters (leaf).

Adapters được phép `import torch`/`cv2` (contract chỉ cấm adapters import nguoc len runtime/application/
profiles). Probe TRẢ VỀ `MachineCapabilities` (DTO kernel thuần) → nơi gọi (profiles) dùng `resolve_device`.

NGUYÊN TẮC: probe KHÔNG BAO GIỜ raise — máy không cài torch/cv2 (như máy dev no-GPU/no-CUDA hiện tại) vẫn dò
được (chỉ trả False). Mọi import + truy vấn CUDA đều bọc try/except. `has_cuda` = "CUDA KHẢ DỤNG THẬT" =
`is_available() AND device_count()>0` (chống ca lạ is_available-True-nhưng-0-GPU).
"""
from __future__ import annotations

from vision_platform.kernel.capabilities import MachineCapabilities


def probe_capabilities() -> MachineCapabilities:
    """Dò năng lực máy hiện tại (an toàn, không raise). Nên gọi 1 lần/tiến trình rồi truyền DI xuống."""
    has_torch = False
    has_cuda = False
    n = 0
    gpu: str | None = None
    has_cv2 = False

    try:
        import torch  # dep NẶNG optional (.[pt]) — có thể vắng trên máy dev

        has_torch = True
        try:
            n = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
            has_cuda = n > 0  # "khả dụng thật" = có driver + ≥1 GPU
            gpu = torch.cuda.get_device_name(0) if has_cuda else None
        except Exception:  # noqa: BLE001 — truy vấn CUDA lỗi (driver/lib hỏng) → coi như không có
            has_cuda, n, gpu = False, 0, None
    except ImportError:
        pass  # máy không cài torch → has_torch=False (KHÔNG raise)

    try:
        import cv2  # noqa: F401 — chỉ kiểm có import được không

        has_cv2 = True
    except ImportError:
        pass

    return MachineCapabilities(
        has_torch=has_torch,
        has_cuda=has_cuda,
        cuda_device_count=n,
        gpu_name=gpu,
        has_cv2=has_cv2,
    )
