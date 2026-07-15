"""Test DTO overlay bất biến (spec web-live-overlay-sync Task 1) — Property 1 (atomic view) nền tảng.

THUẦN, xác định (không I/O/clock/network). Pin hợp đồng: frozen · validate finite/range · enum ·
raw⊥display tách bạch. Chạy trong `vp verify`.
"""
from __future__ import annotations

import dataclasses

import pytest

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.overlay_view import (
    DetectorState,
    DisplayTrack,
    DisplayView,
    HealthSnapshot,
    InputFrameSnapshot,
    NormalizedBox,
    OverlayViewSnapshot,
    Outcome,
    RawDetectionSnapshot,
    SourceState,
)


def _nbox(**kw):
    d = dict(displayId="1:0", trackRevision=0, remainingLeaseMs=100, label="person",
             confidence=0.9, x=0.1, y=0.1, width=0.2, height=0.3)
    d.update(kw)
    return NormalizedBox(**d)


# ---- NormalizedBox validation ----
def test_normalized_box_ok():
    b = _nbox()
    assert b.width == 0.2 and 0.0 <= b.x <= 1.0


@pytest.mark.parametrize("bad", [
    dict(x=1.5), dict(y=-0.1), dict(width=0.0), dict(height=1.5),
    dict(confidence=1.2), dict(confidence=float("nan")), dict(x=float("inf")),
    dict(trackRevision=-1), dict(remainingLeaseMs=-1), dict(displayId=""),
])
def test_normalized_box_rejects_invalid(bad):
    with pytest.raises(ValueError):
        _nbox(**bad)


def test_normalized_box_zero_area_rejected():
    # width/height ∈ (0,1] — zero-area KHÔNG hợp lệ (design §Data Models).
    with pytest.raises(ValueError):
        _nbox(width=0.0)


def test_normalized_box_frozen():
    b = _nbox()
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.x = 0.5   # type: ignore[misc]


# ---- RawDetectionSnapshot: raw truth ----
def test_raw_snapshot_detected_carries_boxes():
    det = Detection(label="person", confidence=0.8,
                    box=BBox(0.1, 0.1, 0.2, 0.2, CoordinateSpace.NORMALIZED))
    r = RawDetectionSnapshot(
        processEpoch="p", sourceEpoch=1, sourceFrameVersion=5, inferenceGeneration=1,
        inputAcquiredNs=10, inferenceStartNs=20, inferenceEndNs=30, publishedNs=31,
        outcome=Outcome.DETECTED, boxes=(det,))
    assert r.outcome is Outcome.DETECTED and len(r.boxes) == 1


def test_raw_snapshot_empty_must_have_no_boxes():
    det = Detection("person", 0.8, BBox(0.1, 0.1, 0.2, 0.2, CoordinateSpace.NORMALIZED))
    with pytest.raises(ValueError):
        RawDetectionSnapshot(
            processEpoch="p", sourceEpoch=1, sourceFrameVersion=5, inferenceGeneration=1,
            inputAcquiredNs=10, inferenceStartNs=20, inferenceEndNs=30, publishedNs=31,
            outcome=Outcome.EMPTY, boxes=(det,))   # EMPTY + có box = mâu thuẫn


def test_raw_snapshot_end_before_start_rejected():
    with pytest.raises(ValueError):
        RawDetectionSnapshot(
            processEpoch="p", sourceEpoch=1, sourceFrameVersion=5, inferenceGeneration=1,
            inputAcquiredNs=10, inferenceStartNs=30, inferenceEndNs=20, publishedNs=31,
            outcome=Outcome.EMPTY)


# ---- InputFrameSnapshot ----
def test_input_snapshot_validates():
    s = InputFrameSnapshot(processEpoch="p", sourceEpoch=1, frameVersion=0,
                           inputAcquiredNs=1, width=640, height=480)
    assert s.sourceEpoch == 1
    for bad in (dict(sourceEpoch=0), dict(frameVersion=-1), dict(width=0)):
        kw = dict(processEpoch="p", sourceEpoch=1, frameVersion=0, inputAcquiredNs=1,
                  width=640, height=480)
        kw.update(bad)
        with pytest.raises(ValueError):
            InputFrameSnapshot(**kw)


# ---- DisplayTrack: phải NORMALIZED ----
def test_display_track_requires_normalized_box():
    with pytest.raises(ValueError):
        DisplayTrack(displayId="1:0", trackRevision=0, label="person",
                     box=BBox(1, 1, 2, 2, CoordinateSpace.ORIGINAL_FRAME),
                     leaseDeadlineNs=100, missCount=0)
    ok = DisplayTrack(displayId="1:0", trackRevision=0, label="person",
                      box=BBox(0.1, 0.1, 0.2, 0.2, CoordinateSpace.NORMALIZED),
                      leaseDeadlineNs=100, missCount=0)
    assert ok.box.space is CoordinateSpace.NORMALIZED


# ---- OverlayViewSnapshot: atomic, nullable rawResult trước first result ----
def test_overlay_snapshot_null_before_first_result():
    snap = OverlayViewSnapshot(
        schemaVersion=1, processEpoch="p", sourceEpoch=1, eventRevision=0,
        health=HealthSnapshot(source=SourceState.INITIALIZING, detector=DetectorState.INITIALIZING),
        display=DisplayView(revision=0, reason="INIT", tracks=()),
        rawResult=None)
    assert snap.rawResult is None
    assert snap.health.source is SourceState.INITIALIZING
    assert snap.display.tracks == ()


def test_overlay_snapshot_frozen():
    snap = OverlayViewSnapshot(
        schemaVersion=1, processEpoch="p", sourceEpoch=1, eventRevision=0,
        health=HealthSnapshot(SourceState.LIVE, DetectorState.LIVE),
        display=DisplayView(0, "INIT", ()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.eventRevision = 9   # type: ignore[misc]
