"""Hình học 2D thuần cho line-crossing (sub-spec line-crossing-count, R1).

Layer: domain — THUẦN toán trên điểm `(x, y)` float. KHÔNG import BBox/kernel (tầng thấp nhất, tối giản,
tái dùng — cho zone/đa-giác sau). Điểm = tuple `(x, y)`.

Dùng orientation (cross-product dấu) để: (a) biết điểm ở phía nào của 1 đường, (b) 2 đoạn thẳng có cắt nhau.
"""
from __future__ import annotations

from typing import Tuple

Point = Tuple[float, float]


def orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """Cross-product (B-A)×(C-A). >0: C bên trái AB · <0: bên phải · =0: thẳng hàng."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """2 đoạn `[p1,p2]` và `[p3,p4]` có cắt nhau (proper intersection) không.

    Dùng so-sánh STRICT `(d>0)` → collinear/chạm-mép xử lý bảo thủ:
    - collinear (mọi orient=0) → False (KHÔNG coi là cắt) — hợp lý cho đếm-qua-vạch (đi DỌC vạch ≠ qua vạch).
    - đoạn suy biến thành ĐIỂM (p1==p2, vật đứng yên) → False (không có chuyển động qua vạch).
    - chạm đúng 1 mép hiếm (1 orient=0) có thể trả True — chấp nhận v1 (xác suất ~0 với float thật).
    """
    d1 = orient(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = orient(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = orient(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = orient(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))
