# Design Document

> **Trạng thái:** PHA 1 (design) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục (R1 ISink · R2 runner · R3 DI IMediaRef · R4 bằng chứng).
> **Cập nhật lúc:** 2026-07-06.

## Overview

Đóng **Gap-1 (K-037)**: rút vòng lặp `source → executor → sink` trùng ở 4 profile thành **1 engine
`PipelineRunner`** (layer `runtime`) + **1 outbound port `ISink`** (layer `kernel/ports`). Hoàn thiện tam giác
hexagonal: inbound port `IFrameSource` → mechanism `SyncLinearExecutor` (runtime) → outbound port `ISink`.

**Vì sao đây là gốc, không phải ngọn:** vấn đề không phải "4 profile dài dòng" mà là **không có nơi DUY NHẤT
định nghĩa cách chạy 1 pipeline** → mỗi profile tự quyết xử EOF/ERROR/teardown → phân kỳ hành vi (1 nơi quên
xử ERROR = bug im lặng trong sản phẩm). Rút engine chung là đưa "một cách đúng" về một chỗ, kiểm chứng một lần.

**Vì sao ADDITIVE, an toàn:** PHA này CHỈ thêm `ISink` + `PipelineRunner` + `RunStats` + test. **KHÔNG đụng 4
profile cũ** → 369 test giữ nguyên. Migrate profile là bước sau (opt-in, có regression riêng) — tách ra để mỗi
bước nhỏ, kiểm được.

**Kiểm chứng nền (đã đọc file thật — chống bịa):**
- `IFrameSource`: `read(timeout_ms=100)->ReadResult[np.ndarray]`, `setup/teardown`, `__enter__/__exit__`
  (trả False, không nuốt exc), `is_finite`, `source_id`. Runner dùng đúng bộ này.
- `SyncLinearExecutor`: `execute(packet)->ExecutionResult`, `setup_all/teardown_all`, `__enter__/__exit__`.
- `ExecutionResult` (kernel/stage_contract): status ∈ {SUCCESS, SKIPPED, ERROR, CANCELLED}, `packet`,
  `failed_stage`, `error_type/message`. `is_processed` = status==SUCCESS.
- `ReadResult` (kernel/read_result): status ∈ {FRAME, EOF, TIMEOUT, RECONNECTING, DROPPED, ERROR},
  `has_data` = FRAME & data!=None.
- 4 profile dựng packet giống hệt (grep verify): chỉ khác cách tạo media_ref → hợp với DI factory (D-038).

## Architecture

```
   kernel/ports          runtime                     kernel                adapters (impl, ngoài PHA này)
   ┌───────────┐   ┌────────────────────┐                                 ┌────────────────────┐
   │ IFrameSource│─▶│  PipelineRunner     │                                 │ FakeFrameSource ... │
   │ (inbound)  │  │   .run(...)         │──dựng──▶ MediaPacket             │ (IFrameSource impl) │
   └───────────┘   │   loop:             │        (media_ref qua factory)   └────────────────────┘
                   │    read→packet→     │──────▶  SyncLinearExecutor(runtime)
   ┌───────────┐   │    execute→handle   │◀─────── ExecutionResult          ┌────────────────────┐
   │ ISink      │◀─│                     │                                  │ PrintSink / JpegSink│
   │ (outbound) │  │   → RunStats        │                                  │ / EventSink (sau)   │
   └───────────┘   └────────────────────┘                                  └────────────────────┘
```

**Chiều phụ thuộc (đúng hexagonal, không phá contract):**
- `ISink` ở **kernel/ports** (Protocol thuần, chỉ tham chiếu `ExecutionResult` ở kernel). Đối xứng
  `IFrameSource`/`IDetector` đã có.
- `PipelineRunner` ở **runtime**: import kernel (MediaPacket, InMemoryArrayRef, IMediaRef, IFrameSource,
  ISink, ReadResult/ReadStatus, ExecutionResult/StageStatus) + runtime (SyncLinearExecutor). Contract cho
  phép runtime→kernel và runtime→runtime; runtime KHÔNG import adapters/application/profiles. ✓

