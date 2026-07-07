# Design Document

> **Trạng thái:** PHA 1 (design) — CHỜ user valid + chốt Q1–Q3 trước tasks/code.
> **Neo:** requirements (R1–R5) + code thật đã đọc: `kernel/ports/detector.py` (IDetector), `adapters/fake_detector.py`,
> `domain/bbox.py` (BBox + CoordinateSpace), `kernel/inference_protocol.py` (Detection). Gap "chưa có transform"
> đã verify bằng grep toàn `src`.
> **Cập nhật lúc:** 2026-07-04.

## Overview

Đóng gap KIẾN TRÚC: box detector ra ở MODEL_INPUT (ảnh đã letterbox 640×640) phải được đưa VỀ ORIGINAL_FRAME
(frame camera) mới dùng được. Thêm 3 mảnh, tách theo layer + tính kiểm-chứng-được:

```
 ORIGINAL_FRAME frame (H×W, từ SHM)
      │  (A) LetterboxTransform: scale + pad   [domain, thuần toán]
      ▼
 MODEL_INPUT array (model_h×model_w)  ──►  inner IDetector.detect()  ──► list[Detection] (box MODEL_INPUT)
      ▲                                                                          │
      │  (A) inverse_box: (coord−pad)/scale → BBox(ORIGINAL_FRAME)               │  (B) OnnxDetector = inner thật
      └──────────────────────────────  DetectorPipeline (adapters, là IDetector) ┘
                       trả list[Detection] box ĐÃ Ở ORIGINAL_FRAME  (+ NMS tuỳ chọn)
```

- **Phần A (verify NGAY, không dep nặng):** `LetterboxTransform` (domain) + `DetectorPipeline` (adapters).
- **Phần B (GATED môi trường):** `OnnxDetector` (adapters, cần `onnxruntime`) — chỉ làm khi verify được (Q3).

## Architecture

### QĐ-1 — `LetterboxTransform` ở `domain/` (thuần toán, không I/O)
Chỉ số học trên BBox + CoordinateSpace (đã ở domain). Domain được dùng numpy (bbox.py đã vậy). KHÔNG cv2/onnx.
LÝ DO: phần TOÁN toạ độ là nơi bug production hay xảy ra nhất → đặt ở domain = thuần, deterministic, property-test
được tuyệt đối, tái dùng cho MỌI detector. Tách khỏi pixel-resize (I/O-ish) là tách bản chất khỏi hạ tầng.

### QĐ-2 — `DetectorPipeline` ở `adapters/` (Decorator over IDetector), pixel-resize TIÊM VÀO (DI)
`DetectorPipeline` tự thoả `IDetector` (R2.4) nhưng bọc 1 inner `IDetector` (tiêm qua DI, kiểu port — KHÔNG
import adapter cụ thể) + `LetterboxTransform`. Chỉ import domain + kernel(port/Detection) → hợp lệ contract
"Adapters la leaf". Pixel-resize là chiến lược TIÊM (`resize_fn`, mặc định numpy nearest-neighbor thuần) → phần A
verify không cần cv2; phần B có thể thay resize bằng cv2/onnx-preprocess mà KHÔNG đổi logic toạ độ.
LÝ DO đặt adapters (không application): pipeline KHÔNG chạm runtime (không SHM) — chỉ domain+kernel; là 1
implementation ghép của port IDetector (Decorator) → đúng bản chất leaf, cắm thẳng vào InferenceServer.

### QĐ-3 — `OnnxDetector` ở `adapters/` (leaf), `onnxruntime` là dep adapter — GATED
Chỉ triển khai khi `onnxruntime` cài + `InferenceSession` chạy được trên máy (verify TRƯỚC, Q3). Thêm forbidden
`onnxruntime` cho domain+kernel (import-linter, như đã làm với zmq/msgpack). KHÔNG verify được → DỪNG, không viết
code không kiểm chứng (luật user).

## Components and Interfaces

- `domain/letterbox_transform.py`:
  - `LetterboxTransform(orig_h, orig_w, model_h, model_w)` — frozen; tính `scale`, `pad_x`, `pad_y` lúc khởi tạo.
  - `.forward_point(x, y) -> (mx, my)` (ORIGINAL→MODEL_INPUT); `.inverse_point(mx, my) -> (x, y)`.
  - `.inverse_box(box: BBox) -> BBox` — fail-fast nếu `box.space != MODEL_INPUT`; trả BBox ORIGINAL_FRAME
    (clamp vào [0, orig] để không âm/tràn — R5.1).
  - `.forward_box(box: BBox) -> BBox` (đối xứng, phục vụ test round-trip).
