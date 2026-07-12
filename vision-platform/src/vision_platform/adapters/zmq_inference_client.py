"""ZmqInferenceClient — inference client cross-process qua ZMQ DEALER. Layer: adapters (leaf).

CHỈ transport (KHÔNG đọc SHM) → import kernel(DTO+codec+port) + zmq + msgpack, KHÔNG runtime → leaf hợp lệ.

QĐ-1 (refine — ZMQ socket KHÔNG thread-safe): dùng **socket-owner-thread**. Caller `infer()` đẩy payload
vào `queue` + đăng ký slot `{request_id: Queue(1)}`, rồi block chờ slot. MỘT thread sở hữu DEALER làm CẢ
send (drain outbound) + recv (poll) → socket chỉ chạm 1 thread (an toàn). Correlation qua request_id (R3).
infer() SYNC blocking + timeout → InferenceError(retryable=True) (R5.1/R7.2), KHÔNG hang khi server chết.
"""
from __future__ import annotations

import queue
import sys
import threading
import time

import msgpack
import zmq

from vision_platform.kernel.inference_protocol import InferenceRequest, InferenceResponse, InferenceError
from vision_platform.kernel import inference_wire_codec as codec
from vision_platform.kernel.backpressure import BoundedQueue, BackpressurePolicy
from vision_platform.kernel.backpressure_metrics import BackpressureMetrics


