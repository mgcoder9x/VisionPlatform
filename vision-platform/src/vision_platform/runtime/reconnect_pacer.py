"""Reconnect pacing cho source discontinuity (spec Task 7, Property 11).

Layer: runtime (THUẦN — không I/O; wait/clock do caller tiêm). Hai việc bản chất (design §Reconnect pacing):
1. **Epoch tăng + clear ĐÚNG MỘT LẦN** tại transition `LIVE→discontinuity` đầu tiên; các retry/reopen thuộc
   epoch mới đó KHÔNG tăng thêm; về LIVE rồi mất lại → episode mới, tăng lại (`ReconnectPacer`).
2. **Mỗi attempt obey clamp** `[reconnectMinMs, reconnectMaxMs]`; retry_after thiếu/không-hợp-lệ → dùng min;
   TUYỆT ĐỐI không sleep 0 (chống busy-loop — lỗ `_video_loop` cũ, K-100 điểm 5). V1 KHÔNG jitter (webcam local).
"""
from __future__ import annotations

import math
from typing import Optional

from vision_platform.kernel.overlay_config import OverlayConfig

_MS = 1_000_000


def clamp_retry_ns(retry_after_ms: Optional[float], config: OverlayConfig) -> int:
    """Trả số ns nên chờ trước lần reconnect kế = clamp(retry_after_ms, [min,max]).
    retry_after_ms None/không-hữu-hạn/<=0/không-phải-số → dùng reconnectMinMs (KHÔNG bao giờ 0)."""
    lo, hi = config.reconnectMinMs, config.reconnectMaxMs
    ms = retry_after_ms
    if (ms is None or isinstance(ms, bool) or not isinstance(ms, (int, float))
            or not math.isfinite(ms) or ms <= 0):
        ms = lo
    ms = max(lo, min(hi, ms))
    return int(ms) * _MS


class ReconnectPacer:
    """Đảm bảo epoch bump ĐÚNG MỘT LẦN mỗi episode mất-kết-nối + clamp mỗi attempt."""

    def __init__(self, config: OverlayConfig) -> None:
        self._cfg = config
        self._in_discontinuity = False

    def on_reconnect_attempt(self, retry_after_ms: Optional[float] = None) -> tuple[bool, int]:
        """Gọi mỗi lần source ở trạng thái mất-kết-nối/đang-retry. Trả (should_bump_epoch, sleep_ns).
        should_bump_epoch=True CHỈ ở attempt ĐẦU của episode (LIVE→discontinuity)."""
        should_bump = not self._in_discontinuity
        self._in_discontinuity = True
        return should_bump, clamp_retry_ns(retry_after_ms, self._cfg)

    def on_live(self) -> None:
        """Source đã LIVE lại → kết thúc episode; mất lại lần sau = episode mới (bump lại)."""
        self._in_discontinuity = False

    @property
    def in_discontinuity(self) -> bool:
        return self._in_discontinuity
