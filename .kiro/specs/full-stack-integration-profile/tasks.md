# Implementation Plan

## Overview

Capstone WIRE toàn chuỗi thành 1 composition-root `profiles/vision_fullstack_profile.py` (self-contained) +
1 full-stack integration test. Tái dùng component đã có (InferenceServer/Supervisor/coordinator/client) —
KHÔNG viết lại. TDD-lite: viết profile + test cùng lúc, verify bằng chạy THẬT (spawn cross-process, guard win32).

Trạng thái: **HOÀN TẤT** — 307 passed/1 skipped · lint 5/0 · full-stack infer_ok≥1 cross-process.

## Tasks

- [x] 1. Verify chữ ký API thật của mọi component sẽ WIRE (đọc file, không tin summary)
  - Đọc: inference_server.py, supervisor.py, writer_epoch_coordinator.py, ring_pool.py, ring_control_plane.py,
    zmq_inference_client.py, inference_protocol.py, noise_frame_source.py, read_result.py, observability.py.
  - Verify contract import-linter: profiles KHÔNG là source của contract nào → import mọi layer hợp lệ.
  - _Requirements: R1.3, R3.1_

- [x] 2. Composition-root + worker-entry self-contained trong `profiles/vision_fullstack_profile.py`
  - `_free_port()` / `_write_result()` / `parse_result()` helper.
  - `inference_server_entry(shutdown_event, ...)`: cp(create=False)+opener+ReaderEpochCoordinator+FakeDetector+InferenceServer.serve.
  - `camera_worker(shutdown_event, heartbeat, ...)`: NoiseFrameSource→WriterEpochCoordinator.write(SHM)→ZmqInferenceClient.infer; cooperative+heartbeat; ghi artifact lúc finally.
  - `run_profile(duration_s, ...)`: RingPool+RingControlPlane(publish epoch1)+endpoint+Supervisor(2 WorkerSpec bulkhead)+run+cleanup.
  - _Requirements: R1.1, R1.2, R1.3, R2.1, R2.2, R2.3, R3.1, R3.2, R4.1, R4.2, R5.1_

- [x] 3. Full-stack integration test THẬT `tests/test_fullstack_integration.py` (guard win32)
  - `run_profile(3.0, result_path=...)` → assert frames_ok≥1 + infer_ok≥1 (Property 1) + run trả về (Property 2).
  - _Requirements: R6.1, R6.2, R6.3_

- [x] 4. Verify + regression
  - Chạy `pytest tests/test_fullstack_integration.py` → PASS (13.29s).
  - Full suite `pytest -q` → 307 passed/1 skipped. Lint `lint-imports` → 5 kept/0 broken. getDiagnostics 0.
  - _Requirements: Definition of Done_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2"] },
    { "wave": 3, "tasks": ["3"] },
    { "wave": 4, "tasks": ["4"] }
  ]
}
```

Task 1 (verify API) → Task 2 (profile) → Task 3 (test) → Task 4 (verify+regression). Tuần tự, không song song.

## Notes

- **Điều chỉnh vs design PHA-1 (C-011):** worker-entry đặt trong profile module (self-contained, shippable),
  KHÔNG ở `tests/` — vì `src` không import được `tests` + module test không ship.
- **Q1–Q3 chốt:** 1 camera+1 server · verify artifact-file · hoãn BoundedQueue (backpressure tự nhiên ring-đầy).
- **Timing (chống flaky):** client timeout_s=5.0; heartbeat_timeout_s=20.0 (>timeout → block infer lúc startup
  KHÔNG bị coi hang); shutdown_grace_s=8.0 (>timeout → camera kịp thoát + ghi artifact lúc finally); n_slots=8.
- **Guard win32:** SHM+ZMQ+spawn verify từng phần Windows; POSIX chưa verify (Non-goal).
- **Còn mở (bản sau):** multi-camera (N pool), BoundedQueue wire (K-017), cross-process metrics aggregation, detector thật.
