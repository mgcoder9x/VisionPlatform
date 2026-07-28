# Requirements Document

> Tài liệu YÊU CẦU (EARS) — Image Preprocessing & Label Display. Nguồn: `design.md` (§A preprocess · §B label · §C phạm vi · §D quyết định đã chốt).
> Ngôn ngữ: tiếng Việt. Quy ước chống bịa: **(MỚI)** = chưa tồn tại · **[đã có]** = đã xác nhận trong code.
> EARS: WHEN/WHILE/IF-THEN (sự kiện/điều kiện) · THE SYSTEM SHALL (bất biến). Mỗi AC kiểm-chứng-được bằng test.

## Introduction

Hệ thống cần chuẩn hoá HAI mép của pipeline thị giác cho sản phẩm thương mại đa-model, chạy chung trên
CPU (nay) và GPU (sau):

1. **Tiền xử lý ảnh theo cảnh (T3)** — "nhiều cách tùy trường hợp" (tối/ngược sáng/nhiễu/fisheye/ROI) cần một
   KHUNG cắm-được, op-agnostic, có thứ tự rõ ràng, và **nghịch-biến toạ-độ** cho op đổi hình học — thay vì nhét
   op vào detector (sai tầng) hay code cứng mỗi entry-point.
2. **Hiển thị tên vật thể** — tách **canonical ⊥ display**: giữ `Detection.label` [đã có] = tên lớp model
   (canonical) xuyên analytics/DB; chỉ áp tên hiển thị (i18n/alias/gộp/ẩn/màu) ở MÉP overlay. Đóng rủi ro
   hiện tại: idx-lạ → số trần và `labels` sai-thứ-tự → **gán NHẦM tên lớp âm thầm** (ground: `yolo_postprocess.py`
   `yolov5_decode`/`yolov8_decode`, cùng biểu thức `label = labels[cid] if labels is not None and cid < len(labels) else str(cid)`).

**Nguyên tắc bất biến (áp cho cả hai):** thứ do MODEL quyết định (T1 normalize + T2 letterbox) là CỐ ĐỊNH trong
adapter; thứ do TRIỂN KHAI quyết định (T3 preprocess + display-name) là CẤU-HÌNH-ĐƯỢC / CẮM-ĐƯỢC.

**Thứ tự triển khai đã chốt (§D):** Wave 1 = Label (nhỏ, đóng ngay rủi ro gán-nhầm-tên) → Wave 2 = Preprocess T3
(lớn, đụng toạ-độ). Cả hai đều là mục tiêu, không bỏ.

## Glossary

- **Canonical (nhãn chuẩn):** tên lớp do MODEL định (vd `person`, `car`), lưu ở `Detection.label`; dùng xuyên analytics/DB. Không đổi theo hiển thị.
- **Display-name (tên hiển thị):** tên áp ở mép overlay (dịch/đổi/gộp), chỉ ảnh hưởng cái người xem thấy.
- **LabelMap:** ánh xạ class-id (int) → canonical (str), theo model; fail-safe idx-lạ → `class_<id>`.
- **DisplayPolicy:** hàm thuần domain canonical → `{visible, display_name, group, color_key}`.
- **T1/T2/T3:** T1 = model-normalize (dtype/kênh/÷255) · T2 = letterbox resize về model_size + inverse-transform · T3 = tiền xử lý theo CẢNH (op cắm-được). T1/T2 [đã có] ở adapter; T3 (MỚI) ở runtime.
- **PreprocessStage:** chuỗi op T3 biến đổi `MediaPacket → MediaPacket` TRƯỚC detect.
- **Nghịch-biến toạ-độ:** op đổi hình học kèm transform ngược để box detect map về ORIGINAL_FRAME đúng pixel.
- **P-A1..P-A4 / P-B1..P-B4:** các correctness property tương ứng trong `design.md`.

## Requirements

### Requirement 1: LabelMap — nguồn chuẩn class-id → canonical, fail-safe

