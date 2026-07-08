"""FakeDetector — adapter detector giả, deterministic theo frame (không cần GPU/model thật).

Layer: adapters (LEAF). Chỉ import domain (BBox/CoordinateSpace) + kernel (Detection) — hợp lệ
contract "Adapters la leaf" (cấm import runtime/application/profiles). Dùng cho dev/test.

Logic giả: 1 detection/frame, label='object', confidence = brightness/255 (deterministic → test
verify được). Box ở MODEL_INPUT space (toạ độ trên frame detector nhận vào — invariant Step 02).

`delay_s` (spec backpressure-cross-process, task 2.1, R7.3): độ trễ giả lập MỖI lần `detect()`
để mô phỏng detector CHẬM → dùng dựng cảnh quá tải TẤT YẾU cho test backpressure cross-process.
Mặc định 0.0 → hành vi cũ KHÔNG đổi (mọi call `FakeDetector()` hiện có giữ nguyên).
"""
import time

import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection


class FakeDetector:
    def __init__(self, *, delay_s: float = 0.0) -> None:
        self._is_setup = False
        self._delay_s = delay_s

    def setup(self) -> None:
        self._is_setup = True

    def teardown(self) -> None:
        self._is_setup = False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # Fail-fast: quên setup() = lỗi cấu hình, phải nổ ngay (không detect ngầm).
        if not self._is_setup:
            raise RuntimeError("setup() must be called before detect()")

        # Giả lập detector chậm (task 2.1): sleep TRƯỚC khi trả kết quả.
        if self._delay_s > 0:
            time.sleep(self._delay_s)

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
