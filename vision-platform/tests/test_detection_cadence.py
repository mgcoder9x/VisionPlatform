"""Test Task 1 (adaptive-detection-perf): DetectionCadenceConfig fail-fast + should_detect thuần.

TDD: pin contract TRƯỚC khi code. Config @kernel (fail-fast mọi invariant + P5 cadence<=lease),
policy `should_detect` @domain (THUẦN — nhận primitive, KHÔNG import kernel; clock/version tiêm → xác định).
"""
import pytest

from vision_platform.kernel.detection_cadence import (
    DetectionCadenceConfig,
    DetectionConfigError,
    assert_cadence_fits_lease,
)
from vision_platform.domain.detect_cadence import should_detect

_MS = 1_000_000


# ----------------------- DetectionCadenceConfig: fail-fast -----------------------

def test_default_config_valid():
    c = DetectionCadenceConfig()
    assert c.detectMinIntervalMs == 0
    assert c.detectEveryN == 1
    assert c.motionGate is False
    assert c.experimental is True


def test_min_interval_negative_rejected():
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(detectMinIntervalMs=-1)


def test_every_n_below_one_rejected():
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(detectEveryN=0)


def test_max_consecutive_skip_negative_rejected():
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(motionMaxConsecutiveSkip=-1)


@pytest.mark.parametrize("ratio", [-0.1, 1.5])
def test_motion_min_area_ratio_out_of_range_rejected(ratio):
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(motionMinAreaRatio=ratio)


@pytest.mark.parametrize("thr", [-1, 256])
def test_motion_pixel_diff_threshold_out_of_range_rejected(thr):
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(motionPixelDiffThreshold=thr)


# ROI CHUẨN-HOÁ [0,1] (tái dùng domain.validate_roi): x,y∈[0,1], w>0,h>0, x+w<=1, y+h<=1.
@pytest.mark.parametrize("roi", [
    (0.1, 0.2, 0.3),           # len != 4
    (0.0, 0.0, 0.0, 0.5),      # w = 0
    (0.0, 0.0, 0.5, 0.0),      # h = 0
    (-0.1, 0.0, 0.5, 0.5),     # x < 0
    (0.6, 0.0, 0.5, 0.5),      # x + w = 1.1 > 1
])
def test_bad_roi_rejected(roi):
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(motionRoi=roi)


def test_good_roi_accepted():
    c = DetectionCadenceConfig(motionRoi=(0.1, 0.1, 0.5, 0.5))
    assert c.motionRoi == (0.1, 0.1, 0.5, 0.5)


def test_full_frame_roi_accepted():
    c = DetectionCadenceConfig(motionRoi=(0.0, 0.0, 1.0, 1.0))
    assert c.motionRoi == (0.0, 0.0, 1.0, 1.0)


def test_bool_not_accepted_as_int_fields():
    # bool là subclass int — fail-fast phải bắt (giống OverlayConfig _pos_int).
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(detectEveryN=True)


# ----------------------- P5: cadence <= lease (liên-spec) -----------------------

def test_cadence_fits_lease_ok():
    c = DetectionCadenceConfig(detectMinIntervalMs=600)
    assert_cadence_fits_lease(c, display_lease_ms=600)   # bằng = OK


def test_cadence_exceeds_lease_rejected():
    c = DetectionCadenceConfig(detectMinIntervalMs=601)
    with pytest.raises(DetectionConfigError):
        assert_cadence_fits_lease(c, display_lease_ms=600)


# ----------------------- should_detect (THUẦN) -----------------------

def test_first_detect_when_no_prior():
    ok, reason = should_detect(now_ns=1000, last_detect_ns=None, frame_version=5,
                               last_detect_version=None, min_interval_ns=100 * _MS, every_n=3)
    assert ok is True
    assert reason == "FIRST"


def test_default_always_detects_on_new_version():
    # min_interval=0, every_n=1 → luôn detect khi có version mới.
    ok, reason = should_detect(now_ns=10, last_detect_ns=1, frame_version=2,
                               last_detect_version=1, min_interval_ns=0, every_n=1)
    assert ok is True
    assert reason == "OK"


