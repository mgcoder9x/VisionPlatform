"""Test reconnect pacing (spec Task 7, Property 11) — clamp + epoch-bump-exactly-once.

THUẦN + xác định (không sleep thật). Chống busy-loop (sleep không bao giờ 0).
"""
from __future__ import annotations

import pytest

from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.runtime.reconnect_pacer import ReconnectPacer, clamp_retry_ns

MS = 1_000_000
CFG = OverlayConfig(reconnectMinMs=200, reconnectMaxMs=5000)


# ---- clamp ----
def test_clamp_within_range():
    assert clamp_retry_ns(1000, CFG) == 1000 * MS


def test_clamp_below_min_and_above_max():
    assert clamp_retry_ns(50, CFG) == 200 * MS       # < min → min
    assert clamp_retry_ns(999999, CFG) == 5000 * MS  # > max → max


@pytest.mark.parametrize("bad", [None, 0, -100, float("nan"), float("inf"), True, "x"])
def test_clamp_invalid_uses_min_never_zero(bad):
    ns = clamp_retry_ns(bad, CFG)
    assert ns == 200 * MS and ns > 0   # KHÔNG bao giờ 0 (chống busy-loop)


# ---- ReconnectPacer: bump exactly once per episode ----
def test_bump_once_per_episode():
    p = ReconnectPacer(CFG)
    b1, s1 = p.on_reconnect_attempt(retry_after_ms=None)
    assert b1 is True and s1 == 200 * MS          # attempt đầu → bump + clamp(min)
    b2, s2 = p.on_reconnect_attempt(retry_after_ms=1000)
    assert b2 is False and s2 == 1000 * MS        # attempt sau → KHÔNG bump, vẫn clamp
    b3, _ = p.on_reconnect_attempt()
    assert b3 is False                            # vẫn không bump (cùng episode)


def test_live_resets_episode():
    p = ReconnectPacer(CFG)
    assert p.on_reconnect_attempt()[0] is True    # episode 1 bump
    assert p.on_reconnect_attempt()[0] is False
    p.on_live()                                   # LIVE lại
    assert p.in_discontinuity is False
    assert p.on_reconnect_attempt()[0] is True    # episode 2 → bump LẠI (Property 11: success reset)


def test_every_attempt_positive_sleep():
    p = ReconnectPacer(CFG)
    for _ in range(10):
        _, s = p.on_reconnect_attempt(retry_after_ms=0)   # server gửi 0 (xấu)
        assert s > 0                                       # không busy-loop
