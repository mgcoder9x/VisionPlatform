"""Test vertical slice: source → DetectStage → CountStage → sink qua PipelineRunner.

CI XÁC ĐỊNH (Fake/Noise + FakeDetector/stub — không cần camera/GPU/mạng). Bám design vision-vertical-slice.
"""
import json

import numpy as np
import pytest

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.kernel.ports.sink import ISink
from vision_platform.adapters.fake_frame_source import FakeFrameSource
from vision_platform.adapters.fake_detector import FakeDetector
from vision_platform.adapters.detector_pipeline import DetectorPipeline
from vision_platform.adapters.jsonl_event_sink import JsonlEventSink
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.composite_sink import CompositeSink
from vision_platform.runtime.collecting_sink import CollectingSink
from vision_platform.runtime.stages.detect_stage import DetectStage
from vision_platform.runtime.stages.count_stage import CountStage


# ---- stub detectors (IDetector) cho test xác định ----
class _KDetector:
    """Trả K detection MODEL_INPUT (box nhỏ, hợp lệ cho inverse-transform nếu bọc DetectorPipeline)."""
    def __init__(self, k: int, label: str = "obj"):
        self._k = k
        self._label = label

    def setup(self) -> None: ...
    def teardown(self) -> None: ...

    def detect(self, frame):
        return [
            Detection(self._label, 0.9, BBox(0.0, 0.0, 10.0, 10.0, CoordinateSpace.MODEL_INPUT))
            for _ in range(self._k)
        ]


class _RaisingDetector:
    def setup(self) -> None: ...
    def teardown(self) -> None: ...
    def detect(self, frame):
        raise RuntimeError("boom detect")


def _packet(arr, **arts):
    p = MediaPacket("p-0", "src", InMemoryArrayRef.from_copy(arr), 0)
    for k, v in arts.items():
        p = p.with_artifact(k, v)
    return p


# ---- T1: ISink conformance ----
def test_collecting_sink_is_isink():
    assert isinstance(CollectingSink(), ISink)


# ---- P1: end-to-end count=1 (FakeDetector qua DetectorPipeline) ----
def test_slice_end_to_end_count_1():
    source = FakeFrameSource(width=64, height=48, max_frames=5)
    executor = SyncLinearExecutor([
        DetectStage(DetectorPipeline(FakeDetector(), 64, 64)),
        CountStage(),
    ])
    collecting = CollectingSink()
    runner = PipelineRunner(source, executor, CompositeSink([collecting]))
    stats = runner.run()
    assert stats.frames_read == 5
    assert stats.processed == 5
    assert stats.stage_errors == 0
    for r in collecting.results:
        assert r.status == StageStatus.SUCCESS
        assert r.packet.artifacts["count"] == 1
        assert r.packet.artifacts["count_by_label"] == {"object": 1}


# ---- P1': count=K (stub) ----
def test_slice_count_k():
    source = FakeFrameSource(width=32, height=32, max_frames=3)
    executor = SyncLinearExecutor([DetectStage(_KDetector(4)), CountStage()])
    collecting = CollectingSink()
    PipelineRunner(source, executor, CompositeSink([collecting])).run()
    assert collecting.counts == [4, 4, 4]
    for r in collecting.results:
        assert r.packet.artifacts["count_by_label"] == {"obj": 4}


# ---- P2: bulkhead — detector ném → stage_errors, không raise ----
def test_slice_detector_raises_bulkhead():
    source = FakeFrameSource(width=16, height=16, max_frames=3)
    executor = SyncLinearExecutor([DetectStage(_RaisingDetector()), CountStage()])
    collecting = CollectingSink()
    stats = PipelineRunner(source, executor, CompositeSink([collecting])).run()
    assert stats.frames_read == 3
    assert stats.processed == 0
    assert stats.stage_errors == 3
    assert all(r.status == StageStatus.ERROR for r in collecting.results)


# ---- P3: edge — thiếu key vs rỗng ----
def test_count_stage_missing_detections_is_error():
    stage = CountStage()
    result = stage.process(_packet(np.zeros((4, 4, 3), np.uint8)))  # KHÔNG có "detections"
    assert result.status == StageStatus.ERROR


def test_count_stage_empty_detections_is_zero():
    stage = CountStage()
    result = stage.process(_packet(np.zeros((4, 4, 3), np.uint8), detections=()))
    assert result.status == StageStatus.SUCCESS
    assert result.packet.artifacts["count"] == 0
    assert result.packet.artifacts["count_by_label"] == {}


# ---- P4: JsonlEventSink — file + event_ts + box.space ----
def test_jsonl_event_sink_writes_events(tmp_path):
    out = tmp_path / "events.jsonl"
    source = FakeFrameSource(width=64, height=48, max_frames=4)
    executor = SyncLinearExecutor([
        DetectStage(DetectorPipeline(FakeDetector(), 64, 64)),
        CountStage(),
    ])
    runner = PipelineRunner(source, executor, CompositeSink([JsonlEventSink(str(out))]))
    stats = runner.run()
    assert stats.processed == 4
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    for line in lines:
        ev = json.loads(line)
        assert ev["count"] == 1
        assert ev["count_by_label"] == {"object": 1}
        assert ev["event_ts"].endswith("Z")  # wall-clock UTC ISO
        assert ev["detections"][0]["box"]["space"] == "original"  # qua DetectorPipeline → ORIGINAL_FRAME


def test_no_out_no_file_created(tmp_path):
    out = tmp_path / "nope.jsonl"
    source = FakeFrameSource(width=16, height=16, max_frames=2)
    executor = SyncLinearExecutor([DetectStage(_KDetector(1)), CountStage()])
    PipelineRunner(source, executor, CompositeSink([])).run()  # KHÔNG gắn Jsonl
    assert not out.exists()


# ---- P4': source ERROR → source_errors, không raise ----
def test_source_error_counted_not_raised():
    source = FakeFrameSource(width=16, height=16, max_frames=4, inject_error_at=1)
    executor = SyncLinearExecutor([DetectStage(_KDetector(1)), CountStage()])
    stats = PipelineRunner(source, executor, CompositeSink([])).run()
    assert stats.source_errors >= 1
    assert stats.frames_read >= 1  # vẫn đọc được các frame khác


# ---- CompositeSink forward tới nhiều sink ----
def test_composite_sink_forwards_all():
    source = FakeFrameSource(width=16, height=16, max_frames=2)
    executor = SyncLinearExecutor([DetectStage(_KDetector(1)), CountStage()])
    s1, s2 = CollectingSink(), CollectingSink()
    PipelineRunner(source, executor, CompositeSink([s1, s2])).run()
    assert len(s1.results) == 2
    assert len(s2.results) == 2


# ---- F1 (#324): CLI args → PipelineConfig mapping (đường CLI-direct dùng chung build_runner) ----
from vision_platform.profiles.vision_slice_app import _args_to_pipeline_config, _build_argparser


def _args(argv):
    return _build_argparser().parse_args(argv)


def test_args_to_pcfg_minimal_noise():
    pcfg = _args_to_pipeline_config(_args(["--source", "noise", "--frames", "5"]))
    assert pcfg.source.type == "noise"
    assert pcfg.source.params["max_frames"] == 5
    assert [s.type for s in pcfg.stages] == ["detect", "count"]
    assert pcfg.detector.type == "fake"
    assert pcfg.detector.params["model_size"] == 640          # default KHỚP (verify #323)
    assert pcfg.sinks == ()


def test_args_to_pcfg_full_stage_order_and_sinks(tmp_path):
    argv = [
        "--source", "fake", "--motion-gate", "--motion-gate-roi", "0,0,0.5,0.5",
        "--track", "--line", "0,0.5,1,0.5",
        "--out", str(tmp_path / "e.jsonl"),
        "--crossing-out", str(tmp_path / "c.jsonl"),
        "--crossing-db", str(tmp_path / "c.sqlite"),
    ]
    pcfg = _args_to_pipeline_config(_args(argv))
    # GIỮ THỨ TỰ stage suy từ cờ.
    assert [s.type for s in pcfg.stages] == ["motion_gate", "detect", "count", "track", "line_crossing"]
    mg = next(s for s in pcfg.stages if s.type == "motion_gate")
    assert mg.params["roi"] == (0.0, 0.0, 0.5, 0.5)
    assert mg.params["max_consecutive_skip"] == 0
    assert mg.params["illumination_robust"] is False
    tr = next(s for s in pcfg.stages if s.type == "track")
    assert tr.params == {"iou_threshold": 0.3, "max_age": 30}   # default KHỚP
    ln = next(s for s in pcfg.stages if s.type == "line_crossing")
    assert ln.params == {"ax": 0.0, "ay": 0.5, "bx": 1.0, "by": 0.5}
    assert [s.type for s in pcfg.sinks] == ["jsonl", "crossing_events", "crossing_events_sqlite"]


def test_args_to_pcfg_rtsp_and_pt():
    p1 = _args_to_pipeline_config(_args(["--source", "rtsp", "--rtsp", "rtsp://h/c"]))
    assert p1.source.type == "rtsp"
    assert p1.source.params["url"] == "rtsp://h/c"
    assert p1.source.params["max_reconnect"] is None
    p2 = _args_to_pipeline_config(_args(["--detector", "pt", "--weights", "w.pt", "--device", "auto"]))
    assert p2.detector.type == "pt"
    assert p2.detector.params == {"weights": "w.pt", "device": "auto"}


def test_cli_direct_uses_build_runner_end_to_end_with_track_summary(capsys):
    """Đường CLI-direct (sau F1) chạy qua build_runner + extra_sinks (_TrackSummarySink) → summary in đúng."""
    from vision_platform.profiles.vision_slice_app import main
    rc = main(["--source", "noise", "--frames", "3", "--track", "--line", "0,0.5,1,0.5"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "vision_slice summary" in err
    assert "unique_tracks" in err and "crossings_in" in err   # track_summary qua extra_sinks hoạt động
