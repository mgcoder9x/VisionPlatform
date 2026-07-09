# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — design-first, CHỜ user đọc-lại-valid trước khi code.
> **Gắn với:** đóng "Lỗ 3" (K-042: analytics-CÓ-STATE vs Stage-stateless + camera-affinity) — sub-spec kế tiếp
> mà `vision-vertical-slice/design.md` đã liệt kê ("còn mở có chủ đích: tracking/đếm-không-trùng"). Roadmap
> `scale-architecture` R3.3 (analytics = Stage/port cắm được: port mới `ITracker`).
> **Cập nhật lúc:** 2026-07-09.

## Introduction

`CountStage` hiện tại STATELESS: đếm số detection **mỗi frame** → 1 vật đứng trong khung 100 frame bị đếm 100 lần.
Nghiệp vụ thật (đếm người/xe qua, ALPR, đếm không trùng) cần **theo dõi vật XUYÊN FRAME** để mỗi vật vật-lý = 1
lần đếm. Đây là bước nghiệp vụ kế tiếp của sản phẩm, và là chỗ chạm **trạng thái** đầu tiên trong pipeline (trước
giờ mọi Stage đều stateless) → phải xử lý đúng bản chất trạng thái + ràng buộc camera-affinity (K-042).

**Nguyên tắc nền (bám "fix bản chất, không rebuild"):** tái dùng `IStage/BaseStage`, `Detection/BBox`, `domain.iou`
(đã có), `ISink`, artifacts CoW. **THÊM** 1 port (`ITracker`) + 1 impl thuần-hình-học (`IouTracker`) + 1 Stage
(`TrackingStage`) + DTO `Track`. KHÔNG sửa lõi Stage/pipeline/detector.

**Chống bịa:** thuật toán liên kết dùng `domain.iou(a,b: BBox)` ĐÃ TỒN TẠI (đọc `domain/nms.py`). Không dùng ML/
model (không cần GPU). Mọi hành vi test được bằng chuỗi detection deterministic (không camera).

**Non-Goal (v1):** KHÔNG ML tracker (DeepSORT/Kalman) — chỉ IoU-greedy (port cho phép nâng cấp sau); KHÔNG
line-crossing/zone (đếm = số track DISTINCT đã tạo); KHÔNG cross-process tracking (state in-process, 1 tiến trình/1
camera — đúng camera-affinity); KHÔNG re-identification sau khi track chết.

## Requirements

### Requirement 1: Gán track_id ổn định xuyên frame (IoU association)
**User Story:** Là kỹ sư analytics, tôi muốn mỗi vật giữ 1 track_id qua các frame liên tiếp, để phân biệt "cùng 1 vật" với "vật mới".
#### Acceptance Criteria
- 1.1 — MỖI detection trong frame PHẢI được gán 1 `track_id:int`; xuất qua `artifacts["tracks"]` (tuple `Track`).
- 1.2 — Detection frame sau khớp track cũ khi **cùng label** VÀ `iou(box_mới, box_track) >= iou_threshold` (cấu hình) → GIỮ nguyên track_id.
- 1.3 — Detection không khớp track nào → tạo track MỚI với `track_id` tăng đơn điệu (chưa từng dùng lại trong stream).
- 1.4 — Liên kết PHẢI xác định (deterministic): cùng chuỗi input → cùng chuỗi track_id (tie-break ổn định), không phụ thuộc thứ tự dict/thời gian.

### Requirement 2: Đếm KHÔNG TRÙNG (unique count) + track sống/chết
**User Story:** Là vận hành, tôi muốn biết tổng số vật DISTINCT đã xuất hiện + số track đang sống, để đếm không trùng.
#### Acceptance Criteria
- 2.1 — `artifacts["unique_count"]:int` = tổng số track_id ĐÃ TẠO tính tới frame hiện tại (đơn điệu tăng, không giảm).
- 2.2 — `artifacts["active_count"]:int` = số track đang sống (được cập nhật trong `max_age` frame gần nhất).
- 2.3 — Track không được khớp trong `max_age` frame liên tiếp PHẢI bị **retire** (loại khỏi tập active) → không so khớp nữa; track_id KHÔNG tái sử dụng.
- 2.4 — `max_age` và `iou_threshold` PHẢI cấu hình được (không hard-code).

