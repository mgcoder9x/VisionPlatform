# Design Document — backpressure-cross-process

## Overview

Tính năng đóng **A2** (mất frame im lặng khi inference chậm hơn capture) và **A3** (ZMQ không set HWM tường minh). Đã chốt **Mô hình A — backpressure BOUND TRƯỚC KHI GỬI (bound-before-send)** sau phân tích doubt-driven dựa trên đọc code thật.

**Lý do gốc (không fix ngọn):** `InferenceServer` (ROUTER, single-thread) **không hủy được request đã nhận** — request đã gửi qua ZMQ chắc chắn bị xử lý. Nếu chỉ bound *in-flight đã gửi* (Mô hình B), việc "bỏ frame cũ nhất" chỉ ngừng theo dõi response mà server VẪN tốn sức inference frame cũ → không giảm tải, không đóng A2. Do đó điều tiết PHẢI xảy ra **trước khi chạm socket**: chỉ gửi request mới khi `In_Flight_Count < window_size` (flow-control); frame vượt cửa sổ nằm trong **hàng đợi outbound có giới hạn** và bị `Backpressure_Policy` xử lý (đếm được) trước khi gửi.

Thay đổi là **additive tuyệt đối**: giữ API `infer()` sync hiện có (các test cũ không đổi), THÊM đường async `submit()`/`poll_responses()`. Baseline phải giữ **436 passed / 1 skipped · lint 5/0**.

## 2. Bằng chứng code đã đọc (chống bịa)

- `adapters/zmq_inference_client.py`: `_outbound: queue.Queue[bytes] = queue.Queue()` — **KHÔNG bound**; `_io_loop` rút cạn outbound gửi hết mỗi vòng (`while True: self._sock.send(self._outbound.get_nowait())`); `infer()` **sync blocking** qua slot `_pending[request_id] = queue.Queue(maxsize=1)`; **KHÔNG set** `SNDHWM`/`RCVHWM`; DEALER; `setup()` gọi `connect()` rồi start thread `_io_loop`.
- `application/inference_server.py`: ROUTER **single-thread**, vòng `poll → recv_multipart → _handle(detect) → send_multipart`; **không có cơ chế hủy request đã nhận**.
- `kernel/backpressure.py`: `BoundedQueue(maxsize, policy)` **thread-safe** (Lock/Condition), 4 policy `DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT`, `put()` DROP_OLDEST = `popleft()` rồi `append()` + `drops += 1` **trả True** (nhận item mới); đếm sẵn `drops`/`rejects`/`block_timeouts`; **cấm dùng cross-process** (K-016) — nhưng client là **1 process** (thread capture ⊥ thread io) nên hợp lệ.
- `kernel/inference_protocol.py`: `InferenceRequest(request_id, source_id, frame_ref)`, `InferenceResponse(request_id, detections, error)`, `InferenceError(error_type, error_message, retryable)`, `Detection(label, confidence, box)`, `InferenceResponse.is_success`. Tất cả frozen, thuần kernel.
- `adapters/fake_detector.py`: `FakeDetector` **hiện KHÔNG có tham số delay** — `detect()` tính brightness. Cần thêm `delay_s` (additive).
- `adapters/noise_frame_source.py` + `kernel/read_result.py`: nguồn = dataclass, `setup()/read(timeout_ms)->ReadResult/teardown()`; `ReadResult(status, data, error, retry_after_ms)` + `has_data`; `ReadStatus.FRAME/EOF/...`. `Push_Frame_Source` bám đúng interface này.
- `profiles/vision_fullstack_profile.py::camera_worker`: hiện gọi `resp = client.infer(...)` **blocking** trong vòng; backpressure hiện chỉ ở tầng SHM ring (`wcoord.write()` trả None khi đầy).
- `tests/test_zmq_inference_cross_process.py` + `tests/zmq_server_worker.py::inference_server_worker(..., detector_kind)`: harness spawn sẵn (`_harness`, `detector_kind` ∈ {"fake","crash"}). Sẽ THÊM `detector_kind="slow"` + ca backpressure.

## Architecture

