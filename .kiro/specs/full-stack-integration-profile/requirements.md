# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid + chốt Q1–Q3 trước design chi tiết/tasks/code.
> **Mục đích:** capstone — WIRE THẬT toàn chuỗi thành 1 composition-root chạy end-to-end + test full-stack.
> **Cập nhật lúc:** 2026-07-04.

## Introduction

Tới giờ mỗi thành phần được test RIÊNG LẺ (SHM #05, switchover #05b, inference zmq, supervisor liveness,
backpressure #07, observability #08). CHƯA có artifact "product-shaped" WIRE tất cả vào 1 luồng end-to-end +
test chứng minh frame chảy camera → SHM → inference → detections dưới supervisor. Đây là gap tôi đã ghi
(audit) + là bước thật hướng sản phẩm thương mại.

Sub-spec này dựng 1 **composition-root profile** + **camera worker** + tái dùng **InferenceServer** +
**Supervisor**, cho **1 camera + 1 inference server** (v1 — đủ chứng minh vòng lặp; multi-camera = scale sau).

**Ranh giới nguồn (chống bịa):** neo CODE THẬT đã có: `runtime/ipc/{ring_pool,ring_control_plane}.py`,
`application/{writer_epoch_coordinator,inference_server,supervisor}.py`, `adapters/{noise_frame_source,
fake_detector,zmq_inference_client}.py`, `kernel/backpressure.py`, `runtime/observability.py`. KHÔNG neo
upstream (vắng). ZMQ+spawn+SHM cross-process ĐÃ verify từng phần (#05b T-B, zmq, #09) — ghép là rủi ro cần test.

## Glossary

- **composition-root**: nơi DUY NHẤT dựng + nối các thành phần cụ thể (profiles/) — không có logic nghiệp vụ.
- **camera worker**: process: source → ghi SHM (switchover-aware) → gửi InferenceRequest (frame_ref) → nhận detections.
- **full-stack test**: spawn cả hệ, chạy vài giây, assert frame chảy end-to-end + shutdown sạch.

## Requirements

### Requirement 1: Composition-root profile wire toàn chuỗi
**User Story:** Là kỹ sư, tôi muốn 1 điểm dựng toàn hệ, để chạy/kiểm end-to-end + làm nền product.
#### Acceptance Criteria
- 1.1 — `profiles/vision_fullstack_profile.py` PHẢI tạo RingPool + RingControlPlane + publish epoch đầu + endpoint ZMQ, rồi dùng `Supervisor` spawn camera-worker + inference-server (bulkhead 2 process).
- 1.2 — Composition-root PHẢI giữ pool creator-handle sống suốt phiên + `pool.close_all()` + cp cleanup lúc kết thúc.
- 1.3 — profiles/ là composition-root: KHÔNG logic nghiệp vụ, chỉ wire (giữ ranh giới layer).

### Requirement 2: Camera worker (process) — capture → SHM → infer
**User Story:** Là camera process, tôi muốn ghi frame vào SHM rồi xin inference, để có detections.
#### Acceptance Criteria
- 2.1 — Camera worker PHẢI: đọc frame (NoiseFrameSource) → ghi SHM qua `WriterEpochCoordinator` (switchover-aware) → tạo `InferenceRequest(frame_ref)` → `ZmqInferenceClient.infer` → nhận `InferenceResponse`.
- 2.2 — Camera worker PHẢI cooperative (poll shutdown_event #09) + đập heartbeat (#09b) → supervisor giám sát được.
- 2.3 — Camera worker PHẢI ghi số liệu (frames_ok / infer_ok / infer_err) ra artifact để test assert (metrics per-process — xem Q2).

### Requirement 3: Inference server (process) — tái dùng InferenceServer
**User Story:** Là inference process, tôi phục vụ detection cross-process, cách ly (bulkhead).
#### Acceptance Criteria
- 3.1 — Tái dùng `InferenceServer` (ZMQ ROUTER + ReaderEpochCoordinator switchover-aware + FakeDetector) — KHÔNG viết lại.
- 3.2 — Chạy dưới Supervisor như cooperative worker (đóng socket + teardown lúc shutdown).

### Requirement 4: Supervisor quản lý (bulkhead + heartbeat + graceful)
**User Story:** Là vận hành, tôi muốn 2 process được giám sát + tắt sạch, để hệ resilient.
#### Acceptance Criteria
- 4.1 — Supervisor spawn camera-worker + inference-server; heartbeat phát hiện hang (#09b); cascade cooperative-first (#09).
- 4.2 — 1 process crash → không kéo process kia (bulkhead) — supervisor restart theo cap.

### Requirement 5: Observability
**User Story:** Là vận hành, tôi muốn thấy số liệu luồng, để biết hệ khoẻ.
#### Acceptance Criteria
- 5.1 — Mỗi process dùng `setup_logging` (#08) + emit log có context (camera_id/request_id qua log_context) + đếm qua InMemoryMetrics (per-process).
- 5.2 — (Đóng phần K-017) backpressure metrics/counter được ghi nhận nếu dùng BoundedQueue trong camera worker (xem Q3).

### Requirement 6: Full-stack integration test THẬT
**User Story:** Là kỹ sư, tôi muốn bằng chứng end-to-end chạy được, để tin hệ ghép đúng.
#### Acceptance Criteria
- 6.1 — Test spawn toàn hệ (qua profile/supervisor), chạy ~1–2s, assert: camera worker `infer_ok >= 1` (frame chảy camera→SHM→inference→detections THẬT cross-process).
- 6.2 — Assert shutdown sạch (supervisor.run trả về, không hang; process kết thúc).
- 6.3 — Guard win32 (spawn; POSIX chưa verify).

## Non-Goals (HOÃN — chống phình)
Multi-camera scaling (N pool) · detector thật (YOLO) · RTSP thật · UI/API · deploy/CI · cross-process metrics
aggregation (Prometheus scrape) · CURVE auth · ghi hình/DB.

## Tiêu chí ĐẬU (Definition of Done)
profile + camera-worker + full-stack test THẬT (infer_ok>=1 cross-process, shutdown sạch); tái dùng
InferenceServer/Supervisor/coordinator (không viết lại); lint 5/0; mọi test cũ giữ xanh; không claim xong khi chưa chạy test (§5).
