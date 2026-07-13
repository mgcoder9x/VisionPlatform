"""ensure_cuda_dll_path — làm cho DLL CUDA/cuDNN của nvidia pip-wheels TÌM ĐƯỢC (Windows). Layer: adapters.

BẢN CHẤT (K-088 — verify #359): onnxruntime-gpu KHÔNG bundle CUDA → cần các wheel `nvidia-*` (cudnn/cublas/
cuda-runtime/cufft/curand/cusparse). DLL nằm `site-packages/nvidia/**/bin[/x86_64]`. `onnxruntime_providers_cuda.dll`
nạp dep BẮC-CẦU (`cublasLt64_13.dll`...) qua Windows loader — mà loader KHÔNG tra thư mục `os.add_dll_directory`
cho dep của DLL nạp-bằng-đường-dẫn-đầy-đủ (thiếu cờ LOAD_LIBRARY_SEARCH_USER_DIRS). ⇒ phải **prepend PATH**
(PATH luôn được tra cho dep bắc-cầu). `ort.preload_dlls()` 1.27 chưa biết layout `cu13/bin/x86_64` nên tự làm.

An toàn: best-effort, IDEMPOTENT, no-op nếu không có nvidia wheels / không phải Windows (không lỗi). Gọi TRƯỚC
khi tạo `InferenceSession` với CUDA/TensorRT provider.
"""
from __future__ import annotations

import glob
import os
import sys
from typing import Optional, Sequence

_applied = False


def _default_nvidia_roots() -> list[str]:
    """Mọi thư mục `nvidia/` trong site-packages của interpreter hiện tại (nơi pip wheel đặt DLL)."""
    roots: list[str] = []
    for p in sys.path:
        if not p:
            continue
        cand = os.path.join(p, "nvidia")
        if os.path.isdir(cand) and cand not in roots:
            roots.append(cand)
    return roots


def _dll_dirs(roots: Sequence[str]) -> list[str]:
    """Các thư mục CHỨA `*.dll` (đệ quy) dưới mỗi root nvidia — bao gồm layout mới `cu13/bin/x86_64`."""
    dirs: list[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dll in glob.glob(os.path.join(root, "**", "*.dll"), recursive=True):
            d = os.path.dirname(dll)
            if d not in dirs:
                dirs.append(d)
    return dirs


def ensure_cuda_dll_path(nvidia_roots: Optional[Sequence[str]] = None, *, force: bool = False) -> tuple[str, ...]:
    """Prepend thư mục DLL nvidia vào PATH (+ add_dll_directory). Trả tuple thư mục đã thêm.

    - `nvidia_roots=None` → tự dò site-packages/nvidia (mặc định, production). Tiêm list để test.
    - IDEMPOTENT: chỉ chạy 1 lần/process (trừ khi `force=True` cho test). Không nhân đôi PATH (chỉ thêm dir CHƯA có).
    - No-op an toàn: không tìm thấy DLL → trả `()`, KHÔNG đổi PATH, KHÔNG raise.
    """
    global _applied
    if _applied and not force:
        return ()
    roots = _default_nvidia_roots() if nvidia_roots is None else list(nvidia_roots)
    dirs = _dll_dirs(roots)
    if not dirs:
        _applied = True
        return ()
    for d in dirs:
        try:
            os.add_dll_directory(d)   # cho DLL nạp trực tiếp (không đủ cho dep bắc-cầu → cần PATH dưới)
        except (OSError, AttributeError):
            pass                       # non-Windows / dir lạ → bỏ qua
    path = os.environ.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    missing = [d for d in dirs if d not in parts]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing) + (os.pathsep + path if path else "")
    _applied = True
    return tuple(dirs)
