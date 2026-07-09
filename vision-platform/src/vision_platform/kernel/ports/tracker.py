"""ITracker — port analytics theo dõi vật xuyên frame (sub-spec object-tracking-count, R3.4).

Layer: kernel/ports — Protocol thuần. Cho phép thay impl (IoU-greedy v1 → Kalman/DeepSORT sau) mà KHÔNG
đụng `TrackingStage`. Đối xứng `IDetector`/`ISink`. Tracker CÓ STATE (khác detector) → có `reset()`.

Camera-affinity (K-042): 1 instance PHỤC VỤ 1 luồng camera — state KHÔNG chia sẻ giữa camera.
"""
from typing import Protocol, Sequence, runtime_checkable

from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.tracking_protocol import Track


@runtime_checkable
class ITracker(Protocol):
    """Theo dõi vật: nhận detections 1 frame → trả tracks (đã gán track_id). Stateful."""

    def update(self, detections: Sequence[Detection]) -> tuple[Track, ...]:
        """1 frame: gán/khớp track_id cho từng detection; cập nhật state nội bộ. Trả tuple Track theo thứ tự detection."""
        ...

    def reset(self) -> None:
        """Xoá toàn bộ state (đổi camera / khởi động lại luồng)."""
        ...

    @property
    def unique_count(self) -> int:
        """Tổng track_id DISTINCT đã tạo (đơn điệu tăng — đếm không trùng)."""
        ...

    @property
    def active_count(self) -> int:
        """Số track đang sống (chưa retire)."""
        ...
