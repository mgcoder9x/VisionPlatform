"""Test app demo trực quan (cần cv2 — guard importorskip)."""
from __future__ import annotations

import glob
import os

import numpy as np
import pytest

pytest.importorskip("cv2", reason="cần opencv-python (.[cv2])")

from vision_platform.profiles.vision_demo_app import (  # noqa: E402
    moving_square_frame, draw_detections, run_demo, _synthetic_source,
)
from vision_platform.adapters.blob_detector import BrightBlobDetector  # noqa: E402
from vision_platform.adapters.detector_pipeline import DetectorPipeline  # noqa: E402


def test_moving_square_frame_has_bright_region():
    f = moving_square_frame(0, 60, 80)
    assert f.shape == (60, 80, 3)
    assert f.max() == 255          # ô sáng
    assert f.min() == 30           # nền xám 30 (đỡ đen thui)
    assert (f == 255).any()        # có vùng sáng để detect


def test_run_demo_saves_annotated_frames(tmp_path):
    """Chạy demo headless → lưu PNG có box; frame có ô sáng → CÓ detection; ảnh có pixel xanh (box đã vẽ)."""
    import cv2
    h, w, n = 60, 80, 5
    detector = DetectorPipeline(BrightBlobDetector(threshold=127), model_h=h, model_w=w)
    stats = run_demo(detector, _synthetic_source(n, h, w), save_dir=str(tmp_path))
    assert stats["frames"] == n
    assert stats["frames_with_detection"] == n            # mỗi frame có ô sáng → đều detect

    pngs = sorted(glob.glob(os.path.join(str(tmp_path), "frame_*.png")))
    assert len(pngs) == n
    img = cv2.imread(pngs[0])
    assert img is not None and img.shape == (h, w, 3)
    # Box vẽ màu xanh (0,255,0) BGR → phải có ít nhất 1 pixel xanh thuần.
    green = (img[:, :, 0] == 0) & (img[:, :, 1] == 255) & (img[:, :, 2] == 0)
    assert green.any(), "không thấy pixel box xanh → box chưa được vẽ"


def test_draw_detections_returns_new_image():
    frame = moving_square_frame(1, 40, 40)
    detector = DetectorPipeline(BrightBlobDetector(threshold=127), model_h=40, model_w=40)
    detector.setup()
    dets = detector.detect(frame)
    detector.teardown()
    out = draw_detections(frame, dets)
    assert out.shape == frame.shape
    assert out is not frame                                 # bản copy, không sửa gốc
