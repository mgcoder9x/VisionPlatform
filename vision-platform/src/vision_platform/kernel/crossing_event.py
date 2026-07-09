"""CrossingEvent DTO — 1 lượt vật băng qua vạch (sub-spec crossing-event-log, R1).

Layer: kernel — DTO thuần (frozen), chỉ str/int/float → json/msgpack-friendly. KHÔNG giữ BBox (chỉ tâm cx,cy
đủ cho event qua-vạch; box đầy đủ ở detections nếu cần). `event_ts` = WALL-CLOCK UTC ISO-8601 (hậu tố "Z") —
giờ THẬT cho log/audit (monotonic vô nghĩa khi đọc lại — đồng bộ QĐ-4 slice/JsonlEventSink).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrossingEvent:
    track_id: int
    label: str
    direction: str      # "in" | "out" (theo dấu phía so vạch A→B)
    source_id: str
    cx: float
    cy: float
    event_ts: str        # ISO-8601 UTC, hậu tố "Z"
