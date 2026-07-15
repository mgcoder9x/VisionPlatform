"""Test OverlayStateStore (spec web-live-overlay-sync Task 4) — Property 1/2/3/4 + acceptance gate.

THUẦN + xác định (clock tiêm). Có 1 test concurrency (đọc atomic trong lúc commit) — nhẹ, không flake.
"""
from __future__ import annotations

import threading

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome, OverlayViewSnapshot, SourceState, DetectorState
from vision_platform.runtime.overlay_state_store import OverlayStateStore


def _nbox(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _store(**cfg):
    base = dict(minHits=1)
    base.update(cfg)
    return OverlayStateStore("proc-1", 1, OverlayConfig(**base), clock=lambda: 0)


def _complete(s, ver, token, *, pe="proc-1", se=1, outcome=Outcome.DETECTED, boxes=None):
    if boxes is None:
        boxes = [("person", _nbox(0.1, 0.1), 0.9)]
    return s.apply_completion(
        process_epoch=pe, source_epoch=se, source_frame_version=ver, token=token,
        outcome=outcome, boxes=boxes,
        input_acquired_ns=10, inference_start_ns=20, inference_end_ns=30, published_ns=31)


# ---- accepted completion ----
def test_accepted_completion_commits():
    s = _store()
    tok = s.begin_inference()
    snap = _complete(s, ver=1, token=tok)
    assert snap.eventRevision == 1
    assert snap.rawResult is not None and snap.rawResult.inferenceGeneration == 1
    assert snap.rawResult.sourceFrameVersion == 1
    assert len(snap.display.tracks) == 1     # minHits=1 → promote ngay


# ---- Property 3: unique monotonic acceptance ----
def test_duplicate_version_rejected_no_change():
    s = _store()
    tok = s.begin_inference()
    _complete(s, ver=5, token=tok)
    snap = _complete(s, ver=5, token=tok)     # duplicate version
    assert snap.eventRevision == 1            # KHÔNG tăng revision
    assert s.reject_reasons().get("NON_MONOTONIC_VERSION") == 1


def test_old_version_rejected():
    s = _store()
    tok = s.begin_inference()
    _complete(s, ver=5, token=tok)
    snap = _complete(s, ver=3, token=tok)     # cũ hơn
    assert snap.eventRevision == 1
    assert s.reject_reasons().get("NON_MONOTONIC_VERSION") == 1


def test_stale_token_rejected():
    s = _store()
    s.begin_inference()                       # token 1
    tok2 = s.begin_inference()                # token 2 (hiện hành)
    snap = _complete(s, ver=1, token=1)       # token cũ
    assert snap.eventRevision == 0
    assert s.reject_reasons().get("STALE_TOKEN") == 1
    # token hiện hành thì nhận
    snap2 = _complete(s, ver=1, token=tok2)
    assert snap2.eventRevision == 1


# ---- Property 2: epoch anti-rollback ----
def test_process_epoch_mismatch_rejected():
    s = _store()
    tok = s.begin_inference()
    snap = _complete(s, ver=1, token=tok, pe="proc-OTHER")
    assert snap.eventRevision == 0
    assert s.reject_reasons().get("PROCESS_EPOCH_MISMATCH") == 1


def test_source_epoch_mismatch_rejected():
    s = _store()
    tok = s.begin_inference()
    snap = _complete(s, ver=1, token=tok, se=99)
    assert snap.eventRevision == 0
    assert s.reject_reasons().get("SOURCE_EPOCH_MISMATCH") == 1


# ---- Property 1/4: snapshot atomic + idempotent ----
def test_snapshot_idempotent():
    s = _store()
    a = s.snapshot()
    b = s.snapshot()
    assert a is b                             # cùng reference, không tạo state mới
    assert isinstance(a, OverlayViewSnapshot) and a.schemaVersion == 1


def test_null_raw_before_first_result():
    s = _store()
    snap = s.snapshot()
    assert snap.rawResult is None
    assert snap.health.source is SourceState.INITIALIZING


# ---- tick: no-op vs expire ----
def test_tick_noop_then_expire():
    s = _store(displayLeaseMs=500)
    tok = s.begin_inference()
    _complete(s, ver=1, token=tok)            # rev 1, deadline = 0+500ms
    rev_after_accept = s.snapshot().eventRevision
    s.apply_tick(now_ns=100 * 1_000_000)      # 100ms < 500ms → no expire
    assert s.snapshot().eventRevision == rev_after_accept   # KHÔNG tăng (Property 4)
    s.apply_tick(now_ns=500 * 1_000_000)      # chạm hạn → expire → commit
    snap = s.snapshot()
    assert snap.eventRevision == rev_after_accept + 1
    assert snap.display.tracks == ()


# ---- discontinuity: clear + token invalidate + version reset (chống race) ----
def test_discontinuity_gate_closes_race():
    s = _store()
    tok = s.begin_inference()                 # token 1, in-flight cho epoch 1
    _complete(s, ver=10, token=tok)           # accepted epoch1 v10
    s.apply_source_discontinuity(2)           # epoch→2, token→2, version reset
    assert s.source_epoch == 2
    # completion in-flight CŨ (epoch1, token1) tới sau → REJECT (gate đóng race, Property 2)
    snap = _complete(s, ver=11, token=tok, se=1)
    assert s.reject_reasons().get("SOURCE_EPOCH_MISMATCH") == 1
    # epoch mới + token mới + version=1 (đã reset) → nhận (dù < v10 cũ)
    tok2 = s.begin_inference()
    snap2 = _complete(s, ver=1, token=tok2, se=2)
    assert snap2.rawResult.sourceFrameVersion == 1 and snap2.sourceEpoch == 2


# ---- health ----
def test_set_health_commits_on_change_only():
    s = _store()
    r0 = s.snapshot().eventRevision
    s.set_health(SourceState.LIVE, DetectorState.LIVE)
    r1 = s.snapshot().eventRevision
    assert r1 == r0 + 1
    s.set_health(SourceState.LIVE, DetectorState.LIVE)   # không đổi
    assert s.snapshot().eventRevision == r1              # no-op


# ---- concurrency: đọc atomic trong lúc commit (Property 1) ----
def test_concurrent_reads_are_consistent():
    s = _store()
    stop = threading.Event()
    errors = []

    def reader():
        while not stop.is_set():
            snap = s.snapshot()
            # mỗi snapshot phải nội-bộ-nhất-quán (không torn/mixed)
            if not (isinstance(snap, OverlayViewSnapshot) and snap.processEpoch == "proc-1"
                    and snap.schemaVersion == 1):
                errors.append(snap)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    tok = s.begin_inference()
    for v in range(1, 200):
        _complete(s, ver=v, token=tok)
    stop.set()
    for t in threads:
        t.join()
    assert errors == []
