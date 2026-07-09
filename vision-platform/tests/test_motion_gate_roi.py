"""Spec motion-gate-roi — test XÁC ĐỊNH (numpy dựng tay + đại số), KHÔNG GPU/camera.

Phủ Correctness Properties của design:
- P1 ROI giới hạn vùng đo · P2 bền đổi-sáng-đều · P3 vẫn bắt chuyển động cục bộ · P4 fail-fast (2 tầng)
- P5 backward-compat BIT-KHỚP v1 · P7 ROI×illum THỨ TỰ mask-trước-mean (phân biệt đúng/sai).
Đóng K-063 (v1 full-frame coi đổi-sáng-đều là chuyển động → chạy detector oan).
"""
import numpy as np
import pytest

from vision_platform.domain.motion import changed_ratio, roi_mask, validate_roi
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.runtime.stages.motion_gate_stage import MotionGateStage
from vision_platform.kernel.config import (
    PipelineConfig, SourceConfig, StageConfig, DetectorConfig,
)
from vision_platform.profiles.pipeline_factory import build_runner, ConfigError


def _packet(frame, source_id="cam0"):
    return MediaPacket(packet_id="p", source_id=source_id,
                       media_ref=InMemoryArrayRef.from_copy(frame), capture_time_ns=0)


# ===================== domain: validate_roi + roi_mask (P4 fail-fast 2 tầng) =====================

def test_validate_roi_accepts_valid():
    validate_roi(0.0, 0.0, 1.0, 1.0)        # toàn frame
    validate_roi(0.25, 0.5, 0.5, 0.4)       # trong biên
    validate_roi(0.3, 0.0, 0.7, 1.0)        # x+w=1.0 (fp) chấp nhận


@pytest.mark.parametrize("roi", [
    (-0.1, 0.0, 0.5, 0.5),   # x<0
    (0.0, 0.0, 0.0, 0.5),    # w=0
    (0.0, 0.0, 0.5, -0.2),   # h<0
    (0.6, 0.0, 0.5, 0.5),    # x+w>1
    (0.0, 0.7, 0.5, 0.5),    # y+h>1
    (1.1, 0.0, 0.1, 0.1),    # x>1
])
def test_validate_roi_rejects_out_of_range(roi):
    with pytest.raises(ValueError):
        validate_roi(*roi)


def test_roi_mask_shape_and_region():
    m = roi_mask(10, 20, 0.0, 0.0, 0.5, 0.5)   # nửa trên-trái
    assert m.shape == (10, 20) and m.dtype == bool
    assert m[0:5, 0:10].all()                  # trong ROI = True
    assert not m[5:, 10:].any()                # ngoài ROI = False
    assert int(m.sum()) == 5 * 10              # mẫu số đúng = pixel ROI


def test_roi_mask_empty_after_pixel_quantize_raises():
    # ROI range hợp lệ nhưng cực nhỏ trên frame nhỏ → rỗng sau round → chỉ phát hiện được khi biết shape.
    with pytest.raises(ValueError):
        roi_mask(4, 4, 0.0, 0.0, 0.1, 0.1)     # 0.1*4=0.4 → round→0 → px1<=px0


# ===================== domain: changed_ratio backward-compat (P5) =====================

def test_changed_ratio_backward_compat_bit_identical():
    rng = np.random.default_rng(42)
    for _ in range(20):
        prev = rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
        curr = rng.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
        # mới KHÔNG tham số == cũ (chữ ký 3 tham số) — BIT-KHỚP
        assert changed_ratio(prev, curr, 25) == changed_ratio(prev, curr, 25, mask=None,
                                                               illumination_robust=False)


# ===================== domain: ROI giới hạn vùng đo (P1) =====================

def test_roi_only_counts_inside():
    prev = np.full((10, 10), 100, dtype=np.uint8)
    curr = prev.copy()
    curr[7:, 7:] = 200                          # đổi NGOÀI ROI (góc dưới-phải)
    mask = roi_mask(10, 10, 0.0, 0.0, 0.5, 0.5)  # ROI = trên-trái 5x5
    assert changed_ratio(prev, curr, 25, mask=mask) == 0.0   # ROI tĩnh → 0 (bỏ qua đổi ngoài)


def test_roi_counts_change_inside():
    prev = np.full((10, 10), 100, dtype=np.uint8)
    curr = prev.copy()
    curr[0:5, 0:5] = 200                         # đổi TRONG ROI
    mask = roi_mask(10, 10, 0.0, 0.0, 0.5, 0.5)
    assert changed_ratio(prev, curr, 25, mask=mask) == 1.0   # cả ROI đổi → 1.0


# ===================== domain: bền đổi-sáng-đều (P2) + đối chứng K-063 =====================

def test_illumination_uniform_shift_zero_when_robust():
    prev = np.full((8, 8), 100, dtype=np.uint8)
    curr = prev + np.uint8(40)                    # đổi-sáng ĐỀU toàn cục (+40 mọi pixel)
    assert changed_ratio(prev, curr, 25, illumination_robust=True) == 0.0   # triệt → SKIP đúng


