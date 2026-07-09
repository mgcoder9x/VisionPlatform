# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — design-first, CHỜ user đọc-lại-valid trước khi code.
> **Gắn với:** xây TRÊN `object-tracking-count` (D-059 ✅ — cần `track_id` ổn định để biết "cùng 1 vật").
> Roadmap `scale-architecture` R3.3 (analytics = Stage cắm được). Nghiệp vụ thương mại phổ biến: đếm người/xe
> qua cổng/làn (people/vehicle counting).
> **Cập nhật lúc:** 2026-07-09.

## Introduction

`TrackingStage` cho mỗi vật 1 `track_id` ổn định + `unique_count` (tổng vật distinct). Nhưng nghiệp vụ đếm
CỬA/LÀN cần biết **vật ĐI QUA MỘT VẠCH** (theo hướng) — vd "bao nhiêu người vào / ra qua cửa", "bao nhiêu xe
qua làn". Đây là analytics tầng-2 chạy TRÊN tracking: so vị-trí-track giữa 2 frame liên tiếp với 1 đoạn thẳng
(vạch) → phát hiện băng qua + hướng.

**Nguyên tắc nền (bám "fix bản chất, không rebuild"):** tái dùng `BaseStage`, `Track` (đã có `box:BBox`
ORIGINAL_FRAME), artifacts CoW, camera-affinity pattern (K-042). **THÊM**: geometry thuần (`domain`) +
`LineCrossingStage` (`runtime`). KHÔNG sửa TrackingStage/DetectStage/pipeline.

