"""zmq-inference Task 2: wire codec DTO↔dict round-trip (Property 6) + msgpack round-trip.

In-process, nhanh. Chứng minh serialize không mất mát: ring_epoch, CoordinateSpace, confidence float.
"""
import msgpack

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.kernel.inference_protocol import (
    InferenceRequest, InferenceResponse, InferenceError, Detection,
)
from vision_platform.kernel import inference_wire_codec as codec


def _req() -> InferenceRequest:
    return InferenceRequest(
        request_id="req_1", source_id="cam1",
        frame_ref=ShmFrameRefData(
            ring_name="vp_pool_x_r2", slot=3, generation=7,
            height=20, width=30, channels=3, ring_epoch=5,
        ),
    )


def test_request_dict_round_trip():
    req = _req()
    d = codec.request_to_dict(req)
    back = codec.dict_to_request(d)
    assert back == req                      # frozen dataclass eq
    assert back.frame_ref.ring_epoch == 5   # KHÔNG mất epoch


def test_request_msgpack_round_trip():
    req = _req()
    packed = msgpack.packb(codec.request_to_dict(req))
    assert isinstance(packed, (bytes, bytearray))
    back = codec.dict_to_request(msgpack.unpackb(packed, raw=False))
    assert back == req


def test_response_success_round_trip():
    resp = InferenceResponse(
        request_id="req_2",
        detections=(
            Detection(label="object", confidence=0.5,
                      box=BBox(x=1.0, y=2.0, w=3.0, h=4.0, space=CoordinateSpace.MODEL_INPUT)),
        ),
    )
    packed = msgpack.packb(codec.response_to_dict(resp))
    back = codec.dict_to_response(msgpack.unpackb(packed, raw=False))
    assert back.request_id == "req_2"
    assert back.is_success is True
    assert len(back.detections) == 1
    assert back.detections[0].box.space == CoordinateSpace.MODEL_INPUT   # enum giữ nguyên
    assert back.detections[0].confidence == 0.5


def test_response_error_round_trip():
    resp = InferenceResponse(
        request_id="req_3",
        error=InferenceError(error_type="ShmReadFailed", error_message="stale", retryable=True),
    )
    back = codec.dict_to_response(msgpack.unpackb(msgpack.packb(codec.response_to_dict(resp)), raw=False))
    assert back.is_success is False
    assert back.error.retryable is True
    assert back.error.error_type == "ShmReadFailed"


def test_inline_client_satisfies_port():
    """R1.2: InlineInferenceClient (#06) thoả IInferenceClient (structural Protocol)."""
    from vision_platform.kernel.ports.inference_client import IInferenceClient
    from vision_platform.application.inline_inference_client import InlineInferenceClient
    from vision_platform.adapters.fake_detector import FakeDetector
    from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer
    import uuid

    ring = ShmRingBuffer(name=f"tc_{uuid.uuid4().hex[:8]}", n_slots=2, height=8, width=8, channels=3, create=True)
    try:
        client: IInferenceClient = InlineInferenceClient(ring, FakeDetector())
        assert hasattr(client, "infer") and hasattr(client, "setup") and hasattr(client, "teardown")
    finally:
        ring.cleanup_all()
