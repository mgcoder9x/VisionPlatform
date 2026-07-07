# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — CHỜ user đọc-lại-valid + chốt Q1–Q3 trước design chi tiết/tasks/code.
> **Mục đích:** làm `IDetector` port PRODUCTION-SHAPED — bổ sung mảnh KIẾN TRÚC còn thiếu (preprocessing
> letterbox + coordinate-transform MODEL_INPUT→ORIGINAL_FRAME) để detector thật (ONNX/YOLO) cắm vào ĐÚNG toạ độ.
> **Cập nhật lúc:** 2026-07-04.

## Introduction

`IDetector.detect(frame)` (kernel/ports/detector.py — đã đọc) trả `list[Detection]`, mỗi `Detection.box` là
`BBox` có `CoordinateSpace` tag, "thường MODEL_INPUT" (toạ độ trên frame detector NHẬN VÀO, ví dụ 640×640).
Frame từ SHM ở `ORIGINAL_FRAME` space (độ phân giải camera). `CoordinateSpace` (domain/bbox.py) được TẠO RA
để "tránh resize/letterbox bug" (docstring nguyên văn) — NHƯNG hiện **CHƯA có component nào transform box từ
MODEL_INPUT về ORIGINAL_FRAME** (verify: grep toàn `src` chỉ ra enum `CoordinateSpace`, KHÔNG có hàm transform/
letterbox/resize). `FakeDetector` né được vì KHÔNG resize (MODEL_INPUT trùng frame size). Detector THẬT resize
frame về input model → box trả ở MODEL_INPUT; nếu downstream (vẽ/lưu/track) dùng thẳng → **box lệch toạ độ**
(bug production #1 của hệ vision). Đây là gap KIẾN TRÚC phải đóng TRƯỚC khi cắm model thật.

Sub-spec này chia 2 phần theo tính KIỂM-CHỨNG-ĐƯỢC (nguyên tắc user: chỉ triển khai cái verify được):
- **Phần A (kiến trúc, verify NGAY, không dep nặng):** toán letterbox + transform toạ độ (thuần domain/numpy).
- **Phần B (inference thật, cần môi trường):** ONNX detector adapter — GATED trên việc verify được `onnxruntime`.

## Glossary

- **letterbox**: resize giữ tỉ lệ khung hình + đệm (pad) 2 bên để vừa khung vuông model input (không méo ảnh).
- **MODEL_INPUT space**: hệ toạ độ trên ảnh đã letterbox/resize (ví dụ 640×640) mà model nhận vào.
- **ORIGINAL_FRAME space**: hệ toạ độ trên frame gốc từ camera (ví dụ 1920×1080).
- **coordinate transform (inverse)**: đưa box từ MODEL_INPUT về ORIGINAL_FRAME = bỏ pad rồi chia scale.
- **NMS (Non-Max Suppression)**: gộp/bỏ box chồng lấn cùng lớp (postprocessing chuẩn của detector).

## Requirements

### Requirement 1: Letterbox transform (toán thuần — domain)
**User Story:** Là kỹ sư, tôi muốn 1 value-object mô tả phép letterbox (scale + pad) + nghịch đảo, để mọi
adapter detector transform toạ độ NHẤT QUÁN, không lặp lại math dễ sai.
#### Acceptance Criteria
- 1.1 — Cho `(orig_h, orig_w, model_h, model_w)`, PHẢI tính `scale = min(model_w/orig_w, model_h/orig_h)` +
  `pad_x, pad_y` (đệm giữa) → xác định ánh xạ ORIGINAL→MODEL_INPUT (giữ tỉ lệ, không méo).
- 1.2 — PHẢI có `inverse_box(box_model_input) -> box_original_frame`: `(coord − pad) / scale`, trả `BBox` gắn
  `CoordinateSpace.ORIGINAL_FRAME`. Fail-fast nếu box đầu vào KHÔNG phải MODEL_INPUT (sai space = bug lập trình).
- 1.3 — PHẢI thuần domain (chỉ numpy/số học) — KHÔNG cv2/torch/onnx. Round-trip `forward` rồi `inverse` ≈ identity (sai số float bounded).

### Requirement 2: DetectorPipeline — bọc preprocessing + IDetector + postprocessing
**User Story:** Là kỹ sư, tôi muốn 1 lớp điều phối biến MỌI `IDetector` (trả box MODEL_INPUT) thành detector
trả box ORIGINAL_FRAME, để downstream luôn nhận toạ độ đúng frame gốc.
#### Acceptance Criteria
- 2.1 — Nhận `frame` ORIGINAL_FRAME → resize theo `LetterboxTransform` → gọi `inner_detector.detect(model_input)`
  → transform NGƯỢC mỗi box về ORIGINAL_FRAME (R1.2).
- 2.2 — PHẢI đảm bảo `Detection` ra có `box.space == ORIGINAL_FRAME` (bất biến kiểm được bằng test).
- 2.3 — (Tuỳ chọn, Q2) áp NMS trên box cùng lớp trước khi trả (khử trùng lặp).
- 2.4 — Chính `DetectorPipeline` cũng thoả `IDetector` (setup/detect/teardown) → cắm thẳng vào InferenceServer.

### Requirement 3: ONNX detector adapter (inference thật) — GATED môi trường
**User Story:** Là hệ thống, tôi muốn 1 detector chạy model ONNX thật, để có detection thật thay vì fake.
#### Acceptance Criteria
- 3.1 — `OnnxDetector` (adapters, leaf) PHẢI: `setup()` nạp model qua `onnxruntime.InferenceSession`; `detect(model_input)`
  chạy session → parse output → `list[Detection]` box MODEL_INPUT; `teardown()` giải phóng.
- 3.2 — CHỈ triển khai/verify khi `onnxruntime` cài + chạy được TRÊN MÁY NÀY (verify TRƯỚC — Q3). KHÔNG verify
  được → DỪNG, KHÔNG viết code không kiểm chứng (luật user). Guard/skip test nếu thiếu onnxruntime/model.
- 3.3 — Layer: `onnxruntime` là dep của ADAPTER (leaf) — thêm forbidden `onnxruntime` cho domain+kernel (import-linter).

### Requirement 4: Layer boundaries
**User Story:** Là kiến trúc sư, tôi muốn transform/pipeline/onnx đặt đúng layer, để giữ ranh giới hexagonal 6-layer.
#### Acceptance Criteria
- 4.1 — `LetterboxTransform` ở `domain/` (thuần) hoặc `kernel/` (nếu cần Detection) — KHÔNG I/O. `DetectorPipeline`
  ở `application/` hoặc `adapters/` tuỳ phụ thuộc (quyết định ở design, giữ contract 6-layer).
- 4.2 — `OnnxDetector` ở `adapters/` (leaf) — cấm import runtime/application/profiles; `onnxruntime` chỉ ở adapter.

### Requirement 5: Tests kiểm chứng
**User Story:** Là kỹ sư, tôi muốn bằng chứng transform + pipeline đúng, để tin box về ORIGINAL_FRAME chính xác.
#### Acceptance Criteria
- 5.1 — Property test (Hypothesis) transform: forward∘inverse ≈ identity; box trong khung → sau inverse vẫn hợp lệ (≥0, trong frame gốc).
- 5.2 — Test DetectorPipeline với FakeDetector (giả model 640×640) → assert box ra ORIGINAL_FRAME đúng vị trí.
- 5.3 — Mọi test cũ (307/1) giữ xanh; lint 5/0.

## Non-Goals (HOÃN — chống phình)
Model YOLO cụ thể + tải weights + license · GPU/CUDA · batching · tracking (ByteTrack) · quantization · training ·
đo mAP/độ chính xác model · video codec. (Phần B chỉ dựng KHUNG ONNX adapter khi verify được runtime, không tuning model.)

## Tiêu chí ĐẬU (Definition of Done)
Phần A: `LetterboxTransform` + `DetectorPipeline` + property/unit test THẬT (round-trip identity, box ra ORIGINAL_FRAME
đúng) + lint 5/0 + test cũ xanh. Phần B: CHỈ khi verify được onnxruntime — nếu không, ghi 🔴 + dừng (không claim xong).
