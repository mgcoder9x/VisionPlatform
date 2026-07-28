"""YOLO postprocess — decode raw output ONNX → list[Detection] (box MODEL_INPUT). Layer: adapters.

Thuần numpy + domain(BBox) + kernel(Detection) → hợp lệ leaf. Dùng làm `postprocess_fn` tiêm vào `OnnxDetector`.
NMS + inverse-transform (MODEL_INPUT→ORIGINAL_FRAME) do `DetectorPipeline` lo (bọc ngoài OnnxDetector).

⚠️ CHỐNG BỊA (điều nên biết): layout output YOLO KHÔNG đồng nhất giữa các phiên bản/cách export:
- YOLOv8/v11 raw:  [1, 4+nc, N]  box[cx,cy,w,h] MODEL_INPUT px, KHÔNG objectness (conf = max class score).
- YOLOv5 raw:      [1, N, 5+nc]  có objectness (conf = obj × class).
- End2end (NMS nhúng): [1, N, 6] = [x1,y1,x2,y2,conf,cls] → KHÔNG cần decode này.
File này decode YOLOv8 raw (phổ biến). TRƯỚC khi tin trên weight THẬT: `describe_onnx()` đối chiếu shape output.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.label_map import LabelMap


def _resolve_label_map(
    label_map: Optional[LabelMap], labels: Optional[Sequence[str]]
) -> LabelMap:
    """1 nguồn resolve nhãn (R1.5): ưu tiên `label_map` → `labels` (compat) → rỗng.

    Thay biểu thức cũ `labels[cid] if ... else str(cid)` bằng LabelMap fail-safe: id ngoài phạm vi → `class_<id>`
    (KHÔNG số trần mơ hồ, KHÔNG gán nhầm tên lớp khác âm thầm). Giữ tương thích: caller truyền `labels` list vẫn chạy.
    """
    if label_map is not None:
        return label_map
    if labels is not None:
        return LabelMap.from_names(labels)
    return LabelMap.empty()


def yolov5_decode(
    raw: Sequence[np.ndarray],
    *,
    conf_threshold: float = 0.25,
    labels: Optional[Sequence[str]] = None,
    label_map: Optional[LabelMap] = None,
) -> list[Detection]:
    """Decode output YOLOv5 raw → list[Detection] (box MODEL_INPUT, chưa NMS/chưa inverse-transform).

    YOLOv5 ONNX (export chuẩn, Detect layer đã áp sigmoid + giải anchor): shape `[1, N, 5+nc]` (vd COCO
    `[1, 25200, 85]`). Mỗi hàng = `[cx, cy, w, h, objectness, class_0..class_{nc-1}]` (pixel MODEL_INPUT).
    KHÁC YOLOv8 (v8 KHÔNG có objectness): **conf = objectness × max(class_score)** (v5); label = argmax class.
    [độ chắc: cao — layout export chuẩn yolov5; XÁC NHẬN lại bằng describe_onnx trên file thật trước khi tin số].
    """
    out = np.asarray(raw[0])
    if out.ndim == 3:
        out = out[0]                        # (N, 5+nc)
    if out.ndim != 2 or out.shape[1] < 6:
        raise ValueError(f"output yolov5 phải (N, 5+nc>=1), got shape {out.shape}")

    boxes = out[:, :4]                      # cx, cy, w, h
    obj = out[:, 4]                         # objectness
    class_scores = out[:, 5:]               # (N, nc)
    cls_ids = np.argmax(class_scores, axis=1)
    conf = obj * class_scores[np.arange(class_scores.shape[0]), cls_ids]   # v5: obj × class

    keep = conf >= conf_threshold
    lm = _resolve_label_map(label_map, labels)
    dets: list[Detection] = []
    for i in np.nonzero(keep)[0]:
        cx, cy, bw, bh = (float(v) for v in boxes[i])
        cid = int(cls_ids[i])
        label = lm.canonical(cid)
        dets.append(
            Detection(
                label=label,
                confidence=float(conf[i]),
                box=BBox(x=cx - bw / 2.0, y=cy - bh / 2.0, w=bw, h=bh, space=CoordinateSpace.MODEL_INPUT),
            )
        )
    return dets


def yolov8_decode(
    raw: Sequence[np.ndarray],
    *,
    conf_threshold: float = 0.25,
    labels: Optional[Sequence[str]] = None,
    label_map: Optional[LabelMap] = None,
    layout: str = "nc_first",
) -> list[Detection]:
    """Decode output YOLOv8 raw → list[Detection] (box MODEL_INPUT, chưa NMS/chưa inverse-transform).

    - `layout="nc_first"` (mặc định YOLOv8): raw[0] shape [1, 4+nc, N] → transpose → [N, 4+nc].
    - `layout="nc_last"`: raw[0] shape [1, N, 4+nc] (đã đúng thứ tự).
    - box = [cx, cy, w, h] MODEL_INPUT pixel; conf = max class score (v8 không có objectness); label = argmax.
    """
    out = np.asarray(raw[0])
    if out.ndim == 3:
        out = out[0]                      # bỏ batch → (4+nc, N) hoặc (N, 4+nc)
    if layout == "nc_first":
        out = out.T                       # (4+nc, N) → (N, 4+nc)
    elif layout != "nc_last":
        raise ValueError(f"layout phải 'nc_first' hoặc 'nc_last', got {layout!r}")

    if out.ndim != 2 or out.shape[1] < 5:
        raise ValueError(f"output decode phải (N, 4+nc>=1), got shape {out.shape}")

    boxes = out[:, :4]                    # cx, cy, w, h
    class_scores = out[:, 4:]             # (N, nc)
    cls_ids = np.argmax(class_scores, axis=1)
    confs = class_scores[np.arange(class_scores.shape[0]), cls_ids]

    keep = confs >= conf_threshold
    lm = _resolve_label_map(label_map, labels)
    dets: list[Detection] = []
    for i in np.nonzero(keep)[0]:
        cx, cy, bw, bh = (float(v) for v in boxes[i])
        cid = int(cls_ids[i])
        label = lm.canonical(cid)
        dets.append(
            Detection(
                label=label,
                confidence=float(confs[i]),
                box=BBox(x=cx - bw / 2.0, y=cy - bh / 2.0, w=bw, h=bh, space=CoordinateSpace.MODEL_INPUT),
            )
        )
    return dets
