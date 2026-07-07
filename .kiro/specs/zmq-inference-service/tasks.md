# Implementation Plan

> Neo: requirements.md (R1–R9) + design.md (QĐ-1..5, Property 1..7). TDD, slice nhỏ, verify thật mỗi slice.
> User đã duyệt Q1–Q4 (pyzmq+msgpack · tcp loopback · threading correlation · server single-thread v1).

## Overview

Xây inference cross-process ZMQ: codec (kernel) → port → client (adapters) → server (application) → test
cross-process (gồm switchover đóng K-023a). Mỗi slice chạy test thật mới sang slice kế.

## Tasks

- [x] 1. Thêm dependency + verify import
  - Thêm `pyzmq` + `msgpack` vào `[project] dependencies`; `pip install`; verify `import zmq, msgpack`. (pyzmq 27.1.0, msgpack 1.2.1)
  - _Requirements: 2, 6_

- [x] 2. Wire codec DTO↔dict (kernel, thuần) + test round-trip
  - `kernel/inference_wire_codec.py` (KHÔNG msgpack). `tests/test_zmq_codec.py` (5 test, Property 6 + inline thoả port).
  - _Requirements: 6.1, 6.2_

- [x] 3. Port `IInferenceClient` (kernel/ports) + inline thoả port
  - `kernel/ports/inference_client.py` (Protocol). `test_inline_client_satisfies_port` pass.
  - _Requirements: 1.1, 1.2_

- [x] 4. `ZmqInferenceClient` (adapters) — DEALER + correlation threading
  - `adapters/zmq_inference_client.py`: socket-owner-thread (ZMQ không thread-safe) + map {request_id: Queue(1)}, timeout→retryable=True.
  - _Requirements: 1.3, 2.2, 3, 5.1, 7.2_

- [x] 5. `InferenceServer` (application) + worker module — ROUTER + switchover-aware
  - `application/inference_server.py` + `tests/zmq_server_worker.py`. ReaderEpochCoordinator (K-023a); retryable đúng (K-023b).
  - _Requirements: 2.1, 4, 5, 7.1, 8_

- [x] 6. Test cross-process THẬT (spawn)
  - `test_zmq_inference_cross_process.py` (Property 1/3/4/5, 4 test) + `test_zmq_switchover.py` (**Property 2** đóng K-023a, 1 test). 5/5 pass.
  - _Requirements: 2.3, 3, 4, 5, 7_

- [x] 7. Contract import-linter + negative-test
  - Thêm `msgpack` vào forbidden domain+kernel (zmq đã có sẵn); negative-test: `import msgpack` ở codec → lint BROKEN → gỡ → 5 kept/0 broken.
  - _Requirements: (kiến trúc, giữ ranh giới)_

- [x] 8. Regression cuối
  - Full `pytest` = **300 passed, 1 skipped**; `lint-imports` 5 kept/0 broken; inline #06 giữ 9 test. Journal/log/tracker cập nhật.
  - _Requirements: Tiêu chí ĐẬU_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2", "3"], "note": "deps + codec (kernel thuần) + port — in-process, low-risk" },
    { "wave": 2, "tasks": ["4"], "note": "ZmqInferenceClient (DEALER + correlation threading) — cần codec+port" },
    { "wave": 3, "tasks": ["5"], "note": "InferenceServer (ROUTER + switchover-aware) + worker module — cần client+codec" },
    { "wave": 4, "tasks": ["6", "7", "8"], "note": "test cross-process + switchover (Property 2) + contract/negative-test + regression cuối" }
  ]
}
```

> wave_2 cần wave_1 (codec+port); wave_3 cần wave_2 (client để test đối); wave_4 cần wave_3.
> Test switchover (Property 2, task 6) là **cổng chấp nhận** đóng K-023a — chỉ đóng sub-spec khi có bằng chứng chạy thật.

## Notes

- Slice 2,3 in-process (nhanh, low-risk) làm trước → 4,5 (ZMQ) → 6 (cross-process spawn, chậm ~vài giây).
- Test switchover (Property 2) là bằng chứng cốt lõi đóng K-023a — ưu tiên đúng.
- Không claim "xong" khi chưa chạy test thật (§5). ZMQ/spawn Windows [chưa kiểm] tới khi test pass.
