"""CrossingEventSqliteSink — ISink ghi CrossingEvent vào SQLite (queryable) (sub-spec crossing-event-sqlite-sink).

Layer: adapters (leaf, I/O sqlite file). `sqlite3` STDLIB (không dep mới). Song song `CrossingEventJsonlSink`:
JSONL để stream/append; SQLite để TRUY VẤN SQL (report theo giờ/hướng/camera). Đọc `artifacts["crossing_events"]`.

Thread-safety (trung thực): `sqlite3.connect` mặc định `check_same_thread=True` → connection dùng ĐÚNG 1 THREAD.
Sink chạy trong luồng runner (SyncLinearExecutor, 1 thread) → OK. Đa-thread/async = Non-Goal v1 (cần conn/thread).
"""
from __future__ import annotations

import os
import sqlite3

from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus

_CREATE = (
    "CREATE TABLE IF NOT EXISTS crossings ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " event_ts TEXT, source_id TEXT, track_id INTEGER, label TEXT,"
    " direction TEXT, cx REAL, cy REAL)"
)
_CREATE_IDX = "CREATE INDEX IF NOT EXISTS ix_crossings_src_ts ON crossings(source_id, event_ts)"
_INSERT = (
    "INSERT INTO crossings (event_ts, source_id, track_id, label, direction, cx, cy) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)


class CrossingEventSqliteSink:
    def __init__(self, path: str):
        self._path = path
        self._conn = None

    def setup(self) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # check_same_thread mặc định True: connection dùng 1 luồng (runner sync). Fail-fast nếu không mở được.
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(_CREATE)            # idempotent (IF NOT EXISTS) — mở DB cũ không hỏng bảng
        self._conn.execute(_CREATE_IDX)        # index query theo (camera, thời gian)
        self._conn.commit()

    def handle(self, result: ExecutionResult) -> None:
        if result.status != StageStatus.SUCCESS or result.packet is None:
            return
        evs = result.packet.artifacts.get("crossing_events", ())
        if not evs:
            return
        # Tham số hoá `?` (chống SQL-injection + đúng kiểu); executemany cho nhiều event/frame.
        self._conn.executemany(
            _INSERT,
            [(e.event_ts, e.source_id, e.track_id, e.label, e.direction, e.cx, e.cy) for e in evs],
        )
        self._conn.commit()                    # durability: commit sau mỗi frame có event

    def teardown(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