```
[Camera thread]                          [Client IO thread (sở hữu DEALER)]        [Server process]
 source.read() ──frame──► submit(req) ─► BoundedQueue(maxsize=Q, policy)           ROUTER single-thread
   frames_captured++         (non-blocking)      │                                   recv→detect→send
                                                  │  while in_flight < window_size:
                                                  │     req = queue.get_nowait()
                                                  │     send(req); pending[id]=ts
                                                  │     in_flight++; frames_submitted++
                                                  ▼
                          policy khi đầy:   poll recv ─► response ─► _responses (thread-safe)
                          DROP_OLDEST evict          pending.pop(id); in_flight--
                          frame CHƯA GỬI cũ nhất     ok/err/timeout++
                          frames_dropped++
 poll_responses() ◄──────────────────────────────── drain _responses
   cập nhật ok/err/timeout (đã do io thread đếm)
```

Hai "van" điều tiết phối hợp:
1. **Van hàng đợi (queue, maxsize=Q):** chặn phình bộ nhớ + là nơi áp policy. DROP_OLDEST evict frame **chưa gửi** cũ nhất → drop sạch.
2. **Van flow-control (in_flight < window_size):** chặn làm ngập server (đóng A2 gốc). Nếu KHÔNG có van này, io thread gửi hết → tràn RCVHWM server → drop im lặng (đúng bug A2).

> **Vì sao cần CẢ HAI:** nếu chỉ có van flow-control mà không có hàng đợi, khi in-flight đầy thì "frame cũ nhất để bỏ" lại là frame **đã gửi** → rơi về Mô hình B (không hủy được). Hàng đợi giữ các frame **chưa gửi** để DROP_OLDEST có cái để evict sạch. Nếu chỉ có hàng đợi mà không flow-control, io thread gửi hết ngay → hàng đợi luôn rỗng → không bao giờ drop ở client → A2 còn nguyên ở server.

## Components and Interfaces

Thành phần theo layer (tôn trọng import-linter 6 layer).

### 4.1 kernel — `Metric_DTO` (R5.5, R9.1)
`kernel/backpressure_metrics.py` (mới) — dataclass **thuần Python**, KHÔNG import zmq/torch/cv2/mp/shm:
```python
@dataclass(frozen=True)
class BackpressureMetrics:
    frames_captured: int
    frames_submitted: int
    frames_dropped_backpressure: int
    infer_ok: int
    infer_err: int
    infer_timeout: int

    @property
    def conserved(self) -> bool:            # bất biến bảo toàn (R4.3)
        return self.frames_submitted + self.frames_dropped_backpressure == self.frames_captured
```
`BoundedQueue` (đã có) **tái dùng nguyên**, không sửa (giữ policy-agnostic — R3.2).

### 4.2 adapters — `ZmqInferenceClient` (mở rộng additive)
Thêm tham số khởi tạo: `window_size: int = 8`, `queue_maxsize: int | None = None` (mặc định = `window_size`), `policy: BackpressurePolicy = DROP_OLDEST`, `sndhwm: int = 1000`, `rcvhwm: int = 1000`.

- `setup()` (R6): set **trước `connect()`**: `sock.setsockopt(zmq.SNDHWM, self._sndhwm)`, `sock.setsockopt(zmq.RCVHWM, self._rcvhwm)` → rồi `connect()` → start io thread. (Thứ tự R6.3.)
- Nội bộ thay `_outbound: queue.Queue` (đường async) bằng `_outbound = BoundedQueue(queue_maxsize, policy)` chứa `InferenceRequest` (không phải bytes — để đếm/evict theo frame). Đường `infer()` cũ giữ nguyên hành vi (xem 4.2.b).
- **API async mới:**
  - `submit(request) -> bool` — **non-blocking**. `accepted = self._outbound.put(request)` (BLOCK-policy dùng `put(request, timeout=...)`). Trả `accepted`. Đây là điểm áp policy → `frames_dropped` = `self._outbound.drops + self._outbound.rejects` (đọc từ BoundedQueue).
  - `poll_responses() -> list[InferenceResponse]` — drain `_responses` (thread-safe `queue.Queue`), non-blocking.
  - `in_flight` (property) — đọc số slot đang chờ (chỉ io thread ghi).
  - `metrics_snapshot() -> BackpressureMetrics` — gộp bộ đếm client (submitted/ok/err/timeout/dropped); `frames_captured` do camera_worker cung cấp (xem 4.3).
