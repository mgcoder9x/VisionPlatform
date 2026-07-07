"""BrightBlobDetector — detector CV cổ điển đơn giản: khoanh vùng SÁNG (sub-spec real-detector, demo).

Layer: adapters (LEAF). THUẦN numpy + domain(BBox) + kernel(Detection). KHÔNG cv2/onnx.

Mục đích: cho app demo có "nhận diện THẬT" (box BÁM vật sáng di chuyển) mà KHÔNG cần weight YOLO — minh hoạ
luồng camera→detect→vẽ-box trực quan. Thoả `IDetector` → cắm thẳng vào `DetectorPipeline` như mọi detector.
Khi có YOLO: đổi sang `OnnxDetector`+`yolov8_decode`, app giữ nguyên.

Thuật toán (đơn giản, deterministic → verify được): ngưỡng độ sáng → bounding-box bao mọi pixel sáng.
"""
from __future__ import annotations

import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection


class BrightBlobDetector:
    """Detect vùng sáng > ngưỡng, trả 1 Detection bao quanh (box MODEL_INPUT). Rỗng nếu không có vùng sáng."""

    def __init__(self, threshold: int = 127, label: str = "bright"):
        self._threshold = threshold
        self._label = label
        self._is_setup = False

    def setup(self) -> None:
        self._is_setup = True

    def teardown(self) -> None:
        self._is_setup = False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if not self._is_setup:
            raise RuntimeError("setup() phải gọi trước detect()")
        gray = frame.mean(axis=2) if frame.ndim == 3 else frame
        mask = gray > self._threshold
        if not mask.any():
            return []
        ys, xs = np.nonzero(mask)
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        confidence = float(mask.mean())          # tỉ lệ pixel sáng (0..1) — "độ mạnh" tín hiệu
        return [
            Detection(
                label=self._label,
                confidence=confidence,
                box=BBox(x=float(x0), y=float(y0), w=float(x1 - x0), h=float(y1 - y0),
                         space=CoordinateSpace.MODEL_INPUT),
            )
        ]
