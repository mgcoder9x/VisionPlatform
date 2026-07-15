"""MotionGate — lõi cổng-chuyển-động TÁI DÙNG được (spec adaptive-detection-perf Task 2).

Layer: domain — THUẦN numpy (import `domain.motion` cùng layer). Mirror ngữ nghĩa `runtime/stages/MotionGateStage`
NHƯNG decouple khỏi `MediaPacket`/pipeline Stage → dùng trực tiếp trong vòng lặp bespoke (`vision_web_app._detect_loop`).

`decide(frame) -> (should_run, ratio, forced)`:
- frame đầu / đổi shape → thiếu mốc so sánh → RUN (thà chạy thừa hơn bỏ sót, QĐ như MotionGateStage), ratio=1.0.
- `changed_ratio < min_area_ratio` (tĩnh) → SKIP; nhưng nếu đã skip liên tiếp tới `max_consecutive_skip` → ÉP RUN
  đúng 1 frame (`forced=True`, chống bỏ sót vật đứng-yên khi cảnh tĩnh lâu) rồi reset đếm.
- có chuyển động → RUN + reset đếm skip.

STATEFUL (nhớ prev-frame + đếm skip) — 1 instance / 1 nguồn (camera-affinity). Không I/O. ROI chuẩn-hoá [0,1].
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from vision_platform.domain.motion import changed_ratio, roi_mask, validate_roi


class MotionGate:
    def __init__(
        self,
        *,
        pixel_diff_threshold: int = 25,
        min_area_ratio: float = 0.005,
        max_consecutive_skip: int = 0,
        roi: Optional[Tuple[float, float, float, float]] = None,
        illumination_robust: bool = False,
    ) -> None:
        if max_consecutive_skip < 0:
            raise ValueError(f"max_consecutive_skip >= 0, got {max_consecutive_skip}")
        if roi is not None:
            validate_roi(*roi)   # fail-fast chuẩn-hoá [0,1] (mask dựng lazy khi biết shape)
        self._threshold = pixel_diff_threshold
        self._min_area_ratio = min_area_ratio
        self._max_consecutive_skip = max_consecutive_skip
        self._roi = tuple(roi) if roi is not None else None
        self._illumination_robust = illumination_robust
        self._prev: Optional[np.ndarray] = None
        self._mask: Optional[np.ndarray] = None
        self._consecutive_skips = 0

    def decide(self, frame: np.ndarray) -> Tuple[bool, float, bool]:
        """Trả (should_run, ratio, forced). should_run=False nghĩa BỎ detect frame này (giữ overlay cũ)."""
        if self._prev is None or self._prev.shape != frame.shape:
            self._prev = frame
            self._consecutive_skips = 0
            if self._roi is not None:
                self._mask = roi_mask(frame.shape[0], frame.shape[1], *self._roi)
            return True, 1.0, False

        ratio = changed_ratio(self._prev, frame, self._threshold,
                              mask=self._mask, illumination_robust=self._illumination_robust)
        self._prev = frame
        if ratio < self._min_area_ratio:
            if self._max_consecutive_skip > 0 and self._consecutive_skips >= self._max_consecutive_skip:
                self._consecutive_skips = 0
                return True, ratio, True         # ép chạy định kỳ (chống bỏ sót)
            self._consecutive_skips += 1
            return False, ratio, False           # tĩnh → bỏ detect
        self._consecutive_skips = 0
        return True, ratio, False                # có chuyển động → chạy

    def reset(self) -> None:
        self._prev = None
        self._mask = None
        self._consecutive_skips = 0