## Components and Interfaces

### C1 — `kernel/ports/sink.py` (MỚI): `ISink`
```
@runtime_checkable
class ISink(Protocol):
    def setup(self) -> None: ...
    def handle(self, result: ExecutionResult) -> None: ...
    def teardown(self) -> None: ...
```
- Nhận CẢ result non-SUCCESS (R1.3) → sink tự quyết (vd chỉ vẽ khi SUCCESS, log khi ERROR). KHÔNG lọc hộ ở
  runner → giữ đầy đủ trạng thái, đúng triết lý `ExecutionResult` (không bóp về None).
- Chỉ import `typing` + `ExecutionResult` (kernel). KHÔNG lifecycle context-manager bắt buộc ở port (runner
  tự quản gọi setup/teardown) — giữ port tối thiểu.

### C2 — `runtime/pipeline_runner.py` (MỚI): `PipelineRunner` + `RunStats`
```
@dataclass(frozen=True)
class RunStats:
    frames_read: int = 0
    processed: int = 0
    skipped: int = 0
    stage_errors: int = 0
    cancelled: int = 0
    eof: int = 0
    source_errors: int = 0

class PipelineRunner:
    def __init__(self, source: IFrameSource, executor: SyncLinearExecutor, sink: ISink,
                 media_ref_factory: Callable[[np.ndarray], IMediaRef] = InMemoryArrayRef.from_copy,
                 clock_ns: Callable[[], int] = time.monotonic_ns): ...

    def run(self, *, max_frames: int | None = None,
            should_stop: Callable[[], bool] | None = None,
            timeout_ms: int = 100) -> RunStats: ...
```
- **Lifecycle (R2.5):** `run` mở theo thứ tự source→executor→sink (setup), đóng ngược sink→executor→source
  (teardown) trong `finally` → teardown chạy kể cả khi thân raise. Vì `ISink` không bắt buộc context-manager,
  runner gọi `sink.setup()/teardown()` tường minh; source/executor dùng context-manager sẵn có HOẶC gọi
  tường minh — chọn **gọi tường minh cả 3 trong try/finally** để thứ tự teardown xác định + đối xứng.
- **Vòng lặp (R2.3/2.4):**
  ```
  seq = 0
  try: setup source, executor, sink
      while True:
          if should_stop and should_stop(): break
          if max_frames is not None and stats.processed_or_read >= max_frames: break   # (chốt: đếm theo frame ĐỌC được, xem QĐ-2)
          r = source.read(timeout_ms)
          if r.status == EOF: eof+=1; if source.is_finite: break; else continue
          if r.status == ERROR: source_errors+=1; continue
          if not r.has_data: continue        # TIMEOUT/RECONNECTING/DROPPED → bỏ qua
          frames_read += 1
          packet = MediaPacket(f"{source_id}-{seq}", source_id, media_ref_factory(r.data), clock_ns())
          seq += 1
          result = executor.execute(packet)
          dispatch: SUCCESS→processed+1 · SKIPPED→skipped+1 · ERROR→stage_errors+1 · CANCELLED→cancelled+1
          sink.handle(result)      # LUÔN gọi, mọi status (R1.3)
      return RunStats(...)
  finally: teardown sink, executor, source (nuốt lỗi teardown, log — không che lỗi thân)
  ```
- **DI (R3):** `media_ref_factory` mặc định `InMemoryArrayRef.from_copy` (giữ hành vi 4 profile); `clock_ns`
  mặc định `time.monotonic_ns` (test tiêm clock đếm để xác định capture_time).
- **packet_id (R3.3):** `f"{source_id}-{seq}"` — duy nhất, xác định, không `id()`/random (K-036).

### C3 — Test helper `_CollectingSink` (trong test, không ship)
- Impl `ISink` gom mọi `ExecutionResult` vào list + đếm setup/teardown → assert R4.

