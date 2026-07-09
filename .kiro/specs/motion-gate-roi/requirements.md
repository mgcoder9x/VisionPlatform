# Requirements Document

> **Spec:** motion-gate-roi (ROI-mask + bền-illumination)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Đóng:** K-063 (motion-gate v1 full-frame → NHẠY đổi-ánh-sáng-toàn-cục: đèn/mây → motion "thừa" → gate mở
> nhầm → PHÍ GPU, phản mục tiêu gate) + Non-Goal v1 của spec `motion-gate` (ROI-mask + background-model).
> **Nền tảng (đã ĐỌC CODE thật):** `domain/motion.py::changed_ratio(prev, curr, pixel_diff_threshold)` (full-frame,
> cast int16); `runtime/stages/motion_gate_stage.py::MotionGateStage` (stateful, camera-affinity K-042, first-frame/
> đổi-shape → đi tiếp, `max_consecutive_skip`). **Cập nhật lúc:** 2026-07-09.

## Introduction

Motion-gate v1 đo tỉ lệ pixel đổi TRÊN TOÀN FRAME. Nhược điểm bản chất (K-063): khi ánh sáng đổi ĐỀU toàn cục
(bật đèn, mây che nắng, auto-exposure camera) → MỌI pixel dịch một lượng ~hằng số Δ → `|curr-prev|` vượt ngưỡng ở
gần như mọi pixel → `motion_ratio ≈ 1` → gate coi là "có chuyển động" → detector CHẠY dù KHÔNG có vật nào di
chuyển → **phí GPU** (đúng thứ gate sinh ra để tránh). Ngoài ra gate đo cả vùng KHÔNG quan tâm (bầu trời, tường)
→ nhiễu.

Tính năng này thêm HAI cải tiến ĐỘC LẬP, đều **tùy chọn (opt-in), mặc định TẮT → hành vi v1 giữ nguyên**:
1. **ROI-mask:** chỉ đo chuyển động TRONG vùng quan tâm (bỏ qua vùng ngoài) → giảm nhiễu + tập trung.
2. **Bền-illumination (pure-numpy):** trừ độ-sáng-nền toàn cục trước khi so → thay đổi sáng ĐỀU không còn bị coi
   là chuyển động; chuyển động CỤC BỘ (vật di chuyển) vẫn phát hiện.

**Ranh giới layer (bám luật + đã kiểm):** cả hai làm bằng **numpy thuần** → ở `domain` (được dùng numpy). Mô hình
nền nâng cao (MOG2/KNN background-subtraction) cần `cv2` → thuộc `adapters` (KHÔNG vào domain) → **Non-Goal** ở đây,
để mở cho sub-spec sau. Thay đổi ADDITIVE: mở rộng `changed_ratio` (thêm tham số optional) + `MotionGateStage`
(thêm param optional) + config/CLI. KHÔNG sửa BaseStage/executor/DetectStage/runner. Baseline **521/1 · lint 5/0** giữ.

**Chống bịa:** mọi tham chiếu (changed_ratio, MotionGateStage, SkipFrameSignal, camera-affinity) ĐÃ đọc code thật.
Toán illumination (uniform-shift bị triệt tiêu bởi mean-subtraction) chứng minh được bằng đại số + test numpy xác định.

### Goals
- Giảm FALSE-motion do đổi-sáng-đều toàn cục (không còn chạy detector oan).
- Chỉ xét chuyển động trong ROI (bỏ vùng không quan tâm).
- Giữ v1 nguyên vẹn khi không bật (backward-compat tuyệt đối).
- Kiểm chứng KHÔNG cần GPU/camera (frame numpy dựng tay + đại số).

### Non-Goals
- KHÔNG background-model nâng cao (MOG2/KNN — cần cv2 → adapters, sub-spec sau).
- KHÔNG optical-flow, KHÔNG ROI đa-giác phức tạp (v1 ROI = hình chữ nhật; polygon để sau nếu cần).
- KHÔNG xử lý đổi-sáng KHÔNG-đều/bóng-đổ hoàn hảo (mean-subtraction chỉ triệt uniform; non-uniform cần background-model = future).

## Glossary
- **ROI (Region Of Interest)** — vùng chữ nhật trong frame nơi ĐO chuyển động; ngoài ROI bị bỏ qua.
- **ROI chuẩn-hoá** — ROI khai báo bằng tỉ lệ [0,1] `(x, y, w, h)` → độc-lập-độ-phân-giải (áp cho mọi camera).
- **Illumination-robust (bền-sáng)** — metric mà thay đổi độ sáng ĐỀU toàn cục (curr = prev + hằng số) → motion ≈ 0.
- **Mean-subtraction** — trừ giá trị trung bình mỗi frame trước khi lấy hiệu: `d = (curr-mean(curr)) - (prev-mean(prev))`.
- **changed_ratio** — (đã có) tỉ lệ pixel `|curr-prev| > threshold`. Mở rộng: nhận `mask` + cờ `illumination_robust`.

## Requirements

### Requirement 1: ROI-mask — chỉ đo chuyển động trong vùng quan tâm
**User Story:** Là kỹ sư giám sát, tôi muốn motion-gate chỉ xét vùng quan tâm (vd làn đường), bỏ qua vùng nhiễu (trời, cây), để gate chính xác + ít trigger oan.
#### Acceptance Criteria
- 1.1 — WHERE ROI được cấu hình, THE `changed_ratio` SHALL chỉ đếm pixel đổi TRONG mask ROI; mẫu số = số pixel trong ROI (không phải toàn frame).
- 1.2 — THE ROI SHALL khai báo dạng chữ nhật CHUẨN-HOÁ `(x, y, w, h)` với mỗi giá trị ∈ [0,1] (tỉ lệ theo chiều rộng/cao frame) → độc-lập-độ-phân-giải.
- 1.3 — IF ROI khai báo ra ngoài [0,1] hoặc `w<=0`/`h<=0` hoặc vùng rỗng sau khi quy về pixel, THEN THE hệ SHALL từ chối cấu hình bằng lỗi rõ ràng (fail-fast, không im lặng đo sai).
- 1.4 — WHERE KHÔNG cấu hình ROI, THE gate SHALL đo TOÀN FRAME (hành vi v1 giữ nguyên).

