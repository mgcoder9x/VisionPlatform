"""Test Task 3 (adaptive-detection-perf): OnnxDetector fail-fast khi input-size cấu hình ≠ model thật.

Đóng lỗ đã chứng minh empiric #395: feed 416 vào model-640 → onnxruntime `InvalidArgument Got 416 Expected 640`
(tối nghĩa, lúc run). Fail-fast lúc setup báo RÕ RÀNG. Dynamic-axis → cho qua (không chặn).
"""
import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from onnx import helper, TensorProto  # noqa: E402

from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize  # noqa: E402


def _stub_model(path: str, h, w):
    """Model input [1,3,h,w] (h/w có thể int cố định hoặc str dynamic) → output Constant [1,6,3]."""
    val = np.zeros((1, 6, 3), dtype=np.float32)
    const = helper.make_tensor("cval", TensorProto.FLOAT, [1, 6, 3], val.flatten().tolist())
    node = helper.make_node("Constant", [], ["output"], value=const)
    x = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, h, w])
    y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 6, 3])
    model = helper.make_model(helper.make_graph([node], "stub", [x], [y]),
                              opset_imports=[helper.make_opsetid("", 18)])
    onnx.checker.check_model(model)
    onnx.save(model, path)


def _det(path, expected):
    return OnnxDetector(path, preprocess_fn=chw_float_normalize,
                        postprocess_fn=lambda raw: [], expected_input_size=expected)


def test_setup_raises_on_mismatch(tmp_path):
    path = str(tmp_path / "m640.onnx")
    _stub_model(path, 640, 640)
    d = _det(path, expected=416)
    with pytest.raises(ValueError) as ei:
        d.setup()
    msg = str(ei.value)
    assert "640" in msg and "416" in msg     # báo rõ model-thật vs cấu hình


def test_setup_ok_when_match(tmp_path):
    path = str(tmp_path / "m640.onnx")
    _stub_model(path, 640, 640)
    d = _det(path, expected=640)
    d.setup()          # không raise
    d.teardown()


def test_setup_ok_when_no_expected(tmp_path):
    path = str(tmp_path / "m640.onnx")
    _stub_model(path, 640, 640)
    d = OnnxDetector(path, preprocess_fn=chw_float_normalize, postprocess_fn=lambda raw: [])
    d.setup()          # expected_input_size=None → không kiểm
    d.teardown()


def test_setup_ok_when_dynamic_axis(tmp_path):
    path = str(tmp_path / "mdyn.onnx")
    _stub_model(path, "height", "width")   # dynamic (str) → không chặn
    d = _det(path, expected=416)
    d.setup()          # dynamic → cho qua
    d.teardown()
