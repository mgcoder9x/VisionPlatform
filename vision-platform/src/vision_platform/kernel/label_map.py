"""LabelMap — value-object ánh xạ class-id → tên lớp canonical (spec image-preprocess-and-labeling, R1).

Layer: kernel — DỮ LIỆU THUẦN (frozen dataclass). KHÔNG import cv2/torch/onnx/zmq/I/O.
Việc ĐỌC nguồn nhãn (file `.names`/metadata ONNX, config) là I/O → nằm ở adapter (loader riêng);
ở đây chỉ giữ ánh xạ đã nạp + logic resolve fail-safe (thuần, test không cần model/file).

Vì sao tồn tại (R1, §B design): trước đây mỗi decoder tự làm `labels[cid] if cid < len(labels) else str(cid)`
→ (a) id ngoài phạm vi ra SỐ TRẦN (`"7"`) mơ hồ; (b) `labels` sai thứ tự/thiếu → gán NHẦM tên lớp khác
ÂM THẦM (nguy hiểm hơn crash); (c) không có 1 nguồn chuẩn. LabelMap chuẩn hoá 1 nơi + fail-safe rõ ràng.

Bất biến (R1.2, P-B2): class-id NGOÀI phạm vi (kể cả âm) → `class_<id>` — KHÔNG raise, KHÔNG gán nhầm.
`label` giữ nguyên = CANONICAL (tên lớp model) để analytics/DB ổn định; display-name áp ở mép (DisplayPolicy).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LabelMap:
    """Ánh xạ vị-trí class-id (int) → canonical (str). `names` positional như output argmax của model.

    Frozen + `names` là tuple → bất biến, hashable (dùng làm khoá/cache an toàn). Rỗng = mọi id `class_<id>`.
    """

    names: tuple[str, ...] = ()

    @classmethod
    def from_names(cls, names: Sequence[str]) -> "LabelMap":
        """Dựng từ danh sách tên (positional). Ép sang tuple → không giữ tham chiếu nguồn (bất biến thật)."""
        return cls(tuple(str(n) for n in names))

    @classmethod
    def empty(cls) -> "LabelMap":
        """Map rỗng — mọi id resolve thành `class_<id>` (nguồn nhãn vắng mặt, R1.3)."""
        return cls(())

    def canonical(self, cid: int) -> str:
        """class-id → canonical. Trong phạm vi → tên; ngoài phạm vi/âm → `class_<id>` (fail-safe, R1.2)."""
        if 0 <= cid < len(self.names):
            return self.names[cid]
        return f"class_{cid}"

    def __len__(self) -> int:
        return len(self.names)
