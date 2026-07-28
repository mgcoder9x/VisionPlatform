"""Test wire LabelMap vào decoder YOLO (spec image-preprocess-and-labeling, R1.5, Task 2).

Xác nhận: (a) id hợp lệ → canonical (bằng hành vi cũ khi labels đúng+đủ); (b) id NGOÀI phạm vi (labels/label_map
thiếu) → `class_<id>` (KHÔNG còn số trần); (c) tương thích ngược: truyền `labels` list vẫn chạy; (d) cả v8 lẫn v5.
"""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.adapters.yolo_postprocess import yolov5_decode, yolov8_decode
from vision_platform.kernel.label_map import LabelMap


def _v8_nc_first(anchors):
    arr = np.array(anchors, dtype=np.float32).T          # (4+nc, N)
    return [arr[np.newaxis, ...]]


def _v5(rows):
    return [np.array([rows], dtype=np.float32)]


def test_v8_label_map_valid_id_canonical():
    """label_map đủ → id hợp lệ ra canonical (bằng kết quả cũ khi labels đúng)."""
    raw = _v8_nc_first([[50, 50, 20, 20, 0.9, 0.1]])     # argmax=0
    lm = LabelMap.from_names(["car", "person"])
    d = yolov8_decode(raw, conf_threshold=0.25, label_map=lm)[0]
    assert d.label == "car"


def test_v8_label_map_out_of_range_class_id():
    """argmax vượt độ dài label_map → `class_<id>` (R1.2/R1.5), KHÔNG số trần."""
    # nc=3, argmax=2, nhưng label_map chỉ 2 tên → canonical(2) = "class_2"
    raw = _v8_nc_first([[50, 50, 20, 20, 0.1, 0.2, 0.9]])
    lm = LabelMap.from_names(["car", "person"])
    d = yolov8_decode(raw, conf_threshold=0.25, label_map=lm)[0]
    assert d.label == "class_2"


def test_v8_no_map_no_labels_is_class_id():
    """Không label_map, không labels → `class_<id>` (thay số trần cũ)."""
    raw = _v8_nc_first([[50, 50, 20, 20, 0.9, 0.1]])
    d = yolov8_decode(raw, conf_threshold=0.25)[0]
    assert d.label == "class_0"


def test_v8_backward_compat_labels_list():
    """Tương thích ngược: truyền `labels` list → id hợp lệ canonical; ngoài phạm vi → class_<id>."""
    raw = _v8_nc_first([
        [50, 50, 20, 20, 0.9, 0.1, 0.05],     # argmax=0 → car
        [80, 80, 10, 10, 0.1, 0.1, 0.9],      # argmax=2 → ngoài labels(2) → class_2
    ])
    dets = yolov8_decode(raw, conf_threshold=0.25, labels=["car", "person"])
    got = {d.label for d in dets}
    assert got == {"car", "class_2"}


def test_v8_label_map_takes_priority_over_labels():
    """Truyền cả label_map lẫn labels → label_map thắng."""
    raw = _v8_nc_first([[50, 50, 20, 20, 0.9, 0.1]])
    d = yolov8_decode(raw, conf_threshold=0.25,
                      labels=["WRONG"], label_map=LabelMap.from_names(["right", "x"]))[0]
    assert d.label == "right"


def test_v5_label_map_and_failsafe():
    """YOLOv5 decode cũng qua LabelMap: hợp lệ → canonical; ngoài phạm vi → class_<id>."""
    raw = _v5([
        [50, 50, 20, 20, 0.9, 0.8, 0.1, 0.05],   # obj0.9×cls0(0.8)=0.72 argmax=0 → dog
        [80, 80, 10, 10, 0.95, 0.1, 0.1, 0.9],   # argmax=2 ngoài map(2) → class_2
    ])
    lm = LabelMap.from_names(["dog", "cat"])
    dets = yolov5_decode(raw, conf_threshold=0.25, label_map=lm)
    assert {d.label for d in dets} == {"dog", "class_2"}


def test_v5_no_labels_class_id():
    raw = _v5([[50, 50, 20, 20, 0.9, 0.8, 0.1]])
    d = yolov5_decode(raw, conf_threshold=0.25)[0]
    assert d.label == "class_0"
