"""Test DisplayPolicy — canonical → DisplayDecision (spec image-preprocess-and-labeling, R3/R4, Task 3).

DisplayPolicy THUẦN @domain (không cv2/torch/I/O) → test không cần model/camera. Phủ: mặc định passthrough,
alias/i18n, gộp lớp, ẩn lớp, chồng nhiều quy tắc (R3.4), màu ổn định (R3.5/P-B3), alias thắng group.
"""
from __future__ import annotations

from vision_platform.domain.display_policy import DisplayPolicy, DisplayDecision


def test_default_empty_passthrough():
    """Policy rỗng → display_name=canonical, visible=True, group=None (R3.2)."""
    p = DisplayPolicy()
    d = p.decide("person")
    assert d == DisplayDecision(visible=True, display_name="person", group=None, color_key="person")


def test_alias_renames_display_only():
    """Alias/i18n đổi display_name, KHÔNG đổi color_key (màu vẫn theo canonical) (R3.3)."""
    p = DisplayPolicy(aliases={"person": "Người"})
    d = p.decide("person")
    assert d.display_name == "Người"
    assert d.visible is True
    assert d.color_key == "person"          # màu ổn định theo canonical, không theo tên hiển thị
    assert d.group is None


def test_group_merges_classes():
    """Gộp lớp: nhiều canonical → 1 group; display_name = group; color_key = group (chung màu) (R3.3)."""
    p = DisplayPolicy(groups={"car": "phương tiện", "truck": "phương tiện", "bus": "phương tiện"})
    car = p.decide("car")
    truck = p.decide("truck")
    assert car.group == "phương tiện"
    assert car.display_name == "phương tiện"
    assert car.color_key == truck.color_key == "phương tiện"    # cùng group → cùng màu


def test_hidden_class_not_visible():
    """Ẩn lớp → visible=False (R3.3/R4.1). display_name vẫn tính (dùng nơi khác nếu cần)."""
    p = DisplayPolicy(hidden={"dog"})
    d = p.decide("dog")
    assert d.visible is False


def test_stacking_alias_group_hide_together():
    """Chồng nhiều quy tắc cùng lúc (R3.4): alias + group + hide áp đồng thời, không mâu thuẫn."""
    p = DisplayPolicy(
        aliases={"person": "Người"},
        groups={"car": "phương tiện", "truck": "phương tiện"},
        hidden={"dog"},
    )
    assert p.decide("person").display_name == "Người"
    assert p.decide("car").group == "phương tiện"
    assert p.decide("dog").visible is False
    assert p.decide("cat") == DisplayDecision(True, "cat", None, "cat")   # không luật → passthrough


def test_alias_beats_group_for_display_name():
    """Thứ tự xác định: alias (cụ thể hơn) THẮNG group cho display_name; color_key vẫn theo group."""
    p = DisplayPolicy(aliases={"car": "Xe hơi"}, groups={"car": "phương tiện"})
    d = p.decide("car")
    assert d.display_name == "Xe hơi"        # alias thắng
    assert d.group == "phương tiện"
    assert d.color_key == "phương tiện"      # màu theo group (chung với lớp cùng group)


# ---------------- R3.5 / P-B3: màu ổn định ----------------

def test_color_key_stable_same_canonical():
    """Cùng canonical → cùng color_key mọi lần gọi (P-B3, không nhấp nháy)."""
    p = DisplayPolicy(aliases={"person": "Người"})
    assert p.decide("person").color_key == p.decide("person").color_key == "person"


def test_color_key_stable_across_instances():
    """color_key là hàm THUẦN của canonical+config → 2 instance cùng config cho cùng color_key."""
    a = DisplayPolicy()
    b = DisplayPolicy()
    assert a.decide("car").color_key == b.decide("car").color_key


def test_decision_is_frozen():
    """DisplayDecision bất biến (frozen) — an toàn truyền qua projection."""
    import dataclasses
    d = DisplayPolicy().decide("person")
    try:
        d.visible = False           # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised
