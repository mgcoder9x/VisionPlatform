"""Sub-spec crossing-event-sqlite-sink — test XÁC ĐỊNH (query lại DB), không GPU.

Phủ: ghi + query lại (P1) · setup idempotent (P2) · chỉ SUCCESS/không-event (P3) · index + tham-số-hoá an toàn
(P4) · cắm config/CLI (P5).
"""
import sqlite3

import numpy as np
import pytest

from vision_platform.adapters.crossing_event_sqlite_sink import CrossingEventSqliteSink
from vision_platform.kernel.crossing_event import CrossingEvent
from vision_platform.kernel.config import (
    AppConfig, PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
)
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus
from vision_platform.profiles.pipeline_factory import build_runner, validate_config, ConfigError


def _pkt(events):
    ref = InMemoryArrayRef.from_copy(np.zeros((2, 2, 3), dtype=np.uint8))
    return MediaPacket(packet_id="p", source_id="cam0", media_ref=ref, capture_time_ns=0)\
        .with_artifact("crossing_events", tuple(events))


def _ev(tid, direction, label="object", ts="2026-01-02T03:04:05Z"):
    return CrossingEvent(tid, label, direction, "cam0", 10.0 + tid, 20.0 + tid, ts)


def test_writes_and_queryable(tmp_path):  # P1
    db = str(tmp_path / "cross.sqlite")
    sink = CrossingEventSqliteSink(db)
    sink.setup()
    try:
        sink.handle(ExecutionResult.processed(_pkt([_ev(1, "in"), _ev(2, "out")])))
    finally:
        sink.teardown()
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT event_ts,source_id,track_id,label,direction,cx,cy FROM crossings ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert rows[0] == ("2026-01-02T03:04:05Z", "cam0", 1, "object", "in", 11.0, 21.0)
    assert rows[1][4] == "out" and rows[1][2] == 2


def test_setup_idempotent_and_teardown(tmp_path):  # P2
    db = str(tmp_path / "c.sqlite")
    s1 = CrossingEventSqliteSink(db)
    s1.setup()
    s1.handle(ExecutionResult.processed(_pkt([_ev(1, "in")])))
    s1.teardown()
    s2 = CrossingEventSqliteSink(db)   # mở lại DB đã có bảng → CREATE IF NOT EXISTS không lỗi
    s2.setup()
    s2.handle(ExecutionResult.processed(_pkt([_ev(2, "out")])))
    s2.teardown()
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM crossings").fetchone()[0] == 2  # nối tiếp, không hỏng
    finally:
        conn.close()


def test_skips_non_success_and_no_events(tmp_path):  # P3
    db = str(tmp_path / "c3.sqlite")
    sink = CrossingEventSqliteSink(db)
    sink.setup()
    try:
        sink.handle(ExecutionResult(status=StageStatus.ERROR))                 # non-SUCCESS
        ref = InMemoryArrayRef.from_copy(np.zeros((2, 2, 3), dtype=np.uint8))
        sink.handle(ExecutionResult.processed(
            MediaPacket(packet_id="p", source_id="c", media_ref=ref, capture_time_ns=0)))  # không crossing_events
    finally:
        sink.teardown()
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM crossings").fetchone()[0] == 0
    finally:
        conn.close()


def test_index_and_parameterized_safe(tmp_path):  # P4
    db = str(tmp_path / "c4.sqlite")
    sink = CrossingEventSqliteSink(db)
    sink.setup()
    try:
        # label chứa dấu nháy đơn — nếu nội suy chuỗi sẽ vỡ SQL; tham số hoá → lưu NGUYÊN.
        sink.handle(ExecutionResult.processed(_pkt([_ev(1, "in", label="car's plate")])))
    finally:
        sink.teardown()
    conn = sqlite3.connect(db)
    try:
        idx = [r[1] for r in conn.execute("PRAGMA index_list(crossings)").fetchall()]
        assert "ix_crossings_src_ts" in idx
        assert conn.execute("SELECT label FROM crossings").fetchone()[0] == "car's plate"
    finally:
        conn.close()


def test_config_and_cli_wiring(tmp_path):  # P5
    db = str(tmp_path / "cfg.sqlite")
    pcfg = PipelineConfig(
        id="cam0",
        source=SourceConfig("fake", {"max_frames": 3}),
        detector=DetectorConfig("fake", {"model_size": 64}),
        stages=[StageConfig("detect"), StageConfig("track"),
                StageConfig("line_crossing", {"ax": 50, "ay": 0, "bx": 50, "by": 100})],
        sinks=[SinkConfig("crossing_events_sqlite", {"path": db})],
    )
    validate_config(AppConfig([pcfg]))                # hợp lệ
    runner = build_runner(pcfg)
    runner.run(max_frames=3)                          # chạy thật, không crash
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM crossings").fetchone()[0] == 0  # box cố định → 0 lượt

    from vision_platform.profiles.vision_slice_app import main
    db2 = str(tmp_path / "cli.sqlite")
    rc = main(["--source", "fake", "--frames", "5", "--track", "--line", "50,0,50,100", "--crossing-db", db2])
    assert rc == 0 and sqlite3.connect(db2).execute("SELECT COUNT(*) FROM crossings").fetchone()[0] == 0


def test_crossing_db_requires_line():
    from vision_platform.profiles.vision_slice_app import main
    with pytest.raises(SystemExit):
        main(["--source", "fake", "--frames", "3", "--track", "--crossing-db", "x.sqlite"])
