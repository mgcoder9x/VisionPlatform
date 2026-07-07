# Mẩu 05 — `InferenceServer.serve`: ROUTER poller-loop single-thread cooperative

**(1) Thuộc về đâu:** `application/inference_server.py`, method `serve`.

**(2) Cần biết trước:** ZMQ ROUTER (server socket, định danh client); `zmq.Poller` (chờ có sự kiện với timeout); cooperative shutdown (#09 — poll shutdown_event); recv_multipart/send_multipart.

**(3) Code thật (quote `application/inference_server.py`):**
```python
def serve(self, shutdown_event) -> None:
    self._coord.bootstrap()
    self._detector.setup()
    ctx = zmq.Context(); sock = ctx.socket(zmq.ROUTER)
    sock.setsockopt(zmq.LINGER, 0); sock.bind(self._endpoint)
    poller = zmq.Poller(); poller.register(sock, zmq.POLLIN)
    try:
        while not shutdown_event.is_set():
            if dict(poller.poll(self._poll_ms)).get(sock) != zmq.POLLIN:
                continue
            try:                                            # BULKHEAD PER-REQUEST (K-024)
                frames = sock.recv_multipart()
                if len(frames) != 2:                        # DEALER hợp lệ = [identity, payload]
                    ... emit malformed; continue
                ident, payload = frames
                sock.send_multipart([ident, self._handle(payload)])
            except Exception as e:                          # 1 request rác KHÔNG chết server
                ... emit request_error; continue
    finally:
        sock.close(0); ctx.term(); self._detector.teardown()
```
> (Đây là bản ĐÃ HARDENED sau doubt-driven audit — K-024. Bản đầu KHÔNG có try/except → 1 request rác chết cả server.)

**(4) Giải thích từng ý nhỏ:**
- `self._coord.bootstrap()` + `bind()` chạy **TRONG process này** (SHM handle + socket per-process).
- `while not shutdown_event.is_set()` → vòng cooperative (#09): dừng khi supervisor set event.
- `poller.poll(poll_ms)` → chờ tối đa `poll_ms` cho request → nếu không có, quay lại kiểm shutdown_event (không block vô hạn → tắt được).
- `recv_multipart()` → `[identity, payload]` (ROUTER prepend identity của DEALER gửi 1 frame).
- `send_multipart([ident, response])` → gửi về đúng client theo identity.
- `finally`: đóng socket + term context + teardown detector (giải phóng sạch).

**(5) Là gì:** vòng chính server: nhận request → xử lý (_handle) → trả response, tới khi được lệnh dừng.

**(6) Tại sao SINGLE-THREAD (QĐ-3):** ZMQ socket không thread-safe → toàn bộ recv+send trên **1 thread**.
`poller.poll(timeout)` cho phép định kỳ kiểm `shutdown_event` (cooperative) mà không cần thread khác.
Backpressure: request dồn ở ZMQ recv-buffer (giới hạn bằng HWM) — v1 không cần BoundedQueue multi-worker.

**(7) Dùng ở đâu trong project:** worker `inference_server_worker` (spawn) gọi `server.serve(shutdown_event)`
trong process con; supervisor (#09) set event khi shutdown. Test cross-process (mẩu 08).

**(8) Không có (block recv vô hạn) thì sao:** `recv()` block → không kiểm được shutdown_event → server không tắt cooperative được (phải kill cứng → không graceful).

**(9) Ví von:** nhân viên quầy nhìn ra cửa mỗi 50ms: có khách thì phục vụ, không thì liếc bảng "hết giờ"
(shutdown_event) để còn dọn quầy đúng lúc — thay vì đứng chôn chân chờ khách (block recv) tới mức không nghe loa báo đóng cửa.

**(10) Liên kết bức tranh lớn:** cooperative loop = pattern #09 (graceful_worker). `_handle` (mẩu 06) là
nơi đọc SHM switchover-aware + detect. Single-thread cùng lý do "ZMQ 1-thread-1-socket" với client (mẩu 04).

**(11) Cạm bẫy:** `bootstrap()` + `bind()` PHẢI trong process con (không truyền socket/handle qua spawn).
`recv_multipart` giả định DEALER gửi ĐÚNG 1 frame (client làm vậy). `LINGER=0` để term không treo.
**K-024 (audit):** phải BỌC recv+handle+send trong try/except + guard số frame — 1 request rác (payload không phải msgpack / sai số frame) mà không bọc sẽ VĂNG khỏi `serve()` → chết cả server. Đã fix + test `test_zmq_server_survives_malformed_request`.

**(12) Tự kiểm:**
- Vì sao dùng `poller.poll(timeout)` thay `recv()` block? Liên quan shutdown thế nào?
- Vì sao `bootstrap()` phải chạy trong process con, không phải process cha?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/inference_server.py` (serve) · design QĐ-3 · test cross-process. Độ chắc: cao (quote thật + test pass).
