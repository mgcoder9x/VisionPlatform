# Design: Image Preprocessing & Label Display (thiết kế chuẩn, mép-vào / mép-ra của pipeline thị giác)

> Tài liệu THIẾT KẾ (design-first). **CHƯA code.** Ngôn ngữ: tiếng Việt. Quy ước chống bịa: **(MỚI)** = chưa tồn
> tại · **[đã có]** = đã xác nhận trong code · **[chưa kiểm]** = suy luận chưa đo. Mọi path/symbol "[đã có]" đã ĐỌC.
> Nguồn ground: `adapters/onnx_detector.py`, `adapters/detector_pipeline.py`, `profiles/pipeline_factory.py`,
> `runtime/display_stabilizer.py`, `kernel/inference_protocol.py::Detection`, D-140 (bản đồ điểm-tiêm preprocessing).

## 0. Vì sao có tài liệu này

User nêu 2 điểm cần "thiết kế chuẩn", không phải vá:
1. **Tiền xử lý ảnh** — "có rất nhiều cách và tùy trường hợp" → cần một khung để CHỌN đúng cách theo ca, và biết
   mỗi cách thuộc TẦNG nào (không để lẫn lộn model-coupled vs scene-coupled).
2. **Hiển thị tên vật thể** — cần chuẩn hoá đường class-id → tên hiển thị (đa model, đa ngôn ngữ, ẩn/gộp lớp,
   lớp lạ) thay vì hiện trạng "danh sách nhãn dán cứng vào detector".

Nguyên tắc xuyên suốt (áp cho cả hai): **thứ do MODEL quyết định thì cố định (đúng-sai); thứ do TRIỂN KHAI quyết
định (camera/cảnh/nghiệp vụ) thì cấu-hình-được, cắm-được.** Trộn hai loại là gốc của mọi rối về sau.

---

# PHẦN A — TIỀN XỬ LÝ ẢNH

## A.1 Hiện trạng (grounded)

Pipeline phát hiện hiện có **2 tầng tiền xử lý đã tồn tại**, tách bạch qua DI:

| Tầng | Việc | Ở đâu (code) | Ai quyết định |
|---|---|---|---|
| **T1 — model-normalize** | HWC uint8 → NCHW float32, ÷255 (hoặc mean/std), thứ tự kênh RGB/BGR, dtype | `onnx_detector.py::_default_preprocess` + `preprocess_fn` (DI) [đã có] | **MODEL** (weight được train thế nào) |
| **T2 — hình học (resize)** | letterbox (giữ tỉ lệ + pad) về `model_size`, + inverse-transform toạ độ về ảnh gốc | `DetectorPipeline` (`resize_fn`) [đã có] | **MODEL** (input shape cố định `[1,3,640,640]`) |
| **T3 — tiền xử lý theo CẢNH** | tăng sáng/tương phản, khử nhiễu, làm nét, cân bằng trắng, khử méo (fisheye), crop/mask ROI, hạ độ phân giải, xám hoá… | **CHƯA có điểm cắm thống nhất** — pipeline stage có tiền lệ (`brightness`/`dark_filter`/`motion_gate` [đã có]) nhưng web `_detect_loop` KHÔNG hook; thiếu `MediaPacket.with_media()` + `PreprocessStage` (D-140 hoãn) | **TRIỂN KHAI** (camera/cảnh) |

