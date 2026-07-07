# Design Document

> **Trạng thái:** PHA 2 XONG — code + test THẬT (307 passed/1 skipped · lint 5/0 · full-stack infer_ok≥1 cross-process). Q1–Q3 đã CHỐT (dưới).
> **Neo:** requirements (R1–R6) + code thật (đã đọc: RingPool/make_pool_opener, RingControlPlane, WriterEpochCoordinator.{bootstrap,write}, ReaderEpochCoordinator, InferenceServer, ZmqInferenceClient, Supervisor, NoiseFrameSource, FakeDetector).
> **Cập nhật lúc:** 2026-07-04.
>
> **CHỐT Q1–Q3 (user "duyệt theo khuyến nghị"):** Q1 = v1 1 camera + 1 inference server ✅ · Q2 = verify ARTIFACT FILE ✅ · Q3 = HOÃN BoundedQueue (v1 ghi thẳng SHM→infer, backpressure tự nhiên qua ring-đầy) ✅.
>
> **ĐIỀU CHỈNH vs bản PHA-1 (ghi C-011):** worker-entry (`camera_worker` + `inference_server_entry`) đặt NGAY
> trong `profiles/vision_fullstack_profile.py` — KHÔNG tách `tests/fullstack_workers.py` + KHÔNG tái dùng
> `tests/zmq_server_worker.py`. LÝ DO GỐC RỄ: profiles là composition-root SHIPPABLE; module `tests/` không
> ship + `src` không được import `tests`. Windows spawn re-import module chứa `target` ở process con → hàm
> module-level trong profile picklable + import được. Profile TỰ CHỨA = nền sản phẩm thật. Vẫn tái dùng
> COMPONENT (InferenceServer/Supervisor/coordinator/client — R3.1), chỉ không tái dùng test-wrapper.

## Overview

1 composition-root spawn 2 process (bulkhead) dưới Supervisor: **camera worker** (capture→ghi SHM→infer) +
**inference server** (ZMQ ROUTER→đọc SHM→detect). Chia sẻ 1 RingPool + control-plane + endpoint ZMQ.

```
 composition-root (parent): tạo RingPool + RingControlPlane(publish epoch1) + endpoint + Supervisor.run()
   │ spawn (locks_map + cp_name + endpoint qua Process args — thừa kế như #05b T-B)
   ├──► camera-worker (proc):  NoiseFrameSource → WriterEpochCoordinator.write(SHM) → ZmqInferenceClient.infer ──┐
   │        (cooperative + heartbeat)                                                                            │ ZMQ
   └──► inference-server (proc): ROUTER ← ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ────┘
            ReaderEpochCoordinator.read_ref(SHM) → FakeDetector → response
```

## Architecture

Layer: **1 file duy nhất** `profiles/vision_fullstack_profile.py` (composition-root, self-contained) chứa:
`run_profile()` (composition-root) + `camera_worker()` + `inference_server_entry()` (worker-entry module-level,
spawn-safe) + `_free_port()`/`_write_result()`/`parse_result()` (helper). KHÔNG file mới trong `tests/` (chỉ 1
file test). KHÔNG đổi component đã có (chỉ WIRE) → mọi test cũ giữ xanh (307 passed/1 skipped).

