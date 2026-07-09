"""Sub-spec crossing-event-log — test XÁC ĐỊNH (clock tiêm), không camera/GPU.

Phủ: LineCrossingStage phát CrossingEvent (P1) · không qua→() (P2) · CrossingEventJsonlSink ghi JSONL (P3) ·
clock mặc định wall-clock "Z" (P4) · wiring --crossing-out (cần --line).
"""
import json
from datetime import datetime, timezone

import numpy as np
import pytest

from vision_platform.adapters.crossing_event_sink import CrossingEventJsonlSink
from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.crossing_event import CrossingEvent
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus
from vision_platform.kernel.tracking_protocol import Track
from vision_platform.runtime.stages.line_crossing_stage import LineCrossingStage

OF = CoordinateSpace.ORIGINAL_FRAME
_T0 = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _track(tid, cx, cy, label="object"):
    return Track(track_id=tid, label=label, box=BBox(cx - 5, cy - 5, 10, 10, OF), age=0, hits=1)


def _packet(tracks, source_id="cam0"):
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4, 3), dtype=np.uint8))
    return MediaPacket(packet_id="p", source_id=source_id, media_ref=ref, capture_time_ns=0)\
        .with_artifact("tracks", tuple(tracks))


# ================= LineCrossingStage phát event =================

def test_stage_emits_crossing_event_with_injected_clock():  # P1 + P4(tiêm)
    st = LineCrossingStage(50, 0, 50, 100, clock=lambda: _T0)
    st.process(_packet([_track(1, 40, 50)]))              # frame1: chưa có prev → không event
    r = st.process(_packet([_track(1, 60, 50)]))          # 40→60 qua vạch
    evs = r.packet.artifacts["crossing_events"]
    assert len(evs) == 1
    e = evs[0]
    assert (e.track_id, e.label, e.direction, e.source_id) == (1, "object", "out", "cam0")
    assert (e.cx, e.cy) == (60.0, 50.0)
    assert e.event_ts == "2026-01-02T03:04:05Z"           # wall-clock tiêm, hậu tố Z


def test_no_cross_emits_empty_events():  # P2
    st = LineCrossingStage(50, 0, 50, 100, clock=lambda: _T0)
    r0 = st.process(_packet([_track(1, 40, 50)]))
    assert r0.packet.artifacts["crossing_events"] == ()   # frame đầu không có prev
    r1 = st.process(_packet([_track(1, 45, 50)]))         # cùng phía → không qua
    assert r1.packet.artifacts["crossing_events"] == ()
    assert r1.packet.artifacts["crossings_total"] == 0    # đếm vẫn đúng (regression)


def test_default_clock_is_wallclock_utc_z():  # P4 (mặc định)
    st = LineCrossingStage(50, 0, 50, 100)                # KHÔNG tiêm → now(UTC)
    st.process(_packet([_track(1, 40, 50)]))
    e = st.process(_packet([_track(1, 60, 50)])).packet.artifacts["crossing_events"][0]
    assert e.event_ts.endswith("Z")
    datetime.fromisoformat(e.event_ts.replace("Z", "+00:00"))  # parse được = ISO hợp lệ


# ================= CrossingEventJsonlSink =================

def _exec(packet):
    return ExecutionResult.processed(packet)


def test_sink_writes_one_line_per_event(tmp_path):  # P3
    path = tmp_path / "cross.jsonl"
    sink = CrossingEventJsonlSink(str(path))
    sink.setup()
    try:
        ref = InMemoryArrayRef.from_copy(np.zeros((2, 2, 3), dtype=np.uint8))
        pkt = MediaPacket(packet_id="p", source_id="cam0", media_ref=ref, capture_time_ns=0).with_artifact(
            "crossing_events",
            (CrossingEvent(1, "car", "in", "cam0", 10.0, 20.0, "2026-01-02T03:04:05Z"),
             CrossingEvent(2, "person", "out", "cam0", 30.0, 40.0, "2026-01-02T03:04:06Z")),
        )
        sink.handle(_exec(pkt))
    finally:
        sink.teardown()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    d0 = json.loads(lines[0])
    assert d0 == {"event_ts": "2026-01-02T03:04:05Z", "source_id": "cam0", "track_id": 1,
                  "label": "car", "direction": "in", "cx": 10.0, "cy": 20.0}
    assert json.loads(lines[1])["track_id"] == 2


def test_sink_skips_non_success_and_no_events(tmp_path):  # P3 (edge)
    path = tmp_path / "c2.jsonl"
    sink = CrossingEventJsonlSink(str(path))
    sink.setup()
    try:
        sink.handle(ExecutionResult(status=StageStatus.ERROR))          # non-SUCCESS → không ghi
        ref = InMemoryArrayRef.from_copy(np.zeros((2, 2, 3), dtype=np.uint8))
        pkt = MediaPacket(packet_id="p", source_id="cam0", media_ref=ref, capture_time_ns=0)
        sink.handle(ExecutionResult.processed(pkt))                     # SUCCESS nhưng KHÔNG có crossing_events
    finally:
        sink.teardown()
    # file tồn tại (setup mở "a") nhưng 0 dòng (không event nào)
    assert path.exists() and path.read_text(encoding="utf-8") == ""


# ================= wiring --crossing-out =================

def test_slice_app_crossing_out_wiring(tmp_path):
    from vision_platform.profiles.vision_slice_app import main
    out = tmp_path / "ev.jsonl"
    rc = main(["--source", "fake", "--frames", "5", "--track", "--line", "50,0,50,100",
               "--crossing-out", str(out)])
    assert rc == 0
    # FakeDetector box cố định → không lượt qua → file tạo (append) nhưng 0 dòng.
    assert out.exists() and out.read_text(encoding="utf-8") == ""


def test_crossing_out_requires_line():
    from vision_platform.profiles.vision_slice_app import main
    with pytest.raises(SystemExit):
        main(["--source", "fake", "--frames", "3", "--track", "--crossing-out", "x.jsonl"])
