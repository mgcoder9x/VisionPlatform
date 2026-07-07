"""Verify LOGIC harness benchmark (chạy máy dev, KHÔNG cần GPU) — spec node-capacity-benchmark PHA2.

Kiểm _stats (percentile/throughput/drop-warmup) + measure_* (đếm mẫu, bỏ warmup, dừng EOF) bằng Fake* trên CPU.
KHÔNG kiểm số capacity (cần GPU) — chỉ kiểm harness TÍNH ĐÚNG.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

# benchmarks/ nằm NGOÀI src (không cài editable) → thêm gốc vision-platform vào sys.path để import.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from benchmarks._stats import summarize, batch_throughput_per_s  # noqa: E402
from benchmarks.bench_capacity import (  # noqa: E402
    measure_infer, measure_latency, measure_decode, measure_infer_batch,
)
from vision_platform.adapters.fake_detector import FakeDetector  # noqa: E402
from vision_platform.adapters.fake_frame_source import FakeFrameSource  # noqa: E402


# ---- _stats.summarize ----

def test_summarize_drops_warmup_and_counts():
    samples = [i * 1_000_000 for i in range(1, 11)]  # 1ms..10ms, 10 mẫu
    st = summarize(samples, warmup=3)
    assert st.n_samples == 7 and st.warmup_dropped == 3


def test_summarize_percentiles_and_throughput_known_input():
    samples = [i * 1_000_000 for i in range(1, 101)]  # 1ms..100ms
    st = summarize(samples, warmup=0)
    assert st.min_ms == pytest.approx(1.0)
    assert st.max_ms == pytest.approx(100.0)
    assert st.p50_ms == pytest.approx(50.5, rel=1e-6)
    assert st.p95_ms == pytest.approx(95.05, rel=1e-6)
    assert st.p50_ms <= st.p95_ms <= st.p99_ms <= st.max_ms
    # tổng = 5050ms = 5.05s → 100/5.05 ≈ 19.80/s
    assert st.throughput_per_s == pytest.approx(100 / 5.05, rel=1e-6)


def test_summarize_empty_after_warmup_raises():
    with pytest.raises(ValueError):
        summarize([1_000_000, 2_000_000], warmup=5)


def test_batch_throughput_images_per_second():
    # 10 batch × 4 ảnh trong 2s → 20 ảnh/s
    assert batch_throughput_per_s(10, 4, 2_000_000_000) == pytest.approx(20.0)


# ---- measure_* với Fake* (CPU) ----

def test_measure_infer_counts_and_drops_warmup():
    det = FakeDetector(); det.setup()
    try:
        frame = np.full((16, 16, 3), 100, dtype=np.uint8)
        st = measure_infer(det, frame, count=10, warmup=2)
        assert st.n_samples == 8 and st.warmup_dropped == 2
        assert st.throughput_per_s > 0
    finally:
        det.teardown()


def test_measure_latency_counts_and_stops_at_eof():
    src = FakeFrameSource(width=16, height=16, max_frames=20); src.setup()
    det = FakeDetector(); det.setup()
    try:
        st = measure_latency(det, src, count=6, warmup=1)
        assert st.n_samples == 5
    finally:
        det.teardown(); src.teardown()


def test_measure_latency_stops_early_when_source_exhausts():
    # nguồn chỉ 3 frame nhưng xin đo 10 → dừng ở EOF (không treo)
    src = FakeFrameSource(width=16, height=16, max_frames=3); src.setup()
    det = FakeDetector(); det.setup()
    try:
        st = measure_latency(det, src, count=10, warmup=0)
        assert st.n_samples == 3
    finally:
        det.teardown(); src.teardown()


def test_measure_decode_counts_frames():
    src = FakeFrameSource(width=16, height=16, max_frames=20); src.setup()
    try:
        st = measure_decode(src, count=6, warmup=1)
        assert st.n_samples == 5 and st.throughput_per_s > 0
    finally:
        src.teardown()


def test_measure_infer_batch_with_injected_fn():
    frame = np.full((16, 16, 3), 100, dtype=np.uint8)
    calls = []
    def fake_infer_batch(imgs):
        calls.append(len(imgs))       # ghi batch size mỗi lần gọi
        return [im.mean() for im in imgs]
    stats, imgs_per_s = measure_infer_batch(
        fake_infer_batch, [frame], batch=4, n_batches=5, warmup=1,
    )
    assert stats.n_samples == 4          # 5 batch - 1 warmup
    assert all(c == 4 for c in calls) and len(calls) == 5
    assert imgs_per_s > 0
