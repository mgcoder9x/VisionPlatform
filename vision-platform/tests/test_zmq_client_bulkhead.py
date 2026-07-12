"""Z1 (review săn bug, #345): `ZmqInferenceClient` io-thread phải BULKHEAD.

Vấn đề (fault-isolation): io thread client sở hữu socket + làm send/recv. Nếu server (hoặc lỗi transport /
version-skew / process lạ) trả 1 RESPONSE rác (không phải msgpack-dict-có-request_id), `_io_loop` (trước fix)
KHÔNG bọc try/except quanh recv/unpack → exception giết io thread (daemon) → client thành HỐ ĐEN (mọi
infer/submit timeout mãi). Đây là BẤT ĐỐI XỨNG với `InferenceServer` (đã bulkhead per-request K-024).

Test (in-process ROUTER thô, KHÔNG spawn → deterministic, event-driven, không assert theo sleep):
gửi response RÁC cho req1 → assert io thread VẪN sống bằng cách req2 hợp lệ VẪN được gửi + nhận response.
"""
from __future__ import annotations

import socket
import time

import msgpack
import zmq

from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient
from vision_platform.kernel import inference_wire_codec as codec
from vision_platform.kernel.inference_protocol import InferenceRequest, InferenceResponse
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _req(rid: str) -> InferenceRequest:
    ref = ShmFrameRefData(ring_name="r", slot=0, generation=1, height=8, width=8, channels=3, ring_epoch=1)
    return InferenceRequest(request_id=rid, source_id="cam", frame_ref=ref)


def _router_recv_rid(router, timeout_ms: int = 5000):
    """Chờ (event-driven) ROUTER nhận 1 request; trả (identity, request_id) hoặc None nếu quá hạn.

    `zmq.Socket.poll(timeout)` trả EVENT MASK (int), khác `zmq.Poller.poll` (list) — kiểm bằng & POLLIN.
    """
    if not (router.poll(timeout_ms) & zmq.POLLIN):
        return None
    ident, payload = router.recv_multipart()
    return ident, msgpack.unpackb(payload, raw=False)["request_id"]


def _poll_for(client, rid: str, deadline_s: float = 5.0):
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        for r in client.poll_responses():
            if r.request_id == rid:
                return r
        time.sleep(0.01)
    return None


def test_client_io_thread_survives_malformed_response():
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    ctx = zmq.Context()
    router = ctx.socket(zmq.ROUTER)
    router.setsockopt(zmq.LINGER, 0)
    router.bind(endpoint)
    client = ZmqInferenceClient(endpoint, timeout_s=3.0, poll_ms=10)
    client.setup()
    try:
        # 1) req1 → ROUTER trả RÁC (0xc1 = byte msgpack 'never used' → unpackb raise chắc chắn).
        client.submit(_req("r1"))
        got1 = _router_recv_rid(router)
        assert got1 is not None, "ROUTER không nhận được req1"
        ident1, rid1 = got1
        assert rid1 == "r1"
        router.send_multipart([ident1, b"\xc1\xc1 garbage-not-msgpack"])

        # 2) req2 hợp lệ → nếu io thread CÒN SỐNG (sau fix) nó vẫn gửi req2 + xử lý reply.
        #    Trước fix: io thread CHẾT ở response rác → req2 không bao giờ được gửi → _router_recv_rid None.
        client.submit(_req("r2"))
        got2 = _router_recv_rid(router)
        assert got2 is not None, "io thread CHẾT sau response rác → req2 không được gửi (Z1 bug)"
        ident2, rid2 = got2
        assert rid2 == "r2"
        router.send_multipart([ident2, msgpack.packb(codec.response_to_dict(InferenceResponse(request_id="r2")))])

        resp = _poll_for(client, "r2")
        assert resp is not None, "io thread CHẾT → không nhận được response hợp lệ r2 (Z1 bug)"
        assert resp.request_id == "r2"
        assert resp.is_success is True
    finally:
        client.teardown()
        router.close(0)
        ctx.term()