class ZmqInferenceClient:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_s: float = 5.0,
        poll_ms: int = 50,
        sndhwm: int = 1000,
        rcvhwm: int = 1000,
        window_size: int = 8,
        queue_maxsize: int | None = None,
        policy: BackpressurePolicy = BackpressurePolicy.DROP_OLDEST,
    ):
        if sndhwm < 1 or rcvhwm < 1:
            raise ValueError("sndhwm/rcvhwm must be >= 1")
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._endpoint = endpoint
        self._timeout_s = timeout_s
        self._poll_ms = poll_ms
        self._sndhwm = sndhwm
        self._rcvhwm = rcvhwm
        self._ctx: zmq.Context | None = None
        self._sock: zmq.Socket | None = None
        # --- đường SYNC infer() (giữ nguyên, additive) ---
        self._outbound: queue.Queue[bytes] = queue.Queue()
        self._pending: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        # --- đường ASYNC submit() (van hàng đợi + flow-control, task 2.4/2.5) ---
        self._window_size = window_size
        self._async_outbound: BoundedQueue[InferenceRequest] = BoundedQueue(
            maxsize=(queue_maxsize if queue_maxsize is not None else window_size),
            policy=policy,
        )
        # Các biến dưới CHỈ io thread ghi (send + recv + timeout-scan cùng 1 thread) → không cần lock.
        self._in_flight = 0
        self._sent = 0        # frames_submitted — đếm TẠI LÚC GỬI (K-051), không lúc enqueue
        self._ok = 0
        self._err = 0
        self._timeout = 0
        self._io_errors = 0   # Z1/#345: số vòng io-loop bị lỗi + cô lập (bulkhead) — quan sát/kiểm thử
        self._pending_async: dict[str, float] = {}   # request_id -> monotonic lúc gửi (io thread)
        self._responses: queue.Queue[InferenceResponse] = queue.Queue()

    def setup(self) -> None:
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.DEALER)
        self._sock.setsockopt(zmq.LINGER, 0)
        # A3 (R6.1–6.3): set HWM TRƯỚC connect — HWM chỉ áp cho pipe tạo SAU khi set.
        # HWM = trần buffer ZMQ nội bộ (chống phình bộ nhớ vô hạn khi server chậm).
        self._sock.setsockopt(zmq.SNDHWM, self._sndhwm)
        self._sock.setsockopt(zmq.RCVHWM, self._rcvhwm)
        self._sock.connect(self._endpoint)   # connect-before-bind OK (ZMQ tự reconnect)
        self._running = True
        self._thread = threading.Thread(target=self._io_loop, name="zmq-client-io", daemon=True)
        self._thread.start()

    def _io_loop(self) -> None:
        """Vòng io duy-nhất-sở-hữu-socket. BULKHEAD (Z1/#345): lỗi 1 vòng (message rác / lỗi transport) được
        CÔ LẬP → io thread KHÔNG chết (đối xứng `InferenceServer.serve` K-024). Không bọc → 1 response rác giết
        thread → client thành hố đen (mọi infer/submit timeout mãi). Request đang chờ tự timeout=retryable."""
        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)
        while self._running:
            try:
                self._loop_body(poller)
            except Exception as e:   # noqa: BLE001 — bulkhead io thread (Z1): giữ thread sống, bỏ vòng lỗi
                self._io_errors += 1
                print(f"[zmq-client] io-loop bỏ qua lỗi (giữ thread sống): {type(e).__name__}: {e}",
                      file=sys.stderr)
                time.sleep(0.005)   # tránh busy-spin nếu lỗi lặp liên tục

    def _loop_body(self, poller) -> None:
        # 1) drain outbound SYNC → send (CHỈ thread này chạm socket).
        try:
            while True:
                self._sock.send(self._outbound.get_nowait())
        except queue.Empty:
            pass
        # 1b) send ASYNC có FLOW-CONTROL: chỉ gửi khi cửa sổ chưa đầy (in_flight < window).
        #     Frame bị BoundedQueue bỏ (DROP_OLDEST) KHÔNG bao giờ tới đây → không đếm submitted.
        while self._in_flight < self._window_size:
            try:
                # timeout=0 = non-blocking: van rỗng → raise Empty NGAY (không chặn io thread).
                req = self._async_outbound.get_or_raise(timeout=0)
            except queue.Empty:
                break
            # Ghi nhận in-flight + submitted NGAY sau khi rời van, TRƯỚC send() (fix F1 review #252):
            # đóng cửa sổ đua drain — nếu tăng SAU send, có khoảnh khắc (outbound_size==0 & in_flight==0)
            # ở frame cuối làm vòng drain camera_worker thoát sớm. send() DEALER là fire-and-forget
            # (window_size ≪ SNDHWM nên không block/raise) → thứ tự này an toàn + chính xác hơn cho flow-control.
            self._pending_async[req.request_id] = time.monotonic()
            self._in_flight += 1
            self._sent += 1     # đếm TẠI LÚC GỬI (K-051)
            self._sock.send(msgpack.packb(codec.request_to_dict(req)))
        # 2) poll recv.
        if dict(poller.poll(self._poll_ms)).get(self._sock) == zmq.POLLIN:
            data = self._sock.recv()
            d = msgpack.unpackb(data, raw=False)
            rid = d["request_id"]
            with self._lock:
                slot = self._pending.pop(rid, None)
            if slot is not None:
                slot.put(d)     # đường SYNC — R3.3: id đã dọn (timeout) → slot None → bỏ an toàn
            elif rid in self._pending_async:
                # đường ASYNC: phân loại ok/err → đẩy vào _responses, giảm in_flight.
                self._pending_async.pop(rid)
                resp = codec.dict_to_response(d)
                if resp.is_success:
                    self._ok += 1
                else:
                    self._err += 1
                self._responses.put(resp)
                self._in_flight -= 1
        # 3) quét TIMEOUT các request async quá hạn (task 2.5): tạo response lỗi retryable.
        if self._pending_async:
            now = time.monotonic()
            expired = [r for r, ts in self._pending_async.items() if now - ts > self._timeout_s]
            for r in expired:
                self._pending_async.pop(r)
                self._responses.put(InferenceResponse(
                    request_id=r,
                    error=InferenceError("Timeout", f"no response in {self._timeout_s}s", retryable=True),
                ))
                self._timeout += 1
                self._in_flight -= 1

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

    # ---- Đường ASYNC (task 2.4/2.5): submit không chặn + poll + metrics ----

    def submit(self, request: InferenceRequest) -> bool:
        """Đưa request vào van hàng đợi outbound (KHÔNG chặn camera). Trả True = đã nhận.

        Dưới DROP_OLDEST luôn True (bỏ frame cũ nhất CHƯA gửi để nhận frame mới → giữ recency).
        BLOCK-policy dùng timeout để không treo vô hạn.
        """
        return self._async_outbound.put(request, timeout=self._timeout_s)

    @property
    def in_flight(self) -> int:
        """Số request đã gửi nhưng CHƯA có kết cục (response/timeout)."""
        return self._in_flight

    @property
    def outbound_size(self) -> int:
        """Số request đang chờ trong van outbound (CHƯA gửi tới server).

        Dùng cho drain: hàng đợi rỗng (outbound_size==0) AND in_flight==0 ⇒ đã gửi hết + có kết cục hết.
        Chỉ in_flight==0 CHƯA đủ: giữa 2 vòng io có thể còn frame trong van chưa kịp gửi.
        """
        return self._async_outbound.qsize()

    def poll_responses(self) -> list[InferenceResponse]:
        """Rút mọi response đã hoàn tất (non-blocking). Camera gọi mỗi vòng để tiêu thụ + drain."""
        out: list[InferenceResponse] = []
        try:
            while True:
                out.append(self._responses.get_nowait())
        except queue.Empty:
            pass
        return out

    def metrics_snapshot(self, frames_captured: int) -> BackpressureMetrics:
        """Gộp bộ đếm hiện tại thành DTO bất biến. `frames_captured` do camera đếm truyền vào.

        dropped = drops (DROP_OLDEST/DROP_NEWEST) + rejects (REJECT) của van outbound.
        Đọc sau khi io thread quiesce → bất biến bảo toàn đúng (P1).
        """
        dropped = self._async_outbound.drops + self._async_outbound.rejects
        return BackpressureMetrics(
            frames_captured=frames_captured,
            frames_submitted=self._sent,
            frames_dropped_backpressure=dropped,
            infer_ok=self._ok,
            infer_err=self._err,
            infer_timeout=self._timeout,
        )

    def teardown(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._sock is not None:
            self._sock.close(0)
        if self._ctx is not None:
            self._ctx.term()
