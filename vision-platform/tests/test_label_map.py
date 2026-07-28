"""Test LabelMap — value-object fail-safe class-id → canonical (spec image-preprocess-and-labeling, R1).

LabelMap thuần @kernel (frozen, không I/O) → test không cần model/file. Bất biến chính (R1.2, P-B2):
class-id NGOÀI phạm vi → `class_<id>` (KHÔNG raise, KHÔNG gán nhầm tên lớp khác — an toàn hơn crash).
"""
from __future__ import annotations

from vision_platform.kernel.label_map import LabelMap


def test_valid_id_returns_canonical():
    """id trong phạm vi → tên canonical theo vị trí (R1.1)."""
    lm = LabelMap.from_names(["person", "car", "dog"])
    assert lm.canonical(0) == "person"
    assert lm.canonical(1) == "car"
    assert lm.canonical(2) == "dog"


def test_out_of_range_id_is_failsafe():
    """id >= len → `class_<id>`, KHÔNG raise, KHÔNG gán nhầm (R1.2, P-B2)."""
    lm = LabelMap.from_names(["person", "car"])
    assert lm.canonical(2) == "class_2"
    assert lm.canonical(7) == "class_7"


def test_negative_id_is_failsafe():
    """id âm (bất thường) → `class_<id>`, không raise (fail-safe tuyệt đối)."""
    lm = LabelMap.from_names(["person"])
    assert lm.canonical(-1) == "class_-1"


def test_empty_map_all_class_id():
    """map rỗng → MỌI id ra `class_<id>` (R1.3 nguồn rỗng)."""
    lm = LabelMap.empty()
    assert lm.canonical(0) == "class_0"
    assert lm.canonical(5) == "class_5"


def test_frozen_and_hashable():
    """value-object bất biến: hai LabelMap cùng names bằng nhau + hashable (dùng làm khoá/cache)."""
    a = LabelMap.from_names(["person", "car"])
    b = LabelMap.from_names(["person", "car"])
    assert a == b
    assert hash(a) == hash(b)
    assert len(a) == 2


def test_from_names_coerces_to_tuple():
    """from_names nhận list → lưu tuple (bất biến), không giữ tham chiếu list gốc."""
    src = ["person", "car"]
    lm = LabelMap.from_names(src)
    src.append("dog")                       # đột biến nguồn KHÔNG ảnh hưởng LabelMap
    assert lm.canonical(2) == "class_2"
    assert len(lm) == 2
