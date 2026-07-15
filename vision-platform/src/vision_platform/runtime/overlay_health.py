"""derive_health — dẫn xuất trạng thái source/detector từ nhịp thời gian (spec Task 6, Property 6).

Layer: runtime (THUẦN — dùng enum kernel, không I/O). Bản chất: PHÂN BIỆT được các tình huống lỗi khác nhau
để chẩn đoán đúng, KHÔNG bịa "EMPTY" khi thực chất detector lỗi/nguồn mất (design §3):
- init (chưa có dữ liệu) ≠ raw EMPTY (detector chạy, 0 vật) ≠ detector ERROR/STALE ≠ source RECONNECTING/STALE/ERROR.
- Lỗi KHÔNG refresh display (chỉ set health) → box cũ sống tới hết lease rồi thôi (không "hồi sinh" giả).

Thuần theo timestamps monotonic (ns) + ngưỡng config → clock tiêm ở caller (test fake-clock, xác định).
`error` tường minh > STALE-suy-từ-thời-gian > LIVE. `None` timestamp = chưa từng xảy ra → INITIALIZING.
"""
from __future__ import annotations

from typing import Optional

from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import DetectorState, HealthSnapshot, SourceState

_MS = 1_000_000


def derive_health(
    *, now_ns: int, config: OverlayConfig,
    source_error: bool = False, detector_error: bool = False,
    last_read_ns: Optional[int] = None,
    last_completion_ns: Optional[int] = None,
    in_flight_start_ns: Optional[int] = None,
) -> HealthSnapshot:
    """Trả HealthSnapshot phân biệt được (Property 6). Ưu tiên: error > hung/stale > init > live."""
    # ---- source ----
    if source_error:
        source = SourceState.ERROR
    elif last_read_ns is None:
        source = SourceState.INITIALIZING
    elif now_ns - last_read_ns > config.sourceStaleMs * _MS:
        source = SourceState.STALE
    else:
        source = SourceState.LIVE

    # ---- detector ----
    if detector_error:
        detector = DetectorState.ERROR
    elif in_flight_start_ns is not None and now_ns - in_flight_start_ns > config.detectorHangMs * _MS:
        detector = DetectorState.STALE        # 1 inference treo quá lâu = hung
    elif last_completion_ns is None:
        detector = DetectorState.INITIALIZING
    elif now_ns - last_completion_ns > config.detectorStaleMs * _MS:
        detector = DetectorState.STALE
    else:
        detector = DetectorState.LIVE

    return HealthSnapshot(source=source, detector=detector)
