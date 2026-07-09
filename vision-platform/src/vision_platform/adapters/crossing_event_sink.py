"""CrossingEventJsonlSink — ISink ghi mỗi CrossingEvent thành 1 dòng JSONL (sub-spec crossing-event-log, R3).

Layer: adapters (leaf, chạm I/O file). Theo Y mẫu `JsonlEventSink`: mkdir cha + open "a" (append) + flush mỗi dòng
(durability) + chỉ ghi khi result SUCCESS. Đọc `artifacts["crossing_events"]` (do LineCrossingStage phát).

Lưu trữ OPTIONAL (C-013): gắn → có event log; không gắn → không tạo file, pipeline y hệt.
`.get("crossing_events", ())` → an toàn cả khi pipeline KHÔNG có LineCrossingStage (backward-compat).
"""
from __future__ import annotations

import json
import os

from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus


class CrossingEventJsonlSink:
    def __init__(self, path: str):
        self._path = path
        self._f = None

    def setup(self) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # mode "a": append (không đè log cũ). Fail-fast nếu không mở được (không chạy mù).
        self._f = open(self._path, "a", encoding="utf-8")

    def handle(self, result: ExecutionResult) -> None:
        if result.status != StageStatus.SUCCESS or result.packet is None:
            return
        for ev in result.packet.artifacts.get("crossing_events", ()):
            row = {
                "event_ts": ev.event_ts,
                "source_id": ev.source_id,
                "track_id": ev.track_id,
                "label": ev.label,
                "direction": ev.direction,
                "cx": ev.cx,
                "cy": ev.cy,
            }
            self._f.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._f.flush()

    def teardown(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None