def test_illumination_off_uniform_shift_high_proves_k063():
    prev = np.full((8, 8), 100, dtype=np.uint8)
    curr = prev + np.uint8(40)
    # KHÔNG bật illum-robust → v1: |40|>25 mọi pixel → ratio=1.0 (đây CHÍNH LÀ lỗi K-063 detector chạy oan)
    assert changed_ratio(prev, curr, 25, illumination_robust=False) == 1.0


def test_illumination_local_change_still_detected():
    prev = np.full((10, 10), 100, dtype=np.uint8)
    curr = prev + np.uint8(30)                    # nền dịch đều +30
    curr[0:3, 0:3] = 250                          # + vật cục bộ đổi mạnh
    ratio = changed_ratio(prev, curr, 25, illumination_robust=True)
    assert ratio > 0.0                            # vẫn phát hiện chuyển động cục bộ (không nuốt vật thật)


# ===================== domain: P7 — ROI × illum THỨ TỰ mask-trước-mean (phân biệt đúng/sai) =====================

def test_roi_x_illum_order_mask_before_mean():
    """Đổi-sáng-đều CHỈ NGOÀI ROI. Impl ĐÚNG (mask trước → mean TRONG ROI) → ratio 0.
    Impl SAI (mean toàn-frame trước) sẽ ra ratio cao → test này BẮT lỗi thứ tự."""
    prev = np.full((10, 10), 100, dtype=np.int16)
    curr = prev.copy()
    curr[5:, 5:] += 40                            # đổi-sáng chỉ ở góc dưới-phải (NGOÀI ROI)
    mask = roi_mask(10, 10, 0.0, 0.0, 0.5, 0.5)   # ROI trên-trái (tĩnh hoàn toàn)
    ratio = changed_ratio(prev, curr, 5, mask=mask, illumination_robust=True)
    assert ratio == 0.0                           # ROI không đổi → 0; nếu mean toàn-frame sẽ ~1.0 (SAI)


# ===================== stage: fail-fast construction + ROI skip =====================

def test_stage_construction_validates_roi():
    with pytest.raises(ValueError):
        MotionGateStage(roi=(0.6, 0.0, 0.5, 0.5))   # x+w>1 → fail-fast NGAY lúc dựng (không đợi frame)


def test_stage_roi_skips_change_outside():
    st = MotionGateStage(roi=(0.0, 0.0, 0.5, 0.5))
    base = np.full((10, 10, 3), 100, dtype=np.uint8)
    st.process(_packet(base))                       # frame đầu → pass + dựng mask
    moved = base.copy()
    moved[7:, 7:] = 200                             # đổi NGOÀI ROI
    r = st.process(_packet(moved))
    assert r.status == StageStatus.SKIPPED          # ROI tĩnh → gate skip (không chạy detector oan)


def test_stage_roi_passes_change_inside():
    st = MotionGateStage(roi=(0.0, 0.0, 0.5, 0.5))
    base = np.full((10, 10, 3), 100, dtype=np.uint8)
    st.process(_packet(base))
    moved = base.copy()
    moved[0:5, 0:5] = 200                            # đổi TRONG ROI
    r = st.process(_packet(moved))
    assert r.status == StageStatus.SUCCESS


def test_stage_illum_robust_skips_global_brightness():
    st = MotionGateStage(illumination_robust=True)
    base = np.full((8, 8, 3), 100, dtype=np.uint8)
    st.process(_packet(base))
    brighter = base + np.uint8(40)                   # đèn bật / mây tan → sáng đều +40
    r = st.process(_packet(brighter))
    assert r.status == StageStatus.SKIPPED           # bền-illumination → không trigger oan (đóng K-063)


def test_stage_roi_empty_pixel_errors_first_frame():
    st = MotionGateStage(roi=(0.0, 0.0, 0.1, 0.1))   # range hợp lệ; rỗng-pixel lộ ở frame đầu (cần shape)
    r = st.process(_packet(np.full((4, 4, 3), 100, dtype=np.uint8)))
    assert r.status == StageStatus.ERROR and r.error_type == "ValueError"


# ===================== config/CLI (P4 config-time + deploy-by-config) =====================

def _pcfg(motion_params):
    return PipelineConfig(
        id="cam0",
        source=SourceConfig("fake", {"max_frames": 3}),
        detector=DetectorConfig("fake", {"model_size": 64}),
        stages=[
            StageConfig("motion_gate", motion_params),
            StageConfig("detect"),
            StageConfig("count"),
        ],
        sinks=(),
    )


def test_config_motion_gate_roi_builds():
    runner = build_runner(_pcfg({"roi": [0.0, 0.0, 0.5, 0.5], "illumination_robust": True}))
    assert runner is not None


def test_config_bad_roi_range_configerror():
    with pytest.raises(ConfigError):
        build_runner(_pcfg({"roi": [0.6, 0.0, 0.5, 0.5]}))    # x+w>1 → ConfigError SỚM (config-time)


def test_config_bad_roi_arity_configerror():
    with pytest.raises(ConfigError):
        build_runner(_pcfg({"roi": [0.0, 0.0, 0.5]}))         # chỉ 3 số → ConfigError


def test_config_unknown_param_still_rejected():
    with pytest.raises(ConfigError):
        build_runner(_pcfg({"bogus": 1}))                     # K-046 strict-key giữ nguyên
