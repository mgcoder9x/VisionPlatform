"""DisplayPolicy — canonical → quyết định hiển thị (spec image-preprocess-and-labeling, R3/R4, §B.3).

Layer: domain — THUẦN (dataclasses/typing). KHÔNG cv2/torch/I/O/numpy-side-effect → test không cần camera.
Đây là nơi "hiển thị tên chuẩn" sống: i18n/alias, gộp lớp, ẩn lớp, khoá màu ổn định. Config-driven per-deployment.

NGUYÊN TẮC canonical ⊥ display (§B.3): KHÔNG đụng `Detection.label` (canonical) — chỉ TÍNH quyết định hiển thị
áp ở MÉP (overlay_projection). Nhờ vậy analytics/DB/track dùng canonical bất biến (P-B1); đổi policy = đổi hiển thị.

Ẩn ⊥ Đếm (§D-3, R4): `visible=false` CHỈ ảnh hưởng RENDER; đếm/analytics dùng canonical BẤT KỂ visible.

Màu ổn định (P-B3, R3.5): `color_key` là hàm THUẦN của canonical + config (group nếu gộp, else canonical) →
cùng lớp luôn cùng khoá màu, không nhấp nháy. Render (client) map color_key → màu pixel (domain không giữ RGB).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Collection, Mapping, Optional


@dataclass(frozen=True)
class DisplayDecision:
    """Quyết định hiển thị cho 1 canonical. Bất biến → an toàn truyền qua projection.

    - `visible`: có vẽ ở overlay không (KHÔNG ảnh hưởng đếm).
    - `display_name`: tên hiện ra (alias > group > canonical).
    - `group`: tên nhóm nếu lớp bị gộp, else None.
    - `color_key`: khoá màu ổn định (group nếu gộp, else canonical) — render map sang màu.
    """

    visible: bool
    display_name: str
    group: Optional[str]
    color_key: str


@dataclass(frozen=True)
class DisplayPolicy:
    """Chính sách hiển thị per-deployment. Mặc định RỖNG → passthrough (display = canonical, visible=True).

    Chồng được (R3.4): `aliases` + `groups` + `hidden` áp ĐỒNG THỜI theo thứ tự xác định (hide → alias → group).
    """

    aliases: Mapping[str, str] = field(default_factory=dict)   # canonical → tên hiển thị (i18n/đổi tên)
    groups: Mapping[str, str] = field(default_factory=dict)    # canonical → tên nhóm (gộp lớp)
    hidden: Collection[str] = field(default_factory=frozenset)  # canonical bị ẩn khỏi overlay

    def decide(self, canonical: str) -> DisplayDecision:
        """canonical → DisplayDecision. Hàm THUẦN (cùng input+config → cùng output)."""
        visible = canonical not in self.hidden
        group = self.groups.get(canonical)                      # None nếu không gộp
        # Thứ tự display_name: alias (cụ thể nhất) > group (gộp) > canonical.
        if canonical in self.aliases:
            display_name = self.aliases[canonical]
        elif group is not None:
            display_name = group
        else:
            display_name = canonical
        # Màu theo group nếu gộp (chung màu), else theo canonical (ổn định, P-B3).
        color_key = group if group is not None else canonical
        return DisplayDecision(
            visible=visible, display_name=display_name, group=group, color_key=color_key
        )
