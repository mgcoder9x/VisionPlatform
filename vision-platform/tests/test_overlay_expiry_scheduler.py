"""Test OverlayExpiryScheduler (spec Task 5, Property 13) — exactly-once + wait-plan, fake clock/sleep.

THUẦN + xác định: clock/sleep TIÊM. serve() dừng qua stop_event (event-driven, không sleep thật).
"""
from __future__ import annotations

import threading

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome
from vision_platform.runtime.overlay_expiry_scheduler import OverlayExpiryScheduler
from vision_platform.runtime.overlay_state_store import OverlayStateStore

MS = 1_000_000


def _nbox(x, y):
    return BBox(x, y, 0.1, 0.1, CoordinateSpace.NORMALIZED)


def _store_with_track(display_lease_ms=500, clock=lambda: 0):
    # tự tính config hợp lệ (candidate<=display<=ghost · clientCap<=ghost) quanh display_lease tuỳ ý.
    cand = min(300, display_lease_ms)
    ghost = max(1500, display_lease_ms)
    cfg = OverlayConfig(minHits=1, candidateLeaseMs=cand, displayLeaseMs=display_lease_ms,
                        ghostSlaMs=ghost, clientSilenceCapMs=min(1200, ghost))
    s = OverlayStateStore("proc-1", 1, cfg, clock=clock)
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.1), 0.9)],
                       input_acquired_ns=1, inference_start_ns=2, inference_end_ns=3, published_ns=4)
    return s


def test_next_expiry_reported():
    s = _store_with_track(display_lease_ms=500)   # promote tại clock=0 → deadline 500ms
    assert s.next_expiry_ns() == 500 * MS


def test_wait_plan_uses_deadline_then_idle():
    s = _store_with_track(display_lease_ms=500)
    sched = OverlayExpiryScheduler(s, clock=lambda: 0, sleep_ns=lambda ns: None,
                                   idle_poll_ns=250 * MS, max_wait_ns=1000 * MS)
    assert sched.wait_plan_ns(now_ns=0) == 500 * MS          # chờ tới deadline
    assert sched.wait_plan_ns(now_ns=600 * MS) == 0          # đã quá hạn → tick ngay


def test_wait_plan_idle_when_empty():
    s = OverlayStateStore("proc-1", 1, OverlayConfig(minHits=1), clock=lambda: 0)
    sched = OverlayExpiryScheduler(s, clock=lambda: 0, sleep_ns=lambda ns: None, idle_poll_ns=250 * MS)
    assert sched.wait_plan_ns(now_ns=0) == 250 * MS          # không có gì hết hạn → poll thưa


def test_wait_plan_capped():
    s = _store_with_track(display_lease_ms=5000)             # deadline 5s
    sched = OverlayExpiryScheduler(s, clock=lambda: 0, sleep_ns=lambda ns: None, max_wait_ns=1000 * MS)
    assert sched.wait_plan_ns(now_ns=0) == 1000 * MS         # cap 1s (không ngủ 5s)


def test_step_exactly_once_across_same_deadline():
    # Property 13: nhiều tick QUA CÙNG deadline → hiệu ứng state exactly-once.
    now = {"t": 0}
    s = _store_with_track(display_lease_ms=500, clock=lambda: now["t"])
    sched = OverlayExpiryScheduler(s, clock=lambda: now["t"], sleep_ns=lambda ns: None)
    rev0 = s.snapshot().eventRevision
    now["t"] = 500 * MS
    sched.step()                                             # chạm hạn → xóa track → commit
    rev1 = s.snapshot().eventRevision
    assert rev1 == rev0 + 1 and s.snapshot().display.tracks == ()
    now["t"] = 501 * MS
    sched.step()                                             # không còn track → no-op
    assert s.snapshot().eventRevision == rev1                # KHÔNG tăng nữa (exactly-once)


def test_serve_loop_terminates_and_ticks():
    now = {"t": 0}
    s = _store_with_track(display_lease_ms=100, clock=lambda: now["t"])
    stop = threading.Event()
    slept: list[int] = []

    def fake_sleep(ns):
        slept.append(ns)
        now["t"] += ns          # sleep = tiến clock ảo
        if len(slept) >= 3:
            stop.set()

    sched = OverlayExpiryScheduler(s, clock=lambda: now["t"], sleep_ns=fake_sleep,
                                   idle_poll_ns=50 * MS, max_wait_ns=1000 * MS)
    sched.serve(stop)                                        # phải DỪNG (không treo)
    assert len(slept) >= 1
    # sau khi clock vượt 100ms, track đã bị tick xóa
    assert s.snapshot().display.tracks == ()
