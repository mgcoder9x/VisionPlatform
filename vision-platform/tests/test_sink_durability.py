"""Durability per-event (bất biến K-074) — MÁY-KIỂM cho kết luận "abrupt-kill/SIGTERM KHÔNG mất dữ liệu".

Bối cảnh (K-074/#302): quyết định KHÔNG cài graceful-shutdown dựa trên FACT tải-trọng: mọi sink làm dữ liệu
BỀN NGAY sau `handle()` (JSONL flush/dòng · SQLite commit/frame) → KHÔNG phụ thuộc `teardown()`. Nếu điều đó
đúng thì ngay cả khi process bị kill đột ngột (không chạy finally/teardown), event ĐÃ xử lý vẫn còn trên đĩa.

Test này KIỂM CHỨNG fact đó bằng OBSERVABLE (đọc-lại bằng handle/connection KHÁC KHI sink CHƯA teardown) —
mạnh hơn "đọc code thấy flush". Deterministic, cross-platform (KHÔNG subprocess/không timing → không flake).

**Vai trò regression (điều kiện đảo K-074):** nếu tương lai đổi sink sang BATCH/bỏ flush-per-event → các test
này FAIL → buộc xét lại nhu cầu graceful-shutdown (SIGTERM→should_stop→teardown). = máy-kiểm thay kỷ luật.
"""
from __future__ import annotations

import json
import sqlite3

import numpy as np

from vision_platform.adapters.jsonl_event_sink import JsonlEventSink
from vision_platform.adapters.crossing_event_sink import CrossingEventJsonlSink
from vision_platform.adapters.crossing_event_sqlite_sink import CrossingEventSqliteSink
from vision_platform.kernel.crossing_event import CrossingEvent
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import ExecutionResult


def _packet(source_id="cam0", **artifacts):
    ref = InMemoryArrayRef.from_copy(np.zeros((2, 2, 3), dtype=np.uint8))
    pkt = MediaPacket(packet_id="p", source_id=source_id, media_ref=ref, capture_time_ns=0)
    for k, v in artifacts.items():
        pkt = pkt.with_artifact(k, v)
    return pkt


def test_jsonl_event_sink_durable_without_teardown(tmp_path):
    """JsonlEventSink: sau handle() (flush/dòng) → đọc file bằng handle KHÁC, CHƯA teardown → event đã có."""
    path = tmp_path / "e.jsonl"
    sink = JsonlEventSink(str(path))
    sink.setup()
    sink.handle(ExecutionResult.processed(_packet(count=7)))
    # CỐ Ý KHÔNG teardown() — mô phỏng process bị kill đột ngột trước khi dọn dẹp.
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["count"] == 7        # đã flush ra đĩa, đọc lại được
    sink.teardown()                                  # dọn cho gọn (không ảnh hưởng khẳng định trên)


def test_crossing_jsonl_sink_durable_without_teardown(tmp_path):
    """CrossingEventJsonlSink: event qua-vạch bền ngay sau handle(), chưa teardown."""
    path = tmp_path / "c.jsonl"
    sink = CrossingEventJsonlSink(str(path))
    sink.setup()
    sink.handle(ExecutionResult.processed(_packet(
        crossing_events=(CrossingEvent(1, "car", "in", "cam0", 10.0, 20.0, "2026-01-02T03:04:05Z"),))))
    # KHÔNG teardown()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["track_id"] == 1
    sink.teardown()


def test_crossing_sqlite_sink_durable_without_teardown(tmp_path):
    """CrossingEventSqliteSink: sau handle() (commit/frame) → connection KHÁC đọc thấy row, CHƯA teardown."""
    db = str(tmp_path / "c.sqlite")
    sink = CrossingEventSqliteSink(db)
    sink.setup()
    sink.handle(ExecutionResult.processed(_packet(
        crossing_events=(CrossingEvent(1, "car", "in", "cam0", 10.0, 20.0, "2026-01-02T03:04:05Z"),))))
    # CỐ Ý KHÔNG teardown() — mở connection MỚI đọc dữ liệu ĐÃ commit.
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM crossings").fetchone()[0]
    finally:
        conn.close()
    assert n == 1                                    # commit-per-frame → visible cho connection khác trước teardown
    sink.teardown()
