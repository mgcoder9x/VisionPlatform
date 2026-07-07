# Bài #06 — Inference inline: câu chuyện (vòng cung vấn đề → giải pháp)

> Đọc file này TRƯỚC. Nó kể *tại sao cần* tầng inference và *tại sao thiết kế như vậy*, trước khi
> bạn xem từng dòng code ở các mẩu `01..11`. Mọi thuật ngữ lạ đều có gloss 1 dòng hoặc link ngay tại chỗ.
> Bám code thật: `vision-platform/src/vision_platform/{kernel/inference_protocol.py, kernel/ports/detector.py,
> adapters/fake_detector.py, application/inline_inference_client.py}` + test `tests/test_step_06_inference.py`
> (trạng thái: **9 test pass**, full 261 passed/1 skipped, lint 5 kept/0 broken).

---

## Nhịp 1 — Tổng quan: thứ này nằm ở đâu trong hệ?

Tới giờ (bài #01→#05) bạn đã có: camera → *pipeline* xử lý → **SHM ring** (vùng nhớ chia sẻ để 2
tiến trình đọc/ghi cùng 1 khung hình mà không copy — xem `knowledge-base/00-GLOSSARY.md#shm` và bài #05).
Còn thiếu mảnh quan trọng nhất của một hệ thị giác máy: **phát hiện vật thể (object detection)** — chạy
mô hình AI (YOLO/RTMDet...) để nói "trong khung hình có cái gì, ở đâu".

Bức tranh #06 (hộp + mũi tên):

```
Camera process                         Inference (bài #06)
  ┌──────────┐   ghi frame    ┌───────────┐   đọc frame     ┌────────────┐
  │ pipeline │ ─────────────► │  SHM ring │ ◄────────────── │ InlineInfer│
  └──────────┘                └───────────┘                 │   Client   │
                                    ▲                        └─────┬──────┘
        InferenceRequest {request_id, frame_ref} ─────────────────┘   │ detect()
                                                                       ▼
                                                                 ┌──────────┐
                                                                 │ IDetector│ (FakeDetector)
                                                                 └──────────┘
        InferenceResponse {request_id, detections} ◄────────────────┘
```

Ý chính: camera KHÔNG gửi cả khung hình đi (nặng). Nó gửi **một tấm vé** (`InferenceRequest`) chỉ
chứa *vị trí frame trong SHM* + một mã số `request_id`. Bên inference cầm vé → đọc frame từ SHM →
chạy detector → trả `InferenceResponse` kèm lại đúng `request_id`.

> **Layer nào?** (6 layer hexagonal — xem `knowledge-base/hexagonal-architecture/` / glossary):
> DTO + port ở `kernel/`; detector giả ở `adapters/`; client điều phối ở `application/`.
> (Vì sao đúng chỗ đó → nhịp 4 + mẩu 09.)

---

## Nhịp 2 — Vấn đề & TẠI SAO nó là vấn đề (Forces)

Ở đây có **hai nỗi đau** khác nhau, đừng lẫn.

**Nỗi đau A — trả lời lệch chủ (correlation).**
Inference thường chạy **bất đồng bộ (async)**: nhiều camera gửi yêu cầu, một service gom lại xử lý
theo lô (batch) trên GPU rồi trả về — **không nhất thiết đúng thứ tự gửi**. Ví dụ:
- Camera 1 gửi yêu cầu lúc t=0; Camera 2 gửi lúc t=1.
- GPU xử lý cam 2 xong trước (frame nhỏ hơn) → trả cam 2, rồi mới trả cam 1.
- Nếu response **không mang mã** → cam 1 nhận nhầm kết quả của cam 2 → **tracking lệch toàn hệ**.

Lực giằng: *muốn xử lý theo lô cho nhanh (đảo thứ tự)* ↔ *mỗi bên phải nhận đúng kết quả của mình*.
→ 🤔 **Đoán thử:** làm sao mỗi bên biết response nào là của mình khi thứ tự bị đảo?

**Nỗi đau B — đọc nhầm frame sau khi ring đổi thế hệ (switchover).**
Bài #05b vừa xây cơ chế **switchover**: khi ring hỏng, hệ chuyển sang ring thế hệ mới, mỗi frame gắn
số **`ring_epoch`** (số thế hệ — xem glossary + bài #05b mẩu 02). Nếu `InferenceRequest` cầm vé của
*thế hệ cũ* mà bên inference đọc trên *ring hiện tại* → có thể trúng đúng ô/số đếm nhưng là **frame
khác** → detect ra rác. Đây là nỗi đau tích hợp: tầng inference phải "ăn khớp" với invariant của #05.

Lực giằng: *thiết kế inference đơn giản (chỉ slot+generation)* ↔ *phải đúng cả khi ring đã switchover*.

---

## Nhịp 3 — Khám phá nhiều hướng

**Cho nỗi đau A (correlation):**
- *Hướng 1 — dựa thứ tự:* giả định "gửi trước nhận trước". → HỎNG ngay khi batch đảo thứ tự (chính
  cái ta muốn để nhanh). Loại.
- *Hướng 2 — mỗi camera một kênh riêng, chờ đồng bộ:* mỗi request chặn tới khi có response. → mất
  hết lợi ích async/batch; 1 camera chậm kéo cả hệ. Loại cho production.
- *Hướng 3 — gắn mã `request_id` vào request, response echo lại:* client giữ bản đồ `request_id →
  chỗ chờ`, ai về thì khớp mã. → giữ được async + batch, mỗi bên nhận đúng. **Chọn.**

**Cho nỗi đau B (stale-epoch):**
- *Hướng 1 — bỏ qua, chỉ dùng slot+generation:* đúng Design gốc (viết trước #05). → thủng lỗ hổng
  đọc-nhầm-frame sau switchover. Loại (không an toàn cho sản phẩm).
- *Hướng 2 — vé mang thêm `ring_epoch`, reader tự kiểm:* tái dùng đúng `ShmFrameReader.read_ref` mà
  #05 đã có (ref epoch cũ → trả None). **Chọn** — không viết lại logic, khớp invariant sẵn có.

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO nó thắng

1. **`request_id` correlation** (nỗi đau A) — mã duy nhất mỗi request; response *echo* lại mã. Đây là
   **pattern lõi** của inference async, dù transport là inline (bài này) hay ZMQ (production sau). Học
   pattern này ở bản inline dễ (không phải debug socket), rồi tái dùng y nguyên khi lên ZMQ.

2. **Vé = `InferenceRequest` nhúng thẳng `ShmFrameRefData`** (nỗi đau B) — `ShmFrameRefData` là DTO
   đã có từ #05, mang đủ `{ring_name, slot, generation, ring_epoch, H, W, C}`. Client gọi
   `reader.read_ref(frame_ref)` → tự động kiểm `ring_epoch`. **Thắng** vì: một nguồn sự thật (không
   lặp field), tái dùng stale-check verified của #05, đúng ngay từ đầu cho switchover.

3. **Chỗ đặt file theo luật kiến trúc** (không phải tùy tiện):
   - DTO + port `IDetector` → `kernel/` (dữ liệu thuần + hợp đồng).
   - `FakeDetector` → `adapters/` (bản cài đặt cụ thể, "lá" ngoài rìa).
   - `InlineInferenceClient` → **`application/`**, KHÔNG phải `adapters/`. Vì nó phải đọc SHM
     (`runtime`), mà luật *"adapters là lá, cấm gọi ngược lên runtime"*. Client thực chất là **service
     điều phối** (ghép runtime reader + port detector) → đúng vai application. (Chi tiết + bằng chứng
     luật ở mẩu 09; đây là điểm Design gốc sai và ta sửa — **ERRATA E-06-1**.)

> Hai chỗ ta **đổi so với Design gốc** (Design viết trước #05): **E-06-1** (client → application) và
> **E-06-2** (vé mang `ring_epoch`, dùng `read_ref`). Cả hai đã ghi ERRATA ở đầu `Design/module-03-build-along/
> step-06-add-inference.md` + sổ `ai-decision-journal` (D-023/C-007). Bài học nói rõ để bạn hiểu *vì sao đổi*.

---

## Nhịp 5 — Triển khai (vào code thật)

Đọc lần lượt các mẩu (mỗi mẩu 1 ý nhỏ nhất, quote code nguyên văn — xem `00-muc-luc.md`):
vấn đề correlation → 4 DTO → port → adapter giả → client (chỗ đặt + luồng `infer`) → test.

## Nhịp 6 — Nên làm / nên tránh (tóm; chi tiết ở từng mẩu)

- ✅ **NÊN:** gắn `request_id` cho MỌI request async; response luôn echo lại.
- ✅ **NÊN:** cho vé mang đủ `ShmFrameRefData` (gồm `ring_epoch`) + đọc bằng `read_ref` → an toàn switchover.
- ✅ **NÊN:** `InferenceError` chỉ giữ **chuỗi** (`error_type`/`error_message`), không giữ Exception gốc.
- ⛔ **TRÁNH:** giả định response về đúng thứ tự gửi.
- ⛔ **TRÁNH:** đặt client đọc-SHM vào `adapters/` (vỡ luật layer — lint sẽ báo `broken`).
- ⛔ **TRÁNH:** đẻ port `IInferenceClient` NGAY bây giờ khi chỉ có 1 bản (inline) — trừu tượng hóa
  sớm. Để dành tới khi làm bản ZMQ (lúc đó có 2 bản mới cần port chung).
