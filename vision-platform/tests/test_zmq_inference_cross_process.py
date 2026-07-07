"""zmq-inference Task 6: test cross-process THẬT (spawn) — Property 1/3/4/5.

Parent = client + orchestrator (tạo RingPool/control-plane, ghi frame, ZmqInferenceClient).
Child (spawn) = InferenceServer đọc SHM (lock thừa kế) + detect + trả response.
Guard win32 (nền hiện tại — như #05b/#09); POSIX chưa verify.
"""
from __future__ import annotations

import contextlib
import dataclasses
import multiprocessing as mp
import socket
import sys
import time
import uuid

import numpy as np
import pytest
import zmq

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool
from vision_platform.runtime.ipc.shm_frame_ring import ShmFrameWriter
from vision_platform.kernel.inference_protocol import InferenceRequest
from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient
from tests.zmq_server_worker import inference_server_worker

_N, _H, _W, _C = 4, 8, 8, 3

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="verify Windows (nền hiện tại); POSIX chưa verify")


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _frame(v: int) -> np.ndarray:
    return np.full((_H, _W, _C), v, dtype=np.uint8)


@contextlib.contextmanager
def _harness(detector_kind: str = "fake", *, client_timeout: float = 10.0, start_server: bool = True):
    pool = RingPool(_N, _H, _W, _C, pool_size=3)
    cp = RingControlPlane(name=f"cp_{uuid.uuid4().hex[:8]}", create=True)
    name1 = pool.activate(1)
    cp.publish(1, name1)
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    ev = mp.Event()
    p = mp.Process(
        target=inference_server_worker,
        args=(ev, endpoint, cp.name, pool.slot_locks_map(), _N, _H, _W, _C, detector_kind),
        daemon=True,
    )
    if start_server:
        p.start()
    client = ZmqInferenceClient(endpoint, timeout_s=client_timeout)
    client.setup()
    try:
        yield pool, cp, client, p, ev
    finally:
        with contextlib.suppress(Exception):
            client.teardown()
        ev.set()
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()
            p.join(timeout=2)
        with contextlib.suppress(Exception):
            pool.close_all()
        with contextlib.suppress(Exception):
            cp.close()
        with contextlib.suppress(Exception):
            cp.unlink()


def test_zmq_end_to_end_and_correlation():
    """Property 1: 3 request khác id → mỗi response echo đúng request_id + detect thành công."""
    with _harness() as (pool, cp, client, p, ev):
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        refs = [writer.write(_frame(100 + i)) for i in range(3)]
        assert all(r is not None for r in refs)
        for i, ref in enumerate(refs):
            resp = client.infer(InferenceRequest(f"req_{i}", "cam1", ref))
            assert resp.request_id == f"req_{i}"          # correlation
            assert resp.is_success is True
            assert len(resp.detections) == 1


def test_zmq_stale_epoch_returns_retryable_error():
    """Property 3: ref epoch cũ → server read None → InferenceError(retryable=True), không torn."""
    with _harness() as (pool, cp, client, p, ev):
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        ref = writer.write(_frame(120))
        assert ref is not None
        stale = dataclasses.replace(ref, ring_epoch=ref.ring_epoch - 1)   # epoch 0 < hiện tại 1
        resp = client.infer(InferenceRequest("req_stale", "cam1", stale))
        assert resp.is_success is False
        assert resp.error.error_type == "ShmReadFailed"
        assert resp.error.retryable is True


def test_zmq_bulkhead_detector_crash_does_not_kill_server():
    """Property 4: detector ném → client nhận error(retryable=False); server VẪN sống (request kế vẫn có response)."""
    with _harness(detector_kind="crash") as (pool, cp, client, p, ev):
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        ref1 = writer.write(_frame(100))
        ref2 = writer.write(_frame(110))
        r1 = client.infer(InferenceRequest("c1", "cam1", ref1))
        r2 = client.infer(InferenceRequest("c2", "cam1", ref2))
        assert r1.is_success is False and r1.error.retryable is False   # detector lỗi = permanent
        assert r1.error.error_type == "ValueError"
        assert r2.request_id == "c2"                                    # server còn sống → có response thứ 2
        assert r2.is_success is False and r2.error.retryable is False


def test_zmq_server_dead_client_does_not_hang():
    """Property 5: server chết → client.infer TIMEOUT → InferenceError(retryable=True), KHÔNG hang."""
    with _harness(client_timeout=1.5) as (pool, cp, client, p, ev):
        p.terminate()               # giết server
        p.join(timeout=3)
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        ref = writer.write(_frame(100))
        resp = client.infer(InferenceRequest("req_dead", "cam1", ref))
        assert resp.is_success is False
        assert resp.error.retryable is True     # timeout = transient


def test_zmq_server_survives_malformed_request():
    """K-024 (audit doubt-driven): request RÁC (không phải msgpack / sai số frame) → server KHÔNG chết;
    request hợp lệ kế vẫn được phục vụ (bulkhead per-request cho lỗi transport/deserialize)."""
    with _harness() as (pool, cp, client, p, ev):
        # Gửi rác qua 1 DEALER THÔ (không qua ZmqInferenceClient) tới cùng endpoint.
        rc = zmq.Context()
        rs = rc.socket(zmq.DEALER)
        rs.setsockopt(zmq.LINGER, 0)
        rs.connect(client._endpoint)
        rs.send(b"garbage-not-msgpack")            # payload rác → _handle unpackb raise
        rs.send_multipart([b"a", b"b", b"c"])      # sai số frame → ROUTER thấy 4 frame != 2
        time.sleep(0.3)                            # cho server xử lý (và phải KHÔNG chết)
        rs.close(0)
        rc.term()

        # Server phải còn sống → request HỢP LỆ vẫn OK.
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        ref = writer.write(_frame(100))
        assert ref is not None
        resp = client.infer(InferenceRequest("after_garbage", "cam1", ref))
        assert resp.request_id == "after_garbage"
        assert resp.is_success is True             # server sống sót rác → phục vụ tiếp
        assert len(resp.detections) == 1
