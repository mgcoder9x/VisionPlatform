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
