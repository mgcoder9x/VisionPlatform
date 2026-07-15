"""Confidence hysteresis chống flicker vật ở xa (K-106) — web-live-overlay-sync.

GỐC (verify browser MCP #404): vật xa conf DAO ĐỘNG quanh 1 ngưỡng cứng → rớt→xóa track→vượt lại→promote
displayId MỚI (churn). FIX: 2 ngưỡng kiểu Schmitt-trigger — TẠO track mới cần conf CAO (createConfThreshold);
NUÔI track đã tồn tại (khớp IoU) chỉ cần conf THẤP (sustainConfThreshold). Vật dao động quanh ngưỡng KHÔNG
rớt ra → 1 displayId ổn định. Mặc định 0/0 = TẮT (hành vi cũ).

THUẦN, xác định (clock tiêm now_ns). _Requirements: web-live-overlay-sync (chống flicker) + K-106._
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.runtime.display_stabilizer import DisplayStabilizer

MS = 1_000_000


def _box(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _in(x, y, conf, label="person"):
    return (label, _box(x, y), conf)


def _hyst(**kw):
    # minHits=1 để promote ngay khi có 1 box >= create (cô lập logic hysteresis khỏi promotion-streak)
    base = dict(minHits=1, maxMisses=2, createConfThreshold=0.30, sustainConfThreshold=0.10)
    base.update(kw)
    return OverlayConfig(**base)


# ---- config invariant ----
def test_config_rejects_sustain_gt_create():
    import pytest
    with pytest.raises(Exception):
        OverlayConfig(createConfThreshold=0.2, sustainConfThreshold=0.5)   # nuôi khó hơn tạo → sai chiều
    with pytest.raises(Exception):
        OverlayConfig(createConfThreshold=1.5)                              # ngoài [0,1]


# ---- 1) box YẾU nuôi track ĐÃ tồn tại (không rớt) ----
def test_weak_box_sustains_existing_track():
    st = DisplayStabilizer(source_epoch=1, config=_hyst())
    v0 = st.on_accepted_result([_in(0.5, 0.5, 0.45)], now_ns=0)          # conf>=create → promote
    assert st.confirmed_count == 1
    did = v0.tracks[0].displayId
    # box YẾU (0.15 < create 0.30, >= sustain 0.10) CÙNG vị trí → NUÔI track (miss=0), GIỮ displayId
    v1 = st.on_accepted_result([_in(0.5, 0.5, 0.15)], now_ns=10 * MS)
    assert st.confirmed_count == 1
    assert v1.tracks[0].displayId == did                                 # KHÔNG churn ID
    assert v1.tracks[0].missCount == 0


# ---- 2) box YẾU KHÔNG tạo track mới (chống rác) ----
def test_weak_box_does_not_create_track():
    st = DisplayStabilizer(source_epoch=1, config=_hyst())
    st.on_accepted_result([_in(0.2, 0.2, 0.15)], now_ns=0)               # 0.15 < create → KHÔNG candidate
    assert st.candidate_count == 0 and st.confirmed_count == 0


# ---- 3) box MẠNH tạo track ----
def test_strong_box_creates_track():
    st = DisplayStabilizer(source_epoch=1, config=_hyst())
    st.on_accepted_result([_in(0.2, 0.2, 0.40)], now_ns=0)               # >= create → promote (minHits=1)
    assert st.confirmed_count == 1


# ---- 4) KỊCH BẢN FLICKER: conf dao động mạnh/yếu → 1 displayId ổn định (hết churn) ----
def test_oscillating_conf_no_churn():
    st = DisplayStabilizer(source_epoch=1, config=_hyst())
    ids = set()
    confs = [0.40, 0.15, 0.35, 0.12, 0.50, 0.14, 0.33]   # dao động quanh 0.25 (create=0.30)
    for k, c in enumerate(confs):
        v = st.on_accepted_result([_in(0.5, 0.5, c)], now_ns=k * 100 * MS)
        assert st.confirmed_count == 1, f"mất track ở bước {k} (conf={c})"
        ids.add(v.tracks[0].displayId)
    assert len(ids) == 1, f"churn displayId: {ids} (kỳ vọng 1)"          # BẢN CHẤT fix: 1 ID duy nhất


# ---- 5) vật RỜI thật (conf < sustain → không phát box) → xóa NHANH theo maxMisses ----
def test_departed_object_removed():
    st = DisplayStabilizer(source_epoch=1, config=_hyst(maxMisses=2))
    st.on_accepted_result([_in(0.5, 0.5, 0.45)], now_ns=0)               # confirmed
    st.on_accepted_result([], now_ns=100 * MS)                           # miss=1
    st.on_accepted_result([], now_ns=200 * MS)                           # miss=2 <= max → giữ
    assert st.confirmed_count == 1
    st.on_accepted_result([], now_ns=300 * MS)                           # miss=3 > max → xóa
    assert st.confirmed_count == 0


# ---- 6) ADDITIVE: mặc định 0/0 → box yếu vẫn tạo candidate như cũ ----
def test_default_thresholds_preserve_old_behavior():
    st = DisplayStabilizer(source_epoch=1, config=OverlayConfig(minHits=2))   # create=0/sustain=0 mặc định
    st.on_accepted_result([_in(0.2, 0.2, 0.05)], now_ns=0)               # conf 0.05 >= 0 → candidate (cũ)
    assert st.candidate_count == 1