### QĐ-1 — v1: 1 camera + 1 inference server (1 RingPool)
Bất biến 1-writer/ring (#05 F-4) → 1 ring pool chỉ 1 writer = 1 camera. Multi-camera = N pool (Non-goal v1).
Đủ chứng minh vòng lặp end-to-end. Lý do: giữ verify được + không phá single-writer.

### QĐ-2 — Truyền tài nguyên qua Supervisor spawn args (thừa kế)
Composition-root tạo `pool` + `cp`(publish epoch1) + `endpoint`. Supervisor spawn:
- inference-server: `WorkerSpec(uses_shutdown_event=True, args=(endpoint, cp.name, pool.slot_locks_map(), n,h,w,c))` → `inference_server_worker(shutdown_event, ...)` (ĐÃ CÓ).
- camera-worker: `WorkerSpec(uses_shutdown_event=True, uses_heartbeat=True, args=(endpoint, cp.name, pool.slot_locks_map(), n,h,w,c, result_path))` → `camera_worker(shutdown_event, heartbeat, ...)`.
Thứ tự prepend #09b: `[shutdown_event, heartbeat] + args`. locks_map thừa kế qua Process args (verified #05b T-B).

### QĐ-3 — Camera worker vòng đời (cooperative + heartbeat)
```
opener = make_pool_opener(locks_map, n,h,w,c)
cp = RingControlPlane(cp_name, create=False)
wcoord = WriterEpochCoordinator(cp, opener); wcoord.bootstrap()   # register_writer ring epoch1
client = ZmqInferenceClient(endpoint, timeout_s=...); client.setup()
source = NoiseFrameSource(...); source.setup()
infer_ok = frames_ok = infer_err = 0
try:
  while not shutdown_event.is_set():
    heartbeat.value = time.time()
    r = source.read()
    if r.has_data:
      ref = wcoord.write(r.data)            # None nếu ring đầy (backpressure tự nhiên)
      if ref is not None:
        frames_ok += 1
        resp = client.infer(InferenceRequest(uuid4().hex, "cam1", ref))
        infer_ok += resp.is_success; infer_err += (not resp.is_success)
    time.sleep(pace_s)                      # pace cho server kịp (tránh cycle-đè slot)
finally:
  _write_result(result_path, frames_ok, infer_ok, infer_err)   # artifact cho test (QĐ-4)
  client.teardown(); source.teardown()
```

### QĐ-4 — Verify qua ARTIFACT FILE (không cross-process metrics aggregation)
Camera-worker ghi `frames_ok/infer_ok/infer_err` ra `result_path` (file) lúc `finally`. Test đọc file sau
shutdown. Lý do: InMemoryMetrics per-process (mỗi process 1 bản) — gộp về parent cần scrape (Non-goal). File
artifact đơn giản + robust cross-process (đã dùng pattern này ở #09). Metrics/log per-process VẪN có (R5).

### QĐ-5 — Startup coordination
Composition-root publish epoch1 TRƯỚC khi spawn (bootstrap cần epoch>0). Inference-server bind endpoint;
camera connect (ZMQ connect-before-bind OK → message chờ tới khi server bind). `infer` timeout đủ lớn cho spawn.
Pace + ring n_slots đủ (≥4) → frame READY khi server đọc; nếu cycle-đè → gen mismatch → infer_err (chấp nhận, backpressure).

## Components and Interfaces

- `profiles/vision_fullstack_profile.py`:
  - `run_profile(duration_s, *, n_slots=8, height=16, width=16, channels=3, result_path=None) -> dict` — composition-root: tạo pool/cp(publish epoch1)/endpoint, dựng Supervisor(2 WorkerSpec), `sup.run(duration_s)`, `pool.close_all()`+cp cleanup, trả restart_counts. (không nghiệp vụ.)
  - `inference_server_entry(shutdown_event, endpoint, cp_name, locks_map, n_slots, h, w, c)` — worker: cp(create=False)+opener+ReaderEpochCoordinator+FakeDetector+InferenceServer.serve.
  - `camera_worker(shutdown_event, heartbeat, endpoint, cp_name, locks_map, n_slots, h, w, c, result_path)` — worker QĐ-3 (self-contained, không ở tests/).
  - `parse_result(path) -> dict` — đọc artifact cho test.
- Tái dùng COMPONENT (không viết lại): `InferenceServer`, `Supervisor`+`WorkerSpec`, `WriterEpochCoordinator`, `ReaderEpochCoordinator`, `ZmqInferenceClient`, `FakeDetector`, `NoiseFrameSource`, `RingPool`, `RingControlPlane`.

## Data Models
Result artifact: file text `frames_ok=<int>\ninfer_ok=<int>\ninfer_err=<int>\n` (parse đơn giản). Không DTO mới.

## Correctness Properties

### Property 1: End-to-end flow
Frame chảy camera → SHM → (ZMQ) inference → detections THẬT cross-process: `infer_ok >= 1`. **Validates: Requirements 1, 2, 3, 6**

### Property 2: Bulkhead + graceful shutdown
2 process dưới Supervisor; `sup.run(duration)` trả về, shutdown sạch (không hang). **Validates: Requirements 4, 6**

### Property 3: Tái dùng (không viết lại)
InferenceServer/Supervisor/coordinator/client dùng nguyên; test cũ (306) giữ xanh. **Validates: Requirements 3**

## Error Handling
Camera: `wcoord.write` None (ring đầy) → skip infer (backpressure); `infer` lỗi (stale/timeout) → infer_err++,
tiếp tục. Server: bulkhead per-request (K-024). Shutdown: cascade cooperative-first (#09) + heartbeat (#09b).

## Testing Strategy
`tests/test_fullstack_integration.py` (guard win32, spawn):
- Property 1: `run_profile(duration_s≈1.5)` → đọc result artifact → `infer_ok >= 1`.
- Property 2: `run_profile` trả về (không hang) + process kết thúc.
- Regression: full `pytest` (306 + mới) + lint 5/0.

## Open Questions (ĐÃ CHỐT)
- **Q1 ✅:** v1 = 1 camera + 1 inference server (multi-camera scale sau — Non-goal).
- **Q2 ✅:** Verify qua ARTIFACT FILE (QĐ-4) — đã dùng, robust cross-process.
- **Q3 ✅ (HOÃN BoundedQueue):** camera-worker v1 ghi THẲNG SHM→infer, backpressure tự nhiên qua ring-đầy
  (`write()` trả None → skip+sleep). Wire BoundedQueue (đóng K-017) để bản sau khi có submit-thread thật.

## Kết quả VERIFY (PHA 2)
- `tests/test_fullstack_integration.py::test_fullstack_end_to_end` PASSED (13.29s): `frames_ok≥1` + `infer_ok≥1`
  cross-process (camera→SHM→ZMQ→FakeDetector→response) + `run_profile` trả về (shutdown sạch, không hang).
- Full suite: **307 passed / 1 skipped** (thêm 1 test full-stack, mọi test cũ giữ xanh).
- Lint import-linter: **5 kept / 0 broken** (profiles import mọi layer hợp lệ — không contract nào lấy profiles làm source).
