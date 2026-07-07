"""Thống kê cho benchmark (THUẦN — không torch/GPU, test được trên máy dev).

Tách riêng để verify LOGIC (percentile/throughput/drop-warmup) độc lập với việc đo GPU thật.
Đơn vị: mẫu thời gian = nanô-giây (perf_counter_ns); latency báo cáo = mili-giây; throughput = /giây.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class Stats:
    """Tổng hợp 1 phép đo (sau khi bỏ warmup). Thời gian ở mili-giây; throughput ở /giây."""
    n_samples: int          # số mẫu ĐƯỢC TÍNH (đã bỏ warmup)
    warmup_dropped: int     # số mẫu warmup đã bỏ
    median_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    throughput_per_s: float  # = n_samples / tổng thời gian steady-state

    def as_row(self) -> str:
        return (f"n={self.n_samples} (warmup bỏ {self.warmup_dropped}) · "
                f"throughput={self.throughput_per_s:.2f}/s · "
                f"latency ms p50={self.p50_ms:.3f} p95={self.p95_ms:.3f} "
                f"p99={self.p99_ms:.3f} min={self.min_ms:.3f} max={self.max_ms:.3f}")


def summarize(sample_ns: Sequence[int], *, warmup: int = 0) -> Stats:
    """Bỏ `warmup` mẫu đầu → tính percentile latency (ms) + throughput (/s).

    - `sample_ns`: list khoảng thời gian mỗi lần đo (ns), THEO THỨ TỰ đo (để bỏ warmup đầu).
    - throughput = n / (tổng thời gian các mẫu steady-state). Raise nếu không còn mẫu sau warmup.
    """
    if warmup < 0:
        raise ValueError("warmup không âm")
    kept = list(sample_ns[warmup:])
    if not kept:
        raise ValueError(f"không còn mẫu sau khi bỏ {warmup} warmup (tổng {len(sample_ns)})")

    arr_ms = np.asarray(kept, dtype=np.float64) / 1e6  # ns → ms
    total_s = float(np.sum(arr_ms)) / 1e3              # ms → s
    throughput = (len(kept) / total_s) if total_s > 0 else float("inf")

    return Stats(
        n_samples=len(kept),
        warmup_dropped=min(warmup, len(sample_ns)),
        median_ms=float(np.median(arr_ms)),
        p50_ms=float(np.percentile(arr_ms, 50)),
        p95_ms=float(np.percentile(arr_ms, 95)),
        p99_ms=float(np.percentile(arr_ms, 99)),
        min_ms=float(np.min(arr_ms)),
        max_ms=float(np.max(arr_ms)),
        throughput_per_s=throughput,
    )


def batch_throughput_per_s(n_batches: int, batch_size: int, total_ns: int) -> float:
    """Throughput inference (ảnh/giây) khi chạy `n_batches` batch cỡ `batch_size` trong `total_ns`."""
    if total_ns <= 0:
        raise ValueError("total_ns phải > 0")
    return (n_batches * batch_size) / (total_ns / 1e9)
