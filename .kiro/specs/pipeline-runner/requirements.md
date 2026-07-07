# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid trước design/code.
> **Mục đích:** đóng **Gap-1 (K-037)** — chưa có engine chuẩn chạy `source → stages → sink`, khiến 4 profile
> mỗi cái TỰ viết lại vòng lặp read→dựng-packet→execute→xử-lý-status (trùng lặp + dễ lệch).
> **Cập nhật lúc:** 2026-07-06.

## Introduction

Audit K-037 (Gap-1) chỉ ra: base có `IStage` + `SyncLinearExecutor` (chạy 1 packet qua chuỗi stage) nhưng
**KHÔNG có "PipelineRunner"** — thành phần đọc frame từ nguồn, đóng gói thành `MediaPacket`, đẩy qua executor,
rồi định tuyến kết quả. Hệ quả (đã verify bằng grep, KHÔNG bịa): **4 profile** tự tay viết cùng 1 vòng lặp:

- `profiles/demo_pipeline.py` — `with source, executor: while True: r=source.read(); ...; executor.execute(packet)`
- `profiles/vision_web_app.py` — vòng `src.read()` + xử `ReadStatus.EOF/ERROR/has_data`
- `profiles/vision_fullstack_profile.py` — `while not shutdown_event.is_set(): source.read(); ...`
- `profiles/vision_demo_app.py` — `while got < n: r=src.read(); if EOF break; ...`

Bốn bản này lặp lại: xử lý `ReadStatus` (EOF/ERROR/no-data), dựng `MediaPacket` (packet_id/source_id/
media_ref/capture_time_ns), gọi `executor.execute`, phân nhánh `ExecutionResult.status`, đếm thống kê. Trùng
lặp = mỗi nơi có thể xử SAI KHÁC NHAU (vd quên xử ERROR, quên teardown) → rủi ro cho sản phẩm thương mại.

**Giải pháp (bản chất, ADDITIVE):** rút vòng lặp chung thành **1 engine `PipelineRunner` ở layer `runtime`**
(cùng tầng executor), + **1 outbound port `ISink`** (kernel/ports) cho "làm gì với packet đã xử lý". Đây là
mảnh còn thiếu của kiến trúc hexagonal: **inbound port `IFrameSource` → mechanism (executor) → outbound port
`ISink`**, runner là bộ điều phối. KHÔNG rebuild — thêm mới; profile cũ tạm giữ nguyên (migrate là bước sau).

**Ràng buộc nguồn (đã verify — chống bịa):**
- `IFrameSource` (kernel/ports/frame_source.py) đã có: `read(timeout_ms)->ReadResult`, `setup/teardown`,
  context manager, `is_finite`, `source_id`. Runner dùng ĐÚNG các API này.
- `SyncLinearExecutor` (runtime) đã có: `execute(packet)->ExecutionResult`, `setup_all/teardown_all`,
  context manager. Runner CHỈ cần `execute` + lifecycle.
- Dựng packet uniform ở cả 4 loop: `MediaPacket(packet_id, source_id, media_ref=<factory>(data), capture_time_ns)`.
  Chỗ DUY NHẤT biến thiên là cách tạo `media_ref` → khớp port `IMediaRef` vừa thêm (D-038) → DI factory.

## Requirements

### Requirement 1: Port `ISink` (outbound, kernel)
**User Story:** Là kiến trúc sư, tôi muốn 1 outbound port cho "đích xử lý packet sau pipeline", để runner không
buộc cứng vào print/JPEG/DB — nghiệp vụ sau (event/DB/queue) chỉ cần thêm 1 impl ISink.
#### Acceptance Criteria
- 1.1 — PHẢI có `ISink` (Protocol, kernel/ports) tối thiểu: `handle(result: ExecutionResult) -> None` +
  `setup() -> None` + `teardown() -> None` (idempotent, đối xứng IFrameSource/IDetector).
- 1.2 — `ISink` KHÔNG import layer ngoài/adapter cụ thể; chỉ phụ thuộc kernel (ExecutionResult ở kernel).
- 1.3 — `handle` nhận CẢ ExecutionResult non-SUCCESS (SKIPPED/ERROR/CANCELLED) — sink tự quyết xử/bỏ (giữ
  đầy đủ trạng thái, không bóp về None — cùng triết lý ExecutionResult).

### Requirement 2: `PipelineRunner` (runtime) — engine source→executor→sink
**User Story:** Là kỹ sư, tôi muốn 1 runner chuẩn chạy nguồn→pipeline→sink với lifecycle + thống kê đúng, để
KHÔNG phải viết lại vòng lặp read/EOF/error/teardown ở mỗi profile.
#### Acceptance Criteria
- 2.1 — `PipelineRunner` sống ở `runtime/pipeline_runner.py`; phụ thuộc kernel (MediaPacket/ports/DTO) +
  runtime (executor). KHÔNG import adapters/application/profiles (giữ contract import-linter).
