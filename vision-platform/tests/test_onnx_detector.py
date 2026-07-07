"""Test OnnxDetector (sub-spec real-detector-integration, Phần B, R3).

Verify BẰNG model ONNX TÍ HON tự tạo (license sạch, KHÔNG tải weight YOLO/AGPL — K-029): chứng minh adapter
nạp session + chạy + preprocess/postprocess DI hoạt động THẬT, và ghép được vào DetectorPipeline (Phần A).

Guard skip nếu thiếu onnxruntime/onnx (base install không bắt buộc — optional dep `.[onnx]`).
"""
from __future__ import annotations

import numpy as np
import pytest

onnx = pytest.importorskip("onnx", reason="cần optional dep onnx (.[onnx])")
ort = pytest.importorskip("onnxruntime", reason="cần optional dep onnxruntime (.[onnx])")

from onnx import helper, TensorProto  # noqa: E402

from vision_platform.domain.bbox import BBox, CoordinateSpace  # noqa: E402
from vision_platform.kernel.inference_protocol import Detection  # noqa: E402
from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize  # noqa: E402
from vision_platform.adapters.detector_pipeline import DetectorPipeline  # noqa: E402


def _make_identity_model(path: str, c: int = 3, h: int = 8, w: int = 8) -> None:
    """Tạo model ONNX Identity [1,c,h,w]→[1,c,h,w] (tí hon, license sạch)."""
    x = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, c, h, w])
    y = helper.make_tensor_value_info("out", TensorProto.FLOAT, [1, c, h, w])
    node = helper.make_node("Identity", ["images"], ["out"])
    graph = helper.make_graph([node], "identity_det", [x], [y])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    onnx.save(model, path)


def _fixed_postprocess(raw):
    """Postprocess giả: confidence = mean của raw output (chứng minh DATA chảy qua session)."""
    conf = float(np.asarray(raw[0]).mean())
    return [Detection("object", conf, BBox(2, 2, 4, 4, CoordinateSpace.MODEL_INPUT))]


def test_chw_float_normalize_shape_and_scale():
    frame = np.full((8, 8, 3), 255, dtype=np.uint8)
    out = chw_float_normalize(frame)
    assert out.shape == (1, 3, 8, 8)
    assert out.dtype == np.float32
    assert out.max() == pytest.approx(1.0)


def test_onnx_detector_runs_real_session(tmp_path):
    """Nạp model ONNX + chạy session THẬT → Detection; confidence phản ánh input (data chảy qua)."""
    model_path = str(tmp_path / "identity.onnx")
    _make_identity_model(model_path)
    det = OnnxDetector(model_path, preprocess_fn=chw_float_normalize, postprocess_fn=_fixed_postprocess)
    det.setup()
    try:
        frame = np.full((8, 8, 3), 255, dtype=np.uint8)   # normalize → 1.0 → mean 1.0
        out = det.detect(frame)
    finally:
        det.teardown()
    assert len(out) == 1
    assert out[0].box.space == CoordinateSpace.MODEL_INPUT
    assert out[0].confidence == pytest.approx(1.0)


def test_onnx_detector_detect_before_setup_fails(tmp_path):
    model_path = str(tmp_path / "identity.onnx")
    _make_identity_model(model_path)
    det = OnnxDetector(model_path, preprocess_fn=chw_float_normalize, postprocess_fn=_fixed_postprocess)
    with pytest.raises(RuntimeError, match="setup"):
        det.detect(np.zeros((8, 8, 3), dtype=np.uint8))


def test_onnx_detector_in_pipeline_returns_original_frame(tmp_path):
    """Ghép Phần A + B: OnnxDetector làm inner của DetectorPipeline → box ra ORIGINAL_FRAME."""
    model_path = str(tmp_path / "identity.onnx")
    _make_identity_model(model_path, h=8, w=8)
    inner = OnnxDetector(model_path, preprocess_fn=chw_float_normalize, postprocess_fn=_fixed_postprocess)
    pipe = DetectorPipeline(inner, model_h=8, model_w=8)
    pipe.setup()
    try:
        frame = np.full((16, 32, 3), 128, dtype=np.uint8)   # frame gốc khác model size
        dets = pipe.detect(frame)
    finally:
        pipe.teardown()
    assert len(dets) == 1
    assert dets[0].box.space == CoordinateSpace.ORIGINAL_FRAME
