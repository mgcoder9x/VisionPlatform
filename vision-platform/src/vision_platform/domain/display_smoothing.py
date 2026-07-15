"""EMA làm mượt toạ độ hiển thị — THUẦN (web-live-overlay-sync spec Task 2, Property 9).

Layer: domain — chỉ `BBox` + số. KHÔNG import kernel/adapter. Đây là làm-mượt CHO HIỂN THỊ (display
projection), KHÔNG đụng raw truth (raw giữ nguyên — Property 10).

**Matching một-một (Property 8) KHÔNG viết lại ở đây** — TÁI DÙNG `domain.tracking.greedy_associate`
(đã: cùng-label, IoU-greedy, tie-break xác định `(-iou,new,prev)`, mỗi bên tối đa 1 lần). Stabilizer
(Task 3, runtime) gọi thẳng `greedy_associate` để ghép new-box ↔ display-track. Tránh trùng thuật toán.

EMA: `s_t = s_{t-1} + alpha*(x_t - s_{t-1})`, alpha ∈ (0,1] → s_t nằm GIỮA s_{t-1} và x_t (convex);
input hằng (x_t == s_{t-1}) → s_t == s_{t-1} (KHÔNG drift). Chứng minh được, test xác định.
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace


def ema_scalar(prev: float, new: float, alpha: float) -> float:
    """EMA 1 chiều. `alpha` ∈ (0,1]. Kết quả LUÔN nằm trong [min(prev,new), max(prev,new)] (convex combo)."""
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha ∈ (0,1], got {alpha}")
    return prev + alpha * (new - prev)


def ema_box(prev: BBox, new: BBox, alpha: float) -> BBox:
    """EMA từng toạ độ (x,y,w,h) của 2 box CÙNG space. Trả BBox mới cùng space.

    - Fail-fast nếu khác space (làm mượt qua space khác nhau là vô nghĩa — giống `iou`).
    - Vì convex combo: nếu cả hai NORMALIZED (∈[0,1]) thì kết quả cũng ∈[0,1] → không vỡ ràng buộc BBox.
    - Input bằng nhau (prev==new toạ độ) → trả đúng giá trị đó (không drift — Property 9).
    """
    if prev.space != new.space:
        raise ValueError(f"ema_box cần cùng space, got {prev.space} vs {new.space}")
    return BBox(
        x=ema_scalar(prev.x, new.x, alpha),
        y=ema_scalar(prev.y, new.y, alpha),
        w=ema_scalar(prev.w, new.w, alpha),
        h=ema_scalar(prev.h, new.h, alpha),
        space=prev.space,
    )


# Re-export để nơi dùng overlay import 1 chỗ "matching + smoothing" (matching là tái dùng, không định nghĩa lại).
from vision_platform.domain.tracking import greedy_associate  # noqa: E402,F401  (Property 8 reuse)

__all__ = ["ema_scalar", "ema_box", "greedy_associate", "CoordinateSpace"]
