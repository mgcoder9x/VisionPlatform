"""Metric_DTO cho backpressure cross-process (spec backpressure-cross-process §4.1).

DTO thuần Python ở layer kernel — KHÔNG import zmq/torch/cv2/multiprocessing/shared_memory
(giữ contract import-linter #2, R9.1). Dùng để chia sẻ định nghĩa bộ đếm giữa các layer
(client adapters đếm → camera_worker/profiles đọc → ghi artifact) mà không kéo phụ thuộc I/O.

Bất biến bảo toàn (Frame_Conservation_Invariant, R4.3):
    frames_submitted + frames_dropped_backpressure == frames_captured
đúng SAU khi vòng lặp xử lý drain xong (mỗi frame captured được tính ĐÚNG MỘT trong
{submitted, dropped}; không frame nào ở trạng thái lửng). Xem K-051: `frames_submitted`
PHẢI được đếm tại lúc GỬI (không lúc enqueue) để bất biến này không bị đếm trùng dưới DROP_OLDEST.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BackpressureMetrics:
    """Bộ đếm quan sát được của đường submit inference (R5.1).

    Mỗi field chỉ được ghi bởi MỘT thread ở nơi phát sinh (captured=camera thread;
    submitted/infer_ok/infer_err/infer_timeout=io thread; dropped=BoundedQueue dưới lock);
    snapshot đọc sau khi thread quiesce nên DTO này bất biến (frozen), an toàn chia sẻ.
    """

    frames_captured: int
    frames_submitted: int
    frames_dropped_backpressure: int
    infer_ok: int
    infer_err: int
    infer_timeout: int

    @property
    def conserved(self) -> bool:
        """True khi thỏa bất biến bảo toàn (R4.3): submitted + dropped == captured."""
        return (
            self.frames_submitted + self.frames_dropped_backpressure
            == self.frames_captured
        )
