"""Test yolov8_decode (sub-spec real-detector-integration, Phần C, Property C1).

Decode = thuần numpy → test bằng TENSOR TỔNG HỢP (không cần weight thật). + 1 test tích hợp: model ONNX stub
xuất shape kiểu YOLOv8 → OnnxDetector → yolov8_decode → DetectorPipeline (box ra ORIGINAL_FRAME).
"""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.domain.bbox import CoordinateSpace
from vision_platform.adapters.yolo_postprocess import yolov8_decode


def _make_nc_first(anchors):
    """anchors = list [cx,cy,w,h,*class_scores] → array [1, 4+nc, N] (layout YOLOv8)."""
    arr = np.array(anchors, dtype=np.float32).T          # (4+nc, N)
    return [arr[np.newaxis, ...]]                         # [1, 4+nc, N]


def test_decode_filters_by_confidence():
    """3 anchor: 2 trên ngưỡng, 1 dưới → 2 Detection."""
    raw = _make_nc_first([
        [50, 50, 20, 20, 0.9, 0.1],   # cls0 conf0.9
        [10, 10, 4, 4, 0.10, 0.10],   # dưới ngưỡng → bỏ
        [80, 80, 10, 10, 0.2, 0.8],   # cls1 conf0.8
    ])
    dets = yolov8_decode(raw, conf_threshold=0.25, labels=["car", "person"])
    assert len(dets) == 2
    assert {d.label for d in dets} == {"car", "person"}


def test_decode_xywh_to_topleft():
    """box [cx,cy,w,h] → BBox top-left (cx−w/2, cy−h/2) ở MODEL_INPUT."""
    raw = _make_nc_first([[50, 60, 20, 40, 0.9, 0.1]])
    d = yolov8_decode(raw, conf_threshold=0.25)[0]
    assert d.box.space == CoordinateSpace.MODEL_INPUT
    assert (d.box.x, d.box.y, d.box.w, d.box.h) == pytest.approx((40.0, 40.0, 20.0, 40.0))
    assert d.confidence == pytest.approx(0.9)
    assert d.label == "0"                 # không truyền labels → dùng chỉ số class


def test_decode_nc_last_layout():
    """layout nc_last: raw [1, N, 4+nc] không transpose."""
    arr = np.array([[50, 50, 20, 20, 0.9, 0.1]], dtype=np.float32)   # (N=1, 4+nc=6)
    raw = [arr[np.newaxis, ...]]
    dets = yolov8_decode(raw, conf_threshold=0.25, layout="nc_last")
    assert len(dets) == 1
    assert dets[0].box.x == pytest.approx(40.0)


def test_decode_all_below_threshold_empty():
    raw = _make_nc_first([[50, 50, 20, 20, 0.1, 0.05]])
    assert yolov8_decode(raw, conf_threshold=0.25) == []


def test_decode_invalid_layout_raises():
    raw = _make_nc_first([[50, 50, 20, 20, 0.9, 0.1]])
    with pytest.raises(ValueError, match="layout"):
        yolov8_decode(raw, layout="weird")


def test_decode_highest_class_wins():
    """nc=3: argmax chọn đúng lớp + conf = max score."""
    raw = _make_nc_first([[30, 30, 10, 10, 0.2, 0.7, 0.5]])
    d = yolov8_decode(raw, conf_threshold=0.25, labels=["a", "b", "c"])[0]
    assert d.label == "b"
    assert d.confidence == pytest.approx(0.7)


# ---------------- yolov5_decode (có objectness) ----------------

def _make_v5(rows):
    """rows = list [cx,cy,w,h,obj,*class] → array [1, N, 5+nc] (layout YOLOv5)."""
    return [np.array([rows], dtype=np.float32)]


def test_v5_conf_is_obj_times_class():
    """YOLOv5: conf = objectness × max(class). row obj0.9×cls0.8=0.72."""
    from vision_platform.adapters.yolo_postprocess import yolov5_decode
    raw = _make_v5([
        [50, 50, 20, 20, 0.9, 0.8, 0.1],   # conf 0.72, cls0
        [10, 10, 4, 4, 0.2, 0.5, 0.5],     # conf 0.10 → dưới ngưỡng
        [80, 80, 10, 10, 0.95, 0.2, 0.9],  # conf 0.855, cls1
    ])
    dets = yolov5_decode(raw, conf_threshold=0.25, labels=["car", "person"])
    assert len(dets) == 2
    d0 = [d for d in dets if d.label == "car"][0]
    assert d0.confidence == pytest.approx(0.72)
    assert (d0.box.x, d0.box.y, d0.box.w, d0.box.h) == pytest.approx((40.0, 40.0, 20.0, 20.0))
    assert d0.box.space == CoordinateSpace.MODEL_INPUT


def test_v5_all_below_threshold_empty():
    from vision_platform.adapters.yolo_postprocess import yolov5_decode
    raw = _make_v5([[50, 50, 20, 20, 0.2, 0.5, 0.5]])   # conf 0.10
    assert yolov5_decode(raw, conf_threshold=0.25) == []


def test_v5_bad_shape_raises():
    from vision_platform.adapters.yolo_postprocess import yolov5_decode
    with pytest.raises(ValueError, match="yolov5"):
        yolov5_decode([np.zeros((1, 3, 4), dtype=np.float32)])   # <6 cột (thiếu obj+class)


