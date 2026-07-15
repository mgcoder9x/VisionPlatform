"""DetectionCadenceConfig — tham số điều-tiết detect (spec adaptive-detection-perf Task 1), fail-fast.

Layer: kernel — THUẦN (stdlib). Gom các RUNTIME lever giảm tần suất detect trên CPU no-GPU:
- **detect-cadence:** `detectMinIntervalMs` (ns tối thiểu giữa 2 detect) + `detectEveryN` (mỗi N frame-version).
- **motion-gate:** bỏ detect khi cảnh tĩnh (`motion*` — tái dùng `domain.motion.changed_ratio` ở tầng loop).

Validate MỌI invariant lúc dựng (design §Data Models). Mặc định = HÀNH VI HIỆN TẠI (min-interval=0, every-n=1,
motion off) → additive. Ràng buộc liên-spec P5 (`detectMinIntervalMs <= displayLeaseMs` của overlay) KHÔNG
kiểm ở đây (config self-contained) mà ở `assert_cadence_fits_lease` — gọi lúc wire khi biết cả 2 config
(tránh kernel→overlay coupling). `experimental=True` = default CHƯA chốt bằng SLA đo thật (Task 0).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from vision_platform.domain.motion import validate_roi   # roi CHUẨN-HOÁ [0,1] — nguồn sự thật duy nhất


class DetectionConfigError(ValueError):
    """Cấu hình cadence/motion không hợp lệ — fail-fast trước khi chạy (không chạy với giá trị sai)."""


def _nonneg_int(name: str, v: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise DetectionConfigError(f"{name} phải là int, got {type(v).__name__}")
    if v < 0:
        raise DetectionConfigError(f"{name} phải >= 0, got {v}")
    return v


def _pos_int(name: str, v: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise DetectionConfigError(f"{name} phải là int, got {type(v).__name__}")
    if v < 1:
        raise DetectionConfigError(f"{name} phải >= 1, got {v}")
    return v


@dataclass(frozen=True)
class DetectionCadenceConfig:
    """Tham số điều-tiết detect. Đơn vị ms cho duration. Mặc định = hành vi hiện tại (additive)."""
    detectMinIntervalMs: int = 0          # 0 = không giới hạn nhịp (throttle; hành vi hiện tại)
    detectMaxIntervalMs: int = 0          # 0 = tắt heartbeat; >0 = ÉP detect nếu quá lâu (chống mất box K-103)
    detectEveryN: int = 1                 # 1 = detect mọi frame-version mới (hành vi hiện tại)
    motionGate: bool = False              # False = không cổng chuyển động (hành vi hiện tại)
    motionPixelDiffThreshold: int = 25    # ngưỡng pixel đổi (0..255) — mirror MotionGateStage
    motionMinAreaRatio: float = 0.005     # < ngưỡng này (tỉ lệ pixel đổi) → coi là tĩnh → bỏ detect
    motionMaxConsecutiveSkip: int = 0     # 0 = skip tự do; >0 = sau N skip liên tiếp ép 1 detect
    motionRoi: Optional[Tuple[float, float, float, float]] = None   # (x,y,w,h) CHUẨN-HOÁ [0,1] — None=toàn khung
    experimental: bool = True

    def __post_init__(self) -> None:
        _nonneg_int("detectMinIntervalMs", self.detectMinIntervalMs)
        _nonneg_int("detectMaxIntervalMs", self.detectMaxIntervalMs)
        _pos_int("detectEveryN", self.detectEveryN)
        if self.detectMaxIntervalMs > 0 and self.detectMinIntervalMs > self.detectMaxIntervalMs:
            raise DetectionConfigError(
                f"detectMinIntervalMs ({self.detectMinIntervalMs}) > detectMaxIntervalMs "
                f"({self.detectMaxIntervalMs}) — throttle không được lớn hơn heartbeat")
        _nonneg_int("motionMaxConsecutiveSkip", self.motionMaxConsecutiveSkip)
        _nonneg_int("motionPixelDiffThreshold", self.motionPixelDiffThreshold)
        if self.motionPixelDiffThreshold > 255:
            raise DetectionConfigError(
                f"motionPixelDiffThreshold ∈ [0,255], got {self.motionPixelDiffThreshold}")
        if not isinstance(self.motionMinAreaRatio, (int, float)) or isinstance(self.motionMinAreaRatio, bool):
            raise DetectionConfigError(
                f"motionMinAreaRatio phải là số, got {type(self.motionMinAreaRatio).__name__}")
        if not (0.0 <= float(self.motionMinAreaRatio) <= 1.0):
            raise DetectionConfigError(
                f"motionMinAreaRatio ∈ [0,1], got {self.motionMinAreaRatio}")
        if self.motionRoi is not None:
            roi = self.motionRoi
            if len(roi) != 4:
                raise DetectionConfigError(
                    f"motionRoi cần đúng 4 số chuẩn-hoá (x,y,w,h) ∈[0,1], got {roi!r}")
            try:
                validate_roi(*roi)   # tái dùng domain (chuẩn-hoá [0,1]): x,y∈[0,1], w>0,h>0, x+w<=1, y+h<=1
            except ValueError as e:
                raise DetectionConfigError(f"motionRoi không hợp lệ: {e}") from e


def assert_cadence_fits_lease(cfg: DetectionCadenceConfig, *, display_lease_ms: int) -> None:
    """P5 (liên-spec overlay): nếu detect thưa hơn lease thì box hết hạn trước detect kế → GIẬT.

    Cưỡng chế `detectMinIntervalMs <= display_lease_ms`. Gọi lúc WIRE (khi biết cả OverlayConfig +
    DetectionCadenceConfig) — tách khỏi __post_init__ để config này không phụ thuộc overlay.
    """
    if cfg.detectMinIntervalMs > display_lease_ms:
        raise DetectionConfigError(
            f"detectMinIntervalMs ({cfg.detectMinIntervalMs}) > displayLeaseMs ({display_lease_ms}) "
            f"— box sẽ hết hạn trước lần detect kế (giật). Giảm interval hoặc tăng lease.")
    if cfg.detectMaxIntervalMs > 0 and cfg.detectMaxIntervalMs > display_lease_ms:
        raise DetectionConfigError(
            f"detectMaxIntervalMs ({cfg.detectMaxIntervalMs}) > displayLeaseMs ({display_lease_ms}) "
            f"— heartbeat chậm hơn lease → vật đứng-yên vẫn mất box (K-103). Giảm max-interval <= lease.")
