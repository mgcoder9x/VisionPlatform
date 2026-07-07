# Mẩu 08 — 10 test: codec/port + cross-process + switchover (Property 2)

**(1) Thuộc về đâu:** `tests/test_zmq_codec.py` + `tests/test_zmq_inference_cross_process.py` + `tests/test_zmq_switchover.py`. Bằng chứng cho mẩu 01–07.

**(2) Cần biết trước:** spawn worker module (#09 mẩu 07); free TCP port; `mp.Event`; ZMQ connect-before-bind.

**(3) Code thật — test switchover cốt lõi (quote `tests/test_zmq_switchover.py`):**
```python
# --- epoch 1: ghi + infer OK ---
w1 = ShmFrameWriter(pool.ring_for_epoch(1)); ref1 = w1.write(_frame(100))
r1 = client.infer(InferenceRequest("e1", "cam1", ref1))
assert r1.is_success is True and len(r1.detections) == 1
# --- SWITCHOVER epoch 1 → 2 ---
name2 = pool.activate(2); cp.publish(2, name2)
# --- epoch 2: server PHẢI tự chuyển ring (K-023a) ---
w2 = ShmFrameWriter(pool.ring_for_epoch(2)); ref2 = w2.write(_frame(200))
r2 = client.infer(InferenceRequest("e2", "cam1", ref2))
assert r2.is_success is True, f"server KHÔNG switchover-aware (K-023a chưa đóng): {r2.error}"
assert r2.detections[0].confidence > r1.detections[0].confidence   # đọc đúng frame ring MỚI
```

**(4) Giải thích nhóm test (10):**
- **codec/port (5, `test_zmq_codec.py`):** DTO↔dict + msgpack round-trip (Property 6, giữ ring_epoch + CoordinateSpace) + inline thoả `IInferenceClient`. In-process, nhanh.
- **cross-process (4, `test_zmq_inference_cross_process.py`):** spawn server thật:
  - Property 1 correlation: 3 request khác id → response đúng id.
  - Property 3 stale: ref epoch cũ → error `retryable=True`.
  - Property 4 bulkhead: detector crash → error `retryable=False`, server VẪN sống (request kế có response).
  - Property 5: server bị kill → client `infer` timeout → `retryable=True` (không hang).
- **switchover (1, `test_zmq_switchover.py`):** **Property 2** — switchover epoch1→2, request epoch2 → server đọc frame ring mới (confidence cao hơn) → **đóng K-023a**.

**(5) Là gì:** bộ 10 test biến mọi khẳng định #06b thành bằng chứng chạy thật (§5).

**(6) Tại sao test switchover QUAN TRỌNG NHẤT:** nó là cổng chứng minh điểm KHÁC BIỆT bản chất vs inline —
server sống sót switchover. Nếu server không switchover-aware, `r2` sẽ là error (stale) → test đỏ. Test
xanh + confidence cao hơn = đọc đúng frame ring MỚI (không phải ring cũ).

**(7) Dùng ở đâu / kết quả thật:** `pytest tests/test_zmq_*.py` → 10 passed (codec 5 + cross-process 4 + switchover 1); full **300 passed, 1 skipped**; lint **5 kept/0 broken**. Guard win32 (spawn Windows; POSIX chưa verify).

**(8) Không có test switchover thì sao:** không có gì chứng minh K-023 thực sự đóng — chỉ là "đọc code thấy đúng" = CHƯA verify (§5). Regression switchover có thể lọt.

**(9) Ví von:** diễn tập THẬT: dời kho giữa lúc bếp đang phục vụ, xem bếp có tự sang kho mới lấy đúng đồ không — thay vì tin lý thuyết.

**(10) Liên kết bức tranh lớn:** test cross-process tái dùng pattern spawn #05b T-B/#09 (worker module + lock
thừa kế). Property 2 nối #05b (switchover) + đóng K-023 (audit). §5 verify-bằng-chạy-thật.

**(11) Cạm bẫy:** free port có race nhỏ (bind-close-rồi-server-bind) — hiếm trên loopback test. `timeout_s`
đủ lớn cho spawn Windows (~10s). ZMQ connect-before-bind OK (client connect trước server bind, message chờ). Guard win32.

**(12) Tự kiểm:**
- Test switchover chứng minh gì mà test cross-process khác không? Dòng `confidence cao hơn` nghĩa là gì?
- Property 5 (server chết) test điều gì về client?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** 3 test file zmq (10 test pass) · design Testing Strategy + Property 1..7. Độ chắc: cao (output pytest thật: 10 passed / full 300 passed, 1 skipped).
