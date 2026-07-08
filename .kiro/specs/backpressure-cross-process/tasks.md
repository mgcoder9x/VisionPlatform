# Implementation Plan — backpressure-cross-process

> Mô hình A (bound-before-send). ADDITIVE tuyệt đối: giữ baseline **436 passed / 1 skipped · lint 5/0**.
> Môi trường verify: Windows, CWD `vision-platform/`, `.venv\Scripts\python.exe -m pytest -q`;
> lint qua `importlinter.api` (né AV, K-044). Không GPU/torch trên máy dev → mọi test chạy fake/CPU.
> TDD: viết test trước hoặc cùng lúc; mỗi task xong chạy full pytest + lint. Test cross-process guard `win32`.
> **Chống flaky:** assert BẤT BIẾN + `dropped>0` (chọn delay/M/window để quá tải TẤT YẾU), KHÔNG assert số drop cố định.

## Overview

Triển khai Mô hình A (bound-before-send) theo 5 wave, additive tuyệt đối. Wave 1 (kernel DTO) độc lập; Wave 2 (adapters) phụ thuộc Wave 1 cho phần metrics; Wave 3 (profiles/config) phụ thuộc Wave 2; Wave 4 (test cross-process) phụ thuộc Wave 2+3; Wave 5 nghiệm thu baseline.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"], "dependsOn": [] },
    { "wave": 2, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5"], "dependsOn": ["1"] },
    { "wave": 3, "tasks": ["3.1", "3.2"], "dependsOn": ["2.4", "2.5"] },
    { "wave": 4, "tasks": ["4"], "dependsOn": ["2.1", "2.2", "3.1"] },
    { "wave": 5, "tasks": ["5"], "dependsOn": ["3.1", "3.2", "4"] }
  ],
  "edges": [
    { "from": "1", "to": "2.1" },
    { "from": "1", "to": "2.2" },
    { "from": "1", "to": "2.3" },
    { "from": "2.3", "to": "2.4" },
    { "from": "2.4", "to": "2.5" },
    { "from": "2.5", "to": "3.1" },
    { "from": "2.5", "to": "3.2" },
    { "from": "2.1", "to": "4" },
    { "from": "2.2", "to": "4" },
    { "from": "3.1", "to": "4" },
    { "from": "3.1", "to": "5" },
    { "from": "3.2", "to": "5" },
    { "from": "4", "to": "5" }
  ]
}
```

Thứ tự bắt buộc tuần tự trong nhánh chính: `1 → 2.3 → 2.4 → 2.5 → 3.1 → 4 → 5`. Các task `2.1`, `2.2` (adapters độc lập) và `3.2` (config) chèn song song khi phụ thuộc sẵn sàng.

## Tasks

### Wave 1 — kernel (nền, độc lập)

- [x] 1. `BackpressureMetrics` DTO ở kernel
  - Tạo `src/vision_platform/kernel/backpressure_metrics.py`: `@dataclass(frozen=True) BackpressureMetrics` với 6 field `frames_captured/frames_submitted/frames_dropped_backpressure/infer_ok/infer_err/infer_timeout` (int) + property `conserved` (`frames_submitted + frames_dropped_backpressure == frames_captured`).
  - CHỈ import `dataclasses` (thuần Python) — KHÔNG zmq/torch/cv2/mp/shm (R9.1).
  - Test `tests/test_backpressure_metrics.py`: (a) `conserved` True khi bằng, False khi lệch; (b) frozen (gán field → raise); (c) giá trị field giữ đúng.
  - Verify: `pytest tests/test_backpressure_metrics.py -q` PASS; full suite không giảm; lint 5/0.
  - _Requirements: 5.5, 4.3, 9.1_
  - _Properties: P1, P8_

### Wave 2 — adapters (leaf; 2.1/2.2 song song được, 2.3–2.5 tuần tự vì cùng file client)

- [x] 2.1 `FakeDetector.delay_s` (additive)
  - Thêm `__init__(self, *, delay_s: float = 0.0)`; trong `detect()` nếu `delay_s > 0` → `time.sleep(delay_s)` trước khi trả. Mặc định 0.0 → hành vi cũ KHÔNG đổi.
  - Test: `delay_s=0` giữ nguyên output cũ (1 detection, confidence=brightness/255); `delay_s>0` → thời gian `detect()` ≥ delay (đo bằng monotonic, ngưỡng nới rộng để không flaky). Không cần torch/GPU.
  - Verify: pytest file + full suite; lint 5/0 (adapters vẫn leaf).
  - _Requirements: 7.3_

- [x] 2.2 `PushFrameSource` (nguồn đẩy nhịp cố định)
  - Tạo `src/vision_platform/adapters/push_frame_source.py`: bám interface `setup()/read(timeout_ms)->ReadResult/teardown()` (như `NoiseFrameSource`). Params `width,height,max_frames:int,interval_s:float=0.0,seed`. `read()`: phát đủ `max_frames` → `ReadResult(EOF)`; `interval_s>0` và chưa tới hạn → `ReadResult(TIMEOUT)` (nhịp độc lập tốc độ tiêu thụ); tới hạn → `ReadResult(FRAME, data)`. Frame deterministic (giá trị = chỉ số frame) để kiểm recency.
  - Test: phát đúng `M` frame FRAME + 1 EOF; với `interval_s>0` mô phỏng đồng hồ → nhịp không phụ thuộc tốc độ gọi; frame value tăng dần.
  - Verify: pytest file + full suite; lint 5/0.
  - _Requirements: 7.1, 7.2_

- [x] 2.3 `ZmqInferenceClient`: set HWM trước connect (đóng A3)
  - Thêm params `sndhwm:int=1000`, `rcvhwm:int=1000` (≥1). Trong `setup()`: `sock.setsockopt(zmq.SNDHWM, sndhwm)` + `sock.setsockopt(zmq.RCVHWM, rcvhwm)` **TRƯỚC** `sock.connect(endpoint)`.
  - Test: dựng client (không cần server), kiểm `sock.getsockopt(zmq.SNDHWM)/(zmq.RCVHWM)` == giá trị cấu hình sau `setup()`; teardown sạch. (Đường sync `infer()` cũ không đổi.)
  - Verify: pytest + full suite (5 test cross-process cũ vẫn PASS); lint 5/0.
  - _Requirements: 6.1, 6.2, 6.3_
  - _Properties: P6_

- [x] 2.4 `ZmqInferenceClient`: đường async `submit()` + flow-control + đếm submitted-tại-lúc-gửi
  - Thêm params `window_size:int=8`, `queue_maxsize:int|None=None` (mặc định = window_size), `policy:BackpressurePolicy=DROP_OLDEST`.
  - Nội bộ thêm `_outbound = BoundedQueue(queue_maxsize, policy)` chứa `InferenceRequest`; biến đếm `_in_flight`, `_sent` (chỉ io thread ghi).
  - `submit(request) -> bool`: non-blocking `self._outbound.put(request)` (BLOCK-policy dùng timeout) → trả accepted.
  - Sửa `_io_loop`: **gửi có flow-control** — `while self._in_flight < self._window_size:` lấy req từ `_outbound` (non-blocking, hết → break) → `send(packb(req))` → `_pending[req.request_id] = (slot?, monotonic())` → `_in_flight += 1` → `_sent += 1` (**đếm frames_submitted TẠI ĐÂY**, KHÔNG lúc enqueue). Giữ phần recv cũ; on response → `_pending.pop` → `_in_flight -= 1`.
  - `in_flight` property (đọc `_in_flight`).
  - **QUAN TRỌNG:** giữ nguyên hành vi `infer()` sync (tách khỏi đường async, cùng 1 io thread sở hữu socket — không tranh chấp). 5 test cross-process cũ KHÔNG đổi.
  - Unit test XÁC ĐỊNH (không đua timing): mô phỏng `_in_flight` đầy (van đóng) → `submit()` M frame đánh số 0..M-1 vào `BoundedQueue(1, DROP_OLDEST)` → chỉ frame mới nhất còn; `_outbound.drops == M-1`; frame còn lại là frame mới nhất (P3 recency, frame bị bỏ KHÔNG gửi).
  - Verify: pytest + full suite; lint 5/0.
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4_
  - _Properties: P2, P3_

- [x] 2.5 `ZmqInferenceClient`: `poll_responses()` + quét timeout + `metrics_snapshot()`
  - Thêm `_responses: queue.Queue` (thread-safe). io_loop: on recv response → phân loại `is_success` → `_ok += 1` / `_err += 1` → đẩy `InferenceResponse` vào `_responses`.
  - Quét timeout trong io_loop: pending quá `timeout_s` → tạo `InferenceResponse(error=InferenceError("Timeout",...,retryable=True))`, `_timeout += 1`, `_in_flight -= 1`, đẩy vào `_responses`, xoá pending.
  - `poll_responses() -> list[InferenceResponse]`: drain `_responses` non-blocking.
  - `metrics_snapshot() -> BackpressureMetrics`: gộp `_sent`(submitted), `_outbound.drops+_outbound.rejects`(dropped), `_ok/_err/_timeout`; `frames_captured` truyền vào (do camera đếm).
  - Unit test: (a) BLOCK policy non-RTSP → `dropped == 0` (P4); (b) bảo toàn (property-based Hypothesis, deterministic) — với nhiều `(M, window_size, Q, policy)` mô phỏng captured→submit→drain → `metrics.conserved is True` (P1); (c) poll trả đúng các response đã hoàn tất.
  - Verify: pytest + full suite; lint 5/0.
  - _Requirements: 1.4, 5.1, 5.2, 5.3, 5.4_
  - _Properties: P1, P4, P5_

### Wave 3 — profiles / config (phụ thuộc Wave 2)

- [x] 3.1 `camera_worker` chuyển sang async submit + drain + ghi metrics
  - Sửa vòng: `frames_captured += 1` mỗi frame có data; `client.submit(InferenceRequest(...))`; luôn `for resp in client.poll_responses(): phân loại ok/err/timeout`. Bỏ `infer()` blocking (camera không bị chặn — R1).
  - Sau EOF/shutdown: **drain** — tiếp tục `poll_responses()` tới khi `client.in_flight == 0` và outbound rỗng → mọi frame chưa gửi được gửi nốt → bất biến đúng SAU vòng lặp (R4.3). KHÔNG đếm leftover là dropped.
  - Mở rộng artifact (`_write_result`) ghi đủ 6 field `BackpressureMetrics` (thêm captured/submitted/dropped/timeout) — additive, `parse_result` đọc thêm.
  - Verify: `python -m vision_platform.profiles.vision_fullstack_profile --duration 3` chạy được (quan sát) + full suite (test fullstack cũ vẫn PASS) + lint 5/0.
  - _Requirements: 1.2, 4.1, 4.2, 4.3, 5.1_
  - _Properties: P1, P5_

- [x] 3.2 Cấm BLOCK cho nguồn RTSP ở tầng cấu hình
  - Ở nơi dựng client/pipeline từ config (per-source): nếu `source.type == "rtsp"` AND `policy == BackpressurePolicy.BLOCK` → raise `ConfigError` (thông điệp rõ nguyên nhân). KHÔNG đặt ràng buộc ở `BoundedQueue` (giữ policy-agnostic — R3.2).
  - Test: config RTSP+BLOCK → raise ConfigError khớp message; RTSP+DROP_OLDEST OK; non-RTSP+BLOCK OK.
  - Verify: pytest + full suite; lint 5/0.
  - _Requirements: 3.1, 3.2_
  - _Properties: P7_

### Wave 4 — test cross-process end-to-end (spawn)

- [x] 4. Backpressure end-to-end cross-process
  - Thêm `detector_kind="slow"` vào `tests/zmq_server_worker.py` → dùng `FakeDetector(delay_s=...)` (đủ chậm để quá tải tất yếu).
  - Mở rộng `tests/test_zmq_inference_cross_process.py` (guard `win32`): server slow + client `window_size=W`, `policy=DROP_OLDEST`, `queue_maxsize` nhỏ; parent ghi `M` frame vào SHM + `submit()` nhanh hơn server xử lý → quá tải. Sau đó drain.
  - Assert: **P1** `captured == submitted + dropped` (từ `metrics_snapshot()`); **R8.2** `dropped > 0` và bằng `_outbound.drops+_outbound.rejects` (tự nhất quán, KHÔNG số cố định); **P5** `in_flight == 0` sau drain, mỗi request có kết cục.
  - Verify: pytest file (win32) + full suite; lint 5/0.
  - _Requirements: 8.1, 8.2, 8.4, 8.5_
  - _Properties: P1, P5_

### Wave 5 — nghiệm thu baseline

- [x] 5. Verify toàn hệ + không hồi quy
  - Chạy `.venv\Scripts\python.exe -m pytest -q` → kỳ vọng **≥ 436 passed / 1 skipped** (cộng test mới), 0 fail.
  - Chạy lint qua `importlinter.api` → **5 kept / 0 broken** (kernel không import zmq/torch/cv2/mp/shm; adapters leaf).
  - Cập nhật `AI-IMPLEMENTATION-LOG.md` + `activeContext.md` + `progress.md` với baseline mới (số test thực).
  - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - _Properties: P8_

## Notes

- **ADDITIVE tuyệt đối:** giữ nguyên `infer()` sync + 5 test cross-process cũ; chỉ THÊM đường async. Mỗi task xong chạy full pytest + lint (5/0).
- **Verify = chạy thật + đọc output** (không "chắc pass"). Máy dev no-GPU/no-cam → chỉ verify được fake/CPU/parse; test cross-process guard `win32` (POSIX chưa verify — trung thực).
- **Chống flaky:** assert bất biến `submitted+dropped==captured` + `dropped>0` (chọn delay/M/window để quá tải TẤT YẾU); KHÔNG assert số drop cố định; ưu tiên unit xác định (không đua timing) trước, cross-process spawn sau.
- **`frames_submitted` đếm TẠI LÚC GỬI** (không lúc enqueue) — nếu sai sẽ vỡ bất biến dưới DROP_OLDEST (xem design §Data Models / mục 4.2).
- Server set HWM trước bind là bổ sung đối xứng ngoài R6 (R6 chỉ yêu cầu Inference_Client) — không bắt buộc, ghi rõ nếu làm.
