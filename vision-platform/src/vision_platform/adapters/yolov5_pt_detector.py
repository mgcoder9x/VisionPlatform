"""Yolov5PtDetector — chạy THẲNG weight YOLOv5 `.pt` (package `yolov5` + torch). Layer: adapters (leaf).

Vì sao adapter riêng (khác OnnxDetector): weight user là YOLOv5 `.pt` (PyTorch). Chạy trực tiếp = KHÔNG cần
export ONNX. Package `yolov5` (AutoShape) tự lo letterbox + NMS + rescale → trả box Ở TOẠ ĐỘ FRAME GỐC
(ORIGINAL_FRAME). Do đó adapter này là detector HOÀN CHỈNH — **KHÔNG bọc trong DetectorPipeline** (pipeline
kỳ vọng box MODEL_INPUT để inverse-transform; box ở đây đã ORIGINAL_FRAME rồi).

torch + yolov5 = dep NẶNG (chỉ có ở env cài, vd WSL ~/vpvenv) → import LAZY trong setup() (module import được
ở nơi không có torch; contract cấm torch/yolov5 ở domain+kernel). torch>=2.6 mặc định `weights_only=True` chặn
unpickle checkpoint → ép `weights_only=False` (file weight của user = tin cậy).

INVARIANT toạ độ (Step 02): box gắn CoordinateSpace.ORIGINAL_FRAME (đúng — yolov5 đã rescale về frame gốc).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection


class Yolov5PtDetector:
    def __init__(
        self,
        weights_path: str,
        *,
        device: str = "cpu",
        conf: float = 0.25,
        iou: float = 0.45,
    ):
        self._weights_path = weights_path
        self._device = device
        self._conf = conf
        self._iou = iou
        self._model = None

    def setup(self) -> None:
        import torch  # lazy: dep nặng

        # torch>=2.6: weights_only mặc định True → chặn DetectionModel. File user tin cậy → ép False.
        _orig_load = torch.load
        if getattr(_orig_load, "_vp_patched", False) is False:
            def _patched(*a, **k):
                k.setdefault("weights_only", False)
                return _orig_load(*a, **k)
            _patched._vp_patched = True
            torch.load = _patched

        import yolov5  # lazy

        # yolov5 select_device KHÔNG nhận "cuda" trần → chuẩn hóa: cuda/gpu → "cuda:0".
        dev = self._device
        if dev in ("cuda", "gpu"):
            dev = "cuda:0"
        model = yolov5.load(self._weights_path, device=dev)
        model.conf = self._conf
        model.iou = self._iou
        self._model = model

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._model is None:
            raise RuntimeError("setup() phải gọi trước detect()")
        results = self._model(frame)                 # AutoShape: letterbox+infer+NMS+rescale nội bộ
        pred = results.pred[0]                        # tensor [N,6]: x1,y1,x2,y2,conf,cls (ORIGINAL_FRAME)
        names = self._model.names
        dets: list[Detection] = []
        for row in pred.tolist():
            x1, y1, x2, y2, conf, cls = row
            label = names[int(cls)] if isinstance(names, (list, dict)) else str(int(cls))
            dets.append(
                Detection(
                    label=str(label),
                    confidence=float(conf),
                    box=BBox(x=float(x1), y=float(y1), w=float(x2 - x1), h=float(y2 - y1),
                             space=CoordinateSpace.ORIGINAL_FRAME),
                )
            )
        return dets

    def teardown(self) -> None:
        self._model = None
