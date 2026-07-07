# Mẩu 01 — Vì sao tách inference ra process riêng (bulkhead) + K-023

**(1) Thuộc về đâu:** bức tranh tổng #06b. "Móc treo".

**(2) Cần biết trước:** inline client (#06); bulkhead (#09 — mỗi thành phần 1 process, cách ly crash);
switchover + ring_epoch (#05b); process vs thread (glossary).

**(3) Bằng chứng thật (quote docstring `application/inference_server.py`):**
```python
"""InferenceServer — server inference cross-process qua ZMQ ROUTER. Layer: application.
Đọc frame từ SHM (runtime) SWITCHOVER-AWARE qua `ReaderEpochCoordinator` (đóng K-023a — KHÔNG giữ reader
cố định như InlineInferenceClient) + chạy `IDetector` (port) + trả response echo request_id.
...Chạy trong process riêng (bulkhead)..."""
```

**(4) Giải thích từng ý nhỏ:**
- "process riêng (bulkhead)" → detector crash không kéo camera.
- "SWITCHOVER-AWARE ... KHÔNG giữ reader cố định như InlineInferenceClient" → điểm khác cốt lõi vs #06 (đóng K-023a).

**(5) Là gì:** #06b = bản production của inference — detector ở process riêng, nói chuyện qua ZMQ.

**(6) Tại sao tồn tại / vấn đề nó giải (3 nỗi đau):**
- **Bulkhead:** inline (cùng process) → detector/GPU crash kéo sập camera. Tách process → cách ly.
- **K-023(a) — switchover:** inline giữ reader cố định → sau switchover (#05b) đọc ring cũ → **stale vĩnh viễn**, inference chết thầm. Production phải tự hồi phục.
- **K-023(b) — retryable:** inline trả mọi lỗi `retryable=False`; nhưng stale là tạm → circuit-breaker bỏ camera oan.

**(7) Dùng ở đâu trong project:** `InferenceServer` (application) chạy trong process con (spawn) đọc SHM; `ZmqInferenceClient` (adapters) phía camera. Test cross-process (mẩu 08).

**(8) Không có nó (chỉ inline) thì sao:** không cách ly GPU crash + inference chết sau switchover + phân loại lỗi sai → không dùng được cho sản phẩm 24/7.

**(9) Ví von:** thay vì nấu ăn ngay tại bàn khách (inline — cháy nồi thì cháy cả bàn), chuyển bếp ra
phòng riêng (bulkhead); khách đưa **phiếu gọi món** (frame_ref) qua cửa sổ (ZMQ), bếp lấy nguyên liệu
từ kho chung (SHM) nấu, trả món kèm số phiếu.

**(10) Liên kết bức tranh lớn:** hợp nhất #06 (correlation) + #05b (switchover/pool lock thừa kế) + #09
(bulkhead process) + #08 (metrics) + #07 (backpressure). Là bước từ demo → production.

**(11) Cạm bẫy:** đừng gửi cả pixel qua ZMQ (nặng) — gửi `frame_ref`, server đọc SHM. Đừng dùng inline cho hệ có switchover.

**(12) Tự kiểm:**
- Kể 3 nỗi đau inline gặp mà #06b giải.
- Vì sao gửi `frame_ref` chứ không gửi pixel qua ZMQ?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/inference_server.py` (docstring) · journal K-023 · design zmq-inference. Độ chắc: cao (quote thật + 10 test pass).