- **io_loop mới (giữ pattern socket-owner-thread):**
  1. **Gửi có flow-control:** `while self._in_flight < self._window_size:` thử `req = self._outbound.get_or_raise(timeout=0)`; hết → break. Có req → `send(packb(req))`, `self._pending[req.request_id] = (slot?, monotonic())`, `self._in_flight += 1`, `self._sent += 1` (**frames_submitted đếm TẠI ĐÂY**).
  2. **Nhận:** poll `poll_ms`; có POLLIN → `recv` → unpack → `pending.pop(id)` → `self._in_flight -= 1` → phân loại `infer_ok/infer_err` (theo `is_success`) → đẩy response vào `_responses`.
  3. **Quét timeout (R5.4):** với mỗi pending quá `timeout_s` → tạo `InferenceResponse(error=InferenceError("Timeout",...,retryable=True))`, `infer_timeout += 1`, `in_flight -= 1`, đẩy vào `_responses`, xoá pending.
- **Đếm `frames_submitted` TẠI LÚC GỬI, KHÔNG lúc enqueue** (điểm correctness cốt lõi): nếu đếm lúc enqueue, DROP_OLDEST evict một frame đã tính submitted → đếm trùng → vỡ bất biến. Vì hàng đợi chỉ chứa frame **chưa gửi**, frame bị evict chưa từng được tính submitted → mỗi captured frame được tính **đúng một** trong {submitted, dropped}.

#### 4.2.b Tương thích ngược `infer()` (sync)
Giữ nguyên chữ ký + hành vi hiện tại cho các test cũ (`test_zmq_inference_cross_process.py` 5 test). Cách an toàn nhất: `infer()` **không** đi qua van flow-control/hàng đợi bound (nó là đường "1 request đồng bộ" cũ). Tách rõ hai đường: đường async (submit/poll) dùng BoundedQueue + flow-control; đường sync (infer) giữ logic slot cũ. → Không đụng test cũ (giữ 436/1). Chi tiết ranh giới thực thi sẽ ở tasks.md (đảm bảo io thread phục vụ cả hai không tranh chấp socket — vẫn 1 thread sở hữu socket).

### 4.3 adapters — `FakeDetector` thêm `delay_s` (R7.3)
Thêm `__init__(self, *, delay_s: float = 0.0)`; trong `detect()` nếu `delay_s > 0` → `time.sleep(delay_s)` trước khi trả. Mặc định 0.0 → **không đổi hành vi test cũ**. Không cần torch/GPU.

### 4.4 adapters — `Push_Frame_Source` (R7.1, R7.2)
Nguồn dạng đẩy nhịp cố định, bám interface `setup()/read()->ReadResult/teardown()`:
- `PushFrameSource(width, height, max_frames: int = M, interval_s: float = 0.0, seed=...)`.
- `read()`: nếu đã phát đủ `max_frames` → `ReadResult(EOF)`; nếu `interval_s>0` → điều nhịp bằng đồng hồ (phát frame kế khi tới hạn, chưa tới hạn → `ReadResult(TIMEOUT)` để camera loop tiếp tục mà không tiêu thụ) → **nhịp độc lập tốc độ tiêu thụ** (R7.2). Frame deterministic (vd giá trị = chỉ số frame) để test kiểm recency (R8.4).

### 4.5 profiles — `camera_worker` chuyển sang async submit + cấm BLOCK cho RTSP
- Vòng mới: `r = source.read()` → nếu `has_data`: `frames_captured += 1`; `wcoord.write` → ref; `client.submit(InferenceRequest(...))`; luôn `for resp in client.poll_responses(): phân loại`. Không còn `infer()` blocking → camera không bị chặn (R1).
- Sau khi nguồn EOF/shutdown: **drain** — tiếp tục `poll_responses()` tới khi `client.in_flight == 0` và hàng đợi outbound rỗng → mọi frame chưa gửi được gửi nốt (submitted) → bất biến đúng SAU vòng lặp (R4.3). (Không đếm shutdown-leftover là dropped.)
- Ghi `BackpressureMetrics` ra artifact (tái dùng cơ chế `_write_result` — mở rộng thêm field) để test cross-process đọc sau shutdown.
- **Cấm BLOCK cho RTSP (R3):** đặt ở **tầng cấu hình per-source** (khi map config→client), KHÔNG ở BoundedQueue. Điểm thực thi: `pipeline_factory`/nơi dựng client từ config — nếu `source.type == "rtsp"` và `policy == BLOCK` → raise `ConfigError` với thông điệp rõ. (R3.2: BoundedQueue giữ policy-agnostic.)

## Data Models

