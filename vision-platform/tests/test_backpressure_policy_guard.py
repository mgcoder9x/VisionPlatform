"""Wave 3.2 (spec backpressure-cross-process, task 3.2): guard cấm BLOCK cho nguồn RTSP (R3, Property 7).

`assert_policy_allowed_for_source(source_type, policy)`:
- rtsp + BLOCK  → ConfigError (thông điệp nêu rõ TCP Zero Window / mất frame im lặng).
- rtsp + {DROP_OLDEST, DROP_NEWEST, REJECT} → OK (không raise).
- non-rtsp (noise/video/fake) + BLOCK → OK (R3.2: chỉ cấm cho RTSP; BoundedQueue giữ policy-agnostic).

Guard THUẦN (không cần ZMQ/GPU/process) → test xác định, nhanh.
"""
import pytest

from vision_platform.application.config_loader import ConfigError, assert_policy_allowed_for_source
from vision_platform.kernel.backpressure import BackpressurePolicy


# ============ rtsp + BLOCK bị TỪ CHỐI (R3.1 / P7) ============

def test_rtsp_block_rejected():
    with pytest.raises(ConfigError) as ei:
        assert_policy_allowed_for_source("rtsp", BackpressurePolicy.BLOCK)
    msg = str(ei.value)
    assert "RTSP" in msg and "BLOCK" in msg   # thông điệp mô tả rõ nguyên nhân (R3.1)


# ============ rtsp + policy KHÁC BLOCK → OK ============

@pytest.mark.parametrize("policy", [
    BackpressurePolicy.DROP_OLDEST,
    BackpressurePolicy.DROP_NEWEST,
    BackpressurePolicy.REJECT,
])
def test_rtsp_non_block_allowed(policy):
    # Không raise = hợp lệ.
    assert_policy_allowed_for_source("rtsp", policy) is None


# ============ non-RTSP + BLOCK → OK (R3.2: chỉ cấm cho RTSP) ============

@pytest.mark.parametrize("source_type", ["noise", "video", "fake", "push"])
def test_non_rtsp_block_allowed(source_type):
    assert_policy_allowed_for_source(source_type, BackpressurePolicy.BLOCK) is None
