"""Test port IMediaRef (sub-spec media-ref-port).

Chứng minh abstraction THẬT (không chỉ type-hint):
- P1 conformance: InMemoryArrayRef thoả IMediaRef mà KHÔNG sửa nó (structural typing).
- P2 substitutability (Liskov): 1 impl IMediaRef KHÁC cắm vào MediaPacket → BrightnessStage chạy đúng.
- P3/P4 invariance + read-only: pickle round-trip giữ read-only + vẫn là IMediaRef.
"""
import pickle
from dataclasses import dataclass

import numpy as np

from vision_platform.kernel.media_ref import IMediaRef
from vision_platform.kernel.media_packet import InMemoryArrayRef, MediaPacket
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.runtime.stages.brightness_stage import BrightnessStage


def _make_packet(media_ref: IMediaRef) -> MediaPacket:
    return MediaPacket(
        packet_id="pkt_test",
        source_id="src_test",
        media_ref=media_ref,
        capture_time_ns=123,
    )


# ---- P1: conformance (InMemoryArrayRef thoả IMediaRef, không sửa nó) ----
def test_in_memory_array_ref_satisfies_imediaref():
    ref = InMemoryArrayRef.from_copy(np.zeros((4, 4), dtype=np.uint8))
    assert isinstance(ref, IMediaRef)  # runtime_checkable: có thuộc tính `array`
    # dùng ở vị trí IMediaRef không lỗi (materialize được ndarray)
    arr = ref.array
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (4, 4)


# ---- P2: substitutability — impl KHÁC InMemoryArrayRef vẫn chạy Stage ----
@dataclass(frozen=True)
class _FakeMediaRef:
    """Impl IMediaRef độc lập: giữ ndarray theo cách khác InMemoryArrayRef.

    Materialize `.array` bằng cách reconstruct từ bytes + shape/dtype (mô phỏng 1 backend
    khác, vd đọc từ SHM). Chứng minh port đủ rộng cho impl không-phải-InMemoryArrayRef.
    """
    _raw: bytes
    _shape: tuple
    _dtype: str

    @classmethod
    def of(cls, arr: np.ndarray) -> "_FakeMediaRef":
        return cls(_raw=arr.tobytes(), _shape=arr.shape, _dtype=str(arr.dtype))

    @property
    def array(self) -> np.ndarray:
        out = np.frombuffer(self._raw, dtype=self._dtype).reshape(self._shape)
        out.setflags(write=False)  # read-only by contract
        return out


def test_fake_media_ref_is_imediaref():
    fake = _FakeMediaRef.of(np.ones((3, 3), dtype=np.float32))
    assert isinstance(fake, IMediaRef)


def test_stage_runs_on_alternate_media_ref_impl():
    frame = np.full((8, 8), 50, dtype=np.uint8)
    fake = _FakeMediaRef.of(frame)
    packet = _make_packet(fake)

    stage = BrightnessStage()
    result = stage.process(packet)

    assert result.status == StageStatus.SUCCESS
    # brightness phải khớp mean của frame gốc → Stage đọc .array đúng qua port
    assert result.packet.artifacts["brightness"] == float(frame.mean()) == 50.0


def test_stage_gives_same_result_for_both_impls():
    frame = np.arange(16, dtype=np.uint8).reshape(4, 4)
    r_inmem = BrightnessStage().process(_make_packet(InMemoryArrayRef.from_copy(frame)))
    r_fake = BrightnessStage().process(_make_packet(_FakeMediaRef.of(frame)))
    assert r_inmem.status == r_fake.status == StageStatus.SUCCESS
    assert r_inmem.packet.artifacts["brightness"] == r_fake.packet.artifacts["brightness"]


# ---- P3/P4: invariance + read-only qua pickle (không hồi quy) ----
def test_pickle_roundtrip_keeps_readonly_and_imediaref():
    frame = np.arange(9, dtype=np.uint8).reshape(3, 3)
    packet = _make_packet(InMemoryArrayRef.from_copy(frame))

    restored = pickle.loads(pickle.dumps(packet))

    assert isinstance(restored.media_ref, IMediaRef)
    assert restored.media_ref.array.flags.writeable is False  # re-lock qua __setstate__
    assert np.array_equal(restored.media_ref.array, frame)
