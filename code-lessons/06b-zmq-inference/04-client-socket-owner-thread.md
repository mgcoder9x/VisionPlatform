# Mẩu 04 — `ZmqInferenceClient`: DEALER + socket-owner-thread + correlation

**(1) Thuộc về đâu:** `adapters/zmq_inference_client.py`.

**(2) Cần biết trước:** ZMQ DEALER (socket async); `queue.Queue` (hàng đợi thread-safe); thread; correlation map (#06 mẩu 02); "socket không thread-safe".

**(3) Code thật (quote `adapters/zmq_inference_client.py`):**
```python
def _io_loop(self) -> None:
    poller = zmq.Poller()
    poller.register(self._sock, zmq.POLLIN)
    while self._running:
        try:                                   # 1) drain outbound → send (CHỈ thread này chạm socket)
            while True:
                self._sock.send(self._outbound.get_nowait())
        except queue.Empty:
            pass
        if dict(poller.poll(self._poll_ms)).get(self._sock) == zmq.POLLIN:   # 2) recv
            data = self._sock.recv()
            d = msgpack.unpackb(data, raw=False)
            with self._lock:
                slot = self._pending.pop(d["request_id"], None)
            if slot is not None:
                slot.put(d)

def infer(self, request):
    slot = queue.Queue(maxsize=1)
    with self._lock:
        self._pending[request.request_id] = slot
    self._outbound.put(msgpack.packb(codec.request_to_dict(request)))
    try:
        d = slot.get(timeout=self._timeout_s)
    except queue.Empty:
        with self._lock: self._pending.pop(request.request_id, None)
        return InferenceResponse(request.request_id, error=InferenceError("Timeout", ..., retryable=True))
    return codec.dict_to_response(d)
```

**(4) Giải thích từng ý nhỏ:**
- `infer()` (chạy ở caller-thread): tạo `slot = Queue(1)`, đăng ký `_pending[request_id]=slot`, đẩy payload vào `_outbound`, rồi **block** `slot.get(timeout)`.
- `_io_loop` (1 thread RIÊNG, sở hữu DEALER): drain `_outbound` → `send`; poll → `recv` → tìm slot theo `request_id` → `put` (đánh thức caller).
- Timeout → dọn `_pending` + trả `InferenceError(retryable=True)` (không hang).

**(5) Là gì:** client ZMQ: caller gửi request đồng bộ, nhận response đúng của mình qua correlation map.

**(6) Tại sao SOCKET-OWNER-THREAD (điểm bản chất):** ZMQ socket **KHÔNG thread-safe** → KHÔNG được `send`
từ caller-thread và `recv` từ thread khác trên **cùng** socket (undefined behavior). Giải: **chỉ 1 thread
(`_io_loop`) chạm socket** (làm cả send lẫn recv). Caller-thread chỉ đụng `queue.Queue` (thread-safe).
Đây là refine đúng bản chất — không phải "send-from-caller" ngây thơ.

**(7) Dùng ở đâu trong project:** camera pipeline gọi `client.infer(request)`. Test correlation/stale/timeout (mẩu 08).

**(8) Không có (send-from-caller) thì sao:** 2 thread chạm 1 socket → crash/hỏng dữ liệu ngẫu nhiên (undefined). Không timeout → hang mãi khi server chết.

**(9) Ví von:** một nhân viên bưu điện DUY NHẤT (io-thread) đứng ở quầy (socket): nhận thư đi (outbound
queue) + phát thư đến. Khách (caller) chỉ bỏ thư vào hộp + chờ số hiệu của mình — không ai khác đứng chung quầy.

**(10) Liên kết bức tranh lớn:** cùng vấn đề "ZMQ 1-thread-1-socket" với server single-thread (mẩu 05).
`retryable=True` khi timeout nối K-023(b) (transient). Layer adapters (leaf — mẩu 07).

**(11) Cạm bẫy:** đừng gọi `send`/`recv` ngoài `_io_loop`. `slot.get(timeout)` bắt buộc có timeout (không
hang). `LINGER=0` để `close()` không treo. Response cho id đã timeout → `_pending.pop`=None → bỏ an toàn (R3.3).

**(12) Tự kiểm:**
- Vì sao phải socket-owner-thread? Điều gì xảy ra nếu send từ caller + recv từ io-thread?
- Timeout trong `infer` trả gì? Vì sao retryable=True?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `adapters/zmq_inference_client.py` · test cross-process (correlation/timeout). Độ chắc: cao (quote thật + 5 test cross-process pass).
