"""Step 02 tests: domain BBox + kernel ReadResult + MediaPacket immutability."""
import pickle
import numpy as np
import pytest
from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.read_result import ReadResult, ReadStatus
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef


# ============ BBox ============

def test_bbox_basic():
    b = BBox(10, 20, 100, 50, CoordinateSpace.ORIGINAL_FRAME)
    assert b.x == 10
    assert b.x2 == 110
    assert b.y2 == 70
    assert b.area == 5000


def test_bbox_negative_size_rejected():
    with pytest.raises(ValueError):
        BBox(0, 0, -10, 50, CoordinateSpace.ORIGINAL_FRAME)


def test_bbox_immutable():
    b = BBox(10, 20, 100, 50, CoordinateSpace.ORIGINAL_FRAME)
    with pytest.raises(Exception):  # FrozenInstanceError
        b.x = 999


def test_bbox_normalized_out_of_range_rejected():
    """ERRATA E-12 (Risk 3): NORMALIZED yêu cầu tọa độ trong [0,1]."""
    with pytest.raises(ValueError):
        BBox(100.0, 0.0, 0.5, 0.5, CoordinateSpace.NORMALIZED)
    # hợp lệ thì không raise:
    BBox(0.1, 0.2, 0.5, 0.5, CoordinateSpace.NORMALIZED)


def test_bbox_space_is_required():
    """Coordinate space MUST be explicit — không có default."""
    with pytest.raises(TypeError):
        BBox(10, 20, 100, 50)  # missing `space`


# ============ ReadResult ============

def test_readresult_frame_has_data():
    arr = np.zeros((10, 10), dtype=np.uint8)
    r = ReadResult(status=ReadStatus.FRAME, data=arr)
    assert r.has_data
    assert r.data is arr


def test_readresult_eof_no_data():
    r = ReadResult(status=ReadStatus.EOF)
    assert not r.has_data
    assert r.data is None


def test_readresult_immutable():
    r = ReadResult(status=ReadStatus.TIMEOUT)
    with pytest.raises(Exception):
        r.status = ReadStatus.FRAME


# ============ InMemoryArrayRef ============

def test_array_ref_locks_array_readonly():
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef(arr)
    with pytest.raises(ValueError):
        ref.array[0, 0, 0] = 99


def test_array_ref_default_takes_ownership():
    """Default constructor: caller's array also becomes read-only."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef(arr)
    with pytest.raises(ValueError):
        arr[0, 0, 0] = 99


def test_array_ref_from_copy_isolates():
    """from_copy: caller can keep mutating their array."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef.from_copy(arr)
    arr[0, 0, 0] = 99
    assert ref.array[0, 0, 0] == 0


def test_array_ref_rejects_non_ndarray():
    """Type safety (C): non-ndarray → TypeError rõ nghĩa, không phải AttributeError."""
    with pytest.raises(TypeError):
        InMemoryArrayRef([1, 2, 3])


def test_array_ref_stays_readonly_after_pickle():
    """ERRATA E-11: pickle round-trip phải GIỮ read-only (numpy reset writeable=True;
    __post_init__ không chạy lại → __setstate__ re-lock)."""
    ref = InMemoryArrayRef(np.zeros((4, 4, 3), dtype=np.uint8))
    ref2 = pickle.loads(pickle.dumps(ref))
    assert not ref2.array.flags.writeable
    with pytest.raises(ValueError):
        ref2.array[0, 0, 0] = 99


# ============ MediaPacket ============

def _make_packet(meta=None, arts=None):
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    return MediaPacket(
        packet_id="p1",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=12345,
        metadata=meta or {},
        artifacts=arts or {},
    )


def test_packet_metadata_blocked():
    p = _make_packet(meta={"key": "val"})
    with pytest.raises((TypeError, AttributeError)):
        p.metadata["new"] = "x"


def test_packet_artifacts_blocked():
    p = _make_packet(arts={"key": "val"})
    with pytest.raises((TypeError, AttributeError)):
        p.artifacts["new"] = "x"


def test_packet_with_artifact_returns_new_packet():
    p1 = _make_packet()
    p2 = p1.with_artifact("detections", [1, 2, 3])
    assert p1 is not p2
    assert "detections" not in p1.artifacts
    assert p2.artifacts["detections"] == [1, 2, 3]


def test_packet_caller_dict_mutation_does_not_leak():
    """Mutate caller's source dict AFTER construction — packet unchanged."""
    meta = {"k": "original"}
    p = _make_packet(meta=meta)
    meta["k"] = "modified"
    meta["new"] = "added"
    assert p.metadata["k"] == "original"
    assert "new" not in p.metadata


def test_packet_with_metadata_chain():
    """Multiple CoW operations chain correctly."""
    p1 = _make_packet()
    p2 = p1.with_metadata("a", 1).with_metadata("b", 2)
    assert p1.metadata == {}
    assert p2.metadata["a"] == 1
    assert p2.metadata["b"] == 2


def test_packet_without_artifact():
    p1 = _make_packet(arts={"x": 1, "y": 2})
    p2 = p1.without_artifact("x")
    assert "x" in p1.artifacts   # unchanged
    assert "x" not in p2.artifacts
    assert p2.artifacts["y"] == 2


def test_packet_pickle_roundtrip_preserves_immutability():
    """ERRATA E-16: MappingProxyType không pickle được → MediaPacket phải có
    __getstate__/__setstate__. Sau unpickle: giá trị giữ nguyên + vẫn bất biến + array read-only."""
    p = _make_packet(meta={"cam": "front"}, arts={"score": 0.9})
    p2 = pickle.loads(pickle.dumps(p))
    # giá trị giữ nguyên
    assert p2.packet_id == "p1"
    assert p2.metadata["cam"] == "front"
    assert p2.artifacts["score"] == 0.9
    # vẫn bất biến (metadata/artifacts vẫn MappingProxyType → chặn ghi)
    with pytest.raises((TypeError, AttributeError)):
        p2.metadata["x"] = 1
    with pytest.raises((TypeError, AttributeError)):
        p2.artifacts["y"] = 2
    # array vẫn read-only (media_ref.__setstate__ re-lock)
    assert not p2.media_ref.array.flags.writeable