def test_min_interval_blocks_within_window():
    ok, reason = should_detect(now_ns=50 * _MS, last_detect_ns=0, frame_version=100,
                               last_detect_version=1, min_interval_ns=100 * _MS, every_n=1)
    assert ok is False
    assert reason == "MIN_INTERVAL"


def test_min_interval_passes_at_boundary():
    ok, reason = should_detect(now_ns=100 * _MS, last_detect_ns=0, frame_version=100,
                               last_detect_version=1, min_interval_ns=100 * _MS, every_n=1)
    assert ok is True
    assert reason == "OK"


def test_every_n_blocks_until_enough_versions():
    # delta version = 2 < every_n 3 → skip.
    ok, reason = should_detect(now_ns=10 ** 12, last_detect_ns=0, frame_version=3,
                               last_detect_version=1, min_interval_ns=0, every_n=3)
    assert ok is False
    assert reason == "EVERY_N"


def test_every_n_passes_at_threshold():
    ok, reason = should_detect(now_ns=10 ** 12, last_detect_ns=0, frame_version=4,
                               last_detect_version=1, min_interval_ns=0, every_n=3)
    assert ok is True
    assert reason == "OK"


def test_min_interval_checked_before_every_n():
    # cả 2 fail → reason ưu tiên MIN_INTERVAL (thời gian check trước).
    ok, reason = should_detect(now_ns=1, last_detect_ns=0, frame_version=1,
                               last_detect_version=1, min_interval_ns=100 * _MS, every_n=3)
    assert ok is False
    assert reason == "MIN_INTERVAL"


# ----------------------- max-interval (HEARTBEAT — fix gốc K-103) -----------------------

def test_max_interval_forces_detect_over_all_gates():
    # now-last=500ms >= max 400ms → ÉP detect DÙ min-interval (1000ms) chặn + every-n chưa đủ.
    ok, reason = should_detect(now_ns=500 * _MS, last_detect_ns=0, frame_version=1,
                               last_detect_version=1, min_interval_ns=1000 * _MS, every_n=10,
                               max_interval_ns=400 * _MS)
    assert ok is True
    assert reason == "MAX_INTERVAL"


def test_max_interval_zero_disabled():
    # max=0 → không heartbeat → min-interval vẫn chặn.
    ok, reason = should_detect(now_ns=50 * _MS, last_detect_ns=0, frame_version=100,
                               last_detect_version=1, min_interval_ns=100 * _MS, every_n=1,
                               max_interval_ns=0)
    assert ok is False
    assert reason == "MIN_INTERVAL"


def test_max_interval_not_yet_reached_falls_through():
    # now-last=50ms < max 400ms → không force; min-interval 100ms chặn.
    ok, reason = should_detect(now_ns=50 * _MS, last_detect_ns=0, frame_version=100,
                               last_detect_version=1, min_interval_ns=100 * _MS, every_n=1,
                               max_interval_ns=400 * _MS)
    assert ok is False
    assert reason == "MIN_INTERVAL"


# config: max-interval invariants
def test_max_interval_negative_rejected():
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(detectMaxIntervalMs=-1)


def test_max_below_min_rejected():
    with pytest.raises(DetectionConfigError):
        DetectionCadenceConfig(detectMinIntervalMs=500, detectMaxIntervalMs=300)


def test_max_equal_min_ok():
    c = DetectionCadenceConfig(detectMinIntervalMs=300, detectMaxIntervalMs=300)
    assert c.detectMaxIntervalMs == 300


def test_max_interval_exceeds_lease_rejected():
    c = DetectionCadenceConfig(detectMaxIntervalMs=700)
    with pytest.raises(DetectionConfigError):
        assert_cadence_fits_lease(c, display_lease_ms=600)


def test_max_interval_within_lease_ok():
    c = DetectionCadenceConfig(detectMinIntervalMs=100, detectMaxIntervalMs=500)
    assert_cadence_fits_lease(c, display_lease_ms=600)
