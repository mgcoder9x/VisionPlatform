"""IouTracker — impl `ITracker` bằng IoU-greedy association (sub-spec object-tracking-count).

Layer: runtime — GIỮ STATE (`_tracks`, `_next_id`). Dùng `domain.greedy_associate` (thuần) + `Track`@kernel.
Thuần Python (không numpy nặng/không GPU) → xác định, test được không cần camera/model.

Camera-affinity (K-042): 1 instance/1 camera (guard ở `TrackingStage`, không ở đây — tracker chỉ lo thuật toán).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vision_platform.domain.bbox import BBox
from vision_platform.domain.tracking import greedy_associate
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.tracking_protocol import Track


@dataclass
class _TrackState:
    """State nội bộ 1 track (MUTABLE — cập nhật tại chỗ). Không lộ ra ngoài (kết quả trả qua Track frozen)."""
    label: str
    box: BBox
    age: int
    hits: int


class IouTracker:
    """Theo dõi vật bằng IoU-greedy. Thoả `ITracker` (Protocol — không cần kế thừa)."""

    def __init__(self, *, iou_threshold: float = 0.3, max_age: int = 30) -> None:
        if not (0.0 <= iou_threshold <= 1.0):
            raise ValueError(f"iou_threshold phải trong [0,1], got {iou_threshold}")
        if max_age < 0:
            raise ValueError(f"max_age phải >= 0, got {max_age}")
        self._iou_threshold = iou_threshold
        self._max_age = max_age
        self._tracks: dict[int, _TrackState] = {}
        self._next_id: int = 0

    def update(self, detections: Sequence[Detection]) -> tuple[Track, ...]:
        # 1) Mọi track hiện có già đi 1 frame (giả định chưa khớp; khớp sẽ reset age=0).
        for st in self._tracks.values():
            st.age += 1

        # 2) Association index-based (prev = track hiện có theo thứ tự ổn định; new = detections).
        prev_ids = list(self._tracks.keys())
        prev_boxes = [self._tracks[tid].box for tid in prev_ids]
        prev_labels = [self._tracks[tid].label for tid in prev_ids]
        new_boxes = [d.box for d in detections]
        new_labels = [d.label for d in detections]

        matches = greedy_associate(
            prev_boxes, new_boxes, self._iou_threshold,
            prev_labels=prev_labels, new_labels=new_labels,
        )
        new_to_tid: dict[int, int] = {}

        # 3) Cặp khớp → cập nhật track cũ (box mới, age=0, hits+1).
        for new_i, prev_i in matches:
            tid = prev_ids[prev_i]
            det = detections[new_i]
            st = self._tracks[tid]
            st.box = det.box
            st.label = det.label
            st.age = 0
            st.hits += 1
            new_to_tid[new_i] = tid

        # 4) Detection chưa khớp → track MỚI (id đơn điệu, không tái dùng).
        for new_i in range(len(detections)):
            if new_i in new_to_tid:
                continue
            det = detections[new_i]
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = _TrackState(label=det.label, box=det.box, age=0, hits=1)
            new_to_tid[new_i] = tid

        # 5) Retire track quá già (age > max_age) — sau khi khớp (track khớp có age=0).
        for tid in [t for t, st in self._tracks.items() if st.age > self._max_age]:
            del self._tracks[tid]

        # 6) Output: 1 Track / detection frame này, theo thứ tự detection.
        out: list[Track] = []
        for new_i in range(len(detections)):
            tid = new_to_tid[new_i]
            st = self._tracks[tid]
            out.append(Track(track_id=tid, label=st.label, box=st.box, age=st.age, hits=st.hits))
        return tuple(out)

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 0

    @property
    def unique_count(self) -> int:
        return self._next_id

    @property
    def active_count(self) -> int:
        return len(self._tracks)
