"""MotionGateStage — chặn frame TĨNH trước detector để giảm tải GPU (sub-spec motion-gate, R1).

Layer: runtime/stages. Đặt TRƯỚC DetectStage. Đo tỉ lệ pixel đổi (domain.changed_ratio); < ngưỡng → raise
`SkipFrameSignal` (BaseStage bắt → StageResult.SKIPPED → executor dừng chuỗi → detector KHÔNG chạy).

STATEFUL (nhớ frame trước). Camera-affinity (K-042): 1 instance/1 camera; trộn source → fail-fast.
Frame ĐẦU / đổi-shape → CHO ĐI TIẾP (thiếu mốc → thà chạy thừa hơn bỏ sót — QĐ-3).
"""
from typing import Optional

import numpy as np

from vision_platform.domain.motion import changed_ratio
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.stage_contract import SkipFrameSignal
from vision_platform.runtime.base_stage import BaseStage


class MotionGateStage(BaseStage):
    def __init__(
        self,
        *,
        pixel_diff_threshold: int = 25,
        min_area_ratio: float = 0.005,
        max_consecutive_skip: int = 0,
    ):
        super().__init__("motion_gate")
        if max_consecutive_skip < 0:
            raise ValueError(f"max_consecutive_skip phải >= 0, got {max_consecutive_skip}")
        self._pixel_diff_threshold = pixel_diff_threshold
        self._min_area_ratio = min_area_ratio
        # 0 = KHÔNG giới hạn (skip tự do — hành vi gốc). >0 = sau N skip liên tiếp, ÉP 1 frame đi tiếp
        # (chống bỏ sót vật đứng-yên/xuất-hiện-chậm khi cảnh tĩnh lâu → detector chạy định kỳ).
        self._max_consecutive_skip = max_consecutive_skip
        self._consecutive_skips = 0
        self._prev: Optional[np.ndarray] = None
        self._source_id: Optional[str] = None

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        # Camera-affinity (K-042): 1 instance/1 camera.
        if self._source_id is None:
            self._source_id = packet.source_id
        elif packet.source_id != self._source_id:
            raise ValueError(
                f"MotionGateStage nhận 2 source_id ('{self._source_id}' rồi '{packet.source_id}') — "
                "1 instance/1 camera (K-042)"
            )

        curr = packet.media_ref.array
        # Frame đầu / đổi shape → thiếu mốc so sánh → CHO ĐI TIẾP (không bỏ nhầm) + lưu mốc.
        if self._prev is None or self._prev.shape != curr.shape:
            self._prev = curr
            self._consecutive_skips = 0
            return packet.with_artifact("motion_ratio", 1.0)

        ratio = changed_ratio(self._prev, curr, self._pixel_diff_threshold)
        self._prev = curr
        if ratio < self._min_area_ratio:
            # Tĩnh. Nếu đã skip liên tiếp tới hạn → ÉP đi tiếp (chống bỏ sót khi tĩnh lâu — R min-interval).
            if self._max_consecutive_skip > 0 and self._consecutive_skips >= self._max_consecutive_skip:
                self._consecutive_skips = 0
                return (
                    packet
                    .with_artifact("motion_ratio", ratio)
                    .with_artifact("motion_forced", True)   # đi tiếp do hết hạn skip, không do chuyển động
                )
            # Chưa tới hạn → skip (KHÔNG phải lỗi): detector không chạy → tiết kiệm GPU.
            self._consecutive_skips += 1
            raise SkipFrameSignal(
                f"no motion (ratio={ratio:.4f} < {self._min_area_ratio}), "
                f"consecutive_skips={self._consecutive_skips}"
            )
        # Có chuyển động → reset đếm skip.
        self._consecutive_skips = 0
        return packet.with_artifact("motion_ratio", ratio)

    def teardown(self) -> None:
        self._prev = None
        self._consecutive_skips = 0
