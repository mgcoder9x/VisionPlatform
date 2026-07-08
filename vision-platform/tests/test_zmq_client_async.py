"""Task 2.4/2.5 — đường async submit()/poll_responses()/metrics_snapshot() (XÁC ĐỊNH, không server).

Kiểm tách khỏi timing thật: mô phỏng van đóng (KHÔNG setup → io thread không chạy) + mô phỏng
drain thủ công. Bao P1 (bảo toàn), P3 (recency DROP_OLDEST), P4 (BLOCK non-RTSP không drop).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient
from vision_platform.kernel.backpressure import BackpressurePolicy
from vision_platform.kernel.inference_protocol import InferenceRequest, InferenceResponse
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData


def _req(i: int) -> InferenceRequest:
    return InferenceRequest(
        request_id=str(i),
        source_id="cam0",
        frame_ref=ShmFrameRefData(
            ring_name="r", slot=0, generation=i, height=8, width=8, channels=3, ring_epoch=0,
        ),
    )


# ---- P3: DROP_OLDEST giữ frame mới nhất, frame bỏ KHÔNG gửi (task 2.4) ----

def test_submit_drop_oldest_keeps_newest_when_window_closed():
    client = ZmqInferenceClient(
        "tcp://127.0.0.1:5591", window_size=1, queue_maxsize=1,
        policy=BackpressurePolicy.DROP_OLDEST,
    )
    # KHÔNG setup() → io thread không chạy → van đóng (không gửi frame nào).
    M = 5
    for i in range(M):
        assert client.submit(_req(i)) is True   # DROP_OLDEST luôn nhận
    q = client._async_outbound
    assert q.qsize() == 1
    assert q.drops == M - 1
    remaining = q.get_or_raise()
    assert remaining.request_id == str(M - 1)   # còn lại là MỚI NHẤT (recency)
    assert client._sent == 0                     # frame bị bỏ KHÔNG được gửi → submitted=0


# ---- P4: BLOCK non-RTSP trong sức chứa → không drop (task 2.5) ----

def test_block_policy_no_drops_within_capacity():
    client = ZmqInferenceClient(
        "tcp://127.0.0.1:5592", window_size=4, queue_maxsize=4,
        policy=BackpressurePolicy.BLOCK,
    )
    for i in range(4):
        assert client.submit(_req(i)) is True
    m = client.metrics_snapshot(frames_captured=4)
    assert m.frames_dropped_backpressure == 0


# ---- P1: bảo toàn captured == submitted + dropped (property-based, xác định) ----

@settings(max_examples=100, deadline=None)
@given(m=st.integers(min_value=1, max_value=200), qmax=st.integers(min_value=1, max_value=50))
def test_conservation_capture_submit_drain(m, qmax):
    client = ZmqInferenceClient(
        "tcp://127.0.0.1:5593", window_size=qmax, queue_maxsize=qmax,
        policy=BackpressurePolicy.DROP_OLDEST,
    )
    captured = 0
    for i in range(m):
        captured += 1
        client.submit(_req(i))
    # Mô phỏng io thread gửi hết phần CÒN trong van (không server → tự tăng _sent = "đã gửi").
    # Guard qsize()>0 để get_or_raise() luôn có item (timeout=None sẽ chặn vô hạn nếu rỗng).
    q = client._async_outbound
    while q.qsize() > 0:
        q.get_or_raise()
        client._sent += 1
    snap = client.metrics_snapshot(frames_captured=captured)
    assert snap.conserved is True
    assert snap.frames_submitted + snap.frames_dropped_backpressure == captured


# ---- poll_responses drain đúng (task 2.5) ----

def test_poll_responses_drains_all():
    client = ZmqInferenceClient("tcp://127.0.0.1:5594")
    client._responses.put(InferenceResponse(request_id="a"))
    client._responses.put(InferenceResponse(request_id="b"))
    got = client.poll_responses()
    assert [r.request_id for r in got] == ["a", "b"]
    assert client.poll_responses() == []   # đã drain hết
