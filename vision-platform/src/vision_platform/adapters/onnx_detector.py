"""OnnxDetector — chạy inference model ONNX qua onnxruntime (sub-spec real-detector-integration, Phần B).

Layer: adapters (LEAF). `onnxruntime` là dep của adapter (đã cấm ở domain+kernel qua import-linter). Import
được domain + kernel. KHÔNG import runtime/application/profiles.

TRIẾT LÝ MODEL-AGNOSTIC (chống lệ thuộc + chống license bẩn): OnnxDetector CHỈ lo phần CHUNG cho mọi model
ONNX — nạp `InferenceSession`, chạy, trả raw output. Phần RIÊNG theo model (tiền xử lý HWC→NCHW/normalize,
parse output → Detection + NMS layout) TIÊM QUA DI (`preprocess_fn`, `postprocess_fn`). Nhờ vậy:
  - đổi model (YOLOv8/RTMDet/RT-DETR...) = đổi 2 hàm DI, KHÔNG sửa adapter;
  - VERIFY được ngay bằng model ONNX tí hon tự tạo (license sạch) — KHÔNG cần tải weight YOLO (AGPL, K-029).

⚠️ LICENSE (K-029 — điều nên biết cho sản phẩm thương mại): file này KHÔNG nhúng model cụ thể. YOLOv8/v11
(Ultralytics) là **AGPL-3.0** → dùng trong sản phẩm ĐÓNG thương mại phải mua license Ultralytics, hoặc chọn
model license thương-mại-thân-thiện (vd RTMDet Apache-2.0, RT-DETR Apache-2.0, YOLOX Apache-2.0). Việc chọn
model + weight là quyết định vận hành/pháp lý — KHÔNG hard-code ở đây.

Thoả `IDetector` (setup/detect/teardown) → cắm được vào `DetectorPipeline` (làm inner) để tự lo coordinate-transform.
`detect(frame)` nhận frame Ở MODEL_INPUT space (đã letterbox bởi DetectorPipeline) → trả Detection box MODEL_INPUT.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

import numpy as np

from vision_platform.kernel.inference_protocol import Detection


# Kiểu hàm DI (model-specific):
PreprocessFn = Callable[[np.ndarray], np.ndarray]           # frame MODEL_INPUT (H,W,C) → input tensor (vd NCHW float32)
PostprocessFn = Callable[[Sequence[np.ndarray]], list[Detection]]   # raw outputs → Detection (box MODEL_INPUT)


def chw_float_normalize(frame: np.ndarray) -> np.ndarray:
    """Tiền xử lý PHỔ BIẾN: HWC uint8 → NCHW float32 chia 255 (batch=1). Nhiều detector dùng layout này.

    Là 1 lựa chọn MẶC ĐỊNH tiện dụng — model khác layout (BGR/mean-std) thì tiêm preprocess_fn riêng.
    """
    if frame.ndim != 3:
        raise ValueError(f"chw_float_normalize cần (H,W,C), got ndim={frame.ndim}")
    arr = frame.astype(np.float32) / 255.0
    arr = np.transpose(arr, (2, 0, 1))          # HWC → CHW
    return arr[np.newaxis, ...]                  # → NCHW (batch=1)


def describe_onnx(model_path: str) -> dict:
    """In/đối chiếu I/O model ONNX (tên+shape+dtype input/output) — CHỐNG BỊA layout trước khi viết postprocess.

    Trả dict {inputs: [...], outputs: [...]}. Mỗi phần tử {name, shape, type}. Dùng khi user đưa weight thật để
    XÁC ĐỊNH layout (YOLOv8 [1,4+nc,N] vs YOLOv5 [1,N,5+nc] vs end2end [1,N,6]) + n_classes + input size.
    """
    import onnxruntime as ort

    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    def _io(x):
        return {"name": x.name, "shape": x.shape, "type": x.type}
    return {
        "inputs": [_io(i) for i in sess.get_inputs()],
        "outputs": [_io(o) for o in sess.get_outputs()],
    }


class OnnxDetector:
    """Generic ONNX detector. `preprocess_fn`/`postprocess_fn` model-specific (DI)."""

    def __init__(
        self,
        model_path: str,
        *,
        preprocess_fn: PreprocessFn,
        postprocess_fn: PostprocessFn,
        input_name: Optional[str] = None,
        providers: Sequence[str] = ("CPUExecutionProvider",),
        expected_input_size: Optional[int] = None,
    ):
        self._model_path = model_path
        self._preprocess = preprocess_fn
        self._postprocess = postprocess_fn
        self._input_name = input_name
        self._providers = list(providers)
        self._expected_input_size = expected_input_size
        self._session = None

    def setup(self) -> None:
        # Import onnxruntime BÊN TRONG setup (lazy) → import module không bắt buộc có onnxruntime
        # (base install không cần; chỉ khi THẬT SỰ dùng adapter này). Fail-fast rõ ràng nếu thiếu.
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise RuntimeError(
                "OnnxDetector cần onnxruntime — cài `pip install .[onnx]`"
            ) from e
        # D-098/K-088: nếu yêu cầu GPU (CUDA/TensorRT), làm DLL nvidia pip-wheels tìm-được TRƯỚC khi tạo session
        # (onnxruntime-gpu KHÔNG bundle CUDA; cần prepend PATH — add_dll_directory không đủ cho dep bắc-cầu).
        if any(("CUDA" in p) or ("Tensorrt" in p) for p in self._providers):
            from vision_platform.adapters.cuda_dll_path import ensure_cuda_dll_path
            ensure_cuda_dll_path()
        self._session = ort.InferenceSession(self._model_path, providers=self._providers)
        inp = self._session.get_inputs()[0]
        if self._input_name is None:
            self._input_name = inp.name
        self._assert_input_size(inp.shape)

    def _assert_input_size(self, shape) -> None:
        """Fail-fast: nếu model có H/W CỐ ĐỊNH khác `expected_input_size` → raise RÕ lúc setup
        (thay vì onnxruntime `InvalidArgument Got X Expected Y` tối nghĩa lúc run — verify empiric #395).
        Dynamic axis (dim là str/None/<=0) → KHÔNG chặn (model nhận đa kích thước)."""
        if self._expected_input_size is None or len(shape) < 4:
            return
        for axis in (2, 3):                     # NCHW → H=2, W=3
            dim = shape[axis]
            if isinstance(dim, int) and dim > 0 and dim != self._expected_input_size:
                raise ValueError(
                    f"OnnxDetector: model '{self._model_path}' input {shape} có H/W cố định = {dim} "
                    f"nhưng cấu hình model-size = {self._expected_input_size}. "
                    f"Re-export model đúng kích thước (hoặc export dynamic-axes), hoặc sửa --model-size.")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._session is None:
            raise RuntimeError("setup() phải gọi trước detect()")
        input_tensor = self._preprocess(frame)
        raw = self._session.run(None, {self._input_name: input_tensor})
        return self._postprocess(raw)

    def teardown(self) -> None:
        self._session = None      # giải phóng session (onnxruntime tự dọn khi GC)
