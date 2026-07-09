"""Sub-spec object-tracking-count — test XÁC ĐỊNH, không camera/GPU (dựng Detection tay).

Phủ: domain greedy_associate · IouTracker (giữ id/id mới/retire/unique+active/deterministic) ·
TrackingStage (ghi artifacts · edge thiếu-key/rỗng/mixed-source). Bám design Correctness Property P1–P6.
"""
import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.tracking import greedy_associate
from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.runtime.iou_tracker import IouTracker
from vision_platform.runtime.stages.tracking_stage import TrackingStage

OF = CoordinateSpace.ORIGINAL_FRAME


def _box(x, y, w=10.0, h=10.0):
    return BBox(x=x, y=y, w=w, h=h, space=OF)


def _det(x, y, label="object", w=10.0, h=10.0):
    return Detection(label=label, confidence=0.9, box=_box(x, y, w, h))


def _packet(dets, source_id="cam0", pid="p"):
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4, 3), dtype=np.uint8))
    return MediaPacket(
        packet_id=pid, source_id=source_id, media_ref=ref, capture_time_ns=0,
    ).with_artifact("detections", tuple(dets))


# ================= domain: greedy_associate =================

def test_associate_matches_overlapping():
    m = greedy_associate([_box(0, 0)], [_box(1, 1), _box(100, 100)], 0.3)
    assert m == [(0, 0)]  # new0 khớp prev0; new1 (xa) không khớp


def test_associate_respects_threshold():
    # iou((0,0,10,10),(1,1,10,10)) ≈ 0.68 < 0.9 → không khớp.
    assert greedy_associate([_box(0, 0)], [_box(1, 1)], 0.9) == []


def test_associate_respects_label():
    m = greedy_associate(
        [_box(0, 0)], [_box(0, 0)], 0.3,
        prev_labels=["car"], new_labels=["person"],
    )
    assert m == []  # box trùng nhưng khác label → không phải cùng vật


def test_associate_one_to_one():
    # prev 1 box; new 2 box đều overlap → chỉ 1 cặp (prev dùng 1 lần), chọn iou cao nhất (trùng khít).
    m = greedy_associate([_box(0, 0)], [_box(0, 0), _box(1, 1)], 0.3)
    assert m == [(0, 0)]


# ================= IouTracker =================

def test_keep_id_when_object_continuous():  # P1
    t = IouTracker(iou_threshold=0.3, max_age=30)
    ids = []
    for x in range(5):  # box dịch 1px/frame → IoU cao
        tracks = t.update([_det(x, x)])
        assert len(tracks) == 1
        ids.append(tracks[0].track_id)
    assert len(set(ids)) == 1          # cùng 1 track_id suốt
    assert t.unique_count == 1
    assert t.active_count == 1
    assert tracks[-1].hits == 5


def test_new_id_when_far_or_diff_label():  # P2
    t = IouTracker(iou_threshold=0.3, max_age=30)
    a = t.update([_det(0, 0)])[0].track_id
    b = t.update([_det(100, 100)])[0].track_id   # IoU=0 → vật mới
    assert a != b
    assert t.unique_count == 2
    # label khác trên cùng vị trí → vật mới
    t2 = IouTracker()
    id_car = t2.update([_det(0, 0, "car")])[0].track_id
    id_person = t2.update([_det(0, 0, "person")])[0].track_id
    assert id_car != id_person and t2.unique_count == 2


def test_retire_after_max_age_no_id_reuse():  # P3
    t = IouTracker(iou_threshold=0.3, max_age=2)
    first = t.update([_det(0, 0)])[0].track_id
    for _ in range(3):        # 3 frame rỗng → age 1,2,3 → 3>2 retire
        t.update([])
    assert t.active_count == 0
    again = t.update([_det(0, 0)])[0].track_id
    assert again != first     # id KHÔNG tái dùng
    assert t.unique_count == 2


def test_empty_detections_valid():  # P5 (rỗng)
    t = IouTracker()
    t.update([_det(0, 0)])
    out = t.update([])        # không detection → hợp lệ, output rỗng
    assert out == ()
    assert t.active_count == 1  # track vẫn sống (age 1 <= max_age)


def test_deterministic_same_sequence():  # P4
    def run():
        t = IouTracker(iou_threshold=0.3, max_age=5)
        seq = []
        for frame in ([_det(0, 0)], [_det(1, 1), _det(100, 100)], [_det(2, 2)]):
            seq.append(tuple(tr.track_id for tr in t.update(frame)))
        return seq
    assert run() == run()     # cùng input → cùng chuỗi track_id


def test_match_existing_independent_of_order():  # P4 (tie-break/order)
    t = IouTracker(iou_threshold=0.3, max_age=30)
    t.update([_det(0, 0)])                     # tạo id0 tại (0,0)
    # frame có [khớp-id0, vật-mới-xa] và đảo thứ tự → id gán cho từng box giống nhau
    fwd = {(tr.box.x, tr.box.y): tr.track_id for tr in t.update([_det(1, 1), _det(100, 100)])}
    t2 = IouTracker(iou_threshold=0.3, max_age=30)
    t2.update([_det(0, 0)])
    rev = {(tr.box.x, tr.box.y): tr.track_id for tr in t2.update([_det(100, 100), _det(1, 1)])}
    assert fwd[(1.0, 1.0)] == rev[(1.0, 1.0)] == 0   # box gần luôn khớp id0 bất kể vị trí trong list


# ================= TrackingStage =================

def test_stage_writes_artifacts():
    stage = TrackingStage(IouTracker(iou_threshold=0.3, max_age=30))
    r = stage.process(_packet([_det(0, 0), _det(100, 100)]))
    assert r.status == StageStatus.SUCCESS
    assert len(r.packet.artifacts["tracks"]) == 2
    assert r.packet.artifacts["unique_count"] == 2
    assert r.packet.artifacts["active_count"] == 2


def test_stage_missing_detections_key_errors():  # P5 (thiếu key)
    stage = TrackingStage(IouTracker())
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4, 3), dtype=np.uint8))
    pkt = MediaPacket(packet_id="p", source_id="cam0", media_ref=ref, capture_time_ns=0)  # KHÔNG có detections
    r = stage.process(pkt)
    assert r.status == StageStatus.ERROR
    assert r.error_type == "ValueError"


def test_stage_mixed_source_errors():  # P5 (camera-affinity K-042)
    stage = TrackingStage(IouTracker())
    assert stage.process(_packet([_det(0, 0)], source_id="cam0")).status == StageStatus.SUCCESS
    r = stage.process(_packet([_det(0, 0)], source_id="cam9"))   # source lạ → fail-fast
    assert r.status == StageStatus.ERROR
    assert r.error_type == "ValueError"


def test_stage_teardown_resets_tracker():
    tracker = IouTracker()
    stage = TrackingStage(tracker)
    stage.process(_packet([_det(0, 0)]))
    assert tracker.active_count == 1
    stage.teardown()
    assert tracker.active_count == 0 and tracker.unique_count == 0


# ================= wiring vào vision_slice_app (--track) =================

def test_slice_app_track_wiring(capsys):
    """--track chạy end-to-end: FakeDetector trả box CỐ ĐỊNH mỗi frame → 1 track distinct.

    `unique_tracks` đọc từ ARTIFACTS pipeline (không phải tracker sau teardown) → phải = 1 dù nhiều frame.
    """
    from vision_platform.profiles.vision_slice_app import main
    rc = main(["--source", "fake", "--frames", "5", "--track"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "unique_tracks: 1" in err   # 1 vật (box cố định) qua 5 frame → đếm-không-trùng = 1
    assert "active_tracks: 1" in err
