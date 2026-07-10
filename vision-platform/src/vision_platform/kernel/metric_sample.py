"""MetricSample — DTO thuần cho 1 điểm metric CÓ CẤU TRÚC (spec metrics-exposition).

Layer: kernel — thuần Python (frozen dataclass). KHÔNG import lib ngoài. Dùng chung giữa `runtime`
(`InMemoryMetrics.iter_metrics` TẠO ra) và `adapters` (renderer Prometheus TIÊU THỤ) mà không đảo hướng
phụ thuộc (cả hai → kernel).

Vì sao có cấu trúc (name + labels tách rời) thay vì chuỗi key `name{k=v}`: key nội bộ của InMemoryMetrics
nối chuỗi KHÔNG escape → parse-ngược bị LOSSY khi value nhãn chứa `,`/`=`/`}`. DTO này giữ (name, labels)
nguyên vẹn từ lúc GHI → renderer khỏi parse → đúng tuyệt đối (fix gốc, xem spec D-071/#280).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class MetricSample:
    """1 điểm metric: loại + tên + nhãn (bounded) + giá trị. Immutable, thuần."""

    mtype: str                                  # "counter" | "gauge" (v1; histogram = Non-Goal)
    name: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)
