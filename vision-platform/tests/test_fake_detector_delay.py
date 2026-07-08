"""Task 2.1 — FakeDetector.delay_s (additive, R7.3).

- delay_s=0 (mặc định): output KHÔNG đổi so với hành vi cũ (1 detection, confidence=brightness/255).
- delay_s>0: thời gian detect() ≥ delay (đo monotonic, ngưỡng nới để không flaky).
Không cần torch/GPU.
"""
import time

import numpy as np

from vision_platform.adapters.fake_detector import FakeDetector
from vision_platform.domain.bbox import CoordinateSpace


def _frame(value: int, h: int = 32, w: int = 48) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.uint8)


def test_delay_default_zero_keeps_output():
    det = FakeDetector()  # mặc định delay_s=0.0
    det.setup()
    dets = det.detect(_frame(100))
    assert len(dets) == 1
    d = dets[0]
    assert d.label == "object"
    assert d.confidence == 100.0 / 255.0
    assert d.box.space == CoordinateSpace.MODEL_INPUT


def test_delay_default_is_fast():
    det = FakeDetector()
    det.setup()
    t0 = time.monotonic()
    det.detect(_frame(100))
    assert time.monotonic() - t0 < 0.05  # không delay → phải nhanh


def test_delay_positive_sleeps_at_least_delay():
    delay = 0.05
    det = FakeDetector(delay_s=delay)
    det.setup()
    t0 = time.monotonic()
    dets = det.detect(_frame(100))
    elapsed = time.monotonic() - t0
    assert elapsed >= delay * 0.8  # nới ngưỡng để không flaky do sleep granularity
    assert len(dets) == 1  # output vẫn đúng
