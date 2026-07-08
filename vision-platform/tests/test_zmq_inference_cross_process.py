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
from vision_platform.kernel.backpressure import BackpressurePolicy
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
def _harness(detector_kind: str = "fake", *, client_timeout: float = 10.0, start_server: bool = True,
             n_slots: int = _N, client_kwargs: dict | None = None):
    pool = RingPool(n_slots, _H, _W, _C, pool_size=3)
    cp = RingControlPlane(name=f"cp_{uuid.uuid4().hex[:8]}", create=True)
    name1 = pool.activate(1)
    cp.publish(1, name1)
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    ev = mp.Event()
    p = mp.Process(
        target=inference_server_worker,
        args=(ev, endpoint, cp.name, pool.slot_locks_map(), n_slots, _H, _W, _C, detector_kind),
        daemon=True,
    )
    if start_server:
        p.start()
    client = ZmqInferenceClient(endpoint, timeout_s=client_timeout, **(client_kwargs or {}))
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


def test_zmq_backpressure_overload_conserves():
    """Wave 4 (R8.1/8.2/8.4/8.5 · Property 1/5): server CHẬM (detector_kind='slow', ~20 infer/s) + client
    cửa sổ nhỏ (window=1, queue=1, DROP_OLDEST) + submit M frame NHANH → quá tải TẤT YẾU cross-process.

    Assert BẤT BIẾN 2-tầng (C-019/T-020/K-053): mỗi frame captured → ĐÚNG MỘT trong {submitted, client-drop,
    shm-drop} → `submitted + client_dropped + shm_dropped == M`. Đây là kế toán airtight (submit_calls =
    _sent + queue.drops sau drain; M = shm_dropped + submit_calls).

    Chống flaky (design §8.2): assert BẤT BIẾN (luôn đúng bất kể timing) + `dropped_total > 0` (quá tải là
    TẤT YẾU do delay·M ≫ thời-gian-submit + capacity client = window+queue = 2). KHÔNG assert số drop cố định.
    Dùng SHM ring LỚN (n_slots=64 > M) để cô lập backpressure tầng client-window (thứ spec này thêm) — shm_dropped
    kỳ vọng 0 nhưng vẫn kế toán tổng quát để robust.
    """
    M = 50
    shm_dropped = 0
    with _harness(
        "slow",
        client_timeout=10.0,
        n_slots=64,
        client_kwargs={"window_size": 1, "queue_maxsize": 1, "policy": BackpressurePolicy.DROP_OLDEST},
    ) as (pool, cp, client, p, ev):
        writer = ShmFrameWriter(pool.ring_for_epoch(1))
        for i in range(M):
            ref = writer.write(_frame(i % 256))
            if ref is None:                 # SHM ring đầy = backpressure tầng truyền (K-053) — không submit
                shm_dropped += 1
                client.poll_responses()
                continue
            client.submit(InferenceRequest(f"r{i}", "cam1", ref))   # non-blocking; DROP_OLDEST khi van đầy
            client.poll_responses()
        # DRAIN: io thread gửi nốt van + thu kết cục tới khi van rỗng & in_flight==0 (server chậm nhưng sống).
        deadline = time.monotonic() + 12.0
        while (client.outbound_size > 0 or client.in_flight > 0) and time.monotonic() < deadline:
            client.poll_responses()
            time.sleep(0.01)
        client.poll_responses()

        snap = client.metrics_snapshot(M)              # captured = M (tổng frame thử)
        client_dropped = snap.frames_dropped_backpressure
        total_dropped = client_dropped + shm_dropped

        # P1 — bất biến bảo toàn 2-tầng (chính xác, không phải bound):
        assert snap.frames_submitted + total_dropped == M, (
            f"VỠ bất biến: submitted={snap.frames_submitted} + client_drop={client_dropped} "
            f"+ shm_drop={shm_dropped} != M={M}"
        )
        # R8.2 — quá tải THẬT xảy ra (≥1 tầng bỏ frame); tất yếu do server chậm + cửa sổ nhỏ:
        assert total_dropped > 0, f"KHÔNG có drop (quá tải không xảy ra?): submitted={snap.frames_submitted}"
        # P5 — sau drain: mọi request đã gửi có kết cục, không còn treo:
        assert client.in_flight == 0, f"còn {client.in_flight} request treo sau drain"