### Requirement 2: Metric bền-illumination (pure-numpy, opt-in)
**User Story:** Là kỹ sư, tôi muốn thay đổi ánh sáng đều (đèn/mây/auto-exposure) KHÔNG bị coi là chuyển động, để gate không chạy detector oan.
#### Acceptance Criteria
- 2.1 — WHERE bật chế độ bền-illumination, WHEN `curr = prev + c` với `c` là hằng số cộng đều mọi pixel, THE `motion_ratio` SHALL ≈ 0 (dưới `min_area_ratio`) → gate SKIP (không chạy detector).
- 2.2 — WHERE bật chế độ bền-illumination, WHEN có vật di chuyển CỤC BỘ (một vùng đổi khác phần còn lại), THE `motion_ratio` SHALL phản ánh vùng cục bộ đó (> 0, phát hiện được).
- 2.3 — THE chế độ bền-illumination SHALL dùng **mean-subtraction** (numpy thuần): `d = (curr - mean(curr)) - (prev - mean(prev))`, rồi đếm `|d| > pixel_diff_threshold`. (mean theo toàn ROI/frame đang xét.)
- 2.4 — WHERE KHÔNG bật, THE metric SHALL là hiệu thô như v1 (`|curr-prev|`) — backward-compat.
- 2.5 — THE tài liệu SHALL ghi rõ giới hạn: mean-subtraction chỉ triệt đổi-sáng ĐỀU (uniform); đổi-sáng KHÔNG-đều/bóng-đổ cần background-model (Non-Goal, sub-spec cv2 sau) — KHÔNG over-claim.

### Requirement 3: Additive + camera-affinity + edge giữ nguyên
**User Story:** Là kiến trúc sư, tôi muốn cải tiến này KHÔNG phá v1 và giữ đúng ranh giới layer.
#### Acceptance Criteria
- 3.1 — THE `changed_ratio` mở rộng SHALL giữ nguyên chữ ký cũ hoạt động (tham số `mask`/`illumination_robust` là optional, default None/False → kết quả y hệt v1).
- 3.2 — THE `MotionGateStage` SHALL nhận thêm param optional (roi, illumination_robust) — mặc định giữ hành vi v1; camera-affinity (K-042), first-frame/đổi-shape → đi tiếp, `max_consecutive_skip` GIỮ NGUYÊN.
- 3.3 — THE toán ROI + illumination SHALL ở `domain` (numpy thuần) — KHÔNG import cv2/torch. Mask xây từ ROI chuẩn-hoá + shape frame (lazy khi biết shape).
- 3.4 — THE thay đổi SHALL additive: KHÔNG sửa BaseStage/executor/DetectStage/runner. Baseline **521 passed/1 skipped · lint 5/0** giữ (+ test mới).

### Requirement 4: Cắm config + CLI (deploy-by-config)
**User Story:** Là kỹ sư triển khai ~100 cam, tôi muốn bật ROI + bền-sáng qua config/CLI không đổi code.
#### Acceptance Criteria
- 4.1 — THE builder `motion_gate` (registry `pipeline_factory`) SHALL nhận thêm params `roi` (list/tuple 4 số [0,1]) + `illumination_robust` (bool) + `allowed_params` cập nhật (K-046 strict-key).
- 4.2 — THE CLI SHALL thêm cờ tùy chọn (vd `--motion-roi x,y,w,h` + `--motion-illum-robust`) — mặc định không bật.
- 4.3 — WHERE cấu hình ROI/illum sai kiểu, THE loader SHALL fail-fast `ConfigError` với thông điệp rõ.

### Requirement 5: Kiểm chứng KHÔNG cần GPU/camera (xác định)
**User Story:** Là kỹ sư, tôi muốn test xác định trên máy dev để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test ROI (numpy dựng tay): vật đổi TRONG ROI → có motion; đổi NGOÀI ROI (trong ROI tĩnh) → SKIP; mẫu số đúng = pixel trong ROI.
- 5.2 — Test illumination (đại số + numpy): `curr = prev + c` (c hằng số) + bật illum-robust → ratio ≈ 0 (SKIP); vật cục bộ → ratio > 0 (đi tiếp). Đối chứng: KHÔNG bật illum-robust + `curr=prev+c` → ratio cao (chứng minh v1 bị lỗi K-063, cải tiến sửa đúng).
- 5.3 — Test backward-compat: không ROI + không illum → kết quả y hệt v1 (so `changed_ratio` cũ).
- 5.4 — Test config/CLI: bật qua config → dựng đúng; ROI sai → ConfigError.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` có: (a) mở rộng `changed_ratio` (mask + illumination_robust, giữ backward-compat) + chứng minh đại số
uniform-shift → 0; (b) xây mask từ ROI chuẩn-hoá + shape (lazy, edge rỗng/ngoài-biên); (c) `MotionGateStage` param
mới (giữ mọi edge v1); (d) đăng ký config/CLI; (e) Correctness Properties map Requirements; (f) Testing no-GPU;
(g) doubt-driven review (≥3 forces + layer + "khi nào KHÔNG dùng"). **0 diagnostic. KHÔNG code ở PHA này.**
