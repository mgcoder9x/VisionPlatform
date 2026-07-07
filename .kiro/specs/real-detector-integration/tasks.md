# Implementation Plan

## Overview

Đóng gap coordinate-transform để detector thật cắm vào ĐÚNG toạ độ. Chia 2 phần theo tính kiểm-chứng-được:
**Phần A** (LetterboxTransform domain + NMS domain + DetectorPipeline adapters — verify NGAY, không dep nặng) =
**HOÀN TẤT**. **Phần B** (OnnxDetector — cần onnxruntime + model) = **GATED**, chờ user chốt Q3 (cho cài onnxruntime verify).

Trạng thái Phần A: **327 passed/1 skipped · lint 5/0 · 20 test mới (property 300 examples + unit)**.

## Tasks

- [x] 1. Verify contract detector hiện có + gap (đọc IDetector/FakeDetector/BBox+CoordinateSpace/Detection; grep xác nhận CHƯA có transform)
  - _Requirements: R1, R4_

- [x] 2. `domain/letterbox_transform.py` — LetterboxTransform (scale/pad + forward/inverse point/box + clamp + fail-fast space)
  - _Requirements: R1.1, R1.2, R1.3_

- [x] 3. `domain/nms.py` — iou + nms_indices (INDEX-based: domain không import Detection@kernel; per-label greedy)
  - _Requirements: R2.3_

- [x] 4. `adapters/detector_pipeline.py` — DetectorPipeline (Decorator over IDetector, resize DI) + letterbox_resize_np (numpy)
  - _Requirements: R2.1, R2.2, R2.4_

- [x] 5. Tests + verify: test_letterbox_transform.py (property round-trip + unit) + test_detector_pipeline.py (pipeline + NMS)
  - Chạy: 20 passed. Full: 327 passed/1 skipped. Lint: 5 kept/0 broken. getDiagnostics 0.
  - _Requirements: R5.1, R5.2, R5.3_

- [x] 6. **(Q3 ✅ user duyệt)** Phần B: verify `onnxruntime`+`onnx` cài+chạy THẬT (Identity model, session run OK) → `adapters/onnx_detector.py` (model-agnostic, preprocess/postprocess DI, lazy import, `chw_float_normalize`) + optional dep `.[onnx]` + contract forbidden `onnxruntime`/`onnx` (domain+kernel, negative-test BROKEN→KEPT) + `tests/test_onnx_detector.py` (guard importorskip, model ONNX tí hon, ghép DetectorPipeline).
  - Verify: onnxruntime 1.27.0 + onnx 1.22.0 chạy thật; 4 test onnx PASS; full 331 passed/1 skipped; lint 5 kept/0 broken (negative-test có răng); getDiagnostics 0.
  - _Requirements: R3.1, R3.2, R3.3_

- [x] 7. **(Phần C — YOLO postprocess, verify được không cần weight)** `adapters/yolo_postprocess.py::yolov8_decode` (decode [1,4+nc,N] raw → Detection MODEL_INPUT) + `describe_onnx()` (đối chiếu layout file thật) + test tensor tổng hợp + tích hợp ONNX-stub→decode→DetectorPipeline.
  - Verify: 8 test PASS; full 339 passed/1 skipped; lint 5/0; getDiagnostics 0.
  - _Requirements: R3.1 (parse output)_

- [x] 7b. **yolov5_decode** (weight user là YOLOv5, xác nhận từ code syn): `adapters/yolo_postprocess.py::yolov5_decode` ([1,N,5+nc] có objectness, conf=obj×class) + 4 test (tensor tổng hợp + ONNX-stub v5→pipeline). 356/1, lint 5/0. Sẵn cho khi có .onnx.
  - _Requirements: R3.1_

- [ ] 8. **(CHẶN CUỐI — cần user)** User export `.pt`→`.onnx` ở env syn (yolov5, torch đúng version — export tại máy này FAIL #191) → đưa vào `models/` → `describe_onnx` đối chiếu layout → wire OnnxDetector(chw_float_normalize, yolov5_decode)+DetectorPipeline chạy trên ảnh/video THẬT + đo.
  - _Requirements: R3.2 (verify model thật)_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2", "3"] },
    { "wave": 3, "tasks": ["4"] },
    { "wave": 4, "tasks": ["5"] },
    { "wave": 5, "tasks": ["6"] },
    { "wave": 6, "tasks": ["7"] },
    { "wave": 7, "tasks": ["8"] }
  ]
}
```

Task 1 → (2,3 song song: transform + nms độc lập) → 4 (pipeline dùng cả 2) → 5 (test) → 6 (Phần B, gated).

## Notes

- **Q1 chốt:** làm Phần A trước (verify được + tiền đề bắt buộc), Phần B sau.
- **Q2 chốt:** GỒM NMS vào Phần A (thuần domain, verify được, detector thật cần); pipeline `nms_iou=None` mặc định (tắt), bật khi cần.
- **Q3 CHỜ user:** cho phép `pip install onnxruntime` để verify Phần B? Chưa cài → chưa làm OnnxDetector (không code không kiểm chứng).
- **Layer insight (K-028):** NMS ở domain PHẢI index-based (boxes+scores+labels → kept indices) vì domain là tầng THẤP NHẤT, cấm import `Detection`@kernel. Pipeline (adapters) ghép index về Detection.
- **Chưa làm (Phần B / bản sau):** OnnxDetector · model YOLO thật + weights/license · GPU · batching · tracking · đo mAP.
