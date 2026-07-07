"""Wave 1 (spec backpressure-cross-process, task 1): BackpressureMetrics DTO ở kernel.

Kiểm 3 nhóm theo design §4.1 / tasks task 1:
- (a) property `conserved` = bất biến bảo toàn (R4.3): True khi submitted+dropped==captured, False khi lệch.
- (b) frozen (R5.5 DTO thuần): gán lại field → raise FrozenInstanceError.
- (c) 6 field int giữ đúng giá trị truyền vào.
- (d) kernel thuần: module KHÔNG import zmq/torch/cv2/multiprocessing/shared_memory (R9.1).
"""
import dataclasses

import pytest

from vision_platform.kernel.backpressure_metrics import BackpressureMetrics


# ============ (c) field giữ đúng giá trị ============

def test_fields_kept():
    m = BackpressureMetrics(
        frames_captured=10,
        frames_submitted=7,
        frames_dropped_backpressure=3,
        infer_ok=5,
        infer_err=1,
        infer_timeout=1,
    )
    assert m.frames_captured == 10
    assert m.frames_submitted == 7
    assert m.frames_dropped_backpressure == 3
    assert m.infer_ok == 5
    assert m.infer_err == 1
    assert m.infer_timeout == 1


# ============ (a) property conserved ============

def test_conserved_true_when_balanced():
    # 7 + 3 == 10 → bảo toàn
    m = BackpressureMetrics(10, 7, 3, 5, 1, 1)
    assert m.conserved is True


def test_conserved_true_zero():
    # 0 + 0 == 0 → bảo toàn (trạng thái rỗng)
    m = BackpressureMetrics(0, 0, 0, 0, 0, 0)
    assert m.conserved is True


def test_conserved_false_when_submitted_plus_dropped_less_than_captured():
    # 6 + 3 = 9 != 10 → có frame lửng (chưa gửi/chưa drop) → KHÔNG bảo toàn
    m = BackpressureMetrics(10, 6, 3, 5, 1, 0)
    assert m.conserved is False


def test_conserved_false_when_double_counted():
    # 8 + 3 = 11 > 10 → đếm trùng (đúng loại lỗi K-051 muốn chống) → KHÔNG bảo toàn
    m = BackpressureMetrics(10, 8, 3, 5, 1, 0)
    assert m.conserved is False


# ============ (b) frozen (DTO bất biến) ============

def test_frozen_cannot_reassign_field():
    m = BackpressureMetrics(10, 7, 3, 5, 1, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.frames_captured = 99  # type: ignore[misc]


# ============ (d) kernel thuần — không import I/O layer ngoài (R9.1) ============

def test_module_pure_no_forbidden_imports():
    import sys

    import vision_platform.kernel.backpressure_metrics as mod

    # Module chỉ được kéo theo stdlib thuần; KHÔNG kéo zmq/torch/cv2/mp/shm.
    forbidden = {
        "zmq", "torch", "cv2", "onnxruntime", "onnx", "yolov5",
        "multiprocessing", "multiprocessing.shared_memory",
    }
    # Kiểm chính module không tham chiếu (an toàn kể cả khi lib khác đã nạp trong sys.modules
    # do test khác): xét các tên mà module này thực sự bind ở cấp global.
    referenced = set(vars(mod).keys())
    assert forbidden.isdisjoint(referenced), (
        f"backpressure_metrics KHÔNG được bind symbol cấm: {forbidden & referenced}"
    )
    assert mod.__name__ == "vision_platform.kernel.backpressure_metrics"
