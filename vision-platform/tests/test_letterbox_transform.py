"""Test LetterboxTransform (sub-spec real-detector-integration, Property 1 R1).

Property (Hypothesis): forward_box ∘ inverse_box ≈ identity cho box nằm TRONG frame gốc.
Unit: scale/pad cho các tỉ lệ (vuông/ngang/dọc); fail-fast sai space.
"""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, strategies as st

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.letterbox_transform import LetterboxTransform


def test_scale_pad_wide_frame():
    """Frame ngang 1280×720 về model 640×640: scale=0.5, pad_x=0, pad_y=140."""
    t = LetterboxTransform(orig_h=720, orig_w=1280, model_h=640, model_w=640)
    assert t.scale == pytest.approx(0.5)
    assert t.pad_x == pytest.approx(0.0)
    assert t.pad_y == pytest.approx(140.0)


def test_scale_pad_tall_frame():
    """Frame dọc 720×1280 về 640×640: scale=0.5, pad_x=140, pad_y=0."""
    t = LetterboxTransform(orig_h=1280, orig_w=720, model_h=640, model_w=640)
    assert t.scale == pytest.approx(0.5)
    assert t.pad_x == pytest.approx(140.0)
    assert t.pad_y == pytest.approx(0.0)


def test_scale_pad_square_frame():
    """Frame vuông → không pad."""
    t = LetterboxTransform(orig_h=640, orig_w=640, model_h=640, model_w=640)
    assert t.scale == pytest.approx(1.0)
    assert t.pad_x == pytest.approx(0.0)
    assert t.pad_y == pytest.approx(0.0)


def test_inverse_box_known_value():
    """Box giữa MODEL_INPUT (160,160,320,320) trên frame 1280×720 → ORIGINAL_FRAME (320,40,640,640)."""
    t = LetterboxTransform(orig_h=720, orig_w=1280, model_h=640, model_w=640)
    box_mi = BBox(x=160, y=160, w=320, h=320, space=CoordinateSpace.MODEL_INPUT)
    out = t.inverse_box(box_mi)
    assert out.space == CoordinateSpace.ORIGINAL_FRAME
    assert (out.x, out.y, out.w, out.h) == pytest.approx((320.0, 40.0, 640.0, 640.0))


def test_inverse_box_wrong_space_fails():
    box = BBox(x=1, y=1, w=1, h=1, space=CoordinateSpace.ORIGINAL_FRAME)
    t = LetterboxTransform(orig_h=100, orig_w=100, model_h=64, model_w=64)
    with pytest.raises(ValueError, match="MODEL_INPUT"):
        t.inverse_box(box)


def test_forward_box_wrong_space_fails():
    box = BBox(x=1, y=1, w=1, h=1, space=CoordinateSpace.MODEL_INPUT)
    t = LetterboxTransform(orig_h=100, orig_w=100, model_h=64, model_w=64)
    with pytest.raises(ValueError, match="ORIGINAL_FRAME"):
        t.forward_box(box)


def test_inverse_box_clamps_out_of_frame():
    """Box model lố ra ngoài vùng nội dung → clamp về khung gốc [0,orig], w/h không âm."""
    t = LetterboxTransform(orig_h=720, orig_w=1280, model_h=640, model_w=640)
    # box model bao trọn khung (kể cả pad) → sau inverse phải bị kẹp vào [0,1280]×[0,720].
    box_mi = BBox(x=0, y=0, w=640, h=640, space=CoordinateSpace.MODEL_INPUT)
    out = t.inverse_box(box_mi)
    assert out.x >= 0 and out.y >= 0
    assert out.x2 <= 1280.0 + 1e-9 and out.y2 <= 720.0 + 1e-9
    assert out.w >= 0 and out.h >= 0


@settings(max_examples=300)
@given(
    orig_w=st.integers(min_value=1, max_value=4000),
    orig_h=st.integers(min_value=1, max_value=4000),
    model_w=st.integers(min_value=1, max_value=2000),
    model_h=st.integers(min_value=1, max_value=2000),
    fx=st.floats(min_value=0.0, max_value=1.0),
    fy=st.floats(min_value=0.0, max_value=1.0),
    fw=st.floats(min_value=0.0, max_value=1.0),
    fh=st.floats(min_value=0.0, max_value=1.0),
)
def test_round_trip_identity(orig_w, orig_h, model_w, model_h, fx, fy, fw, fh):
    """forward_box rồi inverse_box ≈ box gốc (box nằm TRONG frame gốc → clamp không kích hoạt)."""
    # Dựng box HỢP LỆ trong [0,orig] từ các tỉ lệ f*.
    x = fx * orig_w
    y = fy * orig_h
    w = fw * (orig_w - x)
    h = fh * (orig_h - y)
    box = BBox(x=x, y=y, w=w, h=h, space=CoordinateSpace.ORIGINAL_FRAME)
    t = LetterboxTransform(orig_h=orig_h, orig_w=orig_w, model_h=model_h, model_w=model_w)
    back = t.inverse_box(t.forward_box(box))
    assert back.space == CoordinateSpace.ORIGINAL_FRAME
    for a, b in ((back.x, x), (back.y, y), (back.w, w), (back.h, h)):
        assert math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-4), f"{a} != {b}"