### C4 — Ghi chú migrate (KHÔNG làm PHA này)
- Sau khi runner được valid + xanh: có thể migrate `demo_pipeline` (đơn giản nhất, in ra) sang runner +
  `PrintSink` để CHỨNG MINH xoá trùng lặp. Làm ở bước riêng, có regression. Web/fullstack dùng thread + heartbeat
  → cần `should_stop`/`on_tick`; đánh giá riêng.

## Data Models

- `RunStats` (frozen dataclass) — struct số liệu 1 lần chạy. Immutable, trả về từ `run()`.
- KHÔNG DTO mới khác. `ISink` là interface. `MediaPacket`/`ExecutionResult`/`ReadResult` tái dùng nguyên.

## Correctness Properties

### Property 1: Không mất/không thêm frame (đếm khớp)
Với nguồn hữu hạn N frame có data, chạy tới EOF: `frames_read == N` và
`processed + skipped + stage_errors + cancelled == frames_read` (mọi packet dựng ra được dispatch đúng 1 nhánh).
**Validates: Requirements 2.3, 2.6, 4.1**

### Property 2: Sink nhận đúng mọi ExecutionResult
Số lần `sink.handle` được gọi == `frames_read`, và tập status sink nhận khớp với thống kê (SUCCESS/SKIPPED/
ERROR/CANCELLED). Sink KHÔNG bị runner lọc hộ.
**Validates: Requirements 1.3, 4.2**

### Property 3: Không raise vì lỗi nguồn; teardown luôn chạy
Source trả `ReadStatus.ERROR` → `source_errors` tăng, vòng lặp tiếp tục, KHÔNG raise. Nếu thân vòng lặp raise
(vd `sink.handle` ném) → exception PROPAGATE ra ngoài NHƯNG `teardown` của source/executor/sink vẫn được gọi
(finally). Thứ tự teardown: sink → executor → source.
**Validates: Requirements 2.3, 2.5, 4.4**

### Property 4: Điều kiện dừng đúng, không kẹt nguồn vô hạn
`max_frames=k` → dừng sau đúng k frame xử lý; `should_stop()` True → dừng ở vòng kế; nguồn `is_finite=False`
(vô hạn) gặp EOF vẫn tiếp (không dừng nhầm), nhưng `should_stop`/`max_frames` phải cắt được → không treo.
**Validates: Requirements 2.4, 4.3**

### Property 5: DI xác định (media_ref + clock + packet_id)
Với `clock_ns` tiêm trả giá trị đếm, `capture_time_ns` của packet == giá trị factory trả; `media_ref` là kết
quả `media_ref_factory(data)`; `packet_id == f"{source_id}-{seq}"` tăng đều từ 0.
**Validates: Requirements 3.1, 3.2, 3.3**

## Error Handling

- **Lỗi đọc nguồn** (`ReadStatus.ERROR`): đếm `source_errors`, log, TIẾP TỤC — không raise (nguồn stream có thể
  chập chờn; runner không được chết vì 1 frame lỗi). Đây là bulkhead ở tầng runner.
- **Lỗi trong stage:** đã được `executor`/`BaseStage` bọc thành `ExecutionResult.ERROR` (không ném ra runner).
  Runner đếm `stage_errors` + vẫn `sink.handle`. Không có exception lọt.
- **Lỗi trong `sink.handle`:** KHÔNG bọc nuốt — đây là lỗi lập trình đích, để PROPAGATE (fail-fast) nhưng
  `finally` đảm bảo teardown. Lý do: sink lỗi = bug wiring của người dùng runner, che đi sẽ mất frame âm thầm.
- **Lỗi teardown:** nuốt + log (giống `executor.teardown_all` hiện tại) — teardown là dọn dẹp, không được che
  lỗi gốc của thân `run`.
- **`setup` nguồn/executor lỗi:** propagate (không thể chạy pipeline nếu không mở được) — `finally` teardown
  phần đã mở (executor.setup_all đã tự rollback nội bộ; runner teardown những cái đã setup).

## Testing Strategy

