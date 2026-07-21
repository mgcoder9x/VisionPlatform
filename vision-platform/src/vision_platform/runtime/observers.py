"""Observers cho PipelineRunner — impl `IPipelineObserver` (spec pipeline-observability).

Layer: runtime (được import structlog — contract #3 chỉ cấm application/adapters/profiles). Tái dùng
`InMemoryMetrics` đã có (#08/D-025) → zero dependency mới. Adapter Prometheus/StatsD = Non-Goal v1 (tầng
adapters sau, chỉ cần implement `on_snapshot`).

Mọi observer ở đây NON-BLOCKING (chỉ ghi bộ nhớ/log) — đúng hợp đồng port (chạy trong thread run()).
"""
from __future__ import annotations

from typing import List

import structlog

from vision_platform.kernel.observability_port import PipelineSnapshot


class NoopObserver:
    """Mặc định của PipelineRunner — KHÔNG làm gì (backward-compat: bật observability = opt-in)."""

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        return None


class CollectingObserver:
    """Thu snapshot vào list (test + demo). Non-blocking (chỉ append)."""

    def __init__(self) -> None:
        self.snapshots: List[PipelineSnapshot] = []

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        self.snapshots.append(snapshot)


class LoggingObserver:
    """Ghi mỗi snapshot 1 dòng structlog JSON (parse được bởi Loki/ELK/Datadog)."""

    def __init__(self) -> None:
        self._log = structlog.get_logger("pipeline_observer")

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        self._log.info(
            "pipeline_snapshot",
            source_id=snapshot.source_id,
            frames_read=snapshot.frames_read,
            processed=snapshot.processed,
            skipped=snapshot.skipped,
            stage_errors=snapshot.stage_errors,
            fps=round(snapshot.frames_per_second, 2),
            skip_rate=round(snapshot.skip_rate, 4),
            is_final=snapshot.is_final,
        )


class FileLoggingObserver:
    """Ghi mỗi snapshot 1 dòng JSON tới `sink` NON-BLOCKING (spec F5.3/K-018 — production logging).

    `sink` TIÊM qua DI (duck-typed `.emit(str)`) — runtime KHÔNG import adapter (contract #3). Composition
    (profiles) truyền `ProductionLogHandle` (adapter: bounded-queue non-blocking + rotating + flush-on-shutdown).
    Observer chỉ SERIALIZE + gọi `emit` (non-blocking) → hot-path không chặn bởi I/O file (đúng hợp đồng
    `IPipelineObserver`). Tách serialize (runtime) ⊥ transport/rotation/flush (adapter).
    """

    def __init__(self, sink) -> None:
        self._sink = sink   # object có .emit(str) — vd ProductionLogHandle (tiêm ở profiles)

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        import json
        self._sink.emit(json.dumps({
            "event": "pipeline_snapshot",
            "source_id": snapshot.source_id,
            "frames_read": snapshot.frames_read,
            "processed": snapshot.processed,
            "skipped": snapshot.skipped,
            "stage_errors": snapshot.stage_errors,
            "fps": round(snapshot.frames_per_second, 2),
            "skip_rate": round(snapshot.skip_rate, 4),
            "is_final": snapshot.is_final,
        }, ensure_ascii=False))


class MetricsObserver:
    """Cập nhật gauge vào `InMemoryMetrics` (nhãn CHỈ `source` — bounded cardinality K-019).

    Production: thay `InMemoryMetrics` bằng adapter Prometheus/StatsD (implement cùng interface gauge)."""

    def __init__(self, metrics) -> None:
        self._m = metrics

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None:
        src = snapshot.source_id
        self._m.gauge("pipeline_fps", snapshot.frames_per_second, source=src)
        self._m.gauge("pipeline_skip_rate", snapshot.skip_rate, source=src)
        self._m.gauge("pipeline_frames_read", float(snapshot.frames_read), source=src)
        self._m.gauge("pipeline_stage_errors", float(snapshot.stage_errors), source=src)