**User Story:** Là kỹ sư tích hợp model, tôi muốn một nguồn DUY NHẤT ánh xạ class-id → tên lớp canonical theo model,
để không còn mỗi decoder tự truyền list nhãn (dễ lệch thứ tự → gán sai tên âm thầm) và lớp lạ luôn được xử lý an toàn.

#### Acceptance Criteria

1. WHEN decoder cần tên lớp cho một class-id hợp lệ (trong phạm vi map) THE SYSTEM SHALL trả về canonical tương ứng.
2. IF class-id nằm NGOÀI phạm vi LabelMap THEN THE SYSTEM SHALL trả về `class_<id>` (vd `class_7`) và KHÔNG raise, KHÔNG gán nhầm tên lớp khác.
3. THE SYSTEM SHALL nạp LabelMap theo thứ tự ưu tiên nguồn: (a) file `.names`/metadata cạnh `.onnx` → (b) config `labels` → (c) rỗng (mọi id → `class_<id>`). *(§D-5)*
4. WHEN cả file metadata lẫn config `labels` cùng có mặt THE SYSTEM SHALL ưu tiên file metadata cạnh model.
5. THE SYSTEM SHALL thay biểu thức `str(cid)` hiện tại trong `yolov5_decode`/`yolov8_decode` bằng LabelMap fail-safe, giữ nguyên hành vi cho id hợp lệ (không đổi kết quả khi `labels` đúng và đủ).
6. WHERE LabelMap là adapter đọc file THE SYSTEM SHALL tuân thủ import 6 layer (adapter đọc I/O; DTO/type ở kernel; không I/O ở domain).

### Requirement 2: Canonical bất biến qua analytics (tách canonical ⊥ display)

**User Story:** Là kỹ sư analytics, tôi muốn đổi tên hiển thị (i18n/alias/gộp) KHÔNG làm thay đổi nhãn mà tracker/
crossing-event/DB dùng, để track không vỡ và dữ liệu lịch sử nhất quán khi khách đổi ngôn ngữ/nhãn.

#### Acceptance Criteria

1. THE SYSTEM SHALL giữ `Detection.label` [đã có] = canonical xuyên suốt stabilizer, crossing-event, và SQLite sink.
2. WHEN DisplayPolicy đổi (i18n/alias/gộp/ẩn) THE SYSTEM SHALL KHÔNG thay đổi `Detection.label` → kết quả track/DB không đổi. *(P-B1)*
3. THE SYSTEM SHALL chỉ áp display-name tại MÉP hiển thị (projection/overlay), không tại tầng analytics.

### Requirement 3: DisplayPolicy — i18n/alias/gộp/ẩn/màu, thuần domain, chồng được

**User Story:** Là người triển khai theo khách, tôi muốn cấu hình tên hiển thị (dịch, đổi tên, gộp lớp, ẩn lớp,
màu ổn định) per-deployment mà không đụng code lõi, để mỗi khách có cách hiển thị riêng.

#### Acceptance Criteria

1. THE SYSTEM SHALL cung cấp DisplayPolicy (MỚI, THUẦN @domain) nhận canonical → quyết định `{visible, display_name, group, color_key}`.
2. WHERE không cấu hình gì THE SYSTEM SHALL mặc định `display_name = canonical`, `visible = true` (không ép ai dùng i18n). *(§D-2)*
3. THE SYSTEM SHALL hỗ trợ i18n/alias (canonical → tên khác), gộp lớp (nhiều canonical → 1 group), và ẩn lớp (`visible=false`).
4. WHEN nhiều quy tắc policy cùng áp (alias + group + hide) THE SYSTEM SHALL cho phép chồng (kết hợp) theo thứ tự xác định, không mâu thuẫn. *(§D-2 "kết hợp tuỳ")*
5. WHEN cùng một canonical được hiển thị ở nhiều frame THE SYSTEM SHALL cho ra cùng một `color_key` (màu ổn định, không nhấp nháy). *(P-B3)*
6. WHERE DisplayPolicy chạy ở domain THE SYSTEM SHALL không import cv2/torch/I/O (thuần, test không cần camera).

### Requirement 4: Ẩn ⊥ Đếm (visible chỉ ảnh hưởng render)