- **`BackpressureMetrics`** (kernel, mới — mục 4.1): frozen dataclass 6 field int (`frames_captured`, `frames_submitted`, `frames_dropped_backpressure`, `infer_ok`, `infer_err`, `infer_timeout`) + property `conserved`. Thuần Python, không phụ thuộc zmq/torch (R5.5, R9.1).
- **Tái dùng không đổi:** `InferenceRequest(request_id, source_id, frame_ref)`, `InferenceResponse(request_id, detections, error)`, `InferenceError(error_type, error_message, retryable)`, `Detection(label, confidence, box)` — `kernel/inference_protocol.py`. `BoundedQueue(maxsize, policy)` + `BackpressurePolicy` — `kernel/backpressure.py` (đếm sẵn `drops`/`rejects`/`block_timeouts`).
- **Wire format:** msgpack (do adapter ZMQ xử lý, đã có `inference_wire_codec`) — không đổi.

## Hạch toán frame & bất biến bảo toàn (R4)

| Sự kiện | Bộ đếm | Nơi đếm |
|---|---|---|
| `source.read()` có data | `frames_captured += 1` | camera thread |
| io thread GỬI request tới server | `frames_submitted += 1` | io thread (lúc send) |
| policy evict/reject frame **chưa gửi** | `frames_dropped_backpressure` = `queue.drops + queue.rejects` | BoundedQueue |
| response thành công | `infer_ok += 1` | io thread |
| response lỗi (không timeout) | `infer_err += 1` | io thread |
| pending quá hạn | `infer_timeout += 1` | io thread (quét) |

**Bất biến** `frames_submitted + frames_dropped_backpressure == frames_captured` đúng **sau khi drain** (mọi frame chưa gửi hoặc đã được gửi=submitted hoặc đã bị evict=dropped; không frame nào ở trạng thái lửng). An toàn thread: mỗi bộ đếm chỉ ghi bởi **một** thread (captured=camera; submitted/ok/err/timeout=io; dropped=BoundedQueue-lock); đọc snapshot **sau khi** thread quiesce (teardown) → không cần khoá gộp.

## 6. ZMQ HWM (R6)
`setup()` set `SNDHWM`/`RCVHWM` (cấu hình, ≥1) **trước `connect()`**. Server (`inference_server.py`) cũng nên set RCVHWM/SNDHWM trước `bind()` — bổ sung additive (R6 nói Inference_Client; server set thêm để hành vi đối xứng, ghi rõ là mở rộng). Không đổi contract layer (zmq vẫn chỉ ở adapters/application).

## Error Handling

- **Server chết / không phản hồi:** io thread quét pending quá `timeout_s` → sinh `InferenceResponse(error=InferenceError("Timeout", retryable=True))`, `infer_timeout += 1`, `in_flight -= 1` → camera không hang (bảo toàn hành vi `infer()` cũ, test Property 5 hiện có).
- **Response lỗi không-timeout:** `is_success == False` và không phải timeout → `infer_err += 1` (vd detector ném = retryable False; stale SHM = retryable True — tái dùng phân loại server hiện có).
- **Hàng đợi outbound đầy:** áp `Backpressure_Policy` (DROP_OLDEST/DROP_NEWEST/REJECT đếm `frames_dropped_backpressure`; BLOCK chờ) — KHÔNG ném lỗi lên camera (camera không bị chặn ngoài trường hợp BLOCK cố ý).
- **Cấu hình sai (RTSP + BLOCK):** fail-fast `ConfigError` tại tầng dựng-từ-config, trước khi chạy (R3).
- **Teardown:** drain outbound + chờ `in_flight == 0` để bất biến đúng sau vòng lặp; `teardown()` client đóng socket/ctx như hiện tại (LINGER 0).

## Correctness Properties

### Property 1: Bảo toàn
Sau drain, `frames_submitted + frames_dropped_backpressure == frames_captured`.

**Validates: Requirements 4.3, 8.1**

### Property 2: Không tràn server
`in_flight` KHÔNG bao giờ vượt `window_size` tại mọi thời điểm.

**Validates: Requirements 1.3**

### Property 3: DROP_OLDEST recency
Dưới quá tải, tập frame **được gửi** là các frame **mới hơn**; frame chưa-gửi cũ nhất bị evict trước. Frame bị evict **không** tới server.

**Validates: Requirements 2.2, 8.4**

