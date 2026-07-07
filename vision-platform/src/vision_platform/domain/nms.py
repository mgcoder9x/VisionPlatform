"""NMS (Non-Max Suppression) — khử box chồng lấn (sub-spec real-detector-integration, Q2).

Layer: domain — THUẦN TOÁN trên `BBox` + số (KHÔNG import `Detection`@kernel: domain là tầng THẤP NHẤT,
cấm import kernel). Vì vậy API là INDEX-BASED: nhận `boxes`+`scores`(+`labels`) → trả index GIỮ LẠI;
tầng trên (DetectorPipeline@adapters) ghép index về `Detection`. Đây là ranh giới layer đúng bản chất.

NMS chuẩn detector: cùng lớp, giữ box confidence cao nhất, bỏ box khác chồng lấn IoU > ngưỡng (tham lam).
"""
from __future__ import annotations

from typing import Optional, Sequence

from vision_platform.domain.bbox import BBox


def iou(a: BBox, b: BBox) -> float:
    """Intersection-over-Union 2 box CÙNG space. Fail-fast nếu khác space (so sánh vô nghĩa)."""
    if a.space != b.space:
        raise ValueError(f"iou cần cùng space, got {a.space} vs {b.space}")
    ix0 = max(a.x, b.x)
    iy0 = max(a.y, b.y)
    ix1 = min(a.x2, b.x2)
    iy1 = min(a.y2, b.y2)
    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    inter = iw * ih
    union = a.area + b.area - inter
    return inter / union if union > 0.0 else 0.0


def nms_indices(
    boxes: Sequence[BBox],
    scores: Sequence[float],
    iou_threshold: float,
    *,
    labels: Optional[Sequence[str]] = None,
) -> list[int]:
    """Trả danh sách INDEX (tăng dần) của box được GIỮ sau NMS.

    - Nhóm theo `labels` (NMS per-class); `labels=None` → coi tất cả cùng lớp.
    - Trong mỗi nhóm: sắp theo score giảm, tham lam giữ box cao nhất, bỏ box IoU > ngưỡng với box đã giữ.
    """
    n = len(boxes)
    if len(scores) != n:
        raise ValueError(f"boxes ({n}) và scores ({len(scores)}) phải cùng độ dài")
    if labels is not None and len(labels) != n:
        raise ValueError(f"labels ({len(labels)}) phải cùng độ dài boxes ({n})")
    if not (0.0 <= iou_threshold <= 1.0):
        raise ValueError(f"iou_threshold phải trong [0,1], got {iou_threshold}")

    # Nhóm index theo label.
    groups: dict[object, list[int]] = {}
    for i in range(n):
        key = labels[i] if labels is not None else None
        groups.setdefault(key, []).append(i)

    kept: list[int] = []
    for _key, idxs in groups.items():
        # Sắp theo score giảm dần (ổn định: tie-break theo index nhỏ trước).
        order = sorted(idxs, key=lambda i: (-scores[i], i))
        suppressed: set[int] = set()
        for i in order:
            if i in suppressed:
                continue
            kept.append(i)
            for j in order:
                if j != i and j not in suppressed and iou(boxes[i], boxes[j]) > iou_threshold:
                    suppressed.add(j)

    return sorted(kept)