- `domain/nms.py` (Q2, tuỳ chọn): `nms(detections, iou_threshold) -> list[Detection]` — thuần numpy, IoU trên BBox cùng space.
- `adapters/detector_pipeline.py`:
  - `DetectorPipeline(inner: IDetector, model_h, model_w, *, resize_fn=letterbox_resize_np, nms_iou=None)`.
  - `setup()/teardown()` → uỷ quyền inner. `detect(frame)`: transform = LetterboxTransform(frame.shape, model); 
    `mi = resize_fn(frame, transform)`; `dets = inner.detect(mi)`; map `inverse_box` mỗi det; (NMS nếu nms_iou) → trả.
  - `letterbox_resize_np(frame, transform) -> np.ndarray` (module-level, numpy nearest-neighbor + pad — deterministic).
- `adapters/onnx_detector.py` (Phần B, GATED): `OnnxDetector(model_path, labels, *, providers=...)` thoả IDetector.

## Data Models
KHÔNG DTO mới. Tái dùng `BBox`(domain) + `Detection`(kernel). `LetterboxTransform` là value-object domain (frozen).

## Correctness Properties

### Property 1: Round-trip identity (toán transform)
`forward_box` rồi `inverse_box` trả BBox ≈ ban đầu (sai số float bounded, ví dụ < 1e-6 sau chuẩn hoá scale). **Validates: Requirements 1**

### Property 2: Pipeline trả box ORIGINAL_FRAME đúng vị trí
Với FakeDetector giả trả box giữa MODEL_INPUT, `DetectorPipeline.detect(frame)` trả `Detection` có
`box.space == ORIGINAL_FRAME` + toạ độ = inverse đúng (khớp scale+pad đã tính). **Validates: Requirements 2**

### Property 3: Layer + regression
`onnxruntime` cấm ở domain+kernel (lint 5→6 contract cập nhật, vẫn 0 broken); test cũ (307/1) xanh. **Validates: Requirements 3, 4, 5**

## Error Handling
`inverse_box` sai space → `ValueError` fail-fast (bug lập trình, không nuốt). `resize_fn` sai shape → nổ sớm.
`OnnxDetector.setup` thiếu model/onnxruntime → RuntimeError rõ ràng (không chạy detect ngầm).

## Testing Strategy
- `tests/test_letterbox_transform.py`: property (Hypothesis) round-trip + unit pad/scale các tỉ lệ (vuông, ngang, dọc).
- `tests/test_detector_pipeline.py`: FakeDetector 640×640 → box ra ORIGINAL_FRAME đúng vị trí + space; NMS (nếu Q2).
- `tests/test_onnx_detector.py` (Phần B): GUARD skip nếu thiếu onnxruntime/model.
- Regression: full `pytest` (307 + mới) + `lint-imports` (thêm contract onnxruntime).

## Open Questions
- **Q1 ✅:** làm Phần A trước (verify được + tiền đề bắt buộc) — ĐÃ LÀM XONG.
- **Q2 ✅:** GỒM NMS vào Phần A (`domain/nms.py`, index-based) — ĐÃ LÀM; pipeline `nms_iou=None` mặc định.
- **Q3 ✅ (user duyệt):** đã `pip install onnxruntime onnx` + VERIFY chạy thật (Identity model + session.run OK).
  `OnnxDetector` model-agnostic (preprocess/postprocess DI) + optional dep `.[onnx]` + contract forbidden. LÀM XONG.

## Kết quả VERIFY (PHA 2 — Phần B ONNX)
- onnxruntime **1.27.0** + onnx **1.22.0** cài + chạy THẬT (tạo Identity model, `InferenceSession.run` trả đúng).
- `tests/test_onnx_detector.py` (guard importorskip): chw_float_normalize + session chạy thật (confidence phản ánh input) + fail-fast trước setup + ghép DetectorPipeline (box ra ORIGINAL_FRAME). **4 test PASS.**
- Contract `onnxruntime`/`onnx` cấm ở domain+kernel — **negative-test có răng** (thêm import vào domain.nms → BROKEN; gỡ → KEPT).
- Full **331 passed/1 skipped · lint 5 kept/0 broken** · getDiagnostics 0.
- **K-029 (license, điều nên biết):** KHÔNG nhúng model YOLO (AGPL-3.0). Adapter model-agnostic → chọn model license-thân-thiện (RTMDet/RT-DETR/YOLOX Apache-2.0) hoặc mua license Ultralytics khi làm sản phẩm đóng.