### Property 4: BLOCK không drop
Với BLOCK trên nguồn non-RTSP, `frames_dropped_backpressure == 0`.

**Validates: Requirements 2.5, 8.3**

### Property 5: Response đầy đủ
Mỗi request đã gửi → đúng một kết cục (ok/err/timeout); sau drain `in_flight == 0`.

**Validates: Requirements 1.4, 5.1**

### Property 6: HWM trước connect
SNDHWM/RCVHWM được set (giá trị cấu hình ≥1) TRƯỚC connect.

**Validates: Requirements 6.1**

### Property 7: RTSP+BLOCK bị từ chối
Dựng client RTSP với BLOCK → `ConfigError`.

**Validates: Requirements 3.1**

### Property 8: Kiến trúc
Kernel không import zmq/torch/cv2/mp/shm; adapters leaf; lint 5/0; full suite 436/1 giữ nguyên (+ test mới).

**Validates: Requirements 9.1**

## Testing Strategy

### 8.1 Unit xác định (không ZMQ/process) — chốt logic hạch toán
Test `submit()`/`poll` + hạch toán bằng **fake transport** hoặc gọi thẳng BoundedQueue để loại bỏ đua timing:
- **T-P1/P3 (DROP_OLDEST):** dựng `_outbound = BoundedQueue(1, DROP_OLDEST)`, mô phỏng io thread "kẹt" (in_flight đầy) → submit M frame đánh số 0..M-1 → chỉ frame mới nhất còn trong hàng đợi; `drops == M-1`; kiểm frame còn lại là frame mới nhất (recency). Không sleep-đua.
- **T-P4 (BLOCK):** BoundedQueue(k, BLOCK) non-RTSP → producer/consumer điều khiển tay → `drops == 0`.
- **T bảo toàn (P1):** mô phỏng đầy đủ vòng captured→submit→send(drain) → `metrics.conserved is True` cho nhiều `(M, window_size, Q, policy)` (property-based Hypothesis, tất cả deterministic — không phụ thuộc thời gian).

### 8.2 Cross-process spawn (R8.5) — mở rộng `test_zmq_inference_cross_process.py`
- Thêm `detector_kind="slow"` trong `tests/zmq_server_worker.py` → `FakeDetector(delay_s=...)`.
- Ca mới: server slow + client `window_size=W`, `policy=DROP_OLDEST`, `Q` nhỏ; parent ghi **M** frame vào SHM và `submit()` **nhanh hơn** server xử lý → quá tải chắc chắn (do delay*M ≫ thời gian submit). Sau đó drain. Kiểm:
  - **P1:** `captured == submitted + dropped` (đọc từ metrics/artifact).
  - **R8.2:** `dropped > 0` và bằng `queue.drops+rejects` (tự nhất quán — KHÔNG assert số cố định, tránh flaky).
  - **P5:** `in_flight == 0` sau drain; mỗi request có kết cục.
- **Chống flaky:** assert **bất biến** (luôn đúng bất kể timing) + **dropped>0** (được bảo đảm bằng cách chọn delay/M/W sao cho quá tải là **tất yếu**, không phải xác suất). KHÔNG assert số drop chính xác. Guard `sys.platform == "win32"` như các test hiện có (POSIX chưa verify — trung thực).

### 8.3 Baseline & lint (R9)
Sau khi thêm: chạy full `pytest -q` kỳ vọng ≥ 436 passed (thêm test mới) / 1 skipped; `import-linter` qua `importlinter.api` = 5 kept/0 broken (né AV, K-044).

## 9. Ghi chú requirements
`requirements.md` ĐÃ được cập nhật khớp Mô hình A (Introduction + glossary `Submission_Window`/`In_Flight_Count` + R1 + R2.2–2.5). R3/R4/R5/R6/R7/R8/R9 giữ nguyên và vẫn đúng dưới Mô hình A. **Điểm cần lưu khi làm tasks:** R4.2 "frames_submitted khi submit vào Submission_Window" hiểu chính xác = **đếm lúc GỬI tới server** (mục 4.2/5), không phải lúc enqueue — nếu không sẽ vỡ bất biến dưới DROP_OLDEST.

## 10. Non-goals (nhắc lại)
Không multi-camera N-pool; không thay Noise/Fake bằng RTSP/YOLO thật; không đưa zmq/torch vào kernel; không hợp nhất metrics cross-process (đọc qua artifact như profile hiện tại).
