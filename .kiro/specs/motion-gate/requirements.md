# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — design-first, CHỜ user đọc-lại-valid trước khi code.
> **Gắn với:** scale-architecture R2.4 (motion-gating: gate rẻ CPU đứng TRƯỚC inference đắt) — lever giảm tải GPU
> cho đích ~100 camera. Dùng `SkipFrameSignal` (đã có trong BaseStage/executor).
> **Cập nhật lúc:** 2026-07-09.

## Introduction

Detector (inference) là phần ĐẮT nhất (GPU-bound). Đa số frame giám sát KHÔNG có chuyển động (cảnh tĩnh) → chạy
detector trên chúng là LÃNG PHÍ GPU. **Motion-gate**: 1 Stage RẺ (CPU, frame-diff) đứng TRƯỚC `DetectStage` — chỉ
cho frame CÓ chuyển động đi tiếp; frame tĩnh bị SKIP (detector không chạy). Đây là lever #1 để nhồi nhiều camera
lên GPU giới hạn (scale-architecture R2.4).

**Nguyên tắc nền (bám "fix bản chất, không rebuild"):** tái dùng `SkipFrameSignal` (BaseStage bắt → StageResult.
skipped; executor dừng chuỗi → detector không chạy; PipelineRunner đếm `skipped`) — cơ chế skip ĐÃ CÓ, không thêm
mới. `media_ref.array` (np.ndarray) đọc read-only. **THÊM**: hàm frame-diff thuần (`domain`, numpy) + `MotionGateStage`
(`runtime`) + đăng ký config + CLI.

**Chống bịa:** `SkipFrameSignal` + xử lý skipped đã ĐỌC CODE (`base_stage.py`/`sync_linear_executor.py`/`pipeline_runner.py`).
Motion = frame-diff numpy thuần (domain được dùng numpy theo luật). Test bằng frame dựng tay (đứng yên vs đổi) → xác định, no-GPU.

**Non-Goal (v1):** KHÔNG background-subtraction nâng cao (MOG2...) · KHÔNG vùng-quan-tâm (ROI mask) · KHÔNG
optical-flow · KHÔNG downscale-tối-ưu (v1 diff full-frame; downscale là tối ưu sau nếu benchmark cần).

## Requirements

### Requirement 1: Gate skip frame TĨNH trước detector
**User Story:** Là kỹ sư, tôi muốn frame không có chuyển động bị bỏ trước khi chạy detector, để tiết kiệm GPU.
#### Acceptance Criteria
- 1.1 — `MotionGateStage` đặt TRƯỚC `DetectStage`: frame KHÔNG đủ chuyển động → raise `SkipFrameSignal` → StageResult.SKIPPED → chuỗi dừng (detector KHÔNG chạy), `RunStats.skipped++`.
- 1.2 — Frame CÓ đủ chuyển động → trả packet nguyên vẹn (đi tiếp DetectStage) + ghi `artifacts["motion_ratio"]:float` (quan sát).
- 1.3 — Frame ĐẦU (chưa có frame trước làm mốc) → CHO ĐI TIẾP (không đủ dữ liệu để quyết skip) + lưu làm mốc.

### Requirement 2: Đo chuyển động = tỉ lệ pixel đổi giữa 2 frame liên tiếp
**User Story:** Là kỹ sư, tôi muốn tiêu chí chuyển động rõ ràng, kiểm chứng được.
#### Acceptance Criteria
- 2.1 — `motion_ratio` = (số phần tử có `|curr - prev| > pixel_diff_threshold`) / (tổng phần tử). So trên chính `media_ref.array` (uint8, HxWxC).
- 2.2 — `pixel_diff_threshold` (mặc định 25) và `min_area_ratio` (mặc định 0.005) cấu hình được. `motion_ratio >= min_area_ratio` → CÓ chuyển động.
- 2.3 — 2 frame KHÁC SHAPE (đổi độ phân giải nguồn) → coi là CÓ chuyển động (cho đi tiếp) + cập nhật mốc (không so được → an toàn: không bỏ nhầm).

### Requirement 3: Stateful đúng cách + camera-affinity (K-042)
**User Story:** Là kiến trúc sư, tôi muốn gate nhớ frame trước theo từng camera, không trộn giữa camera.
#### Acceptance Criteria
- 3.1 — `MotionGateStage` giữ frame-trước NỘI BỘ — 1 instance/1 camera.
- 3.2 — Nhận `source_id` khác source đã thấy → fail-fast (raise ValueError → ERROR) — không trộn mốc.
- 3.3 — `teardown` giải phóng frame-trước (state).

### Requirement 4: Cắm config + CLI + không phá lõi
**User Story:** Là kỹ sư triển khai, tôi muốn bật motion-gate qua config/CLI mà không đổi code.
#### Acceptance Criteria
- 4.1 — Đăng ký builder `motion_gate` (params `pixel_diff_threshold`, `min_area_ratio`) vào registry (+ allowed_params).
- 4.2 — CLI `--motion-gate` (bật, đặt TRƯỚC detect trong chuỗi profile).
- 4.3 — Chỉ THÊM: `domain` motion fn + `MotionGateStage` + đăng ký + cờ. KHÔNG sửa BaseStage/executor/DetectStage/runner. Baseline **511/1 · lint 5/0** giữ.

### Requirement 5: Kiểm chứng được KHÔNG cần GPU/camera
**User Story:** Là kỹ sư, tôi muốn test motion-gate xác định trên máy dev, để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test bằng frame numpy dựng tay: 2 frame giống hệt → skip; frame đổi nhiều → đi tiếp; frame đầu → đi tiếp; khác shape → đi tiếp; mixed source → ERROR.
- 5.2 — Test xác định (frame cố định, ngưỡng cố định — không random).

## Non-Goals
- KHÔNG MOG2/optical-flow/ROI-mask · KHÔNG downscale-tối-ưu · KHÔNG đa-camera-1-instance.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` có: hàm motion-diff thuần + `MotionGateStage` (skip qua SkipFrameSignal + stateful + camera-affinity +
first-frame/shape edge) + đăng ký config/CLI + Correctness Properties (map Requirements) + Testing no-GPU. **0 diagnostic.**

## Glossary
- **motion-gate** — Stage rẻ (CPU) chặn frame tĩnh trước detector (giảm tải GPU).
- **motion_ratio** — tỉ lệ pixel đổi giữa 2 frame liên tiếp (> pixel_diff_threshold).
- **SkipFrameSignal** — exception BaseStage bắt → SKIPPED → executor dừng chuỗi (detector không chạy). Đã có sẵn.
- **camera-affinity (K-042)** — 1 instance/1 camera; trộn source → fail-fast.
