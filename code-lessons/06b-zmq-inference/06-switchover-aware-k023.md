# Mẩu 06 — `_handle`: switchover-aware (K-023a) + retryable đúng (K-023b)

**(1) Thuộc về đâu:** `application/inference_server.py`, method `_handle`. **Đây là chỗ ĐÓNG K-023.**

**(2) Cần biết trước:** `ReaderEpochCoordinator._maybe_switch` (#05b/#06 audit); stale-ref (ring_epoch cũ→None); retryable (#06 mẩu 05); K-023 (audit phát hiện inline không self-heal).

**(3) Code thật (quote `application/inference_server.py`):**
```python
def _handle(self, payload: bytes) -> bytes:
    req = codec.dict_to_request(msgpack.unpackb(payload, raw=False))
    frame = self._coord.read_ref(req.frame_ref)          # switchover-aware (K-023a)
    if frame is None:
        resp = InferenceResponse(req.request_id, error=InferenceError(
            "ShmReadFailed", f"... epoch {req.frame_ref.ring_epoch} stale/unreadable", retryable=True))  # K-023b
    else:
        try:
            resp = InferenceResponse(req.request_id, detections=tuple(self._detector.detect(frame)))
        except Exception as e:                            # bulkhead: 1 request lỗi KHÔNG chết server
            resp = InferenceResponse(req.request_id, error=InferenceError(
                type(e).__qualname__, str(e), retryable=False))   # K-023b: detector lỗi = permanent
    if self._metrics is not None:
        self._metrics.counter("inference_requests_total", result=("ok" if resp.is_success else "err"))
    return msgpack.packb(codec.response_to_dict(resp))
```

**(4) Giải thích từng ý nhỏ:**
- `self._coord.read_ref(req.frame_ref)` → **dùng ReaderEpochCoordinator** (KHÔNG reader cố định). Bên trong,
  `read_ref` gọi `_maybe_switch`: đọc control-plane, epoch đổi → mở ring mới → chuyển reader → rồi đọc.
  ⇒ sau switchover, server đọc được frame ring MỚI (đóng **K-023a**).
- `frame is None` (stale/không đọc được) → `retryable=True` (transient — đóng **K-023b**).
- detector ném → `retryable=False` (permanent) + server KHÔNG chết (try/except → request kế vẫn phục vụ, bulkhead).
- `metrics.counter(..., result=...)` → observability (#08), label bounded (ok/err — không cardinality nổ).

**(5) Là gì:** hàm xử lý 1 request: đọc frame switchover-aware → detect → trả response phân loại lỗi đúng.

**(6) Tại sao đây là điểm cốt lõi (đóng K-023):**
- **K-023(a):** inline giữ reader cố định → stale vĩnh viễn sau switchover. Server dùng `ReaderEpochCoordinator`
  → tự chuyển ring → **sống sót switchover**. Đây là KHÁC BIỆT bản chất vs #06.
- **K-023(b):** stale = transient → `retryable=True` (circuit-breaker retry, không bỏ camera oan); detector lỗi = permanent → `False`.

**(7) Dùng ở đâu / bằng chứng:** `test_zmq_switchover.py` — switchover epoch1→2, request epoch2 → server đọc
frame ring mới OK (confidence cao hơn). `test_zmq_inference_cross_process.py` — stale→retryable=True, detector-crash→retryable=False.

**(8) Không có (reader cố định + retryable=False) thì sao:** = đúng lỗ hổng K-023 của inline: inference chết thầm sau switchover + circuit-breaker bỏ camera oan.

**(9) Ví von:** bếp (server) biết kho vừa dời sang phòng mới (switchover): thay vì cứ mở kho cũ trống rỗng
mãi (inline stale), bếp nhìn bảng chỉ dẫn (control-plane) → sang kho mới lấy đồ. Và ghi biên bản "kho tạm
chưa sẵn, thử lại sau" (retryable) thay vì "hỏng vĩnh viễn".

**(10) Liên kết bức tranh lớn:** hợp nhất #05b (switchover/coordinator) + #06 (retryable/DTO) + #08 (metrics).
Đóng K-023 = lý do sub-spec này tồn tại.

**(11) Cạm bẫy:** đừng thay `ReaderEpochCoordinator` bằng `ShmFrameReader` cố định (tái tạo lỗi K-023). `try/except`
quanh detect bắt buộc (bulkhead). retryable phải đặt ĐÚNG loại (đảo → circuit-breaker sai).

**(12) Tự kiểm:**
- Vì sao server đọc được frame sau switchover mà inline thì không? (nối `_maybe_switch`)
- 2 loại lỗi nào → retryable=True, loại nào → False? Vì sao?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/inference_server.py` (_handle) · `application/reader_epoch_coordinator.py` · `test_zmq_switchover.py` · journal K-023. Độ chắc: cao (quote thật + test switchover pass).
