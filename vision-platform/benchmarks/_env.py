"""Thu thập MÔI TRƯỜNG đo (bắt buộc kèm mọi số — Property 4: số vô nghĩa nếu không biết đo trên gì).

Không nổ khi thiếu torch/GPU (máy dev): trường không lấy được → ghi 'not-installed'/'unknown' (KHÔNG bịa).
"""
from __future__ import annotations

import platform
import subprocess
from typing import Optional


def _torch_info() -> dict:
    try:
        import torch  # lazy: máy dev không có torch
    except Exception:
        return {"torch": "not-installed", "cuda_available": "false", "cuda_version": "n/a"}
    cuda_ok = False
    try:
        cuda_ok = bool(torch.cuda.is_available())
    except Exception:
        cuda_ok = False
    return {
        "torch": getattr(torch, "__version__", "unknown"),
        "cuda_available": str(cuda_ok).lower(),
        "cuda_version": str(getattr(getattr(torch, "version", None), "cuda", "n/a")),
    }


def _gpu_name() -> str:
    """Lấy tên GPU qua nvidia-smi; không có → 'unknown' (KHÔNG bịa)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        name = out.stdout.strip().splitlines()
        return name[0].strip() if name else "unknown"
    except Exception:
        return "unknown"


def _yolov5_version() -> str:
    try:
        import yolov5  # lazy
        return getattr(yolov5, "__version__", "installed-unknown-version")
    except Exception:
        return "not-installed"


def collect_env(*, weight: Optional[str] = None, imgsz: Optional[int] = None) -> dict:
    """Trả dict môi trường đầy đủ để in header kết quả benchmark."""
    info = {
        "gpu_name": _gpu_name(),
        "yolov5": _yolov5_version(),
        "weight": weight or "[chưa đặt]",
        "imgsz": str(imgsz) if imgsz is not None else "[chưa đặt]",
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }
    info.update(_torch_info())
    return info


def format_env(env: dict) -> str:
    """1 dòng header môi trường cho bảng kết quả."""
    return (f"GPU={env.get('gpu_name')} · torch={env.get('torch')} "
            f"(cuda_available={env.get('cuda_available')}, cuda={env.get('cuda_version')}) · "
            f"yolov5={env.get('yolov5')} · weight={env.get('weight')} · imgsz={env.get('imgsz')} · "
            f"os={env.get('os')} · py={env.get('python')}")
