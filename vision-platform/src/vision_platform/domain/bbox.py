"""Pure domain value objects. NO I/O imports allowed here."""
from dataclasses import dataclass
from enum import Enum


class CoordinateSpace(Enum):
    """Tag bbox coordinates với space để tránh resize/letterbox bug."""
    ORIGINAL_FRAME = "original"   # tọa độ trên frame raw (pre-resize)
    MODEL_INPUT = "model_input"   # tọa độ trên model input (e.g. 640x640)
    NORMALIZED = "normalized"     # 0.0-1.0 (relative to frame)
    DISPLAY = "display"           # tọa độ trên frame UI hiển thị


@dataclass(frozen=True)
class BBox:
    """Bounding box với coordinate space tag.

    BBox(x=10, y=20, w=100, h=50, space=CoordinateSpace.ORIGINAL_FRAME).

    `space` là quan trọng — KHÔNG thể compare 2 bbox khác space mà chưa transform.
    """
    x: float
    y: float
    w: float
    h: float
    space: CoordinateSpace

    def __post_init__(self):
        if self.w < 0 or self.h < 0:
            raise ValueError(
                f"width/height must be non-negative, got w={self.w} h={self.h}"
            )
        # NORMALIZED space: mọi tọa độ phải trong [0,1] (ERRATA E-12, Risk 3).
        # Bắt lỗi kiểu "bbox 100.0 trong normalized space" ngay lúc khởi tạo.
        if self.space == CoordinateSpace.NORMALIZED:
            for name, val in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
                if not (0.0 <= val <= 1.0):
                    raise ValueError(
                        f"NORMALIZED bbox cần {name} trong [0,1], got {name}={val}"
                    )

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h
