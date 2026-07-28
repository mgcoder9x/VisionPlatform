"""Loader LabelMap — nạp nguồn nhãn thành `LabelMap` (spec image-preprocess-and-labeling, R1.3/R1.4).

Layer: adapters — ĐỌC I/O (file `.names` sidecar + metadata ONNX). Trả về `LabelMap` @kernel (thuần).
Tách rõ: I/O ở đây ⊥ logic resolve fail-safe ở `kernel/label_map.py` (test được không cần file/model).

Thứ tự ưu tiên nguồn (§D-5, R1.3/R1.4) — "model nào cũng chạy được":
  1. sidecar `.names` cạnh model (1 tên/dòng)  ← override tường minh, không cần onnx
  2. metadata ONNX `names` (kiểu Ultralytics: metadata_props['names'] = str(dict))  ← best-effort
  3. config `labels` (fallback)
  4. rỗng → mọi id `class_<id>` (LabelMap.empty)

Đọc metadata ONNX là best-effort: thiếu onnxruntime / model không hợp lệ / không có key → bỏ qua (KHÔNG raise),
rơi xuống nguồn kế. Lý do: loader KHÔNG được làm sập pipeline chỉ vì nhãn — fail-safe là canonical `class_<id>`.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional, Sequence

from vision_platform.kernel.label_map import LabelMap


def load_label_map(
    model_path: Optional[str] = None,
    config_labels: Optional[Sequence[str]] = None,
) -> LabelMap:
    """Nạp LabelMap theo thứ tự ưu tiên nguồn. Không nguồn nào → LabelMap.empty()."""
    if model_path:
        names = _read_names_sidecar(model_path)
        if names:
            return LabelMap.from_names(names)
        names = _read_onnx_metadata_names(model_path)
        if names:
            return LabelMap.from_names(names)
    if config_labels:
        return LabelMap.from_names(config_labels)
    return LabelMap.empty()


def _read_names_sidecar(model_path: str) -> Optional[list[str]]:
    """File `<stem>.names` cạnh model: 1 tên/dòng, bỏ dòng trống. Không có file → None."""
    sidecar = Path(model_path).with_suffix(".names")
    if not sidecar.is_file():
        return None
    lines = [ln.strip() for ln in sidecar.read_text(encoding="utf-8").splitlines()]
    names = [ln for ln in lines if ln]
    return names or None


def _read_onnx_metadata_names(model_path: str) -> Optional[list[str]]:
    """Đọc `names` nhúng trong metadata ONNX (best-effort). Bất kỳ lỗi/thiếu → None (fail-safe, không raise).

    Ultralytics export nhúng `metadata_props['names']` = repr của dict `{0:'person',1:'car',...}`.
    Chuyển dict (khoá int) → list theo thứ tự khoá tăng dần. Nếu là list sẵn → dùng luôn.
    """
    if not str(model_path).lower().endswith(".onnx"):
        return None
    try:
        import onnxruntime as ort

        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        raw = sess.get_modelmeta().custom_metadata_map.get("names")
        if not raw:
            return None
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, dict):
            return [str(parsed[k]) for k in sorted(parsed, key=int)]
        if isinstance(parsed, (list, tuple)):
            return [str(x) for x in parsed]
        return None
    except Exception:
        return None
