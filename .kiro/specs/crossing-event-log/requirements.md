# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — design-first, CHỜ user đọc-lại-valid trước khi code.
> **Gắn với:** xây TRÊN `line-crossing-count` (D-060 ✅). Biến ĐẾM (tổng) → SỰ KIỆN có-thời-gian (audit/tích hợp).
> **Cập nhật lúc:** 2026-07-09.

## Introduction

`LineCrossingStage` hiện cho **con số tổng** `crossings_in/out/total` (aggregate, trong RAM + in stderr). Sản phẩm
thương mại cần **bản ghi TỪNG SỰ KIỆN bền vững**: "track_id X (label) qua vạch theo chiều IN/OUT lúc T (giờ thật)"
— để audit, tích hợp downstream (DB/queue/BI), truy vết. Đây là bước biến hệ thống thành **nguồn dữ liệu dùng được**,
không chỉ số đếm phù du.

**Nguyên tắc nền (bám "fix bản chất, không rebuild"):** tái dùng mẫu `JsonlEventSink` đã có (mkdir/append/flush,
`event_ts` WALL-CLOCK UTC), `ISink`, artifacts CoW. **THÊM**: `CrossingEvent` DTO (`kernel`) + phát-sự-kiện trong
`LineCrossingStage` (additive artifact) + `CrossingEventJsonlSink` (`adapters`). KHÔNG phá đếm cũ.

**Chống bịa:** dùng `datetime.now(timezone.utc).isoformat()` (mẫu y `JsonlEventSink` — đã đọc code). Mốc THẬT =
wall-clock (monotonic vô nghĩa khi đọc log sau). Test dùng CLOCK TIÊM (giờ cố định) → xác định.

**Non-Goal (v1):** KHÔNG DB/queue sink (chỉ JSONL — DB là impl `ISink` khác sau); KHÔNG event cho count-per-frame
(chỉ crossing); KHÔNG chống-trùng qua restart (append thuần); KHÔNG schema-versioning phức tạp.

## Requirements

### Requirement 1: Sinh CrossingEvent cho MỖI lượt băng-vạch
**User Story:** Là kỹ sư tích hợp, tôi muốn mỗi lượt vật qua vạch tạo 1 bản ghi có track_id/nhãn/hướng/thời-gian, để đẩy xuống hệ thống khác.
#### Acceptance Criteria
- 1.1 — Khi `LineCrossingStage` phát hiện 1 track băng vạch → tạo 1 `CrossingEvent` gồm: `track_id:int`, `label:str`, `direction:str` ∈ {"in","out"}, `source_id:str`, tâm `cx,cy:float`, `event_ts:str` (ISO-8601 UTC, hậu tố "Z").
- 1.2 — `event_ts` = WALL-CLOCK UTC (giờ thật) — KHÔNG dùng monotonic (`capture_time_ns` vô nghĩa khi lưu). Đồng bộ mẫu `JsonlEventSink`.
- 1.3 — `direction` khớp quy ước đếm (dấu phía so vạch A→B) — cùng nguồn với `crossings_in/out` (không lệch).

### Requirement 2: Phát sự kiện qua artifacts (additive)
**User Story:** Là maintainer, tôi muốn stage phơi sự kiện qua artifacts để sink tiêu thụ, mà không phá đếm cũ.
#### Acceptance Criteria
- 2.1 — `LineCrossingStage` ghi `artifacts["crossing_events"]:tuple[CrossingEvent,...]` = các sự kiện XẢY RA Ở FRAME NÀY (rỗng `()` nếu không có).
- 2.2 — `crossings_in/out/total` GIỮ NGUYÊN hành vi (đếm cộng dồn) — chỉ THÊM artifact sự kiện.
- 2.3 — Clock TIÊM được (mặc định wall-clock UTC) → test xác định.

### Requirement 3: Sink JSONL bền vững (lưu trữ optional)
**User Story:** Là vận hành, tôi muốn ghi sự kiện qua-vạch ra file .jsonl để lưu/đọc lại, bật/tắt không đổi pipeline.
#### Acceptance Criteria
- 3.1 — `CrossingEventJsonlSink(path)` (ISink): mỗi `CrossingEvent` trong `artifacts["crossing_events"]` → **1 dòng JSON**; `mkdir` cha nếu thiếu; mở "a" (append); `flush()` mỗi dòng (durability).
- 3.2 — Không gắn sink = không tạo file, pipeline chạy y hệt (lưu trữ OPTIONAL — C-013).
- 3.3 — Chỉ ghi khi `result.status == SUCCESS` (đồng bộ JsonlEventSink); frame không SUCCESS/không event → không ghi.

### Requirement 4: Tái dùng nền, không phá lõi + không hồi quy
**User Story:** Là maintainer, tôi muốn thêm event-log mà không sửa tracking/pipeline/đếm đã chạy, để không gây hồi quy.
#### Acceptance Criteria
- 4.1 — Chỉ THÊM: `CrossingEvent`@kernel + `CrossingEventJsonlSink`@adapters + sửa ADDITIVE `LineCrossingStage` (thêm clock param + artifact) + cờ `--crossing-out` profile. KHÔNG sửa TrackingStage/DetectStage/PipelineRunner/BaseStage.
- 4.2 — Baseline **494 passed/1 skipped · lint 5/0** giữ (chỉ tăng test). LineCrossingStage cũ (không dùng clock/event) vẫn pass.
- 4.3 — Không phá import-linter: DTO→kernel; sink→adapters (leaf, I/O file).

### Requirement 5: Kiểm chứng được KHÔNG cần GPU/camera
**User Story:** Là kỹ sư, tôi muốn test event-log xác định trên máy dev không GPU, để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test bằng chuỗi `Track` dựng tay + clock tiêm (giờ cố định) → sự kiện + ts xác định; sink ghi ra `tmp_path` kiểm nội dung.
- 5.2 — Test xác định (không random/không giờ thật).

## Non-Goals (giai đoạn này)
- KHÔNG DB/message-queue sink · KHÔNG event count-per-frame · KHÔNG dedupe qua restart · KHÔNG schema-version.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` có: `CrossingEvent` schema + thay đổi additive `LineCrossingStage` (clock tiêm + artifact) + `CrossingEventJsonlSink`
+ wire `--crossing-out` + Correctness Properties (map Requirements) + Testing no-GPU (clock tiêm). **0 diagnostic.**

## Glossary
- **CrossingEvent** — bản ghi 1 lượt qua vạch: track_id/label/direction/source_id/cx,cy/event_ts.
- **event_ts** — mốc WALL-CLOCK UTC (ISO-8601 "Z") — giờ thật cho log (đối lập monotonic).
- **CrossingEventJsonlSink** — ISink ghi mỗi CrossingEvent thành 1 dòng JSONL (append/flush).
- **clock tiêm** — hàm trả `datetime` (mặc định `now(UTC)`); test tiêm giờ cố định → xác định.
