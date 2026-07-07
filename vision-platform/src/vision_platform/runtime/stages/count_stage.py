"""CountStage — analytics STATELESS đầu tiên: đếm phát-hiện TRONG TỪNG FRAME. Layer: runtime/stages.

Đọc artifacts["detections"] (do DetectStage ghi) → ghi artifacts["count"] + artifacts["count_by_label"].
STATELESS tuyệt đối (chỉ frame hiện tại) — KHÔNG tracking/đếm-không-trùng xuyên-frame (Lỗ 3 K-042, sub-spec sau).

Edge (quan trọng):
- artifacts KHÔNG có "detections" (chạy sai thứ tự stage) → raise → StageResult.ERROR (không đếm 0 âm thầm).
- có key nhưng tuple RỖNG (khung không có object) → count=0, count_by_label={} (HỢP LỆ, không lỗi).
"""
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.runtime.base_stage import BaseStage


class CountStage(BaseStage):
    def __init__(self):
        super().__init__("count")

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        dets = packet.artifacts.get("detections")
        if dets is None:
            raise ValueError(
                "CountStage cần artifacts['detections'] — chạy DetectStage trước (sai thứ tự pipeline)"
            )
        count = len(dets)
        count_by_label: dict[str, int] = {}
        for d in dets:
            count_by_label[d.label] = count_by_label.get(d.label, 0) + 1
        return packet.with_artifact("count", count).with_artifact("count_by_label", count_by_label)