### Requirement 3: Stateful đúng cách + camera-affinity (K-042)
**User Story:** Là kiến trúc sư, tôi muốn Stage có trạng thái không phá mô hình pipeline hiện tại và không trộn state giữa các camera.
#### Acceptance Criteria
- 3.1 — `TrackingStage` giữ trạng thái track NỘI BỘ (đối lập Stage stateless cũ) — 1 instance PHỤC VỤ ĐÚNG 1 luồng camera (camera-affinity).
- 3.2 — Nếu nhận frame từ `source_id` KHÁC với source đã thấy → PHẢI fail-fast (raise → StageResult.ERROR) thay vì trộn state âm thầm (chống dùng sai gây đếm loạn).
- 3.3 — Thiếu `artifacts["detections"]` (chạy sai thứ tự, trước DetectStage) → raise → ERROR (giống CountStage, không đếm bừa). Tuple RỖNG → hợp lệ (không detection: mọi track già đi, có thể retire).
- 3.4 — `TrackingStage` PHẢI nhận tracker qua DI kiểu PORT (`ITracker`) — không import impl cụ thể (swap-ready cho ML tracker sau).

### Requirement 4: Tái dùng nền, không phá lõi + không hồi quy
**User Story:** Là maintainer, tôi muốn thêm tracking mà không sửa Stage/pipeline/detector đã chạy, để không gây hồi quy.
#### Acceptance Criteria
- 4.1 — Chỉ THÊM file mới (port `ITracker`, DTO `Track`, `domain` association, `IouTracker`, `TrackingStage`) + có thể thêm 1 Stage tuỳ chọn xuất event; KHÔNG sửa `DetectStage`/`CountStage`/`PipelineRunner`/`BaseStage`.
- 4.2 — Baseline hiện tại **465 passed / 1 skipped · lint 5 kept/0 broken** PHẢI giữ nguyên (chỉ tăng số test).
- 4.3 — Không phá contract import-linter: geometry thuần → `domain`; port/DTO → `kernel`; impl+stage → `runtime`.

### Requirement 5: Kiểm chứng được KHÔNG cần GPU/camera
**User Story:** Là kỹ sư, tôi muốn test tracking xác định trên máy dev không GPU, để CI ổn định.
#### Acceptance Criteria
- 5.1 — Mọi hành vi (gán id, giữ id, id mới, retire, unique/active count, fail-fast mixed-source) PHẢI test được bằng chuỗi `Detection` dựng tay (không detector thật/không camera).
- 5.2 — Test PHẢI xác định (không đua timing, không random không seed).

## Non-Goals (giai đoạn này)
- KHÔNG ML tracker (Kalman/DeepSORT), KHÔNG re-ID sau chết, KHÔNG line/zone-crossing, KHÔNG cross-process state.
- KHÔNG tối ưu tốc độ (v1 O(tracks×dets)/frame — đủ cho mật độ vật thực tế; tối ưu khi benchmark chỉ ra).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế này)
`design.md` có: kiến trúc (port/DTO/domain/impl/stage + layer) bám API thật + thuật toán association xác định +
mô hình trạng thái (active/retire/unique) + camera-affinity + edge case (thiếu-key/rỗng/mixed-source) + Correctness
Properties (map Requirements) + Testing Strategy no-GPU. **0 diagnostic.** User valid → PHA 2 code TDD.

## Glossary
- **track** — 1 vật được theo dõi xuyên frame; có `track_id`, `label`, `box` (mới nhất), `age` (frame chưa khớp), `hits` (số frame đã khớp).
- **IoU association (greedy)** — ghép detection↔track theo IoU cao nhất ≥ ngưỡng, cùng label, tham lam (không tối ưu toàn cục).
- **max_age** — số frame liên tiếp không khớp trước khi track bị retire.
- **unique_count** — tổng track_id DISTINCT đã tạo (đếm không trùng, đơn điệu tăng).
- **active_count** — số track còn sống (chưa retire).
- **camera-affinity (K-042)** — 1 instance tracking chỉ phục vụ 1 luồng camera (state không chia sẻ giữa camera).
