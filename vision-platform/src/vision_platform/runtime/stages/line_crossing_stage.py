"""LineCrossingStage — đếm vật QUA VẠCH theo hướng (sub-spec line-crossing-count).

Layer: runtime/stages. Đọc artifacts["tracks"] (do TrackingStage ghi) → so tâm-track frame-trước ↔ frame-này
với đoạn vạch [A,B] → nếu cắt: +1 lượt theo hướng. Ghi artifacts crossings_in/out/total (cộng dồn).

STATEFUL (nhớ center_prev/track_id). Camera-affinity (K-042): 1 instance/1 camera/1 vạch — source lạ → fail-fast.
Bounded memory (R3.4): chỉ giữ center_prev cho track CÓ MẶT frame này (prune id vắng) → RAM ~ track sống.
"""
from typing import Optional

from vision_platform.domain.bbox import CoordinateSpace
from vision_platform.domain.geometry import orient, segments_intersect
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.runtime.base_stage import BaseStage


class LineCrossingStage(BaseStage):
    def __init__(
        self,
        ax: float, ay: float, bx: float, by: float,
        *,
        space: CoordinateSpace = CoordinateSpace.ORIGINAL_FRAME,
    ):
        super().__init__("line_crossing")
        self._a = (float(ax), float(ay))
        self._b = (float(bx), float(by))
        self._space = space
        self._last_center: dict[int, tuple[float, float]] = {}
        self._in = 0
        self._out = 0
        self._source_id: Optional[str] = None

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        tracks = packet.artifacts.get("tracks")
        if tracks is None:
            raise ValueError(
                "LineCrossingStage cần artifacts['tracks'] — chạy TrackingStage trước (sai thứ tự pipeline)"
            )
        # Camera-affinity (K-042): 1 instance/1 camera.
        if self._source_id is None:
            self._source_id = packet.source_id
        elif packet.source_id != self._source_id:
            raise ValueError(
                f"LineCrossingStage nhận 2 source_id ('{self._source_id}' rồi '{packet.source_id}') — "
                "1 instance/1 camera (K-042)"
            )

        ax, ay = self._a
        bx, by = self._b
        seen: set[int] = set()
        for tr in tracks:
            if tr.box.space != self._space:
                raise ValueError(
                    f"LineCrossingStage: track box space {tr.box.space} khác space vạch {self._space} "
                    "(so vị trí khác không-gian là vô nghĩa — invariant Step 02)"
                )
            cx = tr.box.x + tr.box.w / 2.0
            cy = tr.box.y + tr.box.h / 2.0
            curr = (cx, cy)
            seen.add(tr.track_id)
            prev = self._last_center.get(tr.track_id)
            if prev is not None and segments_intersect(prev, curr, self._a, self._b):
                # Hướng: dấu phía của tâm HIỆN TẠI so với vạch A→B (quy ước theo thứ tự A,B — R2.1/2.3).
                if orient(ax, ay, bx, by, cx, cy) > 0:
                    self._in += 1
                else:
                    self._out += 1
            self._last_center[tr.track_id] = curr

        # Prune (R3.4 bounded memory): bỏ center_prev của track KHÔNG có mặt frame này.
        for tid in [t for t in self._last_center if t not in seen]:
            del self._last_center[tid]

        return (
            packet
            .with_artifact("crossings_in", self._in)
            .with_artifact("crossings_out", self._out)
            .with_artifact("crossings_total", self._in + self._out)
        )

    def teardown(self) -> None:
        self._last_center.clear()
        self._in = 0
        self._out = 0
