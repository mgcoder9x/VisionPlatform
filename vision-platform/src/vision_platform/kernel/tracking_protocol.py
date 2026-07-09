"""Track DTO — kết quả theo dõi 1 vật xuyên frame (sub-spec object-tracking-count, R1/R2).

Layer: kernel — DTO thuần (frozen), đối xứng `Detection`. Được import `BBox`@domain (kernel↠domain hợp lệ).
KHÔNG import zmq/torch/cv2. `box` giữ nguyên `space` tag của detection (invariant Step 02).
"""
from __future__ import annotations

from dataclasses import dataclass

from vision_platform.domain.bbox import BBox


@dataclass(frozen=True)
class Track:
    """1 vật được theo dõi.

    - `track_id`: định danh ổn định xuyên frame (đơn điệu tăng theo stream, KHÔNG tái dùng).
    - `label`: nhãn lớp (từ detection khớp).
    - `box`: box MỚI NHẤT (space giữ nguyên).
    - `age`: số frame LIÊN TIẾP chưa được khớp (0 khi vừa khớp/vừa tạo).
    - `hits`: tổng số frame track này đã được khớp (>= 1).
    """

    track_id: int
    label: str
    box: BBox
    age: int
    hits: int
