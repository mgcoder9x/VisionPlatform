# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid trước design/code.
> **Mục đích:** lát cắt DỌC đầu tiên chạy THẬT: source → detect → analytics (đếm/frame) → sink. Biến
> `pipeline-runner` (D-039) thành có-người-dùng-thật + Stage-hoá detector (Gap-2 K-037) + chứng minh luồng nghiệp vụ.
> **Cập nhật lúc:** 2026-07-06.

## Introduction

Theo roadmap `scale-architecture` (D-040): **vertical slice TRƯỚC scale-out** (T-011). Đây là lát cắt dọc nhỏ
nhất chạy end-to-end để chứng minh **luồng nghiệp vụ thật** (hiện sink/event/analytics đang trống), đồng thời hiện
thực `PipelineRunner` + `ISink` (đã design ở spec `pipeline-runner`) — cho chúng một người-dùng-thật thay vì hạ
tầng suy đoán.

**Phạm vi v1 (cố tình NHỎ + STATELESS — né Lỗ 3 K-042):** đếm số phát-hiện TRONG TỪNG FRAME (stateless per-frame),
**KHÔNG** tracking/đếm-không-trùng xuyên-frame (stateful + camera-affinity → sub-spec riêng sau). Slice phải chạy
**xác định trong CI** (nguồn + detector giả), chế độ THẬT (RTSP/YOLO) bật qua cờ, KHÔNG vào CI.

**Chống bịa:** tái dùng thành phần đã có + đã đọc code — `FakeFrameSource`/`NoiseFrameSource`, `FakeDetector`,
`DetectorPipeline`, `SyncLinearExecutor`, `MediaPacket`/`IMediaRef`. `PipelineRunner`/`ISink` hiện thực theo đúng
design đã 0-diagnostic ở spec `pipeline-runner`.

## Requirements

### Requirement 1: Hiện thực nền `PipelineRunner` + `ISink` (theo design pipeline-runner)
**User Story:** Là kỹ sư, tôi muốn engine chạy nguồn→pipeline→sink có thật, để slice và mọi profile sau dùng chung một cách chạy đúng.
#### Acceptance Criteria
- 1.1 — PHẢI hiện thực `kernel/ports/sink.py::ISink` + `runtime/pipeline_runner.py::PipelineRunner` + `RunStats` đúng design `pipeline-runner`.
- 1.2 — Giữ contract import-linter (ISink@kernel, runner@runtime) → lint 5/0.
- 1.3 — 369 test cũ PHẢI xanh; test runner mới bổ sung (theo Testing Strategy của pipeline-runner).

### Requirement 2: `DetectStage` — Stage-hoá detector (đóng một phần Gap-2)
**User Story:** Là kỹ sư, tôi muốn detector chạy NHƯ một Stage trong pipeline, để nó ghép chung executor với các analytics khác.
#### Acceptance Criteria
- 2.1 — PHẢI có `DetectStage` (runtime/stages) bọc 1 `IDetector` (DI) → chạy detect trên `packet.media_ref.array` → ghi `artifacts["detections"]` (tuple Detection). STATELESS.
- 2.2 — `DetectStage` PHẢI setup()/teardown() ủy quyền cho detector (nạp/giải phóng model) — đúng lifecycle IStage.
- 2.3 — Lỗi detect → trả StageResult.ERROR qua BaseStage (bulkhead sẵn có), KHÔNG raise ra runner.

### Requirement 3: `CountStage` — analytics STATELESS đầu tiên (đếm/frame)
**User Story:** Là kỹ sư nghiệp vụ, tôi muốn đếm số đối tượng phát hiện trong mỗi frame, để có kết quả nghiệp vụ đầu tiên.
#### Acceptance Criteria
- 3.1 — PHẢI có `CountStage` đọc `artifacts["detections"]` → ghi `artifacts["count"]` = số phát-hiện TRONG FRAME ĐÓ.
- 3.2 — STATELESS tường minh: KHÔNG giữ state xuyên-frame (không dedup/track) — chống nhầm với đếm-không-trùng (Lỗ 3).
- 3.3 — Thiếu `artifacts["detections"]` (chưa qua DetectStage) → skip/ERROR rõ ràng, không đếm bừa.

