"""IDetector — driven port cho object detection (cùng pattern IFrameSource, Step 03).

Layer: kernel/ports — Protocol thuần. Implementation (YOLO/RTMDet/Fake...) sống ở adapters/.
numpy được phép ở kernel (domain cũng dùng numpy; contract chỉ cấm cv2/torch/zmq/...).
"""
from typing import Protocol
import numpy as np

from vision_platform.kernel.inference_protocol import Detection


class IDetector(Protocol):
    """Detector interface.

    Contract:
        - setup() gọi trước detect() đầu tiên (nạp model/weights). Idempotent.
        - detect(frame) trả list[Detection]; box ở space detector khai báo (thường MODEL_INPUT).
        - teardown() giải phóng tài nguyên (GPU/model). Idempotent.
    """
    def detect(self, frame: np.ndarray) -> list[Detection]: ...

    def setup(self) -> None: ...

    def teardown(self) -> None: ...
