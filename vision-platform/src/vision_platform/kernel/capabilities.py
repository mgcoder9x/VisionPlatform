"""Năng lực máy (capability) — DTO thuần + chính sách resolve device (spec capability-aware-execution).

Layer: kernel — THUẦN Python (dataclass + hàm thuần + exception). KHÔNG import torch/cv2 (contract
import-linter "Kernel chi phu thuoc domain"). Việc DÒ năng lực THẬT (`import torch`) nằm ở
`adapters/capability_probe.py` (leaf, được phép chạm dep cụ thể) và TRẢ VỀ `MachineCapabilities` (DTO này).

Vì sao tách DTO+policy (kernel) khỏi probe (adapters): quyết-định-theo-năng-lực là HÀM THUẦN
(`resolve_device`) → test xác định bằng cách TIÊM `MachineCapabilities` giả, KHÔNG cần GPU/torch. Đây là
cách xử lý BẢN CHẤT việc chạy trên máy hỗn tạp GPU/CPU (thay vì rải `if torch...` khắp nơi).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineCapabilities:
    """Năng lực TÍNH TOÁN của máy hiện tại (kết quả probe). Immutable, thuần — tiêm được để test."""

    has_torch: bool
    has_cuda: bool                 # CUDA khả dụng QUA TORCH (torch.cuda) — dùng cho đường .pt (Yolov5PtDetector)
    cuda_device_count: int = 0     # số GPU theo torch (0 khi torch vắng)
    gpu_name: str | None = None
    has_cv2: bool = False
    # CUDA khả dụng QUA ONNXRUNTIME (onnxruntime-gpu providers) — ĐỘC LẬP với torch (K-109). Đường ONNX
    # (OnnxDetector) dùng onnxruntime, KHÔNG dùng torch → phải gate GPU theo cờ này, KHÔNG theo has_cuda(torch).
    # Bug đã bắt (#nnn): máy GPU-không-torch có onnxruntime-gpu → has_cuda(torch)=False nhưng GPU vẫn dùng được
    # qua ONNX; nếu gate onnx theo has_cuda → GPU bất khả dụng oan. Default False = tương thích ngược.
    has_onnx_cuda: bool = False


class CapabilityError(RuntimeError):
    """Yêu cầu năng lực mà máy KHÔNG đáp ứng (vd ép CUDA trên máy không GPU) — fail-fast, báo RÕ."""


_CUDA_BARE = frozenset({"cuda", "gpu"})


def _parse_ordinal(dev_lower: str) -> int:
    """'cuda:N' → int N (≥0). Không phải số nguyên ≥0 → CapabilityError (device không hợp lệ)."""
    suffix = dev_lower.split(":", 1)[1]
    if not suffix.isdigit():  # isdigit → chỉ [0-9]+ (loại '-1', 'x', rỗng) đúng ý "ordinal ≥0"
        raise CapabilityError(
            f"device {dev_lower!r} không hợp lệ: ordinal sau 'cuda:' phải là số nguyên ≥0."
        )
    return int(suffix)


def resolve_device(requested: str, caps: MachineCapabilities) -> str:
    """(requested, caps) → device THẬT (đã chuẩn hoá lower), HOẶC raise CapabilityError. HÀM THUẦN.

    - "cpu"           → "cpu" (luôn được).
    - "auto"          → "cuda" nếu caps.has_cuda, ngược lại "cpu" (fallback ÊM — nơi gọi nên LOG).
    - "cuda"/"gpu"    → "cuda" nếu có CUDA; không → CapabilityError (fail-fast).
    - "cuda:N"        → "cuda:N" nếu có CUDA và N < cuda_device_count; không → CapabilityError.
    - khác            → CapabilityError (device không hợp lệ).

    Chuẩn hoá: LUÔN trả dạng lower ("cpu"/"cuda"/"cuda:0") — 1 dạng chuẩn duy nhất xuống adapter
    (adapter tự map "cuda"→"cuda:0"). Không I/O, không tự probe → test tiêm caps xác định (no-GPU).
    """
    r = (requested or "auto").strip().lower()

    if r == "cpu":
        return "cpu"
    if r == "auto":
        return "cuda" if caps.has_cuda else "cpu"

    if r in _CUDA_BARE or r.startswith("cuda:"):
        if not caps.has_cuda:
            raise CapabilityError(
                f"device={requested!r} yêu cầu CUDA nhưng máy này KHÔNG có CUDA khả dụng "
                f"(has_torch={caps.has_torch}). Dùng device='auto' (tự về cpu) / 'cpu', "
                f"hoặc chạy trên máy có GPU."
            )
        if r.startswith("cuda:"):
            idx = _parse_ordinal(r)
            if idx >= caps.cuda_device_count:
                hi = caps.cuda_device_count - 1
                raise CapabilityError(
                    f"device={requested!r} nhưng máy chỉ có {caps.cuda_device_count} GPU "
                    f"(hợp lệ: cuda:0..cuda:{hi})."
                )
            return r  # "cuda:0" (đã lower)
        return "cuda"  # bare cuda/gpu → dạng chuẩn "cuda" (adapter → "cuda:0")

    raise CapabilityError(
        f"device không hợp lệ: {requested!r} (hợp lệ: auto | cpu | cuda | cuda:N)."
    )


def resolve_onnx_device(requested: str, caps: MachineCapabilities) -> str:
    """Như `resolve_device` NHƯNG gate CUDA theo `caps.has_onnx_cuda` (onnxruntime), KHÔNG theo `has_cuda` (torch).

    VÌ SAO tách (bug #nnn): đường ONNX (`OnnxDetector`) chạy trên **onnxruntime-gpu**, có CUDA ĐỘC LẬP với torch
    (K-109). Nếu quyết định device cho ONNX bằng `has_cuda` (dò qua torch) thì trên máy GPU-KHÔNG-torch (đúng
    kịch bản "CPU-first, no-torch, ONNX") sẽ: `auto`→cpu, `cuda`→CapabilityError → **GPU bất khả dụng oan** dù
    onnxruntime thấy `CUDAExecutionProvider`. Fix GỐC: đường ONNX gate theo năng-lực-ONNX-thật.

    Tái dùng TOÀN BỘ logic đã verify của `resolve_device` bằng cách thay `has_cuda`←`has_onnx_cuda` (một nguồn
    quyết định, không copy nhánh). Lưu ý `cuda:N` ordinal vẫn kiểm theo `cuda_device_count` (torch) → trên máy
    torch-vắng nên dùng `auto`/`cuda` (onnxruntime mặc định device 0); `cuda:N` chi tiết là ngoài phạm vi
    (onnx_providers_for chỉ trả TÊN provider, không set device_id).
    """
    import dataclasses
    return resolve_device(requested, dataclasses.replace(caps, has_cuda=caps.has_onnx_cuda))
