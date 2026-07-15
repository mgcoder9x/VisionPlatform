"""Test OverlayConfig fail-fast (spec web-live-overlay-sync Task 1) — mọi invariant boundary.

THUẦN, xác định. Chống 'chạy với giá trị sai âm thầm' (đồng bộ triết lý fail-fast K-046).
"""
from __future__ import annotations

import pytest

from vision_platform.kernel.overlay_config import OverlayConfig, OverlayConfigError


def test_default_config_valid():
    c = OverlayConfig()
    assert c.candidateLeaseMs <= c.displayLeaseMs <= c.ghostSlaMs
    assert c.clientSilenceCapMs <= c.ghostSlaMs
    assert c.experimental is True   # default CHƯA chốt bằng SLA (Task 0)


@pytest.mark.parametrize("bad", [
    dict(iouThreshold=0.0), dict(iouThreshold=1.1),
    dict(emaAlpha=0.0), dict(emaAlpha=1.1),
    dict(minHits=0), dict(maxMisses=-1),
    dict(candidateLeaseMs=0), dict(displayLeaseMs=0), dict(ghostSlaMs=0), dict(clientSilenceCapMs=0),
    dict(reconnectMinMs=0), dict(reconnectMaxMs=0),
])
def test_config_rejects_out_of_range(bad):
    with pytest.raises(OverlayConfigError):
        OverlayConfig(**bad)


def test_config_reconnect_order():
    with pytest.raises(OverlayConfigError):
        OverlayConfig(reconnectMinMs=5000, reconnectMaxMs=200)


def test_config_lease_ordering():
    # candidate <= display <= ghost — vi phạm bất kỳ → lỗi.
    with pytest.raises(OverlayConfigError):
        OverlayConfig(candidateLeaseMs=700, displayLeaseMs=600, ghostSlaMs=1500)
    with pytest.raises(OverlayConfigError):
        OverlayConfig(candidateLeaseMs=300, displayLeaseMs=1600, ghostSlaMs=1500)


def test_config_client_silence_cap_le_ghost():
    with pytest.raises(OverlayConfigError):
        OverlayConfig(clientSilenceCapMs=2000, ghostSlaMs=1500)


def test_config_cadence_fit_impossible():
    # requiredCadenceMs > ghostSlaMs → stable-mode BẤT KHẢ → fail-fast (không vi phạm ngầm).
    with pytest.raises(OverlayConfigError):
        OverlayConfig(requiredCadenceMs=2000, ghostSlaMs=1500)
    # requiredCadenceMs <= ghost → OK
    c = OverlayConfig(requiredCadenceMs=800, ghostSlaMs=1500)
    assert c.requiredCadenceMs == 800


def test_config_int_type_guard():
    # bool KHÔNG được coi là int hợp lệ cho duration (tránh True==1 lọt).
    with pytest.raises(OverlayConfigError):
        OverlayConfig(ghostSlaMs=True)   # type: ignore[arg-type]
