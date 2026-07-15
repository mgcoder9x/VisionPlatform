"""OverlayConfig — tham số ổn-định-hiển-thị cho web-live-overlay-sync (spec Task 1), fail-fast.

Layer: kernel — THUẦN (stdlib). Validate MỌI invariant lúc khởi tạo (design §Configuration invariants):
duration là int dương hữu hạn; ngưỡng trong khoảng; lease xếp thứ tự candidate<=display<=ghost;
client-silence-cap <= ghost. Nếu yêu-cầu-cadence-đo không lọt dưới ghostSlaMs → `OverlayConfigError`
(KHÔNG âm thầm vi phạm 1 ràng buộc). Chống policy 'tối ưu' bịa: default chờ số đo Task 0 (spec §Diagnostic).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class OverlayConfigError(ValueError):
    """Cấu hình overlay không hợp lệ — fail-fast trước khi start (không chạy với giá trị sai)."""


def _pos_int(name: str, v: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise OverlayConfigError(f"{name} phải là int, got {type(v).__name__}")
    if v <= 0:
        raise OverlayConfigError(f"{name} phải là int dương, got {v}")
    return v


@dataclass(frozen=True)
class OverlayConfig:
    """Tham số stabilizer + lease + reconnect. Đơn vị ms cho mọi duration.

    experimental=True nghĩa là CHƯA chốt bằng SLA đo thật (Task 0) — chỉ dùng để chẩn đoán, KHÔNG
    tuyên bố 'tối ưu'. requiredCadenceMs (optional) = nhịp detector mục tiêu cần phủ; nếu > ghostSlaMs
    thì stable-mode BẤT KHẢ (lease không thể vừa <=ghost vừa phủ cadence) → OverlayConfigError.
    """
    iouThreshold: float = 0.3
    emaAlpha: float = 0.5
    minHits: int = 2
    maxMisses: int = 2
    # Confidence hysteresis (chống flicker vật xa, K-106): 2 ngưỡng kiểu Schmitt-trigger.
    # createConfThreshold = ngưỡng CAO để TẠO track mới (chống track rác); sustainConfThreshold = ngưỡng
    # THẤP để NUÔI track đã tồn tại (khớp IoU) → vật conf dao động quanh ngưỡng KHÔNG rớt ra → hết flicker,
    # ít ghost (rời thật + conf<sustain → xóa nhanh). Mặc định 0.0/0.0 = TẮT (hành vi cũ, additive).
    # Điều kiện: detector decode conf phải <= sustainConfThreshold để box yếu tới được stabilizer.
    createConfThreshold: float = 0.0
    sustainConfThreshold: float = 0.0
    # Motion-aware eviction (chống ghost "người đi qua rồi bbox 1 lúc mới tắt", K-108): ước lượng vận tốc từ
    # 2 vị trí khớp gần nhất; khi track bị miss, dự đoán tâm — nếu RA NGOÀI khung [0,1] (đã rời) → xoá NGAY
    # (không chờ hết lease). Vật đứng-yên/bị-che (dự đoán còn trong khung) → giữ theo lease (không hại flicker).
    # Mặc định False = TẮT (hành vi cũ, additive).
    evictPredictedOffFrame: bool = False
    # Motion-predicted matching (chống flicker vật di chuyển, K-107): khi khớp detection mới ↔ track confirmed,
    # dùng vị trí DỰ ĐOÁN của track (last + vận tốc*dt) thay vì vị trí cũ → vật di chuyển giữa 2 detect thưa
    # (CPU) vẫn IoU-match → giữ 1 displayId (hết churn). Mặc định False = TẮT (hành vi cũ, additive).
    matchUsePrediction: bool = False
    reconnectMinMs: int = 200
    reconnectMaxMs: int = 5000
    candidateLeaseMs: int = 300
    displayLeaseMs: int = 600
    ghostSlaMs: int = 1500
    clientSilenceCapMs: int = 1200
    # Health thresholds (Task 6) — dẫn xuất trạng thái source/detector từ nhịp thời gian.
    sourceStaleMs: int = 2000       # không read-success quá lâu → source STALE
    detectorStaleMs: int = 3000     # không completion quá lâu → detector STALE
    detectorHangMs: int = 5000      # 1 inference in-flight quá lâu → detector STALE (hung)
    requiredCadenceMs: Optional[int] = None
    experimental: bool = True

    def __post_init__(self) -> None:
        if not (0.0 < self.iouThreshold <= 1.0):
            raise OverlayConfigError(f"iouThreshold ∈ (0,1], got {self.iouThreshold}")
        if not (0.0 < self.emaAlpha <= 1.0):
            raise OverlayConfigError(f"emaAlpha ∈ (0,1], got {self.emaAlpha}")
        if self.minHits < 1:
            raise OverlayConfigError(f"minHits >= 1, got {self.minHits}")
        if self.maxMisses < 0:
            raise OverlayConfigError(f"maxMisses >= 0, got {self.maxMisses}")
        # confidence hysteresis: 0 <= sustain <= create <= 1 (nuôi dễ hơn tạo — trễ đúng chiều)
        for _n, _v in (("createConfThreshold", self.createConfThreshold),
                       ("sustainConfThreshold", self.sustainConfThreshold)):
            if not isinstance(_v, (int, float)) or isinstance(_v, bool):
                raise OverlayConfigError(f"{_n} phải là số, got {type(_v).__name__}")
            if not (0.0 <= float(_v) <= 1.0):
                raise OverlayConfigError(f"{_n} ∈ [0,1], got {_v}")
        if self.sustainConfThreshold > self.createConfThreshold:
            raise OverlayConfigError(
                f"sustainConfThreshold ({self.sustainConfThreshold}) phải <= createConfThreshold "
                f"({self.createConfThreshold}) — nuôi track phải dễ hơn tạo track (hysteresis đúng chiều)")
        if not isinstance(self.evictPredictedOffFrame, bool):
            raise OverlayConfigError(
                f"evictPredictedOffFrame phải là bool, got {type(self.evictPredictedOffFrame).__name__}")
        if not isinstance(self.matchUsePrediction, bool):
            raise OverlayConfigError(
                f"matchUsePrediction phải là bool, got {type(self.matchUsePrediction).__name__}")
        # duration dương
        _pos_int("reconnectMinMs", self.reconnectMinMs)
        _pos_int("reconnectMaxMs", self.reconnectMaxMs)
        _pos_int("candidateLeaseMs", self.candidateLeaseMs)
        _pos_int("displayLeaseMs", self.displayLeaseMs)
        _pos_int("ghostSlaMs", self.ghostSlaMs)
        _pos_int("clientSilenceCapMs", self.clientSilenceCapMs)
        _pos_int("sourceStaleMs", self.sourceStaleMs)
        _pos_int("detectorStaleMs", self.detectorStaleMs)
        _pos_int("detectorHangMs", self.detectorHangMs)
        # thứ tự
        if self.reconnectMinMs > self.reconnectMaxMs:
            raise OverlayConfigError(
                f"reconnectMinMs ({self.reconnectMinMs}) <= reconnectMaxMs ({self.reconnectMaxMs})")
        if not (self.candidateLeaseMs <= self.displayLeaseMs <= self.ghostSlaMs):
            raise OverlayConfigError(
                f"cần candidateLeaseMs<=displayLeaseMs<=ghostSlaMs, got "
                f"{self.candidateLeaseMs}/{self.displayLeaseMs}/{self.ghostSlaMs}")
        if self.clientSilenceCapMs > self.ghostSlaMs:
            raise OverlayConfigError(
                f"clientSilenceCapMs ({self.clientSilenceCapMs}) <= ghostSlaMs ({self.ghostSlaMs})")
        # cadence-fit: yêu cầu phủ cadence nhưng không lọt dưới ghost → BẤT KHẢ (fail-fast, không vi phạm ngầm)
        if self.requiredCadenceMs is not None:
            _pos_int("requiredCadenceMs", self.requiredCadenceMs)
            if self.requiredCadenceMs > self.ghostSlaMs:
                raise OverlayConfigError(
                    f"requiredCadenceMs ({self.requiredCadenceMs}) > ghostSlaMs ({self.ghostSlaMs}) "
                    f"— stable-mode BẤT KHẢ (lease không thể vừa phủ cadence vừa <=ghost)")