**User Story:** Là chủ sản phẩm, tôi muốn ẩn một lớp khỏi màn hình mà hệ vẫn ĐẾM lớp đó, để "không hiển thị"
không vô tình biến thành "không thống kê" (hai quyết định nghiệp vụ khác nhau).

#### Acceptance Criteria

1. WHEN một lớp có `visible=false` THE SYSTEM SHALL không vẽ lớp đó ở overlay. *(P-B4)*
2. THE SYSTEM SHALL vẫn đếm/analytics lớp `visible=false` dựa trên canonical, BẤT KỂ trạng thái visible. *(§D-3)*
3. IF nghiệp vụ muốn "không đếm" một lớp THEN THE SYSTEM SHALL yêu cầu một filter riêng ở count-stage, KHÔNG do DisplayPolicy quyết định.

### Requirement 5: Render — phơi display-name/color ra overlay

**User Story:** Là người xem, tôi muốn nhìn thấy tên hiển thị (đã dịch/đổi) với màu ổn định theo lớp và
confidence gọn, để đọc kết quả dễ trên nhiều camera.

#### Acceptance Criteria

1. THE SYSTEM SHALL phơi `displayName` và `colorKey` (cùng canonical để tương thích ngược) trong payload `/overlay`.
2. WHEN client render một detection THE SYSTEM SHALL vẽ `displayName` + confidence theo `colorKey`.
3. WHEN một detection có `visible=false` THE SYSTEM SHALL không render nó (không xuất hiện trong payload overlay, hoặc client bỏ qua).
4. THE SYSTEM SHALL định dạng confidence dạng gọn (vd `0.87`) và xử lý tên dài (cắt/ellipsis) ở tầng render.

### Requirement 6: Không hồi quy — không bật op nào = hành vi y hệt hiện tại

**User Story:** Là người vận hành, tôi muốn thêm khung preprocess KHÔNG làm đổi hành vi khi chưa bật op nào,
để nâng cấp an toàn, không rủi ro cho hệ đang chạy.

#### Acceptance Criteria

1. WHEN không cấu hình op T3 nào THE SYSTEM SHALL cho frame đi qua NGUYÊN VẸN (bytes-identical) tới detect. *(P-A2)*
2. THE SYSTEM SHALL giữ T1 normalize (`preprocess_fn` [đã có]) và T2 letterbox (`DetectorPipeline` [đã có]) trong adapter, KHÔNG di chuyển sang T3.
3. THE SYSTEM SHALL giữ baseline test hiện tại xanh (không sửa hành vi detect khi T3 tắt).

### Requirement 7: PreprocessStage — chuỗi op cắm-được trên MediaPacket trước detect

**User Story:** Là người triển khai camera, tôi muốn khai báo một chuỗi op tiền xử lý per-camera chạy TRƯỚC
detect, để chỉnh cảnh (sáng/nhiễu/ROI...) mà không đụng detector và tái dùng cho mọi model.

#### Acceptance Criteria

1. THE SYSTEM SHALL cung cấp `PreprocessStage` (MỚI) biến đổi `MediaPacket → MediaPacket` bằng cách gọi chuỗi op theo thứ tự cấu hình.
2. THE SYSTEM SHALL cung cấp `MediaPacket.with_media()` (MỚI, copy-on-write) thay frame nhưng giữ metadata.
3. WHEN chuỗi op được khai báo trong config THE SYSTEM SHALL chạy đúng THỨ TỰ khai báo. *(P-A4)*
4. WHERE PreprocessStage sống ở runtime THE SYSTEM SHALL chỉ phụ thuộc kernel (tuân thủ import 6 layer).
5. THE SYSTEM SHALL đọc cấu hình `[preprocess]` per-pipeline/per-camera từ TOML (danh sách op + tham số, có thứ tự).

### Requirement 8: Op-agnostic registry + bộ op v1 thuần/xác định

**User Story:** Là kỹ sư nền tảng, tôi muốn một registry op tổng quát nhận bất kỳ op đăng ký, kèm bộ op phổ biến
sẵn dùng, để mở rộng về sau mà không sửa lõi.