**File test mới:** `tests/test_pipeline_runner.py`.

1. **P1 end-to-end (R4.1):** `FakeFrameSource(max_frames=N)` → `SyncLinearExecutor([BrightnessStage()])` →
   `_CollectingSink` → assert `stats.frames_read==N`, `stats.processed==N`, tổng nhánh==frames_read, sink có N
   result SUCCESS + brightness khớp.
2. **P2 nhánh status (R4.2):** stage skip (DarkFilterStage ngưỡng cao) → `skipped` tăng; stage lỗi (stage giả
   raise) → `stage_errors` tăng + sink vẫn nhận ERROR; source giả trả ERROR vài lần → `source_errors` tăng,
   không raise.
3. **P3/P4 lifecycle + dừng (R4.3/4.4):** `max_frames=k` dừng đúng; `should_stop` dừng sớm; nguồn vô hạn (fake
   is_finite=False) + `max_frames` cắt được (không treo); sink.handle raise → teardown cả 3 vẫn gọi (spy đếm).
4. **P5 DI xác định (R3):** clock tiêm đếm → capture_time khớp; packet_id `src-0, src-1,...`;
   media_ref_factory tùy biến được gọi.
5. **Regression:** `.venv\Scripts\python.exe -m pytest -q` kỳ vọng **≥ 369 + số test mới** passed / 1 skipped
   (KHÔNG đụng profile cũ) + `lint-imports` **5 kept / 0 broken** + `get_diagnostics` = 0.

**DONE:** mọi nhóm có bằng chứng (lệnh + output thật) mới đổi ✅. Chưa chạy = [chưa kiểm].

## Quyết định thiết kế (ghi rõ lý do — cho journal)

- **QĐ-1: `ISink` ở kernel/ports, KHÔNG phải callback.** Lý do: nhất quán với codebase (mọi ranh giới là
  Protocol port); sink có lifecycle setup/teardown (mở file/kết nối DB) mà callback trần không mang được; đây
  là chỗ nghiệp vụ sau (IEventSink/DBSink) cắm vào tự nhiên. Đánh đổi: nhiều hơn 1 file so với callback —
  chấp nhận vì tính mở rộng lâu dài.
- **QĐ-2: `max_frames` đếm theo FRAME ĐỌC ĐƯỢC (có data), không theo vòng lặp.** Lý do: TIMEOUT/no-data không
  nên tính vào hạn mức "xử N frame". (Chốt cụ thể ở code: so `frames_read` với max_frames TRƯỚC khi read kế,
  hoặc break sau khi đạt — sẽ ghi rõ trong impl + test P4.)
- **QĐ-3: Nhận `SyncLinearExecutor` concrete, KHÔNG tạo `IExecutor` port.** Lý do: chỉ 1 executor tồn tại →
  chưa "biến thiên" → trừu tượng bây giờ là premature (YAGNI). Khi có executor async/parallel → mới rút port
  (câu hỏi pattern: *what varies?* — hiện executor KHÔNG varies). Đánh đổi: runner buộc kiểu concrete — chấp
  nhận, đổi sau rẻ (chỉ nới type như đã làm với media_ref).
- **QĐ-4: KHÔNG migrate profile trong PHA này.** Lý do: giữ 369 test bất biến, mỗi bước kiểm được; migrate là
  refactor riêng có rủi ro (web/fullstack dùng thread+heartbeat) → tách để không trộn "thêm engine" với "đổi
  hành vi profile đang chạy".

## Glossary
- **PipelineRunner** — engine runtime chạy `source → executor → sink` + RunStats. Xem C2.
- **ISink** — outbound port đích xử lý packet sau pipeline. Xem C1.
- **RunStats** — struct số liệu 1 lần chạy (immutable). Xem C2.
- **media_ref_factory** — DI tạo IMediaRef từ ndarray (mặc định in-memory; SHM sau). Xem C2, D-038.
- **YAGNI** — "You Aren't Gonna Need It" — không trừu tượng thứ chưa biến thiên (QĐ-3).