- 2.2 — Nhận DI: `source: IFrameSource`, `executor` (SyncLinearExecutor), `sink: ISink`.
- 2.3 — `run(...)` PHẢI: mở lifecycle (`with source, executor, sink`-tương-đương) → vòng lặp:
  đọc `source.read(timeout_ms)`; xử `ReadStatus` (EOF→dừng nếu `source.is_finite`; ERROR→đếm+bỏ, không raise;
  no-data→bỏ qua); dựng `MediaPacket`; `executor.execute`; gọi `sink.handle(result)`; cộng thống kê.
- 2.4 — Điều kiện dừng: (a) EOF khi nguồn hữu hạn; (b) `max_frames` (tùy chọn) đạt; (c) `should_stop()` (tùy
  chọn, callable) trả True — phục vụ luồng nền/web (thay `shutdown_event.is_set()`).
- 2.5 — Teardown PHẢI chạy kể cả khi thân vòng lặp raise (đảm bảo bằng context manager / try-finally). Thứ tự
  ra: sink → executor → source (ngược thứ tự vào).
- 2.6 — `run()` trả `RunStats` (frozen dataclass): frames_read, processed, skipped, stage_errors, cancelled,
  eof, source_errors. Thay các biến đếm rời rạc ở profile.

### Requirement 3: DI hook nối port `IMediaRef` (khớp D-038)
**User Story:** Là kiến trúc sư, tôi muốn runner tạo `media_ref` qua 1 factory tiêm được, để backend frame khác
(SHM `ShmMediaRef` về sau) cắm vào runner mà KHÔNG sửa runner.
#### Acceptance Criteria
- 3.1 — Runner có tham số `media_ref_factory: Callable[[np.ndarray], IMediaRef]`, mặc định
  `InMemoryArrayRef.from_copy` (giữ hành vi hiện tại của 4 profile).
- 3.2 — Có `clock_ns: Callable[[], int]` mặc định `time.monotonic_ns` (DI để test xác định — không phụ thuộc
  thời gian thực).
- 3.3 — `packet_id` sinh xác định theo `source_id` + số thứ tự tăng (vd `f"{source_id}-{seq}"`) — duy nhất,
  không phụ thuộc `id()`/random (bài học K-036: tránh id-reuse).

### Requirement 4: Bằng chứng engine chạy thật (không chỉ khung)
**User Story:** Là kỹ sư, tôi muốn test chứng minh runner chạy end-to-end + xử đúng mọi nhánh status + thống kê khớp.
#### Acceptance Criteria
- 4.1 — Test: `FakeFrameSource`(hữu hạn) → executor[`BrightnessStage`] → `_CollectingSink` → `RunStats.processed`
  bằng số frame, sink nhận đủ ExecutionResult SUCCESS với artifact brightness đúng.
- 4.2 — Test nhánh non-SUCCESS: 1 stage skip/lỗi → `RunStats.skipped`/`stage_errors` tăng đúng + sink vẫn nhận
  result (R1.3). 1 source trả ERROR → `source_errors` tăng + KHÔNG raise (R2.3).
- 4.3 — Test dừng: `max_frames` giới hạn đúng; `should_stop()` trả True → dừng sớm; nguồn vô hạn không kẹt.
- 4.4 — Test lifecycle: teardown source+executor+sink được gọi kể cả khi sink.handle raise (R2.5) — dùng spy.

## Non-Goals (HOÃN — giữ bước nhỏ, chống phình)
- **Migrate 4 profile hiện có sang runner** — bước SAU (opt-in, refactor có regression đầy đủ). PHA này CHỈ
  thêm runner + test; KHÔNG đụng profile cũ để giữ 369 test xanh.
- **`IExecutor` port / executor async / multi-thread** — chỉ có 1 executor (sync_linear) → chưa "biến thiên"
  → chưa trừu tượng (YAGNI, tránh over-engineer). Runner nhận SyncLinearExecutor concrete v1.
- **Fan-out (1 frame → N object → nhánh)** — mô hình khác, sub-spec riêng (Gap-4 K-037).
- **`ShmMediaRef` / chạy runner qua SHM cross-process** — cần ShmMediaRef (Non-Goal media-ref-port). Runner
  đã CHỪA sẵn `media_ref_factory` để sau cắm vào.
- **Backpressure/BoundedQueue trong runner** — runner v1 chạy đồng bộ 1 luồng; queue là biến thể sau.

## Tiêu chí ĐẬU (Definition of Done)
`ISink` port + `PipelineRunner` (DI source/executor/sink + media_ref_factory + clock + stop conditions) +
`RunStats` + test chứng minh end-to-end & mọi nhánh status & lifecycle-teardown-on-raise & stop conditions +
369 test cũ xanh (KHÔNG đụng profile) + lint 5/0 + 0 diagnostic. Additive thuần.

## Glossary
- **PipelineRunner** — engine (runtime) chạy vòng `source → executor → sink` với lifecycle + thống kê.
- **ISink** — outbound port: "làm gì với packet đã qua pipeline" (print/JPEG/DB/event... = impl ở adapters).
- **RunStats** — frozen dataclass gom số liệu 1 lần chạy (frames_read/processed/skipped/...).
- **media_ref_factory** — DI tạo `IMediaRef` từ ndarray; mặc định in-memory, sau đổi SHM không sửa runner.
- **Gap-1 (K-037)** — thiếu runner chuẩn → 4 profile trùng vòng lặp; đây là ma sát lớn nhất của base.
