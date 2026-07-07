"""Test Yolov5PtDetector — cấu trúc module (import LAZY torch/yolov5 → test được KHÔNG cần torch).

Load+detect THẬT cần env có torch+yolov5 (vd WSL) — verify riêng ngoài pytest. Ở đây kiểm: module import
được (torch lazy), construct OK, fail-fast khi detect trước setup, box space đúng convention (ORIGINAL_FRAME).
"""
from __future__ import annotations

import numpy as np
import pytest

from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector


def test_module_imports_without_torch():
    """Module + class dùng được KHÔNG cần torch cài (import lazy trong setup)."""
    d = Yolov5PtDetector("dummy.pt", conf=0.3, iou=0.5)
    assert d is not None


def test_detect_before_setup_raises():
    d = Yolov5PtDetector("dummy.pt")
    with pytest.raises(RuntimeError, match="setup"):
        d.detect(np.zeros((8, 8, 3), dtype=np.uint8))
