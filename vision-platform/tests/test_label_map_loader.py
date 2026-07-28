"""Test loader LabelMap (adapter) — nguồn nhãn theo thứ tự ưu tiên (spec image-preprocess-and-labeling, R1.3/R1.4).

Thứ tự (§D-5): (a) sidecar `.names`/metadata cạnh `.onnx` → (b) config `labels` → (c) rỗng.
Loader = adapter (đọc I/O). Phần lõi (sidecar + config + rỗng) test KHÔNG cần onnx; nhánh ONNX-metadata
test riêng có importorskip('onnx').
"""
from __future__ import annotations

import pytest

from vision_platform.adapters.label_map_loader import load_label_map
from vision_platform.kernel.label_map import LabelMap


def test_empty_when_no_source():
    """Không model, không config → LabelMap rỗng (mọi id `class_<id>`) (R1.3.c)."""
    lm = load_label_map(model_path=None, config_labels=None)
    assert lm == LabelMap.empty()
    assert lm.canonical(0) == "class_0"


def test_config_labels_fallback():
    """Không có nguồn file → dùng config `labels` (R1.3.b)."""
    lm = load_label_map(model_path=None, config_labels=["person", "car"])
    assert lm.canonical(0) == "person"
    assert lm.canonical(1) == "car"
    assert lm.canonical(2) == "class_2"


def test_names_sidecar_file(tmp_path):
    """File `.names` cạnh model (1 tên/dòng, bỏ dòng trống) → nạp theo vị trí (R1.3.a)."""
    model = tmp_path / "model.onnx"
    model.write_bytes(b"not-a-real-onnx")            # nội dung không cần hợp lệ cho nhánh sidecar
    (tmp_path / "model.names").write_text("person\ncar\n\ndog\n", encoding="utf-8")
    lm = load_label_map(model_path=str(model), config_labels=None)
    assert lm.canonical(0) == "person"
    assert lm.canonical(1) == "car"
    assert lm.canonical(2) == "dog"                   # dòng trống bị bỏ qua


def test_sidecar_takes_priority_over_config(tmp_path):
    """Có CẢ sidecar lẫn config → ưu tiên file cạnh model (R1.4)."""
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    (tmp_path / "m.names").write_text("cat\ndog\n", encoding="utf-8")
    lm = load_label_map(model_path=str(model), config_labels=["WRONG", "WRONG2"])
    assert lm.canonical(0) == "cat"
    assert lm.canonical(1) == "dog"


def test_missing_sidecar_falls_back_to_config(tmp_path):
    """Model không có sidecar + không đọc được metadata → rơi về config (R1.3)."""
    model = tmp_path / "no_names.onnx"
    model.write_bytes(b"x")
    lm = load_label_map(model_path=str(model), config_labels=["a", "b"])
    assert lm.canonical(0) == "a"


# ---------------- nhánh ONNX metadata (cần onnx để dựng model có custom_metadata_map) ----------------

onnx = pytest.importorskip("onnx", reason="cần optional dep onnx (.[onnx])")
pytest.importorskip("onnxruntime", reason="cần optional dep onnxruntime (.[onnx])")

from onnx import helper, TensorProto  # noqa: E402


def _make_model_with_names(path: str, names: dict[int, str]) -> None:
    """Model ONNX tối thiểu có metadata_props['names'] = str(dict) (kiểu Ultralytics export)."""
    node = helper.make_node("Identity", ["x"], ["y"])
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])
    model = helper.make_model(helper.make_graph([node], "g", [x], [y]),
                              opset_imports=[helper.make_opsetid("", 18)])
    entry = model.metadata_props.add()
    entry.key = "names"
    entry.value = repr(names)                          # vd "{0: 'person', 1: 'car'}"
    onnx.save(model, path)


def test_onnx_metadata_names(tmp_path):
    """Đọc `names` nhúng trong metadata ONNX khi KHÔNG có sidecar (R1.3.a metadata)."""
    path = str(tmp_path / "with_names.onnx")
    _make_model_with_names(path, {0: "person", 1: "car", 2: "dog"})
    lm = load_label_map(model_path=path, config_labels=["SHOULD_NOT_USE"])
    assert lm.canonical(0) == "person"
    assert lm.canonical(2) == "dog"


def test_sidecar_beats_onnx_metadata(tmp_path):
    """Có cả sidecar lẫn metadata → sidecar thắng (nguồn override tường minh)."""
    path = str(tmp_path / "both.onnx")
    _make_model_with_names(path, {0: "META0", 1: "META1"})
    (tmp_path / "both.names").write_text("side0\nside1\n", encoding="utf-8")
    lm = load_label_map(model_path=path, config_labels=None)
    assert lm.canonical(0) == "side0"
