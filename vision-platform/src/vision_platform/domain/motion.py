"""Đo chuyển động giữa 2 frame — THUẦN numpy (sub-spec motion-gate, R2).

Layer: domain — Python thuần + numpy (luật cho phép; KHÔNG cv2/torch/zmq). Dùng cho MotionGateStage quyết
skip frame tĩnh trước detector (giảm tải GPU).

Mở rộng (spec motion-gate-roi, đóng K-063):
- `changed_ratio` nhận thêm `mask` (chỉ đo trong ROI) + `illumination_robust` (mean-subtraction triệt đổi-sáng
  ĐỀU toàn cục). Cả hai keyword-only optional → default None/False → kết quả BIT-KHỚP v1 (backward-compat).
- `validate_roi` (thuần số, config-time fail-fast) + `roi_mask` (cần shape, runtime) — tách 2 tầng kiểm.
"""
from __future__ import annotations

import numpy as np

# Dung sai cho phép sai số dấu phẩy động khi cộng x+w / y+h (vd 0.3+0.7 = 0.9999999999999999).
_ROI_EPS = 1e-9


def changed_ratio(
    prev: np.ndarray,
    curr: np.ndarray,
    pixel_diff_threshold: int,
    *,
    mask: np.ndarray | None = None,
    illumination_robust: bool = False,
) -> float:
    """Tỉ lệ phần tử ĐỔI giữa `prev` và `curr` (|curr-prev| > threshold) trên tổng phần tử của VÙNG XÉT, ∈ [0,1].

    QUAN TRỌNG: cast `int16` TRƯỚC khi trừ — array frame là uint8, uint8-uint8 UNDERFLOW (vd 10-250 wrap
    thành 16 thay vì -240) → sẽ nuốt chuyển động sáng→tối. Cast int16 cho hiệu đúng dấu/độ lớn.
    Yêu cầu `prev.shape == curr.shape` (caller đảm bảo; shape khác → xử lý ở Stage, không gọi vào đây).

    THỨ TỰ (quan trọng — spec motion-gate-roi): THU VỀ VÙNG ROI (mask) TRƯỚC, RỒI mới mean-subtraction —
    để mean là mean TRONG vùng đang xét. Nếu tính mean toàn-frame trước, đổi-sáng NGOÀI ROI sẽ kéo mean
    → trừ sai → tạo chuyển động GIẢ trong ROI (xem test_roi_x_illum_order).

    Args:
        mask: bool ndarray shape (H, W). None = đo toàn frame (hành vi v1). Áp lên (H,W) hoặc (H,W,C).
        illumination_robust: True = trừ trung-bình-vùng mỗi frame trước khi so (triệt đổi-sáng ĐỀU).
                             False = hiệu thô như v1.

    Backward-compat: mask=None + illumination_robust=False → kết quả BIT-KHỚP v1 (cùng int16 path).
    """
    if prev.shape != curr.shape:
        raise ValueError(f"changed_ratio cần cùng shape, got {prev.shape} vs {curr.shape}")
    a = prev.astype(np.int16)
    b = curr.astype(np.int16)
    # 1) Thu về vùng ROI TRƯỚC (nếu có mask). mask (H,W) index lên (H,W,C) giữ trục kênh C, flatten pixel ROI.
    if mask is not None:
        a = a[mask]
        b = b[mask]
    # Vùng xét rỗng (mask toàn False / frame rỗng) → không có gì để đo → 0.0 (guard TRƯỚC mean để tránh nan).
    if a.size == 0:
        return 0.0
    # 2) RỒI mean-subtraction TRÊN VÙNG ĐANG XÉT (triệt uniform-shift: curr=prev+c → d=0).
    if illumination_robust:
        a = a - a.mean()
        b = b - b.mean()
    diff = np.abs(b - a)
    changed = int(np.count_nonzero(diff > pixel_diff_threshold))
    return changed / diff.size


def validate_roi(x: float, y: float, w: float, h: float) -> None:
    """Kiểm ROI chuẩn-hoá [0,1] — THUẦN SỐ (không cần shape) → gọi được ở config-time (fail-fast SỚM).

    Ràng buộc: x,y ∈ [0,1]; w>0; h>0; x+w<=1; y+h<=1. Sai → ValueError (caller ở config bọc thành ConfigError).
    """
    if not (
        0.0 <= x <= 1.0
        and 0.0 <= y <= 1.0
        and w > 0.0
        and h > 0.0
        and x + w <= 1.0 + _ROI_EPS
        and y + h <= 1.0 + _ROI_EPS
    ):
        raise ValueError(
            f"ROI phải ∈[0,1], w>0, h>0, x+w<=1, y+h<=1; got x={x}, y={y}, w={w}, h={h}"
        )


def roi_mask(height: int, width: int, x: float, y: float, w: float, h: float) -> np.ndarray:
    """Dựng mask bool (height, width) từ chữ nhật ROI chuẩn-hoá [0,1] — CẦN shape → gọi lúc runtime (frame đầu).

    Chuẩn-hoá [0,1] → độc-lập-độ-phân-giải. Rỗng sau khi quy về pixel (ROI cực nhỏ trên frame nhỏ) → ValueError
    (chỉ phát hiện được khi biết shape → không thể kiểm ở config-time).
    """
    validate_roi(x, y, w, h)
    px0 = round(x * width)
    py0 = round(y * height)
    px1 = round((x + w) * width)
    py1 = round((y + h) * height)
    if px1 <= px0 or py1 <= py0:
        raise ValueError(
            f"ROI rỗng sau khi quy về pixel (H={height}, W={width}, x={x}, y={y}, w={w}, h={h})"
        )
    m = np.zeros((height, width), dtype=bool)
    m[py0:py1, px0:px1] = True
    return m