→ **Khoảng trống chính = T3**: T1/T2 đã đúng chỗ (adapter, model-coupled). T3 (thứ "rất nhiều cách, tùy trường
hợp") chưa có khung cắm chuẩn.

## A.2 Vấn đề & TẠI SAO (Forces)

"Nhiều cách tùy trường hợp" là bản chất của T3 — mỗi lực kéo một hướng:
- **Cảnh tối / ngược sáng** → CLAHE / gamma / histogram-eq (nhưng khuếch đại nhiễu).
- **Nhiễu ISO cao ban đêm** → denoise (nhưng làm mờ vật nhỏ → giảm recall vật xa, đối nghịch K-106/K-110).
- **Camera fisheye/góc rộng** → de-warp (nhưng tốn CPU + méo toạ độ nếu không nghịch-biến đúng).
- **Chỉ quan tâm 1 vùng** → crop/mask ROI (giảm tải + false-positive, nhưng mất ngữ cảnh ngoài ROI).
- **Băng thông/CPU eo hẹp** → hạ độ phân giải trước detect (nhưng vật nhỏ biến mất).
- **Model train trên RGB, camera ra BGR** → đây là T1 (model), KHÔNG phải T3 — dễ đặt nhầm tầng.

⇒ Không có "một cách đúng". Cái CHUẨN cần thiết kế là: **(a) một chuỗi op cắm-được, có thứ tự rõ ràng; (b) mỗi op
thuần + nghịch-biến-toạ-độ nếu đổi hình học; (c) chọn theo camera qua config; (d) đo được tác động (recall/CPU).**

## A.3 Các hướng đã cân nhắc

| Hướng | Ưu | Nhược / khi nào KHÔNG dùng |
|---|---|---|
| **(1) Nhét T3 vào `preprocess_fn` của detector** | ít file | SAI TẦNG: trộn scene-op với model-op → không tái dùng cho detector khác, không nghịch-biến toạ-độ được (T3 đổi hình học phải sửa inverse-transform của T2). LOẠI. |
| **(2) Chuỗi `PreprocessStage` trên `MediaPacket` TRƯỚC detect** (khuyến nghị) | đúng tầng (scene-op ⊥ model-op); tái dùng mọi detector; cấu-hình per-camera; đo được | cần `MediaPacket.with_media()` (CoW) + xử lý nghịch-biến toạ-độ cho op đổi-hình-học |
| **(3) Op cứng trong `_video_loop`** | nhanh trước mắt | không cấu-hình-được, lặp code mỗi entry-point, chống-tái-dùng. LOẠI (fix ngọn). |
| **(4) Thư viện ngoài (albumentations…)** | sẵn nhiều phép | nặng, nhiều phép là AUGMENT lúc-train (không hợp inference), thêm dependency lớn. LOẠI cho v1. |

## A.4 Thiết kế đề xuất (chuẩn, cắm-được)

**Bất biến phân tầng (luật):**
- **T1 + T2 do MODEL định** → GIỮ trong adapter (`preprocess_fn` + `DetectorPipeline`), **KHÔNG** phơi cho user chỉnh
  linh tinh (chỉnh sai = detect sai âm thầm). Đổi model = đổi 2 hàm này (đã đúng).
- **T3 do TRIỂN KHAI định** → **chuỗi `PreprocessStage` (MỚI)** chạy trên `MediaPacket` **TRƯỚC** khi vào detect,
  cấu-hình per-camera.

**Thành phần (MỚI, design):**
1. `domain/preprocess_ops.py` (THUẦN, numpy): mỗi op = hàm thuần `frame→frame` (clahe, gamma, denoise, sharpen,
   gray, resize_scale). Thuần → test xác định, không I/O. **Không cv2 ở domain** (luật §4) → op cần cv2 (denoise)
   đặt ở `adapters/`, op numpy-thuần ở `domain/`. *(Ranh giới này phải quyết ở §A.6.)*
2. `runtime/preprocess_stage.py::PreprocessStage` (MỚI): `MediaPacket→MediaPacket`, gọi chuỗi op theo thứ tự cấu
   hình. Op **đổi hình học** (crop/resize/de-warp) phải trả kèm **transform nghịch** để toạ-độ detect map ngược
   đúng về ảnh gốc (giống T2 inverse của `DetectorPipeline`) — **đây là phần khó nhất, phải thiết kế kỹ**.
3. `MediaPacket.with_media()` (MỚI, CoW) — thay frame giữ metadata (D-140 đã nêu).
4. Config: `[preprocess]` per-pipeline/per-camera trong TOML — danh sách op + tham số, có thứ tự.

**Thứ tự chuẩn (khuyến nghị mặc định):** `ROI-crop → de-warp → white-balance → brightness/CLAHE → denoise →
(vào T2 letterbox → T1 normalize)`. Lý do: cắt ROI sớm nhất (giảm tải cho các op sau); hình học (crop/de-warp)
trước quang học (sáng/nhiễu); denoise gần cuối (sau khi đã tăng sáng, tránh khuếch đại nhiễu do tăng sáng).

**Cưỡng chế đo (chống chỉnh mù):** mỗi op T3 khi bật PHẢI kèm khả năng đo tác động **recall/precision + CPU** (tái
dùng `benchmarks/` + verify browser) — "nhiều cách" chỉ chọn được bằng SỐ trên cảnh thật, không bằng cảm tính.

## A.5 Correctness Properties (T3)
- **P-A1 nghịch-biến toạ-độ:** ∀ op đổi hình học, box detect trên ảnh-đã-xử-lý map ngược về ảnh GỐC đúng pixel
  (sai số ≤ 1px). *(test: crop/resize rồi map ngược điểm đã biết.)*
- **P-A2 additive/đảo được:** không bật op T3 nào → hành vi y hệt hiện tại (bytes-identical frame). *(test.)*
- **P-A3 thuần + xác định:** op cùng input → cùng output (test được không cần camera).
- **P-A4 thứ tự tôn trọng config:** chuỗi chạy đúng thứ tự khai báo.

---

# PHẦN B — HIỂN THỊ TÊN VẬT THỂ (label display)

## B.1 Hiện trạng (grounded)

- `Detection.label: str` [đã có] — decoder gán, qua `yolov8_decode(raw, labels=<list>)`; `labels` đến từ CLI
  `--coco-labels` hoặc config `labels="a,b,c"` (`pipeline_factory` parse comma) [đã có].
- `label` là **chuỗi tự do**, chảy NGUYÊN qua stabilizer (match cùng-label), crossing-event, SQLite sink, và web
  overlay vẽ `label + confidence` [đã có].
- Class-idx vượt độ dài `labels` → **[đã kiểm]** `yolo_postprocess.py` L52/L97: `label = labels[cid] if labels is
  not None and cid < len(labels) else str(cid)` → trả **số trần** (`"7"`). Không crash, nhưng: (a) tên số trần mơ
  hồ, không tự-mô-tả; (b) **nếu `labels` sai thứ tự/thiếu → gán NHẦM tên lớp khác ÂM THẦM** (nguy hiểm hơn crash);
  (c) mỗi decoder tự parse `labels`, không có 1 nguồn chuẩn.

## B.2 Vấn đề & TẠI SAO

Với sản phẩm thương mại đa-model (COCO 80 lớp · ANPR · model khách tự train), "nhãn dán cứng vào detector" gãy ở:
1. **Không có registry chuẩn class-id→canonical** theo model (mỗi nơi tự truyền list, dễ lệch thứ tự → gán SAI tên
   mà không ai biết — nguy hiểm hơn crash).
2. **Trộn canonical với display:** cùng một chuỗi vừa dùng cho analytics (khớp track, ghi DB) vừa để hiển thị. Muốn
   i18n ("person"→"Người"), gộp ("car/truck/bus"→"phương tiện"), ẩn lớp, đổi tên theo khách → **đụng cả analytics**
   (DB nhiễu, track vỡ vì đổi label giữa chừng).
3. **Lớp lạ (idx ngoài map)** không có xử lý an-toàn thống nhất.
4. **Trình bày** (màu theo lớp ổn định, cắt tên dài, format confidence, chồng chữ) chưa có chuẩn.

## B.3 Thiết kế đề xuất (3 tầng, tách canonical ⊥ display)

**Nguyên tắc: giữ `Detection.label` = CANONICAL (tên lớp của model) xuyên suốt pipeline + analytics; chỉ áp
DISPLAY-NAME ở MÉP hiển thị (projection/overlay).** Nhờ vậy analytics/DB ổn định, hiển thị đổi thoải mái.

1. **LabelMap (MỚI)** — class-id (int) → canonical (str), **theo model**. Nguồn ưu tiên: file `.names`/metadata
   cạnh `.onnx` → rồi config `labels` → rồi mặc định. **Fail-safe:** idx ngoài map → `"class_<id>"` (KHÔNG crash,
   KHÔNG gán nhầm tên lớp khác). Chuẩn hoá 1 nguồn thay vì mỗi decoder tự parse.
2. **DisplayPolicy (MỚI, THUẦN @domain)** — canonical → `DisplayDecision {visible, display_name, group, color_key}`.
   Đây là nơi "hiển thị tên chuẩn" sống: i18n (vi/en), alias theo khách, gộp lớp, ẩn lớp không quan tâm, màu ổn
   định theo `color_key` (hash canonical → màu cố định, không đổi giữa frame). Config-driven per-deployment.
3. **Render (client/projection)** — vẽ `display_name` + confidence theo `color_key`; cắt tên dài; format `0.87`;
   ẩn nếu `visible=false`. Phần lớn đã ở overlay `_PAGE`, chỉ cần nhận thêm `displayName`/`colorKey` từ `/overlay`.

**Vị trí kiến trúc:** LabelMap = adapter (đọc file) + kernel DTO; DisplayPolicy = domain thuần (test được);
áp vào payload ở `overlay_projection` (mép ra) — analytics KHÔNG thấy display-name.

## B.4 Correctness Properties (label)
- **P-B1 canonical bất biến qua analytics:** đổi DisplayPolicy (i18n/alias) KHÔNG đổi `Detection.label` mà stabilizer/
  crossing/DB dùng → track không vỡ, DB nhất quán. *(test.)*
- **P-B2 lớp lạ an-toàn:** idx ngoài LabelMap → `class_<id>`, không crash, không gán nhầm. *(test.)*
- **P-B3 màu ổn định:** cùng canonical → cùng `color_key` mọi frame (không nhấp nháy màu). *(test.)*
- **P-B4 ẩn lớp:** lớp `visible=false` không xuất hiện ở overlay NHƯNG vẫn được đếm nếu nghiệp vụ cần (tách hiển-thị
  ⊥ đếm). *(test — quyết định: ẩn-hiển-thị có ẩn-đếm không? → câu hỏi valid.)*

---

## C. Phạm vi & thứ tự triển khai (khi được duyệt)
- **Wave 1 (label, nhỏ, giá trị ngay):** LabelMap fail-safe + tách canonical⊥display + DisplayPolicy tối thiểu
  (i18n + ẩn/gộp) + phơi `displayName`/`colorKey` ra `/overlay`. Rủi ro thấp, đóng rủi ro "gán nhầm tên".
- **Wave 2 (preprocess T3):** `MediaPacket.with_media()` + `PreprocessStage` + 2-3 op đầu (CLAHE, ROI-crop có
  nghịch-biến) + config `[preprocess]` + đo tác động. Lớn hơn (đụng toạ-độ) → làm sau, từng op một.
- **Non-Goal v1:** augmentation lúc-train; de-warp fisheye (cần calib); thư viện ngoài.

## D. CÂU HỎI VALID (cần bạn chốt trước khi code)
1. **Ưu tiên:** làm **Label (Wave 1)** trước (nhỏ, đóng rủi ro gán-nhầm-tên) hay **Preprocess (Wave 2)** trước?
2. **i18n:** cần tên hiển thị tiếng Việt ngay không, hay chỉ cần khung (map rỗng, mặc định = canonical)?
3. **Ẩn lớp:** "ẩn khỏi hiển thị" có đồng nghĩa "không đếm" không, hay ẩn-hiển-thị nhưng VẪN đếm?
4. **Preprocess op nào THẬT SỰ cần trước** cho camera của bạn (tối/ngược sáng? fisheye? chỉ 1 vùng ROI?) — để làm
   đúng cái có nhu cầu, không làm rỗng (YAGNI).
5. **Nguồn nhãn:** model của bạn có file `.names`/metadata kèm `.onnx` không, hay chỉ truyền list qua config?

→ Trả lời 5 câu này → tôi dựng requirements + tasks (spec-driven) rồi code TDD từng Wave, verify được mới "xong".