# ---------------- Tích hợp: ONNX stub (shape YOLOv8) → OnnxDetector → yolov8_decode → DetectorPipeline ----------------

onnx = pytest.importorskip("onnx", reason="cần optional dep onnx (.[onnx])")
ort = pytest.importorskip("onnxruntime", reason="cần optional dep onnxruntime (.[onnx])")

from onnx import helper, TensorProto  # noqa: E402

from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize, describe_onnx  # noqa: E402
from vision_platform.adapters.detector_pipeline import DetectorPipeline  # noqa: E402


def _make_yolo_stub_model(path: str, model_hw: int = 8):
    """Model ONNX stub: input [1,3,hw,hw] (bỏ qua) → output Constant [1,6,3] kiểu YOLOv8 (nc=2, 3 anchor)."""
    val = np.zeros((1, 6, 3), dtype=np.float32)
    # anchor0: box center (4,4) size (4,4), cls0 conf 0.9
    val[0, :, 0] = [4, 4, 4, 4, 0.9, 0.1]
    # anchor1: dưới ngưỡng
    val[0, :, 1] = [1, 1, 1, 1, 0.05, 0.05]
    # anchor2: box center (6,6) size (2,2), cls1 conf 0.7
    val[0, :, 2] = [6, 6, 2, 2, 0.1, 0.7]
    const = helper.make_tensor("cval", TensorProto.FLOAT, [1, 6, 3], val.flatten().tolist())
    node = helper.make_node("Constant", [], ["output"], value=const)
    x = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, model_hw, model_hw])
    y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 6, 3])
    model = helper.make_model(helper.make_graph([node], "yolo_stub", [x], [y]),
                              opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    onnx.save(model, path)


def test_describe_onnx_reports_io(tmp_path):
    path = str(tmp_path / "stub.onnx")
    _make_yolo_stub_model(path)
    desc = describe_onnx(path)
    assert desc["inputs"][0]["name"] == "images"
    assert desc["outputs"][0]["shape"] == [1, 6, 3]


def test_yolo_stub_full_chain_original_frame(tmp_path):
    """ONNX stub (shape YOLOv8) → OnnxDetector + yolov8_decode → DetectorPipeline → box ORIGINAL_FRAME."""
    path = str(tmp_path / "stub.onnx")
    _make_yolo_stub_model(path, model_hw=8)

    def _post(raw):
        return yolov8_decode(raw, conf_threshold=0.25, labels=["car", "person"])

    inner = OnnxDetector(path, preprocess_fn=chw_float_normalize, postprocess_fn=_post)
    pipe = DetectorPipeline(inner, model_h=8, model_w=8, nms_iou=0.5)
    pipe.setup()
    try:
        frame = np.full((16, 16, 3), 120, dtype=np.uint8)   # frame gốc 16×16 (model 8×8 → scale 0.5)
        dets = pipe.detect(frame)
    finally:
        pipe.teardown()
    assert len(dets) == 2                                    # 2 anchor trên ngưỡng
    assert all(d.box.space == CoordinateSpace.ORIGINAL_FRAME for d in dets)


def _make_v5_stub_model(path: str, model_hw: int = 8):
    """Model ONNX stub: input [1,3,hw,hw] → output Constant [1,3,7] kiểu YOLOv5 (nc=2, 3 anchor, có objectness)."""
    val = np.zeros((1, 3, 7), dtype=np.float32)
    val[0, 0] = [4, 4, 4, 4, 0.9, 0.8, 0.1]    # conf 0.72, cls0
    val[0, 1] = [1, 1, 1, 1, 0.1, 0.1, 0.1]    # conf 0.01 → bỏ
    val[0, 2] = [6, 6, 2, 2, 0.9, 0.1, 0.9]    # conf 0.81, cls1
    const = helper.make_tensor("cval", TensorProto.FLOAT, [1, 3, 7], val.flatten().tolist())
    node = helper.make_node("Constant", [], ["output"], value=const)
    x = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, model_hw, model_hw])
    y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3, 7])
    model = helper.make_model(helper.make_graph([node], "yolov5_stub", [x], [y]),
                              opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    onnx.save(model, path)


def test_yolov5_stub_full_chain_original_frame(tmp_path):
    """ONNX stub (shape YOLOv5, có objectness) → OnnxDetector + yolov5_decode → DetectorPipeline → ORIGINAL_FRAME."""
    from vision_platform.adapters.yolo_postprocess import yolov5_decode
    path = str(tmp_path / "v5stub.onnx")
    _make_v5_stub_model(path, model_hw=8)

    def _post(raw):
        return yolov5_decode(raw, conf_threshold=0.25, labels=["car", "person"])

    inner = OnnxDetector(path, preprocess_fn=chw_float_normalize, postprocess_fn=_post)
    pipe = DetectorPipeline(inner, model_h=8, model_w=8, nms_iou=0.5)
    pipe.setup()
    try:
        dets = pipe.detect(np.full((16, 16, 3), 128, dtype=np.uint8))
    finally:
        pipe.teardown()
    assert len(dets) == 2
    assert all(d.box.space == CoordinateSpace.ORIGINAL_FRAME for d in dets)
