"""Step 06: Inference protocol + IDetector port + FakeDetector + InlineInferenceClient.

9 test theo Design step-06 (đã đối chiếu code thật — brief implement/06-inference-inline):
- Detector (3): 1 detection · fail-fast khi chưa setup · confidence scale theo brightness.
- DTO (3): is_success · immutable (frozen) · error case.
- Inline client (3): end-to-end · stale-epoch ref → error (F-2) · request_id correlation.

Deviation vs Design (đã valid + duyệt):
- F-1: InlineInferenceClient ở application/ (không phải adapters/) — contract adapters↛runtime.
- F-2: InferenceRequest mang thẳng ShmFrameRefData (gồm ring_epoch); client dùng read_ref.
"""
import dataclasses
import uuid

import numpy as np
import pytest

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.kernel.inference_protocol import (
    InferenceRequest, InferenceResponse, InferenceError, Detection,
)
from vision_platform.adapters.fake_detector import FakeDetector
from vision_platform.application.inline_inference_client import InlineInferenceClient
from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameWriter


@pytest.fixture
def ring():
    """Ring 4 slot, frame 20x20x3 (khớp phong cách test #05)."""
    r = ShmRingBuffer(
        name=f"ti_{uuid.uuid4().hex[:8]}",
        n_slots=4, height=20, width=20, channels=3, create=True,
    )
    yield r
    r.cleanup_all()


def _frame(value: int, h: int = 20, w: int = 20, c: int = 3) -> np.ndarray:
    return np.full((h, w, c), value, dtype=np.uint8)


# ============ Detector (3) ============

def test_fake_detector_returns_one_detection():
    det = FakeDetector()
    det.setup()
    dets = det.detect(_frame(100))
    assert len(dets) == 1
    d = dets[0]
    assert d.label == "object"
    assert d.box.space == CoordinateSpace.MODEL_INPUT
    det.teardown()


def test_fake_detector_requires_setup():
    det = FakeDetector()
    with pytest.raises(RuntimeError):
        det.detect(_frame(100))   # chưa setup → fail-fast


def test_fake_detector_confidence_scales_with_brightness():
    det = FakeDetector()
    det.setup()
    dark = det.detect(_frame(0))[0].confidence
    bright = det.detect(_frame(255))[0].confidence
    assert dark == pytest.approx(0.0)
    assert bright == pytest.approx(1.0)
    assert bright > dark
    det.teardown()


# ============ DTO (3) ============

def test_response_is_success_when_no_error():
    resp = InferenceResponse(request_id="r1")
    assert resp.is_success is True
    assert resp.detections == ()


def test_dtos_are_immutable():
    resp = InferenceResponse(request_id="r1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.request_id = "x"   # frozen → không gán lại được


def test_response_error_case_is_not_success():
    err = InferenceError(error_type="ShmReadFailed", error_message="boom", retryable=False)
    resp = InferenceResponse(request_id="r1", error=err)
    assert resp.is_success is False
    assert resp.error.error_type == "ShmReadFailed"


# ============ Inline client (3) ============

def test_inline_client_end_to_end(ring):
    detector = FakeDetector()
    client = InlineInferenceClient(ring, detector)
    client.setup()

    writer = ShmFrameWriter(ring)
    ref = writer.write(_frame(128))
    assert ref is not None

    req = InferenceRequest(request_id="req_e2e", source_id="cam1", frame_ref=ref)
    resp = client.infer(req)

    assert resp.is_success is True
    assert resp.request_id == "req_e2e"
    assert len(resp.detections) == 1
    assert resp.detections[0].confidence == pytest.approx(128 / 255.0)
    client.teardown()


def test_inline_client_stale_epoch_ref_returns_error(ring):
    """F-2: ref mang ring_epoch cũ (khác epoch ring hiện tại) → read_ref None → error response."""
    detector = FakeDetector()
    client = InlineInferenceClient(ring, detector)
    client.setup()

    writer = ShmFrameWriter(ring)
    ref = writer.write(_frame(50))
    assert ref is not None

    # Giả lập ref stale: epoch cũ hơn ring hiện tại (ring epoch mặc định = 1 → dùng 0).
    stale_ref = dataclasses.replace(ref, ring_epoch=ref.ring_epoch - 1)
    req = InferenceRequest(request_id="req_stale", source_id="cam1", frame_ref=stale_ref)
    resp = client.infer(req)

    assert resp.is_success is False
    assert resp.error.error_type == "ShmReadFailed"
    assert resp.request_id == "req_stale"
    client.teardown()


def test_inline_client_correlates_request_id(ring):
    """Nhiều request → mỗi response.request_id phải khớp request.request_id (correlation)."""
    detector = FakeDetector()
    client = InlineInferenceClient(ring, detector)
    client.setup()

    writer = ShmFrameWriter(ring)
    refs = []
    for i in range(3):
        r = writer.write(_frame(50 + i))
        assert r is not None
        refs.append(r)

    for i, ref in enumerate(refs):
        req = InferenceRequest(request_id=f"req_{i}", source_id="cam1", frame_ref=ref)
        resp = client.infer(req)
        assert resp.request_id == f"req_{i}"   # correlation đảm bảo
        assert resp.is_success is True

    client.teardown()
