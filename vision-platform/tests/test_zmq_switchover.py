"""zmq-inference Task 6: Property 2 — switchover-aware (ĐÓNG K-023a). Test QUAN TRỌNG NHẤT.

Chứng minh KHÁC InlineInferenceClient (#06): server ZMQ tiếp tục đọc được frame SAU khi ring switchover
sang epoch mới (KHÔNG stale vĩnh viễn). Server dùng ReaderEpochCoordinator → _maybe_switch chuyển ring.
Guard win32.
"""
from __future__ import annotations

import contextlib
import multiprocessing as mp
import socket
import sys
import uuid

import numpy as np
import pytest

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


def test_zmq_server_survives_ring_switchover():
    """Property 2: switchover epoch1→2 GIỮA lúc phục vụ → request epoch2 vẫn đọc được frame ring mới."""
    pool = RingPool(_N, _H, _W, _C, pool_size=3)
    cp = RingControlPlane(name=f"cp_{uuid.uuid4().hex[:8]}", create=True)
    name1 = pool.activate(1)
    cp.publish(1, name1)
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    ev = mp.Event()
    p = mp.Process(
        target=inference_server_worker,
        args=(ev, endpoint, cp.name, pool.slot_locks_map(), _N, _H, _W, _C, "fake"),
        daemon=True,
    )
    p.start()
    client = ZmqInferenceClient(endpoint, timeout_s=10.0)
    client.setup()
    try:
        # --- epoch 1: ghi + infer OK ---
        w1 = ShmFrameWriter(pool.ring_for_epoch(1))
        ref1 = w1.write(_frame(100))
        assert ref1 is not None and ref1.ring_epoch == 1
        r1 = client.infer(InferenceRequest("e1", "cam1", ref1))
        assert r1.is_success is True and len(r1.detections) == 1

        # --- SWITCHOVER epoch 1 → 2 ---
        name2 = pool.activate(2)
        assert name2 is not None          # pool[2] fresh → reset OK (drain guard không chặn)
        cp.publish(2, name2)

        # --- epoch 2: ghi ring mới + infer → server PHẢI tự chuyển ring (K-023a) ---
        w2 = ShmFrameWriter(pool.ring_for_epoch(2))
        ref2 = w2.write(_frame(200))
        assert ref2 is not None and ref2.ring_epoch == 2
        r2 = client.infer(InferenceRequest("e2", "cam1", ref2))
        assert r2.request_id == "e2"
        assert r2.is_success is True, f"server KHÔNG switchover-aware (K-023a chưa đóng): {r2.error}"
        assert len(r2.detections) == 1
        # frame2 sáng hơn frame1 → confidence cao hơn (đọc đúng frame ring MỚI, không phải ring cũ)
        assert r2.detections[0].confidence > r1.detections[0].confidence
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
