# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid trước khi design chi tiết/tasks/code.
> **Cập nhật lúc:** 2026-07-04.

## Introduction

Hiện thực inference **cross-process qua ZMQ** (bulkhead cho detector/GPU) — phần đã HOÃN từ #06; đóng
**K-023** (switchover-aware read + retryable classification) + tách port `IInferenceClient`.

Hiện tại `InlineInferenceClient` (#06) chạy detector CÙNG process với caller (no IPC). Production cần tách
detector ra **process riêng** (bulkhead: detector/GPU crash không kéo camera; 1 inference service gộp lô N
camera). Transport: **ZMQ ROUTER (server) / DEALER (client)**, wire = **msgpack**.

**Ranh giới nguồn (TRUNG THỰC — chống bịa):** `Vision_platform_architecture_design/` KHÔNG có trong workspace
này (đã `Get-ChildItem` xác nhận vắng) dù `step-06` trỏ tới. → Spec KHÔNG neo upstream đó. Nguồn neo THẬT:
code hiện có (`kernel/inference_protocol.py`, `application/inline_inference_client.py`,
`application/reader_epoch_coordinator.py`, `runtime/ipc/ring_control_plane.py`, `runtime/ipc/ring_pool.py`),
`step-06-add-inference.md` (intent ZMQ), journal K-023/K-018/K-017/K-016. Ẩn số (pyzmq trên Windows...) gắn
**[chưa kiểm]** tới PHA build.

## Glossary

- **IInferenceClient**: port (Protocol, kernel/ports) — hợp đồng chung inline + zmq.
- **ROUTER/DEALER**: cặp socket ZMQ async — nhiều DEALER gửi tới 1 ROUTER; server trả đúng client theo identity.
- **correlation map**: `request_id → chỗ-chờ` phía client để ghép response bất đồng bộ (kể cả thứ tự đảo).
- **switchover-aware**: đọc frame biết ring đã đổi epoch (#05b) → chuyển ring mới, không giữ reader cố định.
- **bulkhead**: mỗi thành phần 1 process → cách ly crash (#09).

## Requirements

### Requirement 1: Port IInferenceClient (hợp đồng chung inline + zmq)
**User Story:** Là kiến trúc sư, tôi muốn inline và zmq client cùng một interface, để caller đổi transport chỉ qua composition root mà không sửa logic.
#### Acceptance Criteria
- 1.1 — Hệ thống PHẢI định nghĩa `IInferenceClient` (Protocol, kernel/ports): `infer(request: InferenceRequest) -> InferenceResponse` + `setup()`/`teardown()`.
- 1.2 — `InlineInferenceClient` (#06) PHẢI thoả `IInferenceClient` mà KHÔNG đổi hành vi (giữ 9 test #06 xanh).
- 1.3 — `ZmqInferenceClient` (mới) PHẢI thoả cùng port.
- *Nguồn:* step-06 "same IInferenceClient interface"; D-023 (đã cố ý HOÃN port ở #06 tới khi có bản thứ 2).

### Requirement 2: Transport ZMQ cross-process (bulkhead)
**User Story:** Là kỹ sư vận hành, tôi muốn detector chạy process riêng, để detector/GPU crash không kéo sập tiến trình camera.
#### Acceptance Criteria
- 2.1 — `InferenceServer` PHẢI chạy trong process riêng, nhận request qua ZMQ ROUTER.
- 2.2 — `ZmqInferenceClient` PHẢI gửi qua ZMQ DEALER + nhận response bất đồng bộ.
- 2.3 — Detector crash trong server process PHẢI KHÔNG kéo sập client (nhận lỗi/timeout, không hang vô hạn).
- *Nguồn:* step-06 (ROUTER/DEALER, bulkhead); #09.

### Requirement 3: Correlation request_id qua async
**User Story:** Là camera client, tôi muốn nhận đúng kết quả của mình kể cả khi server trả không đúng thứ tự, để tracking không lệch.
#### Acceptance Criteria
- 3.1 — Mỗi response PHẢI echo đúng `request_id` (như #06).
- 3.2 — Client PHẢI giữ correlation map để ghép response về đúng caller kể cả khi server trả KHÔNG đúng thứ tự gửi.
- 3.3 — Response cho `request_id` không còn chờ (timeout đã dọn) PHẢI bị bỏ an toàn (không crash).
- *Nguồn:* step-06 (bug scenario) + `test_inline_client_correlates_request_id`.

### Requirement 4: Đọc frame switchover-aware (đóng K-023a)
**User Story:** Là inference server, tôi muốn tiếp tục đọc được frame sau khi ring switchover, để inference không chết thầm khi ring đổi epoch.
#### Acceptance Criteria
- 4.1 — Server đọc frame theo `frame_ref` PHẢI switchover-aware: epoch đổi (#05b) → chuyển ring mới (dùng `ReaderEpochCoordinator`), KHÔNG giữ reader cố định như inline.
- 4.2 — Ref epoch CŨ (đến muộn) PHẢI trả stale an toàn (None→error), KHÔNG đọc nhầm ring mới.
- *Nguồn:* K-023(a); `reader_epoch_coordinator.py` (`_maybe_switch`).

### Requirement 5: Phân loại retryable đúng (đóng K-023b)
**User Story:** Là camera-side circuit breaker, tôi muốn phân biệt lỗi tạm và lỗi vĩnh viễn, để không bỏ camera oan khi chỉ là stale tạm thời.
#### Acceptance Criteria
- 5.1 — Lỗi transient (stale-epoch, timeout, queue đầy) PHẢI `retryable=True`.
- 5.2 — Lỗi permanent (bad input, model not loaded, CUDA OOM) PHẢI `retryable=False`.
- 5.3 — `InferenceError` PHẢI chỉ giữ chuỗi (không giữ Exception gốc — pattern #06).
- *Nguồn:* K-023(b); step-06; #06.

### Requirement 6: Wire format msgpack + serialize DTO
**User Story:** Là kỹ sư transport, tôi muốn DTO đi qua wire không mất mát, để server/client hiểu nhau chính xác.
#### Acceptance Criteria
- 6.1 — `InferenceRequest`/`Response`/`Detection`/`InferenceError` (+ `ShmFrameRefData` nhúng, `BBox`+space) PHẢI msgpack round-trip KHÔNG mất mát (gồm `ring_epoch`, `CoordinateSpace`).
- 6.2 — Serialize PHẢI ở tầng transport (KHÔNG để kernel DTO biết msgpack — giữ DTO thuần).
- *Nguồn:* step-06 (msgpack handled by ZMQ adapter); #06 DTO thuần.

### Requirement 7: Vòng đời + graceful shutdown (tích hợp #09)
**User Story:** Là supervisor, tôi muốn inference server tắt sạch (đóng socket + teardown detector), để không rò tài nguyên/không hang khi shutdown.
#### Acceptance Criteria
- 7.1 — `InferenceServer` PHẢI chạy như cooperative worker dưới `Supervisor` (#09): poll shutdown_event → đóng socket + detector.teardown() trong `finally`.
- 7.2 — Client PHẢI có timeout gửi/chờ (không hang khi server chết); hết timeout → `InferenceError(retryable=True)`.
- *Nguồn:* #09 (cascade cooperative-first); K-020.

### Requirement 8: Observability (tích hợp #08, đóng phần K-017)
**User Story:** Là kỹ sư vận hành 24/7, tôi muốn thấy số liệu inference, để phát hiện quá tải/lỗi sớm.
#### Acceptance Criteria
- 8.1 — Server/client PHẢI emit metrics qua `InMemoryMetrics` (#08): counter `inference_requests_total{result}`, gauge `inference_queue_depth`, histogram `inference_latency_ms`.
- 8.2 — Label PHẢI bounded (K-019): KHÔNG dùng `request_id`/coords làm label.
- *Nguồn:* #08; K-017/K-019.

### Requirement 9: Backpressure hàng đợi request (tích hợp #07)
**User Story:** Là inference server, tôi muốn giới hạn request tồn đọng, để không phình bộ nhớ vô hạn khi client gửi nhanh hơn xử lý.
#### Acceptance Criteria
- 9.1 — Cơ chế giới hạn request phía server PHẢI chặn phình bộ nhớ vô hạn (BoundedQueue #07 hoặc ZMQ HWM — chốt ở design QĐ-3).
- 9.2 — Khi đầy: đúng policy + emit metric drop/reject.
- *Nguồn:* #07; K-016.

## Non-Goals (HOÃN — chống phình scope)
CURVE/auth ZMQ · server-side batching GPU · detector thật (dùng FakeDetector) · multi-server/load-balance.

## Tiêu chí ĐẬU (Definition of Done)
Port + `ZmqInferenceClient` + `InferenceServer` + codec; test THẬT cross-process (correlation · switchover-trong-inference
đóng K-023a · retryable đúng · server-crash-client-không-hang · msgpack round-trip · graceful shutdown);
lint 5/0 (+ negative-test zmq/msgpack cấm ở kernel/domain); inline #06 giữ 9 test xanh; không claim xong khi chưa chạy test (§5).
