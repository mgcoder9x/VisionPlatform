# Bài #03 — Cổng (Port) & Bộ chuyển (Adapter) cho nguồn frame · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đọc file này TRƯỚC các mẩu chi tiết. Mục tiêu: hiểu **tại sao** cần "cổng" + "bộ chuyển" cho nguồn
> frame, trước khi xem từng dòng. Bám code thật ở `vision-platform/src/vision_platform/`.

---

## 1. Tổng quan — ta đang ở đâu
Bài #01 dựng khung; #02 tạo các viên gạch dữ liệu (BBox, ReadResult, MediaPacket). Bài #03 là **cặp
port→adapter ĐẦU TIÊN**: trừu tượng "nguồn cung cấp frame" (`IFrameSource`).

```
[ Adapter cụ thể ]          [ Cổng (Port) ]              [ Lõi dùng cổng ]
FakeFrameSource  ──┐                                      pipeline/executor
NoiseFrameSource ──┼── khớp ──►  IFrameSource (Protocol) ◄── chỉ biết cổng,
(RTSP, file...)  ──┘            setup/read/teardown...        KHÔNG biết adapter nào
```
> Thuật ngữ: [port](../../knowledge-base/00-GLOSSARY.md#port-cổng--hexagonal) ·
> [adapter](../../knowledge-base/00-GLOSSARY.md#adapter-bộ-chuyển--hexagonal) ·
> [Protocol](../../knowledge-base/00-GLOSSARY.md#protocol-typingprotocol) ·
> [ReadResult](../02-data-objects/04-readresult-status.md).

> **🖼 Sơ đồ tổng quan (nguồn Draw.io):** [port-adapter-hexagonal.drawio](diagrams/port-adapter-hexagonal.drawio) — 1 port giữa, nhiều adapter cắm vào, lõi chỉ biết port.
> Xem nhúng: Draw.io → **Export as → SVG** → lưu `diagrams/port-adapter-hexagonal.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

File thật của #03:
| Thành phần | Tầng | File |
|---|---|---|
| `IFrameSource` (port) | kernel | `kernel/ports/frame_source.py` |
| `FakeFrameSource` (adapter) | adapters | `adapters/fake_frame_source.py` |
| `NoiseFrameSource` (adapter) | adapters | `adapters/noise_frame_source.py` |
| Contract test | tests | `tests/test_step_03_frame_source_contract.py` |

## 2. Vấn đề & TẠI SAO nó là vấn đề
Pipeline cần **frame** để xử lý. Frame có thể đến từ nhiều nguồn: camera RTSP, file video, hay **nguồn
giả** (để test offline, không cần camera). Nếu pipeline gọi thẳng `cv2.VideoCapture(...)`:
- **Dính chặt OpenCV/camera:** lõi pipeline phụ thuộc thư viện I/O + thiết bị thật.
- **Khó test:** muốn test pipeline phải có camera/file thật.
- **Đổi nguồn = sửa lõi:** thêm loại nguồn mới → đụng vào pipeline.
- **Mỗi nguồn "trả lỗi" một kiểu:** nguồn này trả None, nguồn kia ném exception → người gọi xử lý loạn.

**Lực giằng nhau:** *pipeline ổn định* ↔ *nhiều loại nguồn hay thay đổi*. (Đoán thử: làm sao để thêm
nguồn mới mà không sửa pipeline + test được không cần camera?)

## 3. Khám phá nhiều hướng (≥2 cách)
- **Cách A — `if loại == "rtsp": ... elif "file": ...` trong pipeline:** pipeline phải biết MỌI loại nguồn → thêm nguồn = sửa pipeline, dính cứng. ✗
- **Cách B — lớp cha trừu tượng + kế thừa** (`class Rtsp(BaseSource)`): đỡ hơn, nhưng adapter BẮT BUỘC kế thừa đúng lớp cha; mock/test cũng phải kế thừa → nặng. △
- **Cách C — Port là `Protocol` (structural typing) + adapter chỉ cần "đúng hình dạng"** + **contract test** (1 bộ test mọi adapter phải qua): adapter không cần kế thừa, chỉ cần có đủ method đúng dạng; lõi chỉ biết port. ✓ ← chọn.

## 4. Chốt giải pháp + TẠI SAO thắng
- `IFrameSource` = **Protocol** (hợp đồng): `setup() · read()→ReadResult · teardown() · is_finite · source_id`.
- `FakeFrameSource`, `NoiseFrameSource` = **adapter** khớp hợp đồng (không kế thừa) → test offline, không cần camera.
- **Contract test parametrized**: 1 bộ test, MỌI adapter chạy qua → đảm bảo adapter nào cũng tôn trọng hợp đồng. Thêm adapter = thêm 1 dòng `pytest.param`.
- `read()` luôn trả **ReadResult** (mẩu #02-04), không trả None → người gọi xử lý trạng thái rõ ràng.

Thắng vì: nối đúng 2 câu hỏi gốc kiến trúc — *cái gì hay đổi?* (loại nguồn) → đẩy ra adapter ở rìa;
*mũi tên phụ thuộc?* → adapter → kernel (port), lõi KHÔNG biết adapter.
> Học sâu: (sẽ tạo) `knowledge-base/hexagonal-architecture/`.

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự nhỏ nhất → xem `00-muc-luc.md`.

## 6. Nên làm / Nên tránh (cho bài #03)
- **NÊN:** gọi `setup()` trước `read()`; `read()` trả `ReadResult`; mỗi adapter có `source_id` DUY NHẤT; thêm adapter thì thêm vào contract test.
- **TRÁNH:** để lõi/pipeline import adapter cụ thể (chỉ `profiles` mới được); `read()` trả None; `source_id` mặc định cố định (trùng nhau — ERRATA E-13).
- **Cạm bẫy (ERRATA E-13):** `source_id` default cố định → 2 instance trùng id, vi phạm hợp đồng "unique" → dùng `itertools.count` auto-unique.

## Tự kiểm (đạt mới qua bài)
- Vì sao dùng `Protocol` (structural) tốt hơn bắt adapter kế thừa lớp cha?
- "Contract test" giải quyết điều gì khi có nhiều adapter?

## Nguồn
- Code thật: `kernel/ports/frame_source.py`, `adapters/fake_frame_source.py`, `adapters/noise_frame_source.py`,
  `tests/test_step_03_frame_source_contract.py` (đã đọc nguyên văn). · Design: `Design/module-03-build-along/step-03-first-port.md`. · Độ chắc: cao.