#### Acceptance Criteria

1. THE SYSTEM SHALL cung cấp registry op tổng quát (op-agnostic): op mới đăng ký được mà không sửa PreprocessStage. *(§D-4)*
2. THE SYSTEM SHALL hiện thực bộ op v1: CLAHE, gamma, brightness/contrast, denoise, sharpen, white-balance, gray, resize-scale, ROI-crop. *(§D-4)*
3. WHEN một op nhận cùng một input THE SYSTEM SHALL cho ra cùng một output (thuần + xác định, test không cần camera). *(P-A3)*
4. WHERE op numpy-thuần THE SYSTEM SHALL đặt ở `domain/`; WHERE op cần cv2 (vd denoise) THE SYSTEM SHALL đặt ở `adapters/` (luật §4: không cv2 ở domain).
5. THE SYSTEM SHALL cung cấp de-warp (fisheye) như ĐIỂM-CẮM có sẵn nhưng CHƯA hiện thực (Non-Goal v1, cần tham số calib). *(§D-4)*

### Requirement 9: Op đổi hình học phải nghịch-biến toạ-độ

**User Story:** Là kỹ sư analytics, tôi muốn box detect trên ảnh-đã-xử-lý map ngược ĐÚNG về ảnh gốc, để crossing/
đếm/lưu toạ-độ không sai khi bật op crop/resize.

#### Acceptance Criteria

1. WHEN một op đổi hình học (crop/resize/de-warp) được áp THE SYSTEM SHALL trả kèm transform NGHỊCH để map toạ-độ detect về ảnh GỐC.
2. WHEN map ngược một điểm đã biết qua op đổi hình học THE SYSTEM SHALL cho sai số ≤ 1 pixel. *(P-A1)*
3. THE SYSTEM SHALL nối chuỗi các transform nghịch đúng thứ tự (ngược với thứ tự áp op) để toạ-độ cuối về đúng ORIGINAL_FRAME.

### Requirement 10: Chọn op theo SỐ ĐO, không cảm tính

**User Story:** Là người ra quyết định, tôi muốn đo được tác động của mỗi op (recall/precision + CPU) trên cảnh
thật, để chọn "cách tùy trường hợp" bằng số chứ không cảm tính.

#### Acceptance Criteria

1. WHEN một op T3 được bật THE SYSTEM SHALL cho phép đo tác động recall/precision + chi phí CPU (tái dùng `benchmarks/`).
2. THE SYSTEM SHALL không tự bật op T3 mặc định (op chỉ chạy khi cấu hình rõ), để mọi tác động là có chủ đích.

### Requirement 11: Tuân thủ kiến trúc & quy trình verify

**User Story:** Là người bảo trì, tôi muốn mọi thành phần mới tuân thủ import 6 layer và quy trình verify của repo,
để không phá kiến trúc và mọi "xong" đều có bằng chứng.

#### Acceptance Criteria

1. THE SYSTEM SHALL giữ import-linter 7 contracts kept/0 broken (domain thuần; runtime chỉ kernel; adapter chỉ kernel).
2. WHEN một thành phần mới hoàn thành THE SYSTEM SHALL có test chạy thật (pytest) trước khi gọi "xong".
3. THE SYSTEM SHALL giữ `vp verify` xanh (test + import-linter + drift + secret-scan) sau mỗi Wave.
4. THE SYSTEM SHALL phát triển TDD theo từng slice (từng op / từng tầng), không code khối lớn một lần.

### Requirement 12: Non-Goal v1 (chống YAGNI)

**User Story:** Là chủ sản phẩm, tôi muốn giới hạn phạm vi v1 rõ ràng, để không xây feature rỗng khi chưa có nhu cầu.

#### Acceptance Criteria

1. THE SYSTEM SHALL KHÔNG hiện thực augmentation lúc-train trong v1.
2. THE SYSTEM SHALL KHÔNG hiện thực de-warp fisheye đầy đủ trong v1 (chỉ để điểm-cắm, cần calib camera).
3. THE SYSTEM SHALL KHÔNG thêm thư viện ngoài nặng (vd albumentations) trong v1.
