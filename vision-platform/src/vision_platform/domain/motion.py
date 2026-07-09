"""Đo chuyển động giữa 2 frame — THUẦN numpy (sub-spec motion-gate, R2).

Layer: domain — Python thuần + numpy (luật cho phép; KHÔNG cv2/torch/zmq). Dùng cho MotionGateStage quyết
skip frame tĩnh trước detector (giảm tải GPU).
"""
from __future__ import annotations

import numpy as np


def changed_ratio(prev: np.ndarray, curr: np.ndarray, pixel_diff_threshold: int) -> float:
    """Tỉ lệ phần tử ĐỔI giữa `prev` và `curr` (|curr-prev| > threshold) trên tổng phần tử, ∈ [0,1].

    QUAN TRỌNG: cast `int16` TRƯỚC khi trừ — array frame là uint8, uint8-uint8 UNDERFLOW (vd 10-250 wrap
    thành 16 thay vì -240) → sẽ nuốt chuyển động sáng→tối. Cast int16 cho hiệu đúng dấu/độ lớn.
    Yêu cầu `prev.shape == curr.shape` (caller đảm bảo; shape khác → xử lý ở Stage, không gọi vào đây).
    """
    if prev.shape != curr.shape:
        raise ValueError(f"changed_ratio cần cùng shape, got {prev.shape} vs {curr.shape}")
    diff = np.abs(curr.astype(np.int16) - prev.astype(np.int16))
    if diff.size == 0:
        return 0.0
    changed = int(np.count_nonzero(diff > pixel_diff_threshold))
    return changed / diff.size
