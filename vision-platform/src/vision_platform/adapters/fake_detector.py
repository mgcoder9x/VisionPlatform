"""FakeDetector — adapter detector giả, deterministic theo frame (không cần GPU/model thật).

Layer: adapters (LEAF). Chỉ import domain (BBox/CoordinateSpace) + kernel (Detection) — hợp lệ
contract "Adapters la leaf" (cấm import runtime/application/profiles). Dùng cho dev/test.

Logic giả: 1 detection/frame, label='object', confidence = brightness/255 (deterministic → test
verify được). Box ở MODEL_INPUT space (toạ độ trên frame detector nhận vào — invariant Step 02).
"""
import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection


class FakeDetector:
    def __init__(self) -> None:
        self._is_setup = False

    def setup(self) -> None:
        self._is_setup = True

    def teardown(self) -> None:
        self._is_setup = False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # Fail-fast: quên setup() = lỗi cấu hình, phải nổ ngay (không detect ngầm).
        if not self._is_setup:
            raise RuntimeError("setup() must be called before detect()")

        h, w = frame.shape[:2]
        brightness = float(frame.mean())

        return [
            Detection(
                label="object",
                confidence=brightness / 255.0,
                box=BBox(
                    x=w * 0.25,
                    y=h * 0.25,
                    w=w * 0.5,
                    h=h * 0.5,
                    space=CoordinateSpace.MODEL_INPUT,
                ),
            )
        ]
