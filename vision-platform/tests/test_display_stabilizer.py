"""Test DisplayStabilizer (spec web-live-overlay-sync Task 3) — Property 5/7/8/9 + promotion/discontinuity.

THUẦN, xác định: clock TIÊM qua `now_ns` (fake clock, KHÔNG sleep). Không I/O/network.
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.runtime.display_stabilizer import DisplayStabilizer

MS = 1_000_000  # ns/ms


def _box(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _in(x, y, label="person", conf=0.9):
    return (label, _box(x, y), conf)


# ---- Promotion: cần đủ minHits result liên tiếp ----
def test_promotion_after_min_hits():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=2, maxMisses=1))
    v1 = st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)
    assert st.confirmed_count == 0 and st.candidate_count == 1   # hitStreak=1 chưa đủ
    assert v1.tracks == ()
    v2 = st.on_accepted_result([_in(0.1, 0.1)], now_ns=10 * MS)
    assert st.confirmed_count == 1                                # hitStreak=2 → promote
    assert v2.tracks[0].displayId == "1:1"                        # displayId = epoch:counter
    assert v2.tracks[0].trackRevision == 0


def test_promotion_immediate_when_min_hits_one():
    st = DisplayStabilizer(source_epoch=3, config=OverlayConfig(minHits=1))
    v = st.on_accepted_result([_in(0.2, 0.2)], now_ns=0)
    assert st.confirmed_count == 1 and v.tracks[0].displayId == "3:1"


# ---- Matched confirmed: trackRevision++ + missCount=0 ----
def test_matched_track_bumps_revision():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)             # promote → rev 0
    v = st.on_accepted_result([_in(0.1, 0.1)], now_ns=10 * MS)   # matched → rev 1
    assert v.tracks[0].trackRevision == 1 and v.tracks[0].missCount == 0


# ---- Property 7: exact miss (maxMisses=1) ----
def test_exact_miss_semantics():
    # lease mặc định 600ms >> mốc test (1-2ms) → tick không xen; miss xóa theo miss_count, không theo lease.
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, maxMisses=1))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)             # confirmed
    # EMPTY result #1 → miss=1 <= maxMisses → GIỮ
    st.on_accepted_result([], now_ns=1 * MS)
    assert st.confirmed_count == 1
    # EMPTY result #2 → miss=2 > maxMisses → XÓA
    st.on_accepted_result([], now_ns=2 * MS)
    assert st.confirmed_count == 0


def test_matched_resets_miss():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, maxMisses=2))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)
    st.on_accepted_result([], now_ns=1 * MS)                      # miss=1
    v = st.on_accepted_result([_in(0.1, 0.1)], now_ns=2 * MS)     # match lại → miss=0
    assert v.tracks[0].missCount == 0


# ---- Property 5: per-track lease ĐỘC LẬP (match track khác không gia hạn track này) ----
def test_per_track_lease_independent():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, maxMisses=5, displayLeaseMs=600))
    # t0=0: A và B cùng promote → deadline 600ms
    st.on_accepted_result([_in(0.1, 0.1), _in(0.6, 0.6)], now_ns=0)
    assert st.confirmed_count == 2
    # t1=100ms: CHỈ A → A refresh deadline=700ms; B miss (deadline giữ 600ms)
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=100 * MS)
    # tick tại 650ms: B (600<=650) hết hạn; A (700>650) còn → match A KHÔNG kéo dài B
    v = st.on_tick(now_ns=650 * MS)
    assert st.confirmed_count == 1
    assert len(v.tracks) == 1 and v.tracks[0].box.x < 0.3   # còn A (gần 0.1)


# ---- on_tick expire theo lease của chính track ----
def test_tick_expires_by_own_lease():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, displayLeaseMs=500))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)             # deadline 500ms
    assert st.on_tick(now_ns=400 * MS).tracks                     # chưa hết → còn
    assert st.on_tick(now_ns=500 * MS).tracks == ()               # chạm hạn → xóa
    assert st.confirmed_count == 0


def test_tick_no_change_is_noop_revision():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1))   # lease 600ms >> mốc tick 1-2ms
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)
    r_before = st.on_tick(now_ns=1 * MS).revision                 # không hết hạn gì
    r_after = st.on_tick(now_ns=2 * MS).revision
    assert r_before == r_after                                    # tick không đổi state → revision giữ


# ---- EMPTY xóa candidate ----
def test_empty_removes_candidate():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=3))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)             # candidate hitStreak=1
    assert st.candidate_count == 1
    st.on_accepted_result([], now_ns=1 * MS)                      # EMPTY → candidate bị xóa
    assert st.candidate_count == 0 and st.confirmed_count == 0


# ---- Discontinuity: clear + reset counter + epoch mới ----
def test_discontinuity_clears_and_resets():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1))
    st.on_accepted_result([_in(0.1, 0.1)], now_ns=0)             # confirmed "1:1"
    st.on_discontinuity(new_source_epoch=2)
    assert st.confirmed_count == 0 and st.epoch == 2
    v = st.on_accepted_result([_in(0.1, 0.1)], now_ns=10 * MS)    # promote lại trong epoch 2
    assert v.tracks[0].displayId == "2:1"                         # counter reset theo epoch


# ---- EMA integration: box confirmed dịch DẦN về new (nằm giữa) ----
def test_ema_smooths_confirmed_box():
    # box lớn (w=h=0.2) + dịch NHỎ (0.10→0.14) → CHỒNG LẤN đủ (IoU~0.47>=0.3) để match → EMA áp dụng.
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=1, emaAlpha=0.5))
    st.on_accepted_result([("person", _box(0.10, 0.10, 0.2, 0.2), 0.9)], now_ns=0)          # x=0.10
    v = st.on_accepted_result([("person", _box(0.14, 0.14, 0.2, 0.2), 0.9)], now_ns=10 * MS)  # new x=0.14 (IoU~0.47)
    # EMA alpha .5 giữa 0.10 và 0.14 → 0.12
    x = v.tracks[0].box.x
    assert 0.10 < x < 0.14 and abs(x - 0.12) < 1e-9


def test_normalized_input_required():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig())
    bad = ("person", BBox(10, 10, 20, 20, CoordinateSpace.ORIGINAL_FRAME), 0.9)
    import pytest
    with pytest.raises(ValueError):
        st.on_accepted_result([bad], now_ns=0)
