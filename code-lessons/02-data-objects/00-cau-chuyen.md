# Bài #02 — Các "viên gạch dữ liệu" chảy trong pipeline · CÂU CHUYỆN VẤN ĐỀ → GIẢI PHÁP

> Đọc file này TRƯỚC các mẩu chi tiết. Mục tiêu: hiểu **tại sao** dữ liệu lại được gói kiểu này,
> trước khi xem từng dòng. Bám code thật ở `vision-platform/src/vision_platform/`.

---

## 1. Tổng quan — ta đang ở đâu
Bài #01 dựng bộ khung rỗng. Bài #02 tạo **các viên gạch dữ liệu** mà cả hệ thống sẽ chuyền tay nhau:
| Viên gạch | Tầng | File thật | Vai trò |
|---|---|---|---|
| `BBox` | domain | `domain/bbox.py` | một khung chữ nhật (kết quả detect) + nhãn "không gian tọa độ" |
| `CoordinateSpace` | domain | `domain/bbox.py` | nhãn: tọa độ này thuộc frame gốc / model / chuẩn hoá / hiển thị |
| `ReadResult` | kernel | `kernel/read_result.py` | kết quả đọc nguồn, kèm **trạng thái tường minh** (có frame / EOF / timeout...) |
| `MediaPacket` | kernel | `kernel/media_packet.py` | gói 1 **frame ảnh** + metadata, **không cho sửa tại chỗ** |
| `InMemoryArrayRef` | kernel | `kernel/media_packet.py` | bọc mảng ảnh (numpy), **chỉ-đọc theo cam kết** |

> Thuật ngữ: [DTO](../../knowledge-base/00-GLOSSARY.md#dto-data-transfer-object) ·
> [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) · [immutable](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến).

> **🖼 Sơ đồ tổng quan (nguồn Draw.io):** [data-bricks-overview.drawio](diagrams/data-bricks-overview.drawio) — mở bằng extension Draw.io Integration.
> Để xem nhúng: trong Draw.io chọn **Export as → SVG**, lưu thành `diagrams/data-bricks-overview.svg`. _(Ảnh sẽ hiện sau khi Export SVG; hiện chỉ có `.drawio` nguồn nên tạm chưa nhúng ảnh.)_

## 2. Vấn đề & TẠI SAO nó là vấn đề
Một frame ảnh là **mảng số rất lớn** (vd 1920×1080×3 = 6.220.800 ≈ 6,2 triệu số). Frame này chảy qua nhiều bước
(đọc → chỉnh sáng → lọc → suy luận AI → gửi), và **sau này qua nhiều tiến trình** (process). Nếu mỗi
bước được tự do sửa gói/ảnh:
- **Bug khó lần:** bước sau sửa dữ liệu bước trước → không biết "ai đã đổi cái này".
- **Chậm + tốn RAM:** nếu để an toàn mà copy cả ảnh lớn ở mỗi bước → copy hơn 6 triệu số liên tục.
- **Lẫn không gian tọa độ:** bbox tính trên ảnh 640×640 (model) đem vẽ lên ảnh 1920×1080 (gốc) → **vẽ sai chỗ**.
- **Kết quả đọc mơ hồ:** đọc nguồn trả `None` thì là "hết video" hay "timeout" hay "lỗi"? Không rõ → xử lý sai.

**Các lực giằng nhau (forces):** *an toàn* (đừng cho sửa lung tung) ↔ *tốc độ* (đừng copy ảnh lớn).
(Đoán thử: làm sao vừa chia sẻ ảnh cho nhiều bước, vừa không ai sửa được nó?)

## 3. Khám phá nhiều hướng (≥2 cách)
- **Cách A — dict/đối tượng tự do sửa:** code nhanh, nhưng loạn "ai sửa", và đa tiến trình dễ tranh chấp. ✗
- **Cách B — copy phòng thủ mọi nơi** (deep copy mỗi lần truyền): an toàn tuyệt đối nhưng **copy ảnh lớn = chậm/ngốn RAM**. △
- **Cách C — gói BẤT BIẾN + chia sẻ ảnh chỉ-đọc + "đổi thì tạo bản mới"** (Copy-on-Write): chia sẻ
  ảnh zero-copy (không copy), chặn sửa nhầm; muốn thêm metadata thì tạo packet mới (chỉ copy **metadata nhỏ**, KHÔNG copy ảnh). ✓ ← chọn.

## 4. Chốt giải pháp + TẠI SAO thắng
- `MediaPacket` **bất biến** (`frozen=True`); metadata/artifacts bọc `MappingProxyType` → sửa tại chỗ là **báo lỗi**.
- Muốn đổi → dùng **CoW**: `with_metadata(...)` trả về packet MỚI, dùng chung `media_ref` cũ (không copy ảnh).
- `InMemoryArrayRef` đặt mảng ảnh thành **read-only** (`setflags(write=False)`) → chặn ghi nhầm; có
  `from_owned_array` (zero-copy) và `from_copy` (sao chép phòng thủ) cho 2 nhu cầu.
- `BBox` **bắt buộc** đính kèm `CoordinateSpace` → không thể lỡ so sánh/vẽ bbox khác không gian.
- `ReadResult` trả **trạng thái rõ ràng** (`FRAME/EOF/TIMEOUT/...`) thay vì `None` mơ hồ → buộc người gọi xử lý đúng.

Thắng vì nó giải đúng cặp lực: **an toàn (bất biến) mà vẫn nhanh (chia sẻ ảnh, chỉ copy metadata nhỏ)**.
> Học sâu: (sẽ tạo) `knowledge-base/immutability-cow/` · `knowledge-base/pickle/`.

## 5. Triển khai — đọc các mẩu chi tiết (bám code thật)
Theo thứ tự nhỏ nhất → xem `00-muc-luc.md`.

## 6. Nên làm / Nên tránh (cho bài #02)
- **NÊN:** đổi packet bằng `with_metadata/with_artifact` (CoW); gắn đúng `CoordinateSpace` cho bbox; đọc nguồn thì **switch theo `status`**.
- **TRÁNH:** `packet.metadata["k"] = v` (sẽ raise); `from_owned_array` xong còn giữ alias để sửa ảnh; so sánh 2 bbox khác `space` mà chưa transform.
- **Cạm bẫy (ERRATA):** **E-11** pickle KHÔNG giữ `write=False` (đa tiến trình) → có `__setstate__` re-lock; **E-12** bbox `NORMALIZED` phải nằm trong [0,1].

## Tự kiểm (đạt mới qua bài)
- Vì sao chọn "bất biến + CoW" thay vì "copy phòng thủ mọi nơi"? Cái gì được copy, cái gì KHÔNG?
- Vì sao `BBox` bắt buộc có `CoordinateSpace`? Bỏ đi thì hỏng gì?

## Nguồn
- Code thật: `domain/bbox.py`, `kernel/read_result.py`, `kernel/media_packet.py` (đã đọc nguyên văn). ·
  Design: `Design/module-03-build-along/step-02-first-mediapacket.md`. · Độ chắc: cao.
