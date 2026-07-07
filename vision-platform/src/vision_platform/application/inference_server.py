"""InferenceServer — server inference cross-process qua ZMQ ROUTER. Layer: application.

Đọc frame từ SHM (runtime) SWITCHOVER-AWARE qua `ReaderEpochCoordinator` (đóng K-023a — KHÔNG giữ reader
cố định như InlineInferenceClient) + chạy `IDetector` (port) + trả response echo request_id.

QĐ-3: SINGLE-THREAD (ZMQ socket không thread-safe) — vòng `poller.poll(timeout)` để định kỳ kiểm
`shutdown_event` (cooperative, R7.1). QĐ-5 retryable: read stale/None → True; detector ném → False (K-023b).

Chạy trong process riêng (bulkhead) — worker module-level (spawn Windows). `bootstrap()` + socket bind PHẢI
chạy TRONG process này (SHM handle + socket per-process).
"""
from __future__ import annotations

from typing import Optional

import msgpack
import zmq

from vision_platform.kernel.inference_protocol import InferenceResponse, InferenceError
from vision_platform.kernel import inference_wire_codec as codec
from vision_platform.kernel.ports.detector import IDetector
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook


class InferenceServer:
    def __init__(
        self,
        coordinator: ReaderEpochCoordinator,
        detector: IDetector,
        endpoint: str,
        *,
        metrics=None,
        obs: Optional[ObservabilityHook] = None,
        poll_ms: int = 50,
    ):
        self._coord = coordinator
        self._detector = detector
        self._endpoint = endpoint
        self._metrics = metrics
        self._obs = obs if obs is not None else ObservabilityHook()
        self._poll_ms = poll_ms

    def _handle(self, payload: bytes) -> bytes:
        req = codec.dict_to_request(msgpack.unpackb(payload, raw=False))
        frame = self._coord.read_ref(req.frame_ref)          # switchover-aware (K-023a)
        if frame is None:
            resp = InferenceResponse(
                request_id=req.request_id,
                error=InferenceError(
                    "ShmReadFailed",
                    f"slot {req.frame_ref.slot} gen {req.frame_ref.generation} epoch {req.frame_ref.ring_epoch} stale/unreadable",
                    retryable=True,          # K-023b: stale = transient
                ),
            )
        else:
            try:
                resp = InferenceResponse(req.request_id, detections=tuple(self._detector.detect(frame)))
            except Exception as e:           # bulkhead: 1 request lỗi KHÔNG làm chết server
                resp = InferenceResponse(
                    request_id=req.request_id,
                    error=InferenceError(type(e).__qualname__, str(e), retryable=False),   # K-023b: detector lỗi = permanent
                )
        if self._metrics is not None:
            self._metrics.counter("inference_requests_total", result=("ok" if resp.is_success else "err"))
        return msgpack.packb(codec.response_to_dict(resp))

    def serve(self, shutdown_event) -> None:
        """Vòng chính cooperative. bootstrap + bind CHẠY TRONG process này. Dừng khi shutdown_event set."""
        self._coord.bootstrap()
        self._detector.setup()
        ctx = zmq.Context()
        sock = ctx.socket(zmq.ROUTER)
        sock.setsockopt(zmq.LINGER, 0)
        sock.bind(self._endpoint)
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)
        self._obs.emit("inference_server_started", endpoint=self._endpoint)
        try:
            while not shutdown_event.is_set():
                if dict(poller.poll(self._poll_ms)).get(sock) != zmq.POLLIN:
                    continue
                # BULKHEAD PER-REQUEST (K-024): bọc TOÀN BỘ recv+handle+send — 1 request rác/malformed
                # (sai số frame / payload không phải msgpack / deserialize lỗi) KHÔNG được làm CHẾT server.
                try:
                    frames = sock.recv_multipart()
                    if len(frames) != 2:                       # DEALER hợp lệ = [identity, payload]
                        self._obs.emit("inference_malformed_request", n_frames=len(frames))
                        if self._metrics is not None:
                            self._metrics.counter("inference_requests_total", result="malformed")
                        continue
                    ident, payload = frames
                    reply = self._handle(payload)              # có thể raise (unpackb/dict_to_request rác)
                    sock.send_multipart([ident, reply])
                except Exception as e:
                    # Lỗi transport/deserialize 1 request → bỏ, phục vụ tiếp (không crash server).
                    # (payload rác không có request_id để echo → client sẽ timeout=retryable, an toàn.)
                    self._obs.emit("inference_request_error", error_type=type(e).__qualname__, error=str(e))
                    if self._metrics is not None:
                        self._metrics.counter("inference_requests_total", result="error")
                    continue
        finally:
            sock.close(0)
            ctx.term()
            self._detector.teardown()
            self._obs.emit("inference_server_stopped", endpoint=self._endpoint)
