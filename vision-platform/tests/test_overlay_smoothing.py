"""Test EMA display-smoothing (Property 9) + matching reuse (Property 8) — spec Task 2.

THUẦN, xác định. EMA: convex-combo (nằm giữa) + constant-no-drift. Matching: tái dùng greedy_associate
(cùng-label, deterministic) — test ở đây để PIN semantics overlay dựa vào, không định nghĩa lại thuật toán.
"""
from __future__ import annotations

import pytest

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.display_smoothing import ema_box, ema_scalar, greedy_associate


# ---- EMA scalar (Property 9) ----
@pytest.mark.parametrize("prev,new,alpha", [
    (0.0, 1.0, 0.5), (0.2, 0.8, 0.1), (0.9, 0.1, 1.0), (0.3, 0.3, 0.5),
])
def test_ema_scalar_between_prev_and_new(prev, new, alpha):
    s = ema_scalar(prev, new, alpha)
    lo, hi = min(prev, new), max(prev, new)
    assert lo - 1e-12 <= s <= hi + 1e-12   # nằm giữa (convex combo)


def test_ema_scalar_constant_no_drift():
    s = 0.42
    for _ in range(1000):
        s = ema_scalar(s, 0.42, 0.3)
    assert abs(s - 0.42) < 1e-9   # input hằng → KHÔNG trôi


def test_ema_scalar_alpha_one_takes_new():
    assert ema_scalar(0.2, 0.9, 1.0) == pytest.approx(0.9)


@pytest.mark.parametrize("alpha", [0.0, -0.1, 1.1])
def test_ema_scalar_rejects_bad_alpha(alpha):
    with pytest.raises(ValueError):
        ema_scalar(0.1, 0.2, alpha)


# ---- EMA box ----
def test_ema_box_each_coord_between():
    prev = BBox(0.1, 0.1, 0.2, 0.2, CoordinateSpace.NORMALIZED)
    new = BBox(0.3, 0.3, 0.4, 0.4, CoordinateSpace.NORMALIZED)
    out = ema_box(prev, new, 0.5)
    assert out.space is CoordinateSpace.NORMALIZED
    assert 0.1 <= out.x <= 0.3 and 0.2 <= out.w <= 0.4


def test_ema_box_constant_no_drift():
    b = BBox(0.25, 0.25, 0.5, 0.5, CoordinateSpace.NORMALIZED)
    out = ema_box(b, b, 0.3)
    assert (out.x, out.y, out.w, out.h) == pytest.approx((0.25, 0.25, 0.5, 0.5))


def test_ema_box_different_space_fails():
    prev = BBox(0.1, 0.1, 0.2, 0.2, CoordinateSpace.NORMALIZED)
    new = BBox(10, 10, 20, 20, CoordinateSpace.ORIGINAL_FRAME)
    with pytest.raises(ValueError):
        ema_box(prev, new, 0.5)


def test_ema_box_normalized_stays_in_range():
    # convex combo của 2 box NORMALIZED (∈[0,1]) → vẫn ∈[0,1] (BBox NORMALIZED không raise).
    prev = BBox(0.0, 0.0, 1.0, 1.0, CoordinateSpace.NORMALIZED)
    new = BBox(0.5, 0.5, 0.5, 0.5, CoordinateSpace.NORMALIZED)
    out = ema_box(prev, new, 0.7)
    for v in (out.x, out.y, out.w, out.h):
        assert 0.0 <= v <= 1.0


# ---- Matching reuse (Property 8) — pin semantics overlay dựa vào ----
def _nb(x, y):
    return BBox(x, y, 0.1, 0.1, CoordinateSpace.NORMALIZED)


def test_matching_same_label_one_to_one_deterministic():
    prev = [_nb(0.1, 0.1), _nb(0.5, 0.5)]
    new = [_nb(0.11, 0.11), _nb(0.51, 0.51)]
    m1 = greedy_associate(prev, new, 0.3, prev_labels=["person", "car"], new_labels=["person", "car"])
    m2 = greedy_associate(prev, new, 0.3, prev_labels=["person", "car"], new_labels=["person", "car"])
    assert m1 == m2                      # xác định
    assert len(m1) == len(set(ni for ni, _ in m1))  # mỗi new tối đa 1 lần
    assert len(m1) == len(set(pi for _, pi in m1))  # mỗi prev tối đa 1 lần


def test_matching_different_label_never_matches():
    prev = [_nb(0.1, 0.1)]
    new = [_nb(0.1, 0.1)]   # trùng vị trí HOÀN TOÀN nhưng khác label
    m = greedy_associate(prev, new, 0.3, prev_labels=["car"], new_labels=["person"])
    assert m == []          # khác label KHÔNG khớp dù IoU=1
