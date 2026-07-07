"""ZmqInferenceClient — inference client cross-process qua ZMQ DEALER. Layer: adapters (leaf).

CHỈ transport (KHÔNG đọc SHM) → import kernel(DTO+codec+port) + zmq + msgpack, KHÔNG runtime → leaf hợp lệ.

QĐ-1 (refine — ZMQ socket KHÔNG thread-safe): dùng **socket-owner-thread**. Caller `infer()` đẩy payload
vào `queue` + đăng ký slot `{request_id: Queue(1)}`, rồi block chờ slot. MỘT thread sở hữu DEALER làm CẢ
send (drain outbound) + recv (poll) → socket chỉ chạm 1 thread (an toàn). Correlation qua request_id (R3).
infer() SYNC blocking + timeout → InferenceError(retryable=True) (R5.1/R7.2), KHÔNG hang khi server chết.
"""
from __future__ import annotations

import queue
import threading

import msgpack
import zmq

from vision_platform.kernel.inference_protocol import InferenceRequest, InferenceResponse, InferenceError
from vision_platform.kernel import inference_wire_codec as codec


class ZmqInferenceClient:
    def __init__(self, endpoint: str, *, timeout_s: float = 5.0, poll_ms: int = 50):
        self._endpoint = endpoint
        self._timeout_s = timeout_s
        self._poll_ms = poll_ms
        self._ctx: zmq.Context | None = None
        self._sock: zmq.Socket | None = None
        self._outbound: queue.Queue[bytes] = queue.Queue()
        self._pending: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    def setup(self) -> None:
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.DEALER)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.connect(self._endpoint)   # connect-before-bind OK (ZMQ tự reconnect)
        self._running = True
        self._thread = threading.Thread(target=self._io_loop, name="zmq-client-io", daemon=True)
        self._thread.start()

    def _io_loop(self) -> None:
        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)
        while self._running:
            # 1) drain outbound → send (CHỈ thread này chạm socket).
            try:
                while True:
                    self._sock.send(self._outbound.get_nowait())
            except queue.Empty:
                pass
            # 2) poll recv.
            if dict(poller.poll(self._poll_ms)).get(self._sock) == zmq.POLLIN:
                data = self._sock.recv()
                d = msgpack.unpackb(data, raw=False)
                with self._lock:
                    slot = self._pending.pop(d["request_id"], None)
                if slot is not None:
                    slot.put(d)     # R3.3: id đã dọn (timeout) → slot None → bỏ an toàn

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        slot: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[request.request_id] = slot
        self._outbound.put(msgpack.packb(codec.request_to_dict(request)))
        try:
            d = slot.get(timeout=self._timeout_s)
        except queue.Empty:
            with self._lock:
                self._pending.pop(request.request_id, None)
            return InferenceResponse(
                request_id=request.request_id,
                error=InferenceError("Timeout", f"no response in {self._timeout_s}s", retryable=True),
            )
        return codec.dict_to_response(d)

    def teardown(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._sock is not None:
            self._sock.close(0)
        if self._ctx is not None:
            self._ctx.term()
