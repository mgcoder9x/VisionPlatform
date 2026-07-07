"""Test BrightBlobDetector (thuần numpy — không cv2)."""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.domain.bbox import CoordinateSpace
from vision_platform.adapters.blob_detector import BrightBlobDetector


def test_detects_bright_square():
    """Ô vuông sáng ở (y5..15, x10..20) → box bao đúng vùng đó (MODEL_INPUT)."""
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    frame[5:15, 10:20] = 255
    det = BrightBlobDetector(threshold=127)
    det.setup()
    out = det.detect(frame)
    det.teardown()
    assert len(out) == 1
    b = out[0].box
    assert b.space == CoordinateSpace.MODEL_INPUT
    assert (b.x, b.y, b.w, b.h) == (10.0, 5.0, 10.0, 10.0)
    assert out[0].label == "bright"


def test_empty_when_dark():
    det = BrightBlobDetector(threshold=127)
    det.setup()
    assert det.detect(np.zeros((16, 16, 3), dtype=np.uint8)) == []
    det.teardown()


def test_setup_required():
    det = BrightBlobDetector()
    with pytest.raises(RuntimeError, match="setup"):
        det.detect(np.zeros((8, 8, 3), dtype=np.uint8))
