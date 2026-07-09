"""Sub-spec line-crossing-count — test XÁC ĐỊNH, không camera/GPU (dựng Track tay).

Vạch dọc x=50 (A=(50,0),B=(50,100)): orient = -100*(cx-50) → trái(cx<50)=+ ("in"), phải(cx>50)=- ("out").
Phủ: domain geometry (orient/segments_intersect) · LineCrossingStage (qua/không, hướng, edge, prune).
"""
import numpy as np

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.domain.geometry import orient, segments_intersect
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.kernel.tracking_protocol import Track
from vision_platform.runtime.stages.line_crossing_stage import LineCrossingStage

OF = CoordinateSpace.ORIGINAL_FRAME


def _track(tid, cx, cy, space=OF, label="object"):
    # box tâm tại (cx,cy): x=cx-5,y=cy-5,w=h=10.
    return Track(track_id=tid, label=label, box=BBox(cx - 5, cy - 5, 10, 10, space), age=0, hits=1)


def _packet(tracks, source_id="cam0"):
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4, 3), dtype=np.uint8))
    return MediaPacket(packet_id="p", source_id=source_id, media_ref=ref, capture_time_ns=0)\
        .with_artifact("tracks", tuple(tracks))


# ================= domain: geometry =================

def test_orient_sign():
    assert orient(0, 0, 10, 0, 5, 5) > 0     # điểm phía trên đường ngang
    assert orient(0, 0, 10, 0, 5, -5) < 0


def test_segments_intersect_true():
    assert segments_intersect((0, 0), (10, 0), (5, -5), (5, 5)) is True


def test_segments_intersect_false_cases():
    assert segments_intersect((0, 0), (10, 0), (0, 5), (10, 5)) is False   # song song
    assert segments_intersect((0, 0), (10, 0), (20, -5), (20, 5)) is False  # rời (x=20 ngoài đoạn)
    assert segments_intersect((0, 0), (10, 0), (20, 0), (30, 0)) is False   # collinear → không cắt
    assert segments_intersect((5, 5), (5, 5), (50, 0), (50, 100)) is False  # đoạn suy biến (điểm)


# ================= LineCrossingStage =================

def _stage(a=(50, 0), b=(50, 100)):
    return LineCrossingStage(a[0], a[1], b[0], b[1])


def test_cross_counts_once_left_to_right():  # P1
    st = _stage()
    st.process(_packet([_track(1, 40, 50)]))          # frame1: chưa có prev
    r = st.process(_packet([_track(1, 60, 50)]))       # frame2: 40→60 cắt vạch
    assert r.status == StageStatus.SUCCESS
    assert r.packet.artifacts["crossings_total"] == 1
    assert r.packet.artifacts["crossings_out"] == 1    # sang phải = out (A=(50,0),B=(50,100))
    assert r.packet.artifacts["crossings_in"] == 0


def test_direction_right_to_left_is_in():  # P3
    st = _stage()
    st.process(_packet([_track(1, 60, 50)]))
    r = st.process(_packet([_track(1, 40, 50)]))       # 60→40 sang trái = in
    assert r.packet.artifacts["crossings_in"] == 1 and r.packet.artifacts["crossings_out"] == 0


def test_reversed_line_flips_direction():  # P3 (đảo A,B)
    st = _stage(a=(50, 100), b=(50, 0))                # đảo thứ tự → đảo in/out
    st.process(_packet([_track(1, 40, 50)]))
    r = st.process(_packet([_track(1, 60, 50)]))       # 40→60: với vạch đảo → in
    assert r.packet.artifacts["crossings_in"] == 1 and r.packet.artifacts["crossings_out"] == 0


def test_no_cross_same_side_or_stationary():  # P2
    st = _stage()
    st.process(_packet([_track(1, 40, 50)]))
    r = st.process(_packet([_track(1, 45, 50)]))       # 40→45 cùng phía trái
    assert r.packet.artifacts["crossings_total"] == 0
    r2 = st.process(_packet([_track(1, 45, 50)]))      # đứng yên
    assert r2.packet.artifacts["crossings_total"] == 0


def test_missing_tracks_key_errors():  # P4
    st = _stage()
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4, 3), dtype=np.uint8))
    pkt = MediaPacket(packet_id="p", source_id="cam0", media_ref=ref, capture_time_ns=0)  # KHÔNG có tracks
    r = st.process(pkt)
    assert r.status == StageStatus.ERROR and r.error_type == "ValueError"


def test_empty_tracks_valid():  # P4
    st = _stage()
    r = st.process(_packet([]))
    assert r.status == StageStatus.SUCCESS and r.packet.artifacts["crossings_total"] == 0


def test_mixed_source_errors():  # P4 (camera-affinity)
    st = _stage()
    assert st.process(_packet([_track(1, 40, 50)], source_id="cam0")).status == StageStatus.SUCCESS
    r = st.process(_packet([_track(1, 60, 50)], source_id="cam9"))
    assert r.status == StageStatus.ERROR and r.error_type == "ValueError"


def test_wrong_space_errors():  # P4 (space)
    st = _stage()
    r = st.process(_packet([_track(1, 40, 50, space=CoordinateSpace.MODEL_INPUT)]))
    assert r.status == StageStatus.ERROR and r.error_type == "ValueError"


def test_prune_absent_track_bounded_memory():  # P5
    st = _stage()
    st.process(_packet([_track(1, 40, 50)]))
    assert 1 in st._last_center
    st.process(_packet([]))               # id1 vắng → prune
    assert st._last_center == {}
    # quay lại sau prune → coi như mốc mới, KHÔNG nối đoạn cũ (không đếm bừa)
    r = st.process(_packet([_track(1, 60, 50)]))
    assert r.packet.artifacts["crossings_total"] == 0 and 1 in st._last_center


# ================= wiring vào vision_slice_app (--line) =================

def test_slice_app_line_wiring(capsys):
    """--line (cần --track) chạy end-to-end: FakeDetector box CỐ ĐỊNH → track đứng yên → 0 lượt qua.

    Smoke test xác nhận LineCrossingStage được wire + summary in ra (logic đếm đã test riêng ở trên).
    """
    from vision_platform.profiles.vision_slice_app import main
    rc = main(["--source", "fake", "--frames", "5", "--track", "--line", "50,0,50,100"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "crossings_tot: 0" in err   # box cố định → không có chuyển động qua vạch


def test_slice_app_line_requires_track():
    """--line thiếu --track → lỗi cấu hình (fail-fast), KHÔNG chạy mù."""
    import pytest
    from vision_platform.profiles.vision_slice_app import main
    with pytest.raises(SystemExit):   # argparse parser.error → SystemExit
        main(["--source", "fake", "--frames", "3", "--line", "50,0,50,100"])
