"""Tracking association — THUẦN hình học (sub-spec object-tracking-count, R1).

Layer: domain — chỉ `BBox` + số + `domain.nms.iou`. KHÔNG import `Detection`@kernel (domain là tầng
THẤP NHẤT, cấm import kernel) → API INDEX-BASED (giống `nms_indices`): nhận boxes/labels rời, trả cặp index.
Tầng trên (`runtime/iou_tracker.py`) ghép index ↔ track_id/Detection.

Thuật toán: greedy IoU association — ghép detection(new) ↔ track(prev) theo IoU giảm dần, cùng label,
mỗi bên dùng tối đa 1 lần, chỉ ghép khi iou >= threshold. Tie-break `(-iou, new_idx, prev_idx)` → XÁC ĐỊNH
(không phụ thuộc thứ tự vòng lặp / dict). KHÔNG tối ưu toàn cục (Hungarian) — v1 đủ, ML qua port sau.
"""
from __future__ import annotations

from typing import Optional, Sequence

from vision_platform.domain.bbox import BBox
from vision_platform.domain.nms import iou


def greedy_associate(
    prev_boxes: Sequence[BBox],
    new_boxes: Sequence[BBox],
    iou_threshold: float,
    *,
    prev_labels: Optional[Sequence[str]] = None,
    new_labels: Optional[Sequence[str]] = None,
) -> list[tuple[int, int]]:
    """Ghép new↔prev theo IoU-greedy. Trả list `(new_idx, prev_idx)` (sort theo new_idx — xác định).

    - `iou_threshold` ∈ [0,1]. Chỉ ghép cặp có iou >= ngưỡng.
    - Nếu cấp labels: chỉ ghép cặp CÙNG label (khác label không phải cùng vật).
    - Mỗi new_idx và mỗi prev_idx xuất hiện TỐI ĐA 1 lần trong kết quả.
    """
    if not (0.0 <= iou_threshold <= 1.0):
        raise ValueError(f"iou_threshold phải trong [0,1], got {iou_threshold}")
    if prev_labels is not None and len(prev_labels) != len(prev_boxes):
        raise ValueError("prev_labels phải cùng độ dài prev_boxes")
    if new_labels is not None and len(new_labels) != len(new_boxes):
        raise ValueError("new_labels phải cùng độ dài new_boxes")

    # Ứng viên: mọi cặp (new_i, prev_i) cùng label (nếu có) + iou >= ngưỡng.
    candidates: list[tuple[float, int, int]] = []
    for ni in range(len(new_boxes)):
        for pi in range(len(prev_boxes)):
            if (
                prev_labels is not None
                and new_labels is not None
                and new_labels[ni] != prev_labels[pi]
            ):
                continue
            score = iou(new_boxes[ni], prev_boxes[pi])
            if score >= iou_threshold:
                candidates.append((score, ni, pi))

    # Tie-break XÁC ĐỊNH: iou giảm dần, rồi new_idx tăng, rồi prev_idx tăng.
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))

    used_new: set[int] = set()
    used_prev: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _score, ni, pi in candidates:
        if ni in used_new or pi in used_prev:
            continue
        used_new.add(ni)
        used_prev.add(pi)
        matches.append((ni, pi))

    matches.sort(key=lambda m: m[0])
    return matches
