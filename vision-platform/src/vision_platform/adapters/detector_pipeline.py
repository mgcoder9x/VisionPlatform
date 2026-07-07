"""DetectorPipeline — biến MỌI IDetector (trả box MODEL_INPUT) thành detector trả box ORIGINAL_FRAME.

Layer: adapters (LEAF, Decorator over IDetector). Chỉ import domain (BBox/LetterboxTransform/nms) + kernel
(Detection). `inner` detector TIÊM qua DI (kiểu port `IDetector` — KHÔNG import adapter cụ thể). Pixel-resize
là chiến lược TIÊM (`resize_fn`) → phần A verify bằng numpy thuần; phần B thay bằng cv2/onnx-preprocess mà
KHÔNG đụng logic toạ độ. Chính pipeline cũng thoả `IDetector` → cắm thẳng vào InferenceServer.

BẢN CHẤT (đóng bug production #1): frame gốc → letterbox về input model → inner.detect (box MODEL_INPUT) →
`LetterboxTransform.inverse_box` đưa MỖI box về ORIGINAL_FRAME → (tuỳ chọn) NMS → trả. Downstream luôn nhận
toạ độ đúng frame gốc.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Optional

import numpy as np

from vision_platform.domain.letterbox_transform import LetterboxTransform
from vision_platform.domain.nms import nms_indices
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.ports.detector import IDetector


def letterbox_resize_np(frame: np.ndarray, t: LetterboxTransform, *, pad_value: int = 114) -> np.ndarray:
    """Letterbox resize THUẦN NUMPY (nearest-neighbor + pad) → mảng (model_h, model_w, C).

    Nearest-neighbor đủ cho phần A (verify logic toạ độ, KHÔNG phụ thuộc chất lượng nội suy). Phần B (model
    thật) có thể thay bằng cv2.resize/onnx-preprocess (bilinear) — chỉ đổi hàm này, toạ độ vẫn do LetterboxTransform.
    """
    if frame.ndim != 3:
        raise ValueError(f"letterbox_resize_np cần frame (H,W,C), got ndim={frame.ndim}")
    oh, ow, c = frame.shape
    if oh != t.orig_h or ow != t.orig_w:
        raise ValueError(f"frame ({oh},{ow}) khác transform orig ({t.orig_h},{t.orig_w})")
    cw_i = max(1, int(round(ow * t.scale)))
    ch_i = max(1, int(round(oh * t.scale)))
    # Chỉ số nearest-neighbor (map pixel đích → nguồn).
    ys = np.clip((np.arange(ch_i) / t.scale).astype(np.int64), 0, oh - 1)
    xs = np.clip((np.arange(cw_i) / t.scale).astype(np.int64), 0, ow - 1)
    content = frame[ys][:, xs]                              # (ch_i, cw_i, C)
    out = np.full((t.model_h, t.model_w, c), pad_value, dtype=frame.dtype)
    px = (t.model_w - cw_i) // 2
    py = (t.model_h - ch_i) // 2
    out[py:py + ch_i, px:px + cw_i] = content
    return out


class DetectorPipeline:
    """Decorator over IDetector: preprocessing (letterbox) + inner.detect + inverse-transform (+ NMS)."""

    def __init__(
        self,
        inner: IDetector,
        model_h: int,
        model_w: int,
        *,
        resize_fn: Callable[[np.ndarray, LetterboxTransform], np.ndarray] = letterbox_resize_np,
        nms_iou: Optional[float] = None,
    ):
        self._inner = inner
        self._model_h = model_h
        self._model_w = model_w
        self._resize_fn = resize_fn
        self._nms_iou = nms_iou

    def setup(self) -> None:
        self._inner.setup()

    def teardown(self) -> None:
        self._inner.teardown()

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        t = LetterboxTransform(orig_h=h, orig_w=w, model_h=self._model_h, model_w=self._model_w)
        model_input = self._resize_fn(frame, t)
        raw = self._inner.detect(model_input)                       # box MODEL_INPUT
        dets = [replace(d, box=t.inverse_box(d.box)) for d in raw]   # → ORIGINAL_FRAME
        if self._nms_iou is not None and dets:
            keep = nms_indices(
                [d.box for d in dets],
                [d.confidence for d in dets],
                self._nms_iou,
                labels=[d.label for d in dets],
            )
            dets = [dets[i] for i in keep]
        return dets
