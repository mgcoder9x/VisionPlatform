"""JsonlEventSink — ISink ghi 1 dòng JSON/frame-SUCCESS ra file .jsonl. Layer: adapters (leaf, chạm I/O file).

Minh hoạ LƯU TRỮ OPTIONAL (C-013): gắn vào → có event log; không gắn → không tạo file, pipeline y hệt.

Mốc thời gian: dùng `event_ts` WALL-CLOCK UTC (ISO-8601) làm mốc CHÍNH cho log — vì `capture_time_ns` là
monotonic (mốc gốc không xác định → vô nghĩa khi đọc lại sau). Giữ capture_time_ns như field phụ (đo trễ nội bộ).
Box GIỮ NGUYÊN space tag (invariant Step 02 — không giả định original).

flush() mỗi dòng: durability cho event log (mất tối đa 1 event khi crash cứng) — chấp nhận chậm hơn.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus


class JsonlEventSink:
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
            return  # v1: chỉ ghi event SUCCESS; lỗi/skip đếm ở RunStats.
        packet = result.packet
        arts = packet.artifacts
        event = {
            "event_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "capture_time_ns": packet.capture_time_ns,
            "source_id": packet.source_id,
            "count": arts.get("count"),
            "count_by_label": dict(arts.get("count_by_label") or {}),
            "detections": [self._det_to_dict(d) for d in arts.get("detections", ())],
        }
        self._f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._f.flush()

    @staticmethod
    def _det_to_dict(d) -> dict:
        b = d.box
        return {
            "label": d.label,
            "confidence": d.confidence,
            "box": {"x": b.x, "y": b.y, "w": b.w, "h": b.h, "space": b.space.value},
        }

    def teardown(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None
