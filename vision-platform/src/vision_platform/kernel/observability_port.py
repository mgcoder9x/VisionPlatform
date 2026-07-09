"""Port quan sát vận hành pipeline (spec pipeline-observability) — THUẦN, no lib ngoài.

Layer: kernel — chỉ Python thuần (Protocol + frozen DTO). KHÔNG import structlog/prometheus/runtime/adapters.
Adapter cụ thể (Prometheus/StatsD/log) implement `IPipelineObserver` ở tầng ngoài (runtime/adapters) qua DI.

Kênh SONG SONG với `RunStats`: `RunStats` là số liệu TỔNG trả lúc `run()` kết thúc; `PipelineSnapshot` là
số liệu ĐỊNH KỲ phát TRONG lúc chạy (thấy sức khỏe live, đặc biệt luồng RTSP vô hạn).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PipelineSnapshot:
    """Ảnh chụp số liệu vận hành 1 camera tại 1 thời điểm (immutable).

    - `frames_per_second`: throughput INTERVAL (frame kể từ lần emit trước / thời gian trôi) — phản ánh nhịp
      GẦN ĐÂY, KHÔNG che sự cố (khác trung bình tích luỹ). Xem design §Components.
    - `skip_rate`: `skipped/frames_read` tích luỹ (0.0 nếu frames_read==0) — tỉ lệ frame motion-gate bỏ.
    - `is_final`: True cho snapshot CHỐT lúc `run()` kết thúc.
    """
    source_id: str
    frames_read: int
    processed: int
    skipped: int
    stage_errors: int
    frames_per_second: float
    skip_rate: float
    is_final: bool = False


@runtime_checkable
class IPipelineObserver(Protocol):
    """Nhận snapshot số liệu định kỳ từ `PipelineRunner`. Impl PHẢI non-blocking (chạy trong thread run() —
    I/O chậm sẽ backpressure pipeline; adapter nặng tự buffer async)."""

    def on_snapshot(self, snapshot: PipelineSnapshot) -> None: ...
