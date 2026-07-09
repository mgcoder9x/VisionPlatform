"""TrackingStage — analytics STATEFUL đầu tiên (sub-spec object-tracking-count).

Layer: runtime/stages. Đọc artifacts["detections"] (do DetectStage ghi — CHUNG với CountStage, fan-out R3.1)
→ ITracker.update → ghi artifacts["tracks"] + ["unique_count"] + ["active_count"].

STATEFUL (khác CountStage stateless): state nằm trong `tracker`. Camera-affinity (K-042): 1 instance/1 camera —
nhận source_id lạ → fail-fast (raise → StageResult.ERROR) thay vì trộn state âm thầm (đếm loạn).
"""
from typing import Optional

from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.ports.tracker import ITracker
from vision_platform.runtime.base_stage import BaseStage


class TrackingStage(BaseStage):
    def __init__(self, tracker: ITracker):
        super().__init__("track")
        self._tracker = tracker
        self._source_id: Optional[str] = None

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        dets = packet.artifacts.get("detections")
        if dets is None:
            raise ValueError(
                "TrackingStage cần artifacts['detections'] — chạy DetectStage trước (sai thứ tự pipeline)"
            )
        # Camera-affinity (K-042): 1 instance chỉ phục vụ 1 luồng camera.
        if self._source_id is None:
            self._source_id = packet.source_id
        elif packet.source_id != self._source_id:
            raise ValueError(
                f"TrackingStage nhận 2 source_id ('{self._source_id}' rồi '{packet.source_id}') — "
                "1 instance/1 camera (K-042); trộn state = đếm loạn"
            )

        tracks = self._tracker.update(dets)
        return (
            packet
            .with_artifact("tracks", tracks)
            .with_artifact("unique_count", self._tracker.unique_count)
            .with_artifact("active_count", self._tracker.active_count)
        )

    def teardown(self) -> None:
        # Giải phóng state khi kết thúc luồng.
        self._tracker.reset()
