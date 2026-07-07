"""LetterboxTransform — toán ánh xạ toạ độ ORIGINAL_FRAME ↔ MODEL_INPUT (sub-spec real-detector-integration).

Layer: domain — THUẦN TOÁN (chỉ số học + BBox/CoordinateSpace domain). KHÔNG I/O, KHÔNG cv2/torch/onnx.

VÌ SAO CÓ FILE NÀY (gap verify bằng grep toàn `src`: chỉ có enum CoordinateSpace, CHƯA hàm transform nào):
detector thật resize frame gốc (ví dụ 1920×1080) về input model (letterbox 640×640) → box model trả ra ở
MODEL_INPUT space. Nếu downstream (vẽ/lưu/track) dùng THẲNG box MODEL_INPUT trên frame gốc → LỆCH TOẠ ĐỘ
(bug production #1 của hệ vision). File này là phép nghịch đảo đúng: bỏ pad rồi chia scale → về ORIGINAL_FRAME.

LETTERBOX (giữ tỉ lệ, không méo): scale = min(model_w/orig_w, model_h/orig_h); nội dung resize về
(orig·scale) rồi ĐỆM (pad) đều 2 bên cho vừa khung model. pad_x=(model_w−orig_w·scale)/2, pad_y tương tự.

  MODEL_INPUT:  mx = x·scale + pad_x ;  my = y·scale + pad_y
  ORIGINAL   :  x  = (mx − pad_x)/scale ; y = (my − pad_y)/scale     (nghịch đảo)
"""
from __future__ import annotations

from dataclasses import dataclass

from vision_platform.domain.bbox import BBox, CoordinateSpace


@dataclass(frozen=True)
class LetterboxTransform:
    """Value-object mô tả phép letterbox ORIGINAL(orig_h×orig_w) → MODEL_INPUT(model_h×model_w).

    Frozen: scale/pad tính 1 lần từ 4 kích thước. Dùng lại cho mọi box của cùng 1 frame.
    """
    orig_h: int
    orig_w: int
    model_h: int
    model_w: int

    def __post_init__(self):
        if self.orig_h <= 0 or self.orig_w <= 0 or self.model_h <= 0 or self.model_w <= 0:
            raise ValueError(
                f"kích thước phải dương: orig=({self.orig_h},{self.orig_w}) model=({self.model_h},{self.model_w})"
            )

    @property
    def scale(self) -> float:
        """Hệ số thu nhỏ giữ tỉ lệ (min để nội dung vừa TRỌN khung model, phần thừa là pad)."""
        return min(self.model_w / self.orig_w, self.model_h / self.orig_h)

    @property
    def pad_x(self) -> float:
        """Đệm ngang (mỗi bên) sau khi resize giữ tỉ lệ."""
        return (self.model_w - self.orig_w * self.scale) / 2.0

    @property
    def pad_y(self) -> float:
        """Đệm dọc (mỗi bên)."""
        return (self.model_h - self.orig_h * self.scale) / 2.0

    # ---- điểm ----
    def forward_point(self, x: float, y: float) -> tuple[float, float]:
        """ORIGINAL_FRAME → MODEL_INPUT."""
        s = self.scale
        return x * s + self.pad_x, y * s + self.pad_y

    def inverse_point(self, mx: float, my: float) -> tuple[float, float]:
        """MODEL_INPUT → ORIGINAL_FRAME."""
        s = self.scale
        return (mx - self.pad_x) / s, (my - self.pad_y) / s

    # ---- box ----
    def forward_box(self, box: BBox) -> BBox:
        """ORIGINAL_FRAME box → MODEL_INPUT box. Fail-fast nếu sai space (bug lập trình)."""
        if box.space != CoordinateSpace.ORIGINAL_FRAME:
            raise ValueError(f"forward_box cần ORIGINAL_FRAME, got {box.space}")
        s = self.scale
        mx, my = self.forward_point(box.x, box.y)
        return BBox(x=mx, y=my, w=box.w * s, h=box.h * s, space=CoordinateSpace.MODEL_INPUT)

    def inverse_box(self, box: BBox) -> BBox:
        """MODEL_INPUT box → ORIGINAL_FRAME box (bỏ pad, chia scale) + CLAMP vào khung gốc [0,orig].

        Clamp theo GÓC (không chỉ x/w) để box luôn nằm trong frame gốc + w/h không âm — chống box tràn mép
        do model dự đoán lố ra vùng pad. Fail-fast nếu sai space.
        """
        if box.space != CoordinateSpace.MODEL_INPUT:
            raise ValueError(f"inverse_box cần MODEL_INPUT, got {box.space}")
        x0, y0 = self.inverse_point(box.x, box.y)
        x1, y1 = self.inverse_point(box.x + box.w, box.y + box.h)
        # Clamp góc vào khung gốc rồi tính lại w/h (>=0).
        x0c = min(max(x0, 0.0), float(self.orig_w))
        y0c = min(max(y0, 0.0), float(self.orig_h))
        x1c = min(max(x1, 0.0), float(self.orig_w))
        y1c = min(max(y1, 0.0), float(self.orig_h))
        return BBox(x=x0c, y=y0c, w=x1c - x0c, h=y1c - y0c, space=CoordinateSpace.ORIGINAL_FRAME)