### Requirement 4: Sink cắm/rút — in-memory (test) + JSONL file (lưu trữ TÙY CHỌN)
**User Story:** Là vận hành, tôi muốn kết quả đi tới đích cấu hình được (thu-gom test / ghi file / không lưu), để bật-tắt lưu trữ không đổi pipeline.
#### Acceptance Criteria
- 4.1 — PHẢI có `CollectingSink` (in-memory, thoả ISink) gom ExecutionResult — phục vụ test.
- 4.2 — PHẢI có `JsonlEventSink` (thoả ISink) ghi 1 dòng JSON/frame-thành-công (count + source_id + capture_time) vào file — minh hoạ lưu trữ optional.
- 4.3 — Tắt lưu = không gắn JsonlEventSink; bật = gắn vào. KHÔNG đổi runner/stage (C-013: lưu trữ optional).

### Requirement 5: Profile slice + test CI xác định
**User Story:** Là kỹ sư, tôi muốn 1 lệnh chạy slice end-to-end + test tự động chứng minh nó đúng, để có bằng chứng luồng chạy.
#### Acceptance Criteria
- 5.1 — PHẢI có profile (composition root) wire: source → DetectStage → CountStage → sink, chạy qua PipelineRunner.
- 5.2 — Test CI XÁC ĐỊNH (Fake/Noise source + FakeDetector, không cần camera): assert `RunStats.processed` = số frame, sink nhận đủ event, `count` khớp số detection giả.
- 5.3 — Giữ 369 test cũ xanh + lint 5/0 + 0 diagnostic.

### Requirement 6: Chế độ THẬT qua cờ (không vào CI)
**User Story:** Là kỹ sư, tôi muốn chạy slice trên camera/model thật khi cần, để kiểm chứng ngoài CI.
#### Acceptance Criteria
- 6.1 — Profile PHẢI cho chọn nguồn/detector thật qua cờ (`--rtsp`/`--video`/`--pt`...) tái dùng adapter đã có (RtspFrameSource/VideoFileFrameSource/Yolov5PtDetector).
- 6.2 — Chế độ thật KHÔNG chạy trong pytest CI (tránh phụ thuộc camera/GPU/mạng).

## Non-Goals (HOÃN — giữ bước nhỏ)
- **Tracking/đếm-không-trùng xuyên-frame** (stateful, camera-affinity — Lỗ 3 K-042) → sub-spec riêng.
- **Batching, scheduler, config khai báo, metrics tập trung, multi-camera** (scale-architecture) → sau slice.
- **ShmMediaRef / chạy slice cross-process qua SHM** → sau (slice v1 in-process).
- Classify/OCR đa-tầng fan-out → sau (v1 chỉ detect + count).

## Tiêu chí ĐẬU (Definition of Done)
PipelineRunner+ISink+RunStats hiện thực · DetectStage · CountStage (stateless) · CollectingSink + JsonlEventSink ·
profile + test CI xác định chứng minh end-to-end · 369 test cũ + test mới xanh · lint 5/0 · 0 diagnostic. Additive.

## Glossary
- **vertical slice** — lát cắt dọc nhỏ nhất chạy end-to-end (source→detect→analytics→sink) chứng minh luồng thật.
- **DetectStage** — Stage bọc IDetector, ghi detections vào artifacts (Stage-hoá detector, Gap-2).
- **CountStage** — analytics stateless: đếm phát-hiện trong 1 frame (KHÔNG xuyên-frame).
- **ISink / JsonlEventSink** — outbound port + impl ghi file JSONL (lưu trữ optional).
- **stateless (per-frame)** — không giữ state qua các frame; đối lập tracking (stateful, để sau — Lỗ 3).
