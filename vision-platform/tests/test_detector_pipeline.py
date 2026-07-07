"""Test DetectorPipeline + NMS (sub-spec real-detector-integration, Property 2 R2 + Q2).

- Pipeline với FakeDetector (model 640×640) → box ra ORIGINAL_FRAME đúng vị trí + space.
- NMS: nms_indices trực tiếp + pipeline áp NMS khử box chồng lấn.
"""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.nms import iou, nms_indices
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.adapters.fake_detector import FakeDetector
from vision_platform.adapters.detector_pipeline import DetectorPipeline, letterbox_resize_np
from vision_platform.domain.letterbox_transform import LetterboxTransform


# ---------------- DetectorPipeline (Property 2) ----------------

def test_pipeline_returns_original_frame_space():
    """FakeDetector trả box MODEL_INPUT → pipeline PHẢI trả box ORIGINAL_FRAME."""
    frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
    pipe = DetectorPipeline(FakeDetector(), model_h=640, model_w=640)
    pipe.setup()
    try:
        dets = pipe.detect(frame)
    finally:
        pipe.teardown()
    assert len(dets) == 1
    assert dets[0].box.space == CoordinateSpace.ORIGINAL_FRAME


def test_pipeline_inverse_position_correct():
    """Vị trí box sau inverse khớp giá trị tính tay (frame 1280×720, model 640×640)."""
    frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
    pipe = DetectorPipeline(FakeDetector(), model_h=640, model_w=640)
    pipe.setup()
    try:
        det = pipe.detect(frame)[0]
    finally:
        pipe.teardown()
    # FakeDetector: box MODEL_INPUT (160,160,320,320) → ORIGINAL (320,40,640,640).
    assert (det.box.x, det.box.y, det.box.w, det.box.h) == pytest.approx((320.0, 40.0, 640.0, 640.0))


def test_letterbox_resize_shape_and_pad():
    """letterbox_resize_np trả đúng (model_h,model_w,C) + vùng pad có giá trị pad_value."""
    frame = np.full((720, 1280, 3), 200, dtype=np.uint8)
    t = LetterboxTransform(orig_h=720, orig_w=1280, model_h=640, model_w=640)
    out = letterbox_resize_np(frame, t, pad_value=114)
    assert out.shape == (640, 640, 3)
    # pad_y=140 → hàng đầu (trong vùng pad trên) phải = 114.
    assert int(out[0, 320, 0]) == 114
    # giữa khung (trong vùng nội dung) = 200.
    assert int(out[320, 320, 0]) == 200


def test_letterbox_resize_rejects_2d():
    t = LetterboxTransform(orig_h=10, orig_w=10, model_h=8, model_w=8)
    with pytest.raises(ValueError, match="H,W,C"):
        letterbox_resize_np(np.zeros((10, 10), dtype=np.uint8), t)


# ---------------- NMS (Q2) ----------------

def _b(x, y, w, h):
    return BBox(x=x, y=y, w=w, h=h, space=CoordinateSpace.ORIGINAL_FRAME)


def test_iou_identical_is_one():
    assert iou(_b(0, 0, 10, 10), _b(0, 0, 10, 10)) == pytest.approx(1.0)


def test_iou_disjoint_is_zero():
    assert iou(_b(0, 0, 10, 10), _b(100, 100, 10, 10)) == 0.0


def test_iou_different_space_fails():
    a = _b(0, 0, 10, 10)
    b = BBox(x=0, y=0, w=10, h=10, space=CoordinateSpace.MODEL_INPUT)
    with pytest.raises(ValueError, match="cùng space"):
        iou(a, b)


def test_nms_suppresses_overlap_same_label():
    """2 box chồng lấn CÙNG label → giữ 1 (confidence cao hơn); 1 box xa → giữ."""
    boxes = [_b(0, 0, 10, 10), _b(1, 1, 10, 10), _b(100, 100, 10, 10)]
    scores = [0.9, 0.8, 0.7]
    labels = ["car", "car", "car"]
    keep = nms_indices(boxes, scores, iou_threshold=0.5, labels=labels)
    assert keep == [0, 2]           # index1 bị bỏ (IoU cao với index0)


def test_nms_keeps_overlap_different_label():
    """2 box chồng lấn KHÁC label → giữ cả 2 (NMS per-class)."""
    boxes = [_b(0, 0, 10, 10), _b(1, 1, 10, 10)]
    scores = [0.9, 0.8]
    labels = ["car", "person"]
    keep = nms_indices(boxes, scores, iou_threshold=0.5, labels=labels)
    assert keep == [0, 1]


def test_nms_length_mismatch_fails():
    with pytest.raises(ValueError, match="cùng độ dài"):
        nms_indices([_b(0, 0, 1, 1)], [0.5, 0.6], 0.5)


class _TwoBoxInner:
    """Inner detector giả trả 2 box chồng lấn cùng label (MODEL_INPUT) — test pipeline áp NMS."""
    def setup(self): ...
    def teardown(self): ...
    def detect(self, frame):
        return [
            Detection("car", 0.9, BBox(100, 100, 50, 50, CoordinateSpace.MODEL_INPUT)),
            Detection("car", 0.6, BBox(102, 102, 50, 50, CoordinateSpace.MODEL_INPUT)),
        ]


def test_pipeline_applies_nms():
    """Pipeline với nms_iou → khử box chồng lấn (2→1)."""
    frame = np.full((640, 640, 3), 50, dtype=np.uint8)
    pipe = DetectorPipeline(_TwoBoxInner(), model_h=640, model_w=640, nms_iou=0.5)
    pipe.setup()
    dets = pipe.detect(frame)
    pipe.teardown()
    assert len(dets) == 1
    assert dets[0].confidence == pytest.approx(0.9)   # giữ box confidence cao


def test_pipeline_without_nms_keeps_all():
    frame = np.full((640, 640, 3), 50, dtype=np.uint8)
    pipe = DetectorPipeline(_TwoBoxInner(), model_h=640, model_w=640)
    pipe.setup()
    dets = pipe.detect(frame)
    pipe.teardown()
    assert len(dets) == 2
