"""Test áp DisplayPolicy tại project_overlay (spec image-preprocess-and-labeling, R5/R4, Task 5).

Phủ: (5.1) payload display box có `displayName`+`colorKey`, giữ `label`=canonical; `visible=false` → BỎ khỏi
display.boxes. (5.3 Ẩn⊥Đếm) lớp ẩn KHÔNG ở display.boxes NHƯNG rawResult (nguồn raw cho đếm/analytics) VẪN giữ
theo canonical. No-regression: không truyền policy → passthrough (displayName=label, colorKey=label, không ẩn).
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.display_policy import DisplayPolicy
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome
from vision_platform.runtime.overlay_projection import project_overlay
from vision_platform.runtime.overlay_state_store import OverlayStateStore

MS = 1_000_000


def _nbox(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _store_with(boxes):
    s = OverlayStateStore("proc-1", 1, OverlayConfig(minHits=1, displayLeaseMs=500, ghostSlaMs=1500),
                          clock=lambda: 0)
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=boxes,
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    return s


def test_no_policy_passthrough_adds_default_display_fields():
    """Không truyền policy → displayName=label, colorKey=label, KHÔNG ẩn (no-regression)."""
    s = _store_with([("person", _nbox(0.1, 0.1), 0.9)])
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500)
    b = out["display"]["boxes"][0]
    assert b["label"] == "person"                 # canonical giữ (tương thích ngược)
    assert b["displayName"] == "person"
    assert b["colorKey"] == "person"


def test_alias_and_colorkey_in_payload():
    """Alias/i18n + gộp → displayName/colorKey theo policy; label vẫn canonical (R5.1)."""
    s = _store_with([("car", _nbox(0.2, 0.2), 0.9)])
    policy = DisplayPolicy(aliases={"car": "Xe hơi"}, groups={"car": "phương tiện"})
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500, policy=policy)
    b = out["display"]["boxes"][0]
    assert b["label"] == "car"                    # canonical không đổi
    assert b["displayName"] == "Xe hơi"           # alias thắng
    assert b["colorKey"] == "phương tiện"         # màu theo group


def test_hidden_class_removed_from_display_boxes():
    """visible=false → BỎ khỏi display.boxes (R5.3)."""
    s = _store_with([("person", _nbox(0.1, 0.1), 0.9), ("dog", _nbox(0.6, 0.6), 0.9)])
    policy = DisplayPolicy(hidden={"dog"})
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500, policy=policy)
    labels = [b["label"] for b in out["display"]["boxes"]]
    assert "person" in labels
    assert "dog" not in labels                    # bị ẩn khỏi render


def test_hidden_class_still_in_raw_result_for_counting():
    """Ẩn ⊥ Đếm (R4.2): lớp ẩn KHÔNG ở display.boxes NHƯNG rawResult (nguồn raw cho đếm/analytics) VẪN giữ."""
    s = _store_with([("dog", _nbox(0.6, 0.6), 0.9)])
    policy = DisplayPolicy(hidden={"dog"})
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500, policy=policy)
    assert out["display"]["boxes"] == []          # không hiển thị
    raw_labels = [b["label"] for b in out["rawResult"]["boxes"]]
    assert "dog" in raw_labels                    # raw truth giữ → đếm theo canonical vẫn được
