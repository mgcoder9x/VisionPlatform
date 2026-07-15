"""Motion-aware eviction chống ghost "người đi qua rồi bbox 1 lúc mới tắt" (K-108) — web-live-overlay-sync.

GỐC (user báo #405): track giữ box theo lease/miss cố định → người rời khung nhưng box nán ~lease. FIX: motion
model — ước lượng vận tốc tâm từ 2 lần khớp; khi miss, dự đoán tâm; RA NGOÀI [0,1] → xoá NGAY (đã rời).
Vật đứng-yên/bị-che (vận tốc thấp, dự đoán còn trong khung) → giữ theo lease (không hại flicker).
Mặc định evictPredictedOffFrame=False = TẮT (hành vi cũ). THUẦN, xác định (clock tiêm).
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.runtime.display_stabilizer import DisplayStabilizer

MS = 1_000_000


def _box(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _cfg(**kw):
    # emaAlpha=1.0 → box=new (tâm dự đoán chính xác); lease/maxMisses LỚN để cô lập logic off-frame.
    base = dict(minHits=1, maxMisses=20, displayLeaseMs=1400, emaAlpha=1.0, iouThreshold=0.1,
                evictPredictedOffFrame=True)
    base.update(kw)
    return OverlayConfig(**base)


def _p(x, y, conf=0.9):
    return ("person", _box(x, y), conf)


# ---- 1) track DI CHUYỂN rời khung → miss → xoá NGAY (không chờ lease/maxMisses) ----
def test_moving_out_evicts_immediately_on_miss():
    st = DisplayStabilizer(1, _cfg())
    st.on_accepted_result([_p(0.85, 0.5)], now_ns=0)             # center x=0.90 (promote)
    st.on_accepted_result([_p(0.90, 0.5)], now_ns=100 * MS)      # center x=0.95 (khớp IoU), vel=+0.05/100ms
    assert st.confirmed_count == 1
    # miss tại t=300ms (dt=200ms): dự đoán x = 0.95 + 0.05/100ms*200ms = 1.05 > 1 → off-frame → XOÁ ngay
    st.on_accepted_result([], now_ns=300 * MS)
    assert st.confirmed_count == 0


# ---- 2) vật ĐỨNG YÊN bị miss → KHÔNG xoá sớm (dự đoán còn trong khung) ----
def test_stationary_missed_not_evicted_early():
    st = DisplayStabilizer(1, _cfg())
    st.on_accepted_result([_p(0.5, 0.5)], now_ns=0)
    st.on_accepted_result([_p(0.5, 0.5)], now_ns=100 * MS)       # vel 0
    st.on_accepted_result([], now_ns=200 * MS)                   # miss, dự đoán 0.5 (trong khung) → GIỮ
    assert st.confirmed_count == 1


# ---- 3) on_tick cũng xoá track dự đoán off-frame ----
def test_tick_evicts_predicted_offframe():
    st = DisplayStabilizer(1, _cfg())
    st.on_accepted_result([_p(0.85, 0.5)], now_ns=0)
    st.on_accepted_result([_p(0.90, 0.5)], now_ns=100 * MS)
    st.on_tick(now_ns=300 * MS)                                  # dự đoán 1.05 → xoá qua tick
    assert st.confirmed_count == 0


# ---- 4) chỉ 1 lần khớp (chưa đủ vận tốc) → KHÔNG xoá sớm ----
def test_single_match_no_velocity_no_evict():
    st = DisplayStabilizer(1, _cfg())
    st.on_accepted_result([_p(0.95, 0.5)], now_ns=0)             # 1 match, vel chưa có
    st.on_accepted_result([], now_ns=100 * MS)                   # miss: last_match có nhưng vel=0 → dự đoán 0.95 (trong khung)
    assert st.confirmed_count == 1


# ---- 5) ADDITIVE: mặc định tắt → track rời khung vẫn giữ theo lease (hành vi cũ) ----
def test_default_off_keeps_old_behavior():
    st = DisplayStabilizer(1, _cfg(evictPredictedOffFrame=False))
    st.on_accepted_result([_p(0.85, 0.5)], now_ns=0)
    st.on_accepted_result([_p(0.90, 0.5)], now_ns=100 * MS)
    st.on_accepted_result([], now_ns=300 * MS)                   # miss=1 <= maxMisses 20 → GIỮ (không off-frame evict)
    assert st.confirmed_count == 1


# ---- config validate ----
def test_config_rejects_non_bool():
    import pytest
    with pytest.raises(Exception):
        OverlayConfig(evictPredictedOffFrame="yes")
    with pytest.raises(Exception):
        OverlayConfig(matchUsePrediction="yes")


# ==== motion-predicted matching (K-107): vật di chuyển giữa 2 detect thưa vẫn giữ 1 track ====

def _mcfg(**kw):
    # box lớn 0.2, iouThreshold 0.3 để thể hiện rõ: không-dự-đoán thì mất match khi vật nhảy xa.
    base = dict(minHits=1, maxMisses=5, displayLeaseMs=1400, emaAlpha=1.0, iouThreshold=0.3)
    base.update(kw)
    return OverlayConfig(**base)


def _pb(cx, conf=0.9):
    # box w=h=0.2 tại tâm (cx, 0.5) → x = cx-0.1
    return ("person", BBox(cx - 0.1, 0.4, 0.2, 0.2, CoordinateSpace.NORMALIZED), conf)


def test_prediction_keeps_moving_object_one_track():
    st = DisplayStabilizer(1, _mcfg(matchUsePrediction=True))
    st.on_accepted_result([_pb(0.30)], now_ns=0)                 # promote (center 0.30)
    st.on_accepted_result([_pb(0.40)], now_ns=100 * MS)          # match (IoU~0.33), vel=+0.10/100ms
    # vật NHẢY tới center 0.60: box cũ [0.30-0.50] vs new [0.50-0.70] overlap 0 (không-dự-đoán sẽ MẤT match)
    v = st.on_accepted_result([_pb(0.60)], now_ns=200 * MS)      # dự đoán center 0.50 → box [0.40-0.60] khớp new
    assert st.confirmed_count == 1                               # GIỮ 1 track (dự đoán cứu match)
    assert len(v.tracks) == 1


def test_without_prediction_moving_object_churns():
    st = DisplayStabilizer(1, _mcfg(matchUsePrediction=False))   # control: không dự đoán
    st.on_accepted_result([_pb(0.30)], now_ns=0)
    st.on_accepted_result([_pb(0.40)], now_ns=100 * MS)
    st.on_accepted_result([_pb(0.60)], now_ns=200 * MS)          # overlap 0 → track cũ miss + track MỚI
    assert st.confirmed_count == 2                               # churn (2 track cho 1 vật)


def test_prediction_offframe_clamped_no_crash():
    # HỒI QUY bug #410: track di chuyển ra MÉP → dự đoán toạ độ ÂM → BBox NORMALIZED validate [0,1] ném
    # ValueError (crash detect). _predict_box phải CLAMP → không crash. Input luôn hợp lệ (x>=0).
    st = DisplayStabilizer(1, _mcfg(matchUsePrediction=True))
    st.on_accepted_result([_pb(0.15)], now_ns=0)                 # x=0.05
    st.on_accepted_result([_pb(0.11)], now_ns=100 * MS)          # x=0.01, vận tốc ÂM
    # tại 300ms: dự đoán x = 0.01 + (-0.04/100ms)*200ms = -0.07 → PHẢI clamp về 0, KHÔNG ValueError
    st.on_accepted_result([_pb(0.12)], now_ns=300 * MS)          # trước fix #410: ValueError
    assert st.confirmed_count >= 1                               # tới đây không exception = PASS
