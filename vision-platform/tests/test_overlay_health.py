"""Test derive_health (spec Task 6, Property 6) — init/empty/source-degrade/detector-degrade phân biệt.

THUẦN + xác định (now_ns tiêm). Chứng minh lỗi KHÔNG bịa empty (health riêng, không đụng display).
"""
from __future__ import annotations

from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import DetectorState, SourceState
from vision_platform.runtime.overlay_health import derive_health

MS = 1_000_000
CFG = OverlayConfig(sourceStaleMs=2000, detectorStaleMs=3000, detectorHangMs=5000)


def test_initializing_when_no_data():
    h = derive_health(now_ns=0, config=CFG)   # chưa read, chưa completion
    assert h.source is SourceState.INITIALIZING
    assert h.detector is DetectorState.INITIALIZING


def test_both_live_when_recent():
    now = 10_000 * MS
    h = derive_health(now_ns=now, config=CFG,
                      last_read_ns=now - 100 * MS, last_completion_ns=now - 100 * MS)
    assert h.source is SourceState.LIVE and h.detector is DetectorState.LIVE


def test_source_stale_independent_of_detector():
    now = 10_000 * MS
    h = derive_health(now_ns=now, config=CFG,
                      last_read_ns=now - 2500 * MS,        # > sourceStaleMs 2000
                      last_completion_ns=now - 100 * MS)   # detector còn tươi
    assert h.source is SourceState.STALE
    assert h.detector is DetectorState.LIVE                # ĐỘC LẬP


def test_detector_stale_when_no_completion():
    now = 10_000 * MS
    h = derive_health(now_ns=now, config=CFG,
                      last_read_ns=now - 100 * MS,          # source tươi
                      last_completion_ns=now - 3500 * MS)   # > detectorStaleMs 3000
    assert h.source is SourceState.LIVE
    assert h.detector is DetectorState.STALE


def test_detector_hung_when_inflight_too_long():
    now = 10_000 * MS
    h = derive_health(now_ns=now, config=CFG,
                      last_read_ns=now - 100 * MS,
                      last_completion_ns=now - 100 * MS,    # có completion gần đây
                      in_flight_start_ns=now - 6000 * MS)   # nhưng đang treo 6s > hang 5s
    assert h.detector is DetectorState.STALE                # hung phát hiện dù completion cũ tươi


def test_explicit_error_not_fabricated_empty():
    # detector ERROR/source ERROR = trạng thái RIÊNG, KHÔNG phải EMPTY (Property 6: không bịa empty).
    now = 10_000 * MS
    h = derive_health(now_ns=now, config=CFG, source_error=True, detector_error=True,
                      last_read_ns=now, last_completion_ns=now)
    assert h.source is SourceState.ERROR
    assert h.detector is DetectorState.ERROR


def test_four_situations_distinguishable():
    now = 10_000 * MS
    init = derive_health(now_ns=now, config=CFG)
    live = derive_health(now_ns=now, config=CFG, last_read_ns=now, last_completion_ns=now)
    src_bad = derive_health(now_ns=now, config=CFG, last_read_ns=now - 9000 * MS, last_completion_ns=now)
    det_bad = derive_health(now_ns=now, config=CFG, last_read_ns=now, detector_error=True)
    # 4 tình huống → 4 cặp trạng thái KHÁC nhau (phân biệt được)
    states = {(init.source, init.detector), (live.source, live.detector),
              (src_bad.source, src_bad.detector), (det_bad.source, det_bad.detector)}
    assert len(states) == 4
