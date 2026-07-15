"""Test Task 2 (adaptive-detection-perf): MotionGate core @domain (tái dùng changed_ratio, KHÔNG Stage).

TDD: pin ngữ nghĩa MotionGate (mirror MotionGateStage nhưng decouple MediaPacket) — dùng ở tầng loop bespoke.
"""
import numpy as np

from vision_platform.domain.motion_gate import MotionGate


def _frame(val: int, h: int = 20, w: int = 20) -> np.ndarray:
    return np.full((h, w, 3), val, dtype=np.uint8)


def test_first_frame_always_runs():
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005)
    run, ratio, forced = g.decide(_frame(100))
    assert run is True and forced is False and ratio == 1.0


def test_static_scene_skips():
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005)
    g.decide(_frame(100))                      # frame đầu → run
    run, ratio, forced = g.decide(_frame(100)) # y hệt → tĩnh → skip
    assert run is False and forced is False and ratio == 0.0


def test_motion_scene_runs():
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005)
    g.decide(_frame(0))
    run, ratio, forced = g.decide(_frame(255))  # đổi toàn bộ → ratio=1.0 > ngưỡng → run
    assert run is True and forced is False and ratio == 1.0


def test_shape_change_runs_and_resets():
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005)
    g.decide(_frame(100, 20, 20))
    run, ratio, forced = g.decide(_frame(100, 30, 30))   # đổi shape → thiếu mốc → run
    assert run is True and forced is False and ratio == 1.0


def test_forced_after_max_consecutive_skip():
    # max=2: static frames → skip,skip, rồi FORCED (chống bỏ sót vật đứng yên).
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005, max_consecutive_skip=2)
    g.decide(_frame(100))                       # đầu → run
    r1 = g.decide(_frame(100))                  # skip (cs=1)
    r2 = g.decide(_frame(100))                  # skip (cs=2)
    r3 = g.decide(_frame(100))                  # cs>=2 → FORCED, cs=0
    assert r1[0] is False and r2[0] is False
    assert r3[0] is True and r3[2] is True      # forced=True
    # sau forced, lại đếm từ đầu
    r4 = g.decide(_frame(100))
    assert r4[0] is False


def test_motion_resets_consecutive_skips():
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005, max_consecutive_skip=2)
    g.decide(_frame(100))
    g.decide(_frame(100))          # skip cs=1
    g.decide(_frame(255))          # motion → run, cs reset 0
    r = g.decide(_frame(255))      # static again → skip cs=1 (không forced)
    assert r[0] is False and r[2] is False


def test_roi_restricts_measurement():
    # ROI nửa trái; đổi chỉ nửa PHẢI (ngoài ROI) → trong ROI không đổi → skip.
    g = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005, roi=(0.0, 0.0, 0.5, 1.0))
    base = _frame(100, 20, 20)
    g.decide(base)
    moved = base.copy()
    moved[:, 10:, :] = 255          # đổi nửa phải (cột 10..19) — ngoài ROI trái
    run, ratio, forced = g.decide(moved)
    assert run is False             # ROI trái không đổi → tĩnh → skip
