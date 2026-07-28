# Implementation Plan

> Kế hoạch triển khai TDD cho spec `image-preprocess-and-labeling`. Nguồn: `requirements.md` (R1-R12) + `design.md` (§A/§B/§C/§D).
> Thứ tự đã chốt (§D-1): **Wave 1 (Label) trước** → **Wave 2 (Preprocess) sau**. Mỗi task: viết test TRƯỚC → code → `vp verify` xanh mới đánh dấu xong.
> Ràng buộc xuyên suốt (R11): tuân import 6-layer (domain thuần không cv2 · runtime chỉ kernel · adapter chỉ kernel) · từng slice nhỏ · có bằng chứng test.

## Overview

Hai Wave độc lập, làm tuần tự: **Wave 1 (Label, task 1-6)** đóng rủi ro gán-nhầm-tên + tách canonical⊥display;
**Wave 2 (Preprocess T3, task 7-13)** thêm khung op cắm-được nghịch-biến-toạ-độ. Mỗi leaf-task theo TDD
(test trước → code → xanh). Task 6 và 13 là cổng verify của mỗi Wave.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2", "3", "4", "5", "6"], "dependsOn": [] },
    { "wave": 2, "tasks": ["7", "8", "9", "10", "11", "12", "13"], "dependsOn": ["6"] }
  ],
  "edges": [
    { "from": "1", "to": "2" },
    { "from": "1", "to": "4" },
    { "from": "2", "to": "4" },
    { "from": "3", "to": "4" },
    { "from": "3", "to": "5" },
    { "from": "4", "to": "5" },
    { "from": "2", "to": "6" },
    { "from": "5", "to": "6" },
    { "from": "6", "to": "7" },
    { "from": "7", "to": "11" },
    { "from": "8", "to": "9" },
    { "from": "8", "to": "10" },
    { "from": "9", "to": "11" },
    { "from": "10", "to": "11" },
    { "from": "11", "to": "12" },
    { "from": "11", "to": "13" }
  ]
}
```

Nhánh chính tuần tự: `1 → 2 → 4 → 5 → 6 → 7 → 11 → 13`. Task `3` (DisplayPolicy) chèn song song trước `4`;
`8/9/10` (ops + nghịch-biến) song song trước `11`; `12` (đo) chèn sau `11`. Wave 1 ⊥ Wave 2 (không chia sẻ code).

## Tasks

### WAVE 1 — HIỂN THỊ TÊN VẬT THỂ (Label Display)

- [x] 1. LabelMap: value-object fail-safe (kernel) + loader (adapter)
  - [x] 1.1 Viết test cho LabelMap resolve: id hợp lệ → canonical; id ngoài phạm vi → `class_<id>`; map rỗng → mọi id `class_<id>`; không raise
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 Thêm value-object LabelMap (kernel, frozen, thuần) với method `canonical(cid: int) -> str` fail-safe `class_<id>`
    - _Requirements: 1.1, 1.2, 1.6_
  - [x] 1.3 Viết test loader: đọc file `.names`/metadata cạnh `.onnx`; ưu tiên file > config `labels` > rỗng
    - _Requirements: 1.3, 1.4_
  - [x] 1.4 Thêm loader ở adapter (đọc I/O) dựng LabelMap theo thứ tự ưu tiên nguồn
    - _Requirements: 1.3, 1.4, 1.6_

- [ ] 2. Wire LabelMap vào decoder (thay `str(cid)`), giữ hành vi cho id hợp lệ
  - [x] 2.1 Viết test: `yolov8_decode`/`yolov5_decode` với LabelMap → id hợp lệ ra canonical (bằng kết quả cũ khi labels đúng+đủ); id ngoài phạm vi → `class_<id>` (KHÔNG số trần)
    - _Requirements: 1.5_
  - [x] 2.2 Sửa `yolo_postprocess.py` (`yolov5_decode`, `yolov8_decode`) route qua LabelMap fail-safe thay biểu thức `labels[cid] if ... else str(cid)`
    - _Requirements: 1.5_
  - [x] 2.3 Cập nhật caller (`pipeline_factory`) dựng/truyền LabelMap; giữ tương thích config `labels` hiện có
    - _Requirements: 1.3, 1.5_

- [ ] 3. DisplayPolicy: thuần @domain, i18n/alias/gộp/ẩn/màu-ổn-định, chồng được
  - [x] 3.1 Viết test DisplayPolicy: mặc định rỗng → `display_name=canonical`, `visible=true`; alias; gộp lớp; ẩn lớp; chồng nhiều quy tắc
    - _Requirements: 3.2, 3.3, 3.4_
  - [x] 3.2 Viết test màu ổn định: cùng canonical → cùng `color_key` mọi lần gọi
    - _Requirements: 3.5_
  - [x] 3.3 Thêm DTO `DisplayDecision {visible, display_name, group, color_key}` + DisplayPolicy (domain thuần, không cv2/torch/I/O)
    - _Requirements: 3.1, 3.6_
  - [x] 3.4 Hiện thực i18n/alias + gộp + ẩn + `color_key` (hash canonical ổn định), cho phép chồng quy tắc theo thứ tự xác định
    - _Requirements: 3.3, 3.4, 3.5_

- [ ] 4. Bất biến canonical ⊥ display (analytics không thấy display-name)
  - [ ] 4.1 Viết test bất biến: đổi DisplayPolicy (alias/i18n/gộp/ẩn) KHÔNG đổi `Detection.label` mà stabilizer/crossing/DB dùng
    - _Requirements: 2.1, 2.2_
  - [ ] 4.2 Xác nhận (test + đọc code) display-name CHỈ áp ở mép projection/overlay, KHÔNG ở tầng analytics
    - _Requirements: 2.3_

- [ ] 5. Render: phơi `displayName`/`colorKey` ra `/overlay` + client vẽ
  - [ ] 5.1 Viết test projection: payload `/overlay` chứa `displayName` + `colorKey`; detection `visible=false` KHÔNG có trong payload
    - _Requirements: 5.1, 5.3_
  - [ ] 5.2 Áp DisplayPolicy tại `overlay_projection` (mép ra): thêm `displayName`/`colorKey`, lọc `visible=false`
    - _Requirements: 5.1, 5.3_
  - [ ] 5.3 Viết test Ẩn ⊥ Đếm: lớp `visible=false` không vẽ NHƯNG vẫn được đếm/analytics theo canonical
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ] 5.4 Cập nhật client `_PAGE`: vẽ `displayName` + confidence (format `0.87`) theo `colorKey`; cắt tên dài; ẩn khi `visible=false`
    - _Requirements: 5.2, 5.4_

- [ ] 6. Verify Wave 1 (bằng chứng)
  - [ ] 6.1 Chạy `vp verify` (test + import-linter 7 kept/0 broken + drift + secret) xanh; verify browser overlay hiển thị displayName/màu
    - _Requirements: 11.1, 11.2, 11.3_

### WAVE 2 — TIỀN XỬ LÝ ẢNH THEO CẢNH (Preprocess T3)

- [ ] 7. `MediaPacket.with_media()` (copy-on-write)
  - [ ] 7.1 Viết test: `with_media(new_frame)` trả packet mới với frame thay, metadata giữ nguyên (không đột biến packet gốc)
    - _Requirements: 7.2_
  - [ ] 7.2 Thêm `MediaPacket.with_media()` (CoW)
    - _Requirements: 7.2_

- [ ] 8. Registry op-agnostic + bộ op numpy-thuần (domain)
  - [ ] 8.1 Viết test registry: đăng ký op mới + tra theo tên, không sửa PreprocessStage
    - _Requirements: 8.1_
  - [ ] 8.2 Thêm registry op (op-agnostic) + `domain/preprocess_ops.py` op numpy-thuần: gamma, brightness/contrast, gray, resize-scale, ROI-crop, white-balance, sharpen
    - _Requirements: 8.1, 8.2, 8.4_
  - [ ] 8.3 Viết test tính thuần/xác định: mỗi op cùng input → cùng output (không cần camera)
    - _Requirements: 8.3_

- [ ] 9. Op cần cv2 (adapter): denoise, CLAHE
  - [ ] 9.1 Viết test denoise/CLAHE (adapter) xác định trên ảnh mẫu
    - _Requirements: 8.2, 8.3, 8.4_
  - [ ] 9.2 Thêm op cv2 ở `adapters/` (giữ domain không import cv2 — R11.1) + đăng ký vào registry
    - _Requirements: 8.2, 8.4_
  - [ ] 9.3 Để de-warp (fisheye) là ĐIỂM-CẮM (đăng ký được) nhưng CHƯA hiện thực (Non-Goal v1)
    - _Requirements: 8.5, 12.2_

- [ ] 10. Nghịch-biến toạ-độ cho op đổi hình học
  - [ ] 10.1 Viết test round-trip: crop/resize rồi map ngược một điểm đã biết → sai số ≤ 1px
    - _Requirements: 9.1, 9.2_
  - [ ] 10.2 Mỗi op đổi hình học (crop/resize) trả kèm transform NGHỊCH; nối chuỗi nghịch đúng thứ tự (ngược thứ tự áp) về ORIGINAL_FRAME
    - _Requirements: 9.1, 9.3_

- [ ] 11. `PreprocessStage` (runtime) + config `[preprocess]` + wire, no-regression
  - [ ] 11.1 Viết test no-regression: không cấu hình op → frame đi qua NGUYÊN VẸN (bytes-identical), detect y hệt hiện tại
    - _Requirements: 6.1, 6.3_
  - [ ] 11.2 Viết test thứ tự: chuỗi op chạy đúng thứ tự khai báo trong config
    - _Requirements: 7.3_
  - [ ] 11.3 Thêm `runtime/preprocess_stage.py::PreprocessStage` (`MediaPacket→MediaPacket`, chỉ phụ thuộc kernel)
    - _Requirements: 7.1, 7.4_
  - [ ] 11.4 Parse config `[preprocess]` TOML (danh sách op + tham số, có thứ tự) per-pipeline/per-camera
    - _Requirements: 7.5_
  - [ ] 11.5 Wire PreprocessStage vào detect loop (web `_detect_loop`) TRƯỚC detect; nối transform nghịch vào inverse-transform toạ-độ cuối
    - _Requirements: 6.2, 9.3_

- [ ] 12. Đo tác động op (chọn theo số, không cảm tính)
  - [ ] 12.1 Thêm harness `benchmarks/` đo recall/precision + CPU khi bật/tắt từng op; op T3 KHÔNG tự bật mặc định
    - _Requirements: 10.1, 10.2_

- [ ] 13. Verify Wave 2 + Non-Goal guards
  - [ ] 13.1 Chạy `vp verify` xanh (test + import-linter domain-không-cv2 + drift + secret); xác nhận Non-Goal v1 (không augment-train, de-warp chỉ điểm-cắm, không thư-viện-ngoài nặng)
    - _Requirements: 11.1, 11.3, 11.4, 12.1, 12.2, 12.3_

## Notes

- **Ranh giới tầng (R11.1):** op numpy-thuần → `domain/preprocess_ops.py`; op cần cv2 (denoise/CLAHE) → `adapters/`; PreprocessStage → `runtime/` (chỉ phụ thuộc kernel); LabelMap value-object → kernel, loader → adapter; DisplayPolicy → domain thuần.
- **Chỉ task code/test** — không có task deploy/kiểm-thủ-công. Verify browser (Playwright MCP) ở 6.1 dùng URL sạch + tiêm `Authorization` (K-124), KHÔNG dùng `http://user:pass@host/`.
- **De-warp (fisheye)** = điểm-cắm đăng-ký-được nhưng CHƯA hiện thực trong v1 (cần tham số calib camera — §D-4, R12.2).
- Sau mỗi task hoàn thành: ghi LOG + cập nhật activeContext + `vp check` PASS trước khi sang task kế (§2/§2.5).