**Chống bịa:** dùng hình học ĐOẠN-THẲNG chuẩn (orientation/cross-product) — hàm thuần test được. Đọc `Track.box`
(đã build #259) để lấy tâm vật. KHÔNG ML/không GPU. Test bằng chuỗi Track dựng tay.

**Non-Goal (v1):** KHÔNG đa-vạch (1 line/stage — nhiều vạch = nhiều stage/instance); KHÔNG vùng-đa-giác (zone);
KHÔNG đếm theo lớp riêng (tổng + theo hướng, tách theo label là mở rộng sau); KHÔNG cross-process.

## Requirements

### Requirement 1: Phát hiện băng-vạch theo track giữa 2 frame liên tiếp
**User Story:** Là kỹ sư analytics, tôi muốn biết khi 1 vật (track) đi qua 1 vạch định sẵn, để đếm lượt qua.
#### Acceptance Criteria
- 1.1 — Vạch = đoạn thẳng 2 điểm `A(ax,ay)`, `B(bx,by)` trong không gian `ORIGINAL_FRAME` (cùng space với `Track.box`).
- 1.2 — Với mỗi track có mặt ở CẢ frame trước và frame hiện tại: nếu đoạn di chuyển tâm `[center_prev → center_curr]` CẮT đoạn vạch `[A,B]` → tính 1 lượt băng-vạch.
- 1.3 — Tâm vật = tâm `Track.box` (`x+w/2, y+h/2`), space `ORIGINAL_FRAME` (đồng nhất với vạch — nếu khác space → fail-fast).
- 1.4 — Mỗi lần băng qua tính ĐÚNG 1 lượt (không đếm lặp khi track đứng cạnh vạch nhiều frame mà không thực sự băng qua).

### Requirement 2: Đếm theo HƯỚNG (in/out) + tổng
**User Story:** Là vận hành, tôi muốn phân biệt qua-theo-chiều-nào (vào/ra), để đếm vào-ra riêng.
#### Acceptance Criteria
- 2.1 — Hướng xác định bằng phía của tâm so với vạch (dấu cross-product): prev ở phía âm → curr phía dương = 1 chiều ("in"); ngược lại = "out". Quy ước ổn định + tài liệu hoá.
- 2.2 — Xuất `artifacts["crossings_in"]:int`, `["crossings_out"]:int`, `["crossings_total"]:int` (= in+out) — CỘNG DỒN theo stream (đơn điệu tăng).
- 2.3 — Ngược chiều A→B đảo nghĩa in/out — quy ước phụ thuộc thứ tự (A,B); tài liệu rõ để cấu hình đúng.

### Requirement 3: Stateful đúng cách + camera-affinity (K-042) + bounded memory
**User Story:** Là kiến trúc sư, tôi muốn Stage nhớ vị-trí-trước mỗi track mà không rò state giữa camera / không phình bộ nhớ.
#### Acceptance Criteria
- 3.1 — `LineCrossingStage` giữ `center_prev` theo `track_id` (state nội bộ) — 1 instance/1 camera (camera-affinity).
- 3.2 — Nhận `source_id` khác source đã thấy → fail-fast (raise → ERROR) — không trộn state.
- 3.3 — Thiếu `artifacts["tracks"]` (chạy trước TrackingStage) → raise → ERROR (không đếm bừa). `tracks` RỖNG → hợp lệ (không track: không lượt qua).
- 3.4 — **Bounded memory:** chỉ giữ `center_prev` cho track CÓ MẶT frame hiện tại (prune id vắng) → RAM theo số track đang sống, KHÔNG theo tổng vật (an toàn 24/7). Đánh đổi: track nhấp-nháy (vắng 1 frame rồi lại) reset mốc, có thể sót 1 lượt — tài liệu rõ.

### Requirement 4: Tái dùng nền, không phá lõi + không hồi quy
**User Story:** Là maintainer, tôi muốn thêm đếm-qua-vạch mà không sửa tracking/pipeline đã chạy, để không gây hồi quy.
#### Acceptance Criteria
- 4.1 — Chỉ THÊM file (geometry `domain` + `LineCrossingStage` `runtime` + có thể cờ `--line` profile). KHÔNG sửa TrackingStage/DetectStage/CountStage/PipelineRunner/BaseStage.
- 4.2 — Baseline **480 passed/1 skipped · lint 5/0** giữ nguyên (chỉ tăng số test).
- 4.3 — Không phá import-linter: hình học thuần → `domain`; stage → `runtime`.

### Requirement 5: Kiểm chứng được KHÔNG cần GPU/camera
**User Story:** Là kỹ sư, tôi muốn test đếm-qua-vạch xác định trên máy dev không GPU, để CI ổn định.
#### Acceptance Criteria
- 5.1 — Mọi hành vi (băng qua/không, hướng in/out, đếm-1-lần, thiếu-key/rỗng/mixed-source, prune) test bằng chuỗi `Track` dựng tay (không detector/camera).
- 5.2 — Test xác định (hình học thuần → không random/không timing).

## Non-Goals (giai đoạn này)
- KHÔNG đa-vạch trong 1 stage · KHÔNG zone đa-giác · KHÔNG tách đếm theo label · KHÔNG cross-process state.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` có: kiến trúc (geometry domain + stage runtime + layer) bám API thật (`Track.box`, `BaseStage`,
`with_artifact`) + thuật toán cắt-đoạn-thẳng + quy ước hướng + mô hình state/prune/camera-affinity + edge case +
Correctness Properties (map Requirements) + Testing Strategy no-GPU. **0 diagnostic.** User valid → PHA2 code TDD.

## Glossary
- **vạch (line/gate)** — đoạn thẳng `[A,B]` trong ORIGINAL_FRAME; vật băng qua = lượt đếm.
- **băng-vạch (crossing)** — đoạn `[center_prev, center_curr]` cắt `[A,B]`.
- **hướng in/out** — phía tâm so với vạch (dấu cross-product) trước→sau; quy ước theo thứ tự (A,B).
- **camera-affinity (K-042)** — 1 instance/1 camera; trộn source → fail-fast.
- **bounded memory** — chỉ giữ center_prev cho track đang có mặt → RAM ~ số track sống, không tích luỹ.
