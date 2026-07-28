"""Bất biến canonical ⊥ display (spec image-preprocess-and-labeling, R2, P-B1, Task 4).

Chứng minh: đổi DisplayPolicy (alias/i18n/gộp/ẩn) KHÔNG đổi `Detection.label` (canonical) mà analytics
(stabilizer/crossing/DB) dùng → track không vỡ, DB nhất quán. DisplayPolicy là hàm THUẦN canonical→decision,
KHÔNG nhận/đột biến Detection → bất biến theo CẤU TRÚC. Test kèm DisplayStabilizer THẬT (match/track theo canonical).
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.display_policy import DisplayPolicy
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.runtime.display_stabilizer import DisplayStabilizer


def _norm(x: float, y: float) -> BBox:
    return BBox(x, y, 0.1, 0.1, CoordinateSpace.NORMALIZED)


def test_display_policy_does_not_touch_detection_label():
    """DisplayPolicy nhận canonical (str), KHÔNG đụng Detection.label — đổi policy → label bất biến (P-B1)."""
    det = Detection(label="car", confidence=0.9,
                    box=BBox(10, 10, 20, 20, CoordinateSpace.MODEL_INPUT))
    default = DisplayPolicy()
    aliased = DisplayPolicy(aliases={"car": "Xe hơi"}, groups={"car": "phương tiện"}, hidden={"dog"})

    # display-name đổi theo policy...
    assert default.decide(det.label).display_name == "car"
    assert aliased.decide(det.label).display_name == "Xe hơi"
    # ...nhưng canonical mà analytics/DB dùng KHÔNG đổi.
    assert det.label == "car"


def test_stabilizer_tracks_by_canonical_not_display_name():
    """DisplayStabilizer (analytics-hiển-thị) match/track theo CANONICAL → DisplayTrack.label = canonical.

    Nếu ai đó lỡ nhét display-name vào stabilizer, đổi ngôn ngữ sẽ làm track vỡ. Test khẳng định ta nuôi canonical.
    """
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1))
    v = st.on_accepted_result([("car", _norm(0.1, 0.1), 0.9)], now_ns=0)
    assert v.tracks[0].label == "car"                 # canonical, KHÔNG phải "Xe hơi"

    # DisplayPolicy áp SAU/ở-mép, không đụng label track:
    policy = DisplayPolicy(aliases={"car": "Xe hơi"})
    assert policy.decide(v.tracks[0].label).display_name == "Xe hơi"
    assert v.tracks[0].label == "car"                 # track vẫn canonical → DB/crossing nhất quán


def test_changing_policy_keeps_track_matching_stable():
    """Đổi policy giữa 2 frame KHÔNG ảnh hưởng track (vì stabilizer chỉ thấy canonical) → không tạo track trùng."""
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, maxMisses=3))
    st.on_accepted_result([("car", _norm(0.1, 0.1), 0.9)], now_ns=0)          # promote → 1 track
    # "đổi ngôn ngữ" ở tầng hiển thị KHÔNG đưa vào stabilizer — vẫn nuôi canonical "car"
    v2 = st.on_accepted_result([("car", _norm(0.11, 0.11), 0.9)], now_ns=10_000_000)
    assert st.confirmed_count == 1                    # vẫn 1 track (matched), không vỡ/không nhân đôi
    assert v2.tracks[0].label == "car"