## Kết quả VERIFY (PHA 2 — Phần A)
- `tests/test_letterbox_transform.py`: property round-trip (Hypothesis 300 examples) + unit scale/pad/clamp/fail-fast.
- `tests/test_detector_pipeline.py`: pipeline trả box ORIGINAL_FRAME đúng vị trí (1280×720→model 640: (320,40,640,640)) + NMS (per-label greedy).
- **20 test mới PASS · full 327 passed/1 skipped · lint 5 kept/0 broken** · getDiagnostics 0.
- **Layer insight (K-028):** NMS ở domain index-based (boxes+scores+labels→kept idx) vì domain↛kernel (không import Detection); pipeline@adapters ghép lại.


---

## PHẦN C — YOLO postprocess (thêm 2026-07-05, user có weight thật)

### Bối cảnh + ranh giới chống-bịa
User có file weight YOLO. Nhưng YOLO xuất ONNX ra NHIỀU layout output khác nhau → KHÔNG được đoán:
- **YOLOv8/v11 detect (Ultralytics) raw:** output `[1, 4+nc, N]` (vd COCO `[1, 84, 8400]`), box `[cx,cy,w,h]` ở
  MODEL_INPUT pixel, **KHÔNG có objectness** riêng (conf = max class score). [độ chắc: cao — layout export mặc định Ultralytics; PHẢI verify lại bằng inspect file thật].
- **YOLOv5:** `[1, N, 85]` = `[cx,cy,w,h, objectness, 80 class]` (CÓ objectness) → conf = objectness × class. [khác v8].
- **End2end (nhúng NMS):** `[1, N, 6]` = `[x1,y1,x2,y2,conf,cls]` hoặc 4 output rời (num_dets/boxes/scores/classes).

→ QĐ-C1: viết decode cho layout PHỔ BIẾN NHẤT (YOLOv8 raw `[1, 4+nc, N]`, nc suy từ shape) — VERIFY bằng tensor
tổng hợp (không cần weight). Trước khi chạy weight THẬT: dùng `describe_onnx(path)` in input/output shape → ĐỐI CHIẾU
layout. Nếu file khác (v5/end2end) → viết variant decode tương ứng (chỉ khi thấy shape thật, không đoán).

### Components (Phần C)
- `adapters/yolo_postprocess.py`:
  - `yolov8_decode(raw, *, conf_threshold=0.25, labels=None, layout="nc_first") -> list[Detection]` — thuần numpy:
    squeeze batch → (nếu nc_first) transpose `[4+nc, N]→[N, 4+nc]` → box `[cx,cy,w,h]` + class scores → argmax class,
    conf=max → lọc conf≥threshold → BBox(x=cx−w/2, y=cy−h/2, w, h, MODEL_INPUT). NMS + inverse do DetectorPipeline lo.
- `adapters/onnx_detector.py::describe_onnx(model_path) -> dict` — in tên+shape input/output để ĐỐI CHIẾU layout file thật.

### Property (Phần C)
- **Property C1:** `yolov8_decode` trên tensor tổng hợp `[1, 4+nc, N]` có 1 anchor conf cao + các anchor conf thấp →
  trả đúng 1 Detection (box xywh→xy đúng, label=argmax, conf=max), lọc anchor dưới ngưỡng. **Validates: R3 (parse output)**

### CHỜ USER (Phần C — chặn cuối, không verify được nếu thiếu)
- **QC-1:** ĐƯỜNG DẪN file weight `.onnx` (đặt trong repo hoặc cho path tuyệt đối) → tôi chạy `describe_onnx`
  ĐỐI CHIẾU layout + `n_classes` + input size. Nếu khớp YOLOv8 raw → chạy end-to-end; nếu khác → viết variant.
- **QC-2:** danh sách nhãn lớp (labels) + input size model (vd 640) + conf/iou threshold mong muốn.
