# Design Document

> **Trạng thái:** PHA 1 (design) — CHỜ user đọc-lại-valid + chốt Q1–Q4 (§ Testing/Open) trước khi tasks.md/code.
> **Neo:** requirements.md (R1–R9) + code thật (`ring_pool.py`, `reader_epoch_coordinator.py`,
> `inference_protocol.py`, `inline_inference_client.py`) + step-06 intent. KHÔNG neo upstream (vắng).
> **Cập nhật lúc:** 2026-07-04.

## Overview

Client (camera) ship `InferenceRequest` (có `frame_ref` trỏ SHM) qua ZMQ — KHÔNG gửi pixel. Server (process
riêng, bulkhead) đọc frame từ SHM **switchover-aware**, chạy `IDetector`, trả `InferenceResponse` echo
`request_id`. Đóng K-023: server dùng `ReaderEpochCoordinator` (không giữ reader cố định như inline #06) +
phân loại `retryable` đúng. Tách port `IInferenceClient` (inline + zmq cùng hợp đồng).

```
 CAMERA PROCESS (client)                      INFERENCE PROCESS (server, bulkhead)
 ┌───────────────────────────┐               ┌──────────────────────────────────────────┐
 │ writer → SHM ring (pool)   │               │ InferenceServer (application)              │
 │ ZmqInferenceClient(adapter)│               │  ROUTER ← DEALER                           │
 │  DEALER ──req(msgpack)────► │──ZMQ tcp─────►│  recv → codec → ReaderEpochCoordinator     │
 │  recv-thread ◄─resp────────│◄──────────────│      .read_ref(frame_ref) [switchover]     │
 │  correlation map           │               │    → IDetector.detect → codec → send       │
 └───────────────────────────┘               └──────────────────────────────────────────┘
   shared: RingControlPlane + RingPool.slot_locks_map() truyền qua Process spawn (như #05b T-B)
```

## Architecture

**Layer + import-linter (ép ranh giới):**

| Thành phần | File mới | Layer | Import chính | Vì sao |
|---|---|---|---|---|
| `IInferenceClient` (Protocol) | `kernel/ports/inference_client.py` | kernel/ports | inference_protocol | hợp đồng thuần |
| Wire codec DTO↔dict | `kernel/inference_wire_codec.py` | kernel | DTO + domain(BBox) | thuần, KHÔNG msgpack (QĐ-2) |
| `ZmqInferenceClient` | `adapters/zmq_inference_client.py` | **adapters** | kernel codec+DTO + zmq + msgpack | CHỈ transport, KHÔNG đọc SHM → leaf hợp lệ |
| `InferenceServer` | `application/inference_server.py` | **application** | runtime(make_pool_opener) + ReaderEpochCoordinator + IDetector + zmq + msgpack + codec | đọc SHM + điều phối |

Client ở adapters chỉ chạm kernel+zmq+msgpack (KHÔNG runtime) → contract #5 KEPT. Server ở application chạm
runtime+kernel (được). `InlineInferenceClient` (#06) cũng khai báo thoả port (additive, giữ 9 test).
⚠️ **[valid ở build]** thêm `zmq`+`msgpack` vào forbidden-list domain+kernel (chống rò xuống) như #05 làm với
multiprocessing (E-15) + negative-test chứng minh.

### QĐ-1 — Correlation THREADING (không asyncio)
Repo KHÔNG có asyncio (BoundedQueue #07=threading, supervisor #09=multiprocessing). → DEALER + 1 recv-thread +
map `{request_id: queue.Queue(1)}`; `infer()` gửi rồi block `q.get(timeout)`. Cùng hiệu quả async nhưng verify
được + nhất quán. `infer()` giữ chữ ký SYNC (khớp port + inline). Cái giá: 1 recv-thread/client.

### QĐ-2 — Codec 2 tầng: kernel (DTO↔dict thuần) + transport (dict↔msgpack)
`kernel/inference_wire_codec.py` chỉ DTO↔`dict` (KHÔNG import msgpack) → kernel dependency-free. msgpack
(dict↔bytes) ở rìa transport (client+server). Đổi msgpack→protobuf sau chỉ đổi rìa.

### QĐ-3 — Server SINGLE-THREADED (ZMQ socket không thread-safe) + backpressure qua poller/HWM
ZMQ socket chỉ dùng từ 1 thread → server vòng đơn `poller.poll(timeout)` → recv→process→send. `timeout` để
định kỳ kiểm `shutdown_event` (R7). Backpressure (R9): RCVHWM giới hạn recv-buffer + client timeout. BoundedQueue
multi-worker = biến thể mở rộng (Non-goal v1) vì đòi kiến trúc "socket-owner thread" phức tạp; v1 lo correctness+K-023.

### QĐ-4 — SHM cross-process qua `make_pool_opener` + `ReaderEpochCoordinator` (đóng K-023a)
Tái dùng NGUYÊN cơ chế #05b T-B (verify 5/5): composition root tạo `RingPool` → truyền `pool.slot_locks_map()`
cho server process qua `Process(args=)` (lock thừa kế). Server:
`opener = make_pool_opener(locks_map, n_slots, h, w, c)` → `coord = ReaderEpochCoordinator(control_plane, opener)`
→ `coord.bootstrap()` → mỗi request `coord.read_ref(frame_ref)` (tự `_maybe_switch` → switchover-aware; ref cũ→None stale-SAFE).

## Components and Interfaces

**`IInferenceClient` (kernel/ports):** `infer(request)->InferenceResponse`, `setup()`, `teardown()`.

**Client `infer(req)` (sync, blocking):**
1. `d = codec.request_to_dict(req)`; `payload = msgpack.packb(d)`.
2. `slot = Queue(1)`; `self._pending[req.request_id] = slot`.
3. `DEALER.send(payload)`.
4. `d2 = slot.get(timeout)` → timeout: `pop(id)`, trả `InferenceError(retryable=True,"timeout")`.
5. `return codec.dict_to_response(d2)`.

**Client recv-thread:** `while running: b=DEALER.recv(); d=unpackb(b); slot=self._pending.pop(d['request_id'],None); slot and slot.put(d)` (R3.3 bỏ an toàn nếu đã dọn).

**Server vòng chính (single-thread cooperative):**
```
coord.bootstrap()
while not shutdown_event.is_set():
  if ROUTER in poller.poll(poll_ms):
    ident, _, payload = ROUTER.recv_multipart()
    req = codec.dict_to_request(unpackb(payload))
    frame = coord.read_ref(req.frame_ref)                # switchover-aware (K-023a)
    if frame is None: resp = InferenceResponse(req.request_id, error=InferenceError("ShmReadFailed",...,retryable=True))  # K-023b
    else:
      try: resp = InferenceResponse(req.request_id, detections=tuple(detector.detect(frame)))
      except Exception as e: resp = InferenceResponse(req.request_id, error=InferenceError(type(e).__qualname__, str(e), retryable=False))
    metrics.counter("inference_requests_total", result=("ok" if resp.is_success else "err"))
    ROUTER.send_multipart([ident, b"", packb(codec.response_to_dict(resp))])
# finally: ROUTER.close(); detector.teardown()  (pool.close_all ở composition root)
```

## Data Models

Codec `dict` (msgpack-friendly, thuần Python):
- `BBox` ↔ `{x,y,w,h,space: CoordinateSpace.value}` (enum↔`.value` string).
- `ShmFrameRefData` ↔ `{ring_name,slot,generation,height,width,channels,ring_epoch}`.
- `Detection` ↔ `{label,confidence,box: <BBox dict>}`.
- `InferenceError` ↔ `{error_type,error_message,retryable}` hoặc `None`.
- `InferenceRequest` ↔ `{request_id,source_id,frame_ref: <ref dict>}`.
- `InferenceResponse` ↔ `{request_id,detections:[<Detection dict>...],error: <err dict|None>}`.
Round-trip PHẢI giữ `ring_epoch` (int) + `space` (CoordinateSpace) — test P6.

## Correctness Properties

### Property 1: Correlation đúng request_id
N request đa-client, response đảo thứ tự → mỗi client nhận đúng `request_id`. **Validates: Requirements 3**

### Property 2: Switchover-aware (đóng K-023a)
Switchover GIỮA lúc phục vụ → request epoch mới đọc được frame ring mới (KHÔNG stale vĩnh viễn như inline #06) — điểm khác cốt lõi. **Validates: Requirements 4**

### Property 3: Stale-safe
Ref epoch cũ → error `retryable=True`, không torn. **Validates: Requirements 4, 5**

### Property 4: Bulkhead cách ly
Detector ném → client nhận `InferenceError(retryable=False)`, server KHÔNG chết, request kế vẫn phục vụ. **Validates: Requirements 2, 5**

### Property 5: Server chết → client không hang
Client `infer` timeout → `retryable=True`. **Validates: Requirements 7**

### Property 6: Msgpack round-trip
Round-trip mọi DTO (gồm ring_epoch, CoordinateSpace) bằng nhau. **Validates: Requirements 6**

### Property 7: Graceful shutdown
Server dưới Supervisor #09 → shutdown_event → đóng socket + teardown trong finally. **Validates: Requirements 7**

## Error Handling
`retryable=True`: read stale/None, ZMQ timeout, HWM/queue đầy. `retryable=False`: detector exception (bad
input/model), frame shape sai, deserialize lỗi. `InferenceError` chỉ chuỗi (`error_type`/`error_message`, R5.3).
Server KHÔNG bao giờ crash vì 1 request lỗi (bọc try/except quanh detect + đọc).

## Testing Strategy

Test THẬT, cross-process spawn — như #05b/#09:
- `test_zmq_codec.py`: Property 6 round-trip (in-process, nhanh).
- `test_zmq_inference_cross_process.py`: spawn server (nhận locks_map + control_plane names) + client → P1/P3/P4/P5.
- `test_zmq_switchover.py`: **P2** (test QUAN TRỌNG NHẤT — chứng minh khác inline: switchover→epoch2, client infer ref epoch2 → server đọc được, đóng K-023a).
- `test_inference_client_port.py`: inline + zmq cùng thoả `IInferenceClient` (R1).
- lint-imports 5/0 + negative-test zmq/msgpack cấm ở kernel/domain.

## Open Questions (CHỜ USER CHỐT)
- **Q1:** Đồng ý thêm dep `pyzmq` + `msgpack` vào `[project] dependencies`?
- **Q2:** Endpoint test = `tcp://127.0.0.1:<port>` (đề xuất — Windows KHÔNG hỗ trợ `ipc://`)? [chưa kiểm port free]
- **Q3:** Correlation THREADING (QĐ-1) OK, hay muốn asyncio (khác codebase)?
- **Q4:** Server single-thread v1 (QĐ-3), BoundedQueue multi-worker để bản sau — OK?
