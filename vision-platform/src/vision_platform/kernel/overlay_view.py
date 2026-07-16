"""DTO bất biến cho web-live-overlay-sync (spec Task 1) — raw truth ⊥ display projection.

Layer: kernel — DTO THUẦN (frozen dataclass + enum, chỉ stdlib + `domain.BBox`/`kernel.Detection`).
KHÔNG I/O, KHÔNG import adapter/runtime/profiles (import-linter ép). Đây là các "ảnh chụp bất biến"
mà `OverlayStateStore` (runtime, Task 4) commit và `/overlay` endpoint (profiles, Task 8) chiếu ra JSON.

Nguyên tắc (design §Data Models / §Components):
- **Raw inference truth** (`RawDetectionSnapshot`): kết quả detector bất biến + định danh frame + timestamps
  monotonic. Dùng cho analytics. KHÔNG smoothing.
- **Display projection** (`DisplayTrack`/`DisplayView`): trạng thái CHỈ để vẽ (đã matching/EMA/lease).
  TUYỆT ĐỐI không đi vào tracker/count/sink (Property 10 — cưỡng chế bằng import-linter ở Task 8).
- `OverlayViewSnapshot`: MỘT ảnh committed atomic (không trộn epoch/raw/display/health) — Property 1.
Mọi giá trị số hữu hạn (finite); vi phạm → raise ngay lúc khởi tạo (fail-fast, chống NaN/Inf rò vào wire).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from vision_platform.domain.bbox import BBox
from vision_platform.kernel.inference_protocol import Detection


class Outcome(str, Enum):
    """Kết quả một inference completion (raw truth). Exception KHÔNG tạo EMPTY (design §2)."""
    DETECTED = "DETECTED"
    EMPTY = "EMPTY"


class SourceState(str, Enum):
    """Trạng thái nguồn — độc lập detector (design §HealthSnapshot)."""
    INITIALIZING = "INITIALIZING"
    LIVE = "LIVE"
    RECONNECTING = "RECONNECTING"
    STALE = "STALE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class DetectorState(str, Enum):
    """Trạng thái detector — độc lập nguồn."""
    INITIALIZING = "INITIALIZING"
    LIVE = "LIVE"
    STALE = "STALE"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


def _finite(name: str, v: float) -> float:
    if not math.isfinite(v):
        raise ValueError(f"{name} phải hữu hạn (finite), got {v!r}")
    return v


@dataclass(frozen=True)
class InputFrameSnapshot:
    """Input bất biến đã 'sở hữu' (design §1). `frameVersion` đơn điệu TRONG một `sourceEpoch`
    (không so sánh qua epoch). `inputAcquiredNs` = lúc `read()` trả về theo server monotonic clock
    (KHÔNG phải camera-capture time). `frame` giữ read-only-by-convention sau publish."""
    processEpoch: str
    sourceEpoch: int
    frameVersion: int
    inputAcquiredNs: int
    width: int
    height: int
    frame: object = None   # opaque (np.ndarray) — kernel không import numpy; read-only-by-convention

    def __post_init__(self) -> None:
        if self.sourceEpoch < 1:
            raise ValueError(f"sourceEpoch >= 1, got {self.sourceEpoch}")
        if self.frameVersion < 0:
            raise ValueError(f"frameVersion >= 0, got {self.frameVersion}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"dims > 0, got {self.width}x{self.height}")


@dataclass(frozen=True)
class RawDetectionSnapshot:
    """MỘT inference truth bất biến (design §2). Detector exception KHÔNG tạo snapshot EMPTY (dùng health).

    `boxes` = tuple[Detection] (raw, KHÔNG smoothing). Timestamps monotonic ns (server clock) để endpoint
    chiếu age (`sourceAgeMs = now - inputAcquiredNs`, `resultAgeMs = now - publishedNs`)."""
    processEpoch: str
    sourceEpoch: int
    sourceFrameVersion: int
    inferenceGeneration: int
    inputAcquiredNs: int
    inferenceStartNs: int
    inferenceEndNs: int
    publishedNs: int
    outcome: Outcome
    boxes: Tuple[Detection, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "boxes", tuple(self.boxes))
        if self.outcome == Outcome.EMPTY and self.boxes:
            raise ValueError("outcome EMPTY nhưng có boxes — mâu thuẫn raw truth")
        if self.inferenceEndNs < self.inferenceStartNs:
            raise ValueError("inferenceEndNs < inferenceStartNs")


@dataclass(frozen=True)
class HealthSnapshot:
    """Hai state ĐỘC LẬP (design §3) — commit qua store, endpoint không suy diễn."""
    source: SourceState
    detector: DetectorState


@dataclass(frozen=True)
class NormalizedBox:
    """Wire contract 1 box hiển thị (design §Data Models). Toạ độ chuẩn hoá [0,1]; w/h ∈ (0,1] (zero-area
    bị loại ở projection Task 8). Mọi số hữu hạn. `label` là text (JSON/DOM), KHÔNG HTML."""
    displayId: str
    trackRevision: int
    remainingLeaseMs: int
    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not self.displayId:
            raise ValueError("displayId rỗng")
        if self.trackRevision < 0:
            raise ValueError(f"trackRevision >= 0, got {self.trackRevision}")
        if self.remainingLeaseMs < 0:
            raise ValueError(f"remainingLeaseMs >= 0, got {self.remainingLeaseMs}")
        if not (0.0 <= _finite("confidence", self.confidence) <= 1.0):
            raise ValueError(f"confidence ∈ [0,1], got {self.confidence}")
        for nm, v in (("x", self.x), ("y", self.y)):
            if not (0.0 <= _finite(nm, v) <= 1.0):
                raise ValueError(f"{nm} ∈ [0,1], got {v}")
        for nm, v in (("width", self.width), ("height", self.height)):
            if not (0.0 < _finite(nm, v) <= 1.0):
                raise ValueError(f"{nm} ∈ (0,1] (zero-area bị loại), got {v}")


@dataclass(frozen=True)
class DisplayTrack:
    """Track hiển thị đã xác nhận (server-side, design §4). `box` ở NORMALIZED space (đã EMA).
    `leaseDeadlineNs` = hạn theo server monotonic clock; endpoint chiếu `remainingLeaseMs`.
    `confidence` = độ tin của lần khớp gần nhất (feed vào NormalizedBox wire ở projection Task 8)."""
    displayId: str
    trackRevision: int
    label: str
    box: BBox
    leaseDeadlineNs: int
    missCount: int
    confidence: float = 0.0
    # Vận tốc tâm (chuẩn-hoá / GIÂY) — cho client ngoại suy pos+vel*dt (Wave A, spec overlay-tracking-refactor).
    # Default 0 = chưa đủ dữ liệu vận tốc → client vẽ tĩnh (không ngoại suy sai). Có dấu (âm=trái/lên).
    vx: float = 0.0
    vy: float = 0.0

    def __post_init__(self) -> None:
        if self.box.space.name != "NORMALIZED":
            raise ValueError(f"DisplayTrack.box phải NORMALIZED, got {self.box.space}")
        if self.trackRevision < 0 or self.missCount < 0:
            raise ValueError("trackRevision/missCount >= 0")
        if not (0.0 <= _finite("confidence", self.confidence) <= 1.0):
            raise ValueError(f"confidence ∈ [0,1], got {self.confidence}")
        _finite("vx", self.vx)
        _finite("vy", self.vy)


@dataclass(frozen=True)
class DisplayView:
    """Tập track hiển thị + revision + lý do (bounded enum) tại một commit."""
    revision: int
    reason: str
    tracks: Tuple[DisplayTrack, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        if self.revision < 0:
            raise ValueError(f"revision >= 0, got {self.revision}")


@dataclass(frozen=True)
class OverlayViewSnapshot:
    """MỘT ảnh committed atomic (Property 1) — endpoint chỉ chiếu ảnh này + một serializedAtNs, KHÔNG mutate.
    `rawResult=None` trước first result (health INITIALIZING) — shape ổn định bằng nullable, KHÔNG fake gen 0."""
    schemaVersion: int
    processEpoch: str
    sourceEpoch: int
    eventRevision: int
    health: HealthSnapshot
    display: DisplayView
    rawResult: Optional[RawDetectionSnapshot] = None

    def __post_init__(self) -> None:
        if self.eventRevision < 0:
            raise ValueError(f"eventRevision >= 0, got {self.eventRevision}")
        if self.sourceEpoch < 1:
            raise ValueError(f"sourceEpoch >= 1, got {self.sourceEpoch}")
