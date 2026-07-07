# Bài #02 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung vấn đề→giải pháp). Rồi tới các mẩu nhỏ nhất dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + tự giải thích lại được.

| Mẩu | File | Nội dung | Trạng thái |
|-----|------|----------|-----------|
| 01 | `01-dataclass-frozen-bbox.md` | `dataclass` + `frozen=True` qua `BBox` — value object bất biến | ✅ đã viết |
| 02 | `02-enum-coordinate-space.md` | `Enum` + `CoordinateSpace` — vì sao tag không gian tọa độ | ✅ đã viết |
| 03 | `03-bbox-postinit-validate.md` | `__post_init__` validate (w/h≥0, NORMALIZED [0,1] = E-12) + `@property` | ✅ đã viết |
| 04 | `04-readresult-status.md` | `ReadResult` + `ReadStatus` + `has_data` — trả trạng thái rõ ràng thay vì `None` | ✅ đã viết |
| 05 | `05-generic-typevar.md` | `Generic[T]` + `TypeVar` — vì sao `ReadResult` "generic" | ✅ đã viết |
| 06 | `06-inmemoryarrayref-readonly.md` | `InMemoryArrayRef`: ndarray read-only by contract + `from_owned` vs `from_copy` | ✅ đã viết |
| 07 | `07-setstate-pickle-e11.md` | `__setstate__`: pickle KHÔNG giữ `write=False` (ERRATA E-11) | ✅ đã viết |
| 08 | `08-mediapacket-immutable.md` | `MediaPacket` bất biến + `MappingProxyType` + `__post_init__` | ✅ đã viết |
| 09 | `09-mediapacket-cow.md` | CoW: `with_metadata/with_artifact/without_artifact` + `replace` | ✅ đã viết |

> Tạo từng mẩu một. Xong #02 → sang #03 (Port/Adapter)... cho tới #05.
> **Sơ đồ (`diagrams/`, nguồn Draw.io — xuất SVG bằng extension để xem nhúng):** `data-bricks-overview.drawio` (tổng quan, nhúng ở cau-chuyen) · `mediapacket-cow.drawio` (mẩu 09) · `pickle-e11.drawio` (mẩu 07).
> Ghi chú: #02 có **9 mẩu** (nhiều hơn #01=7) vì gồm 3 file code + nhiều khái niệm mới — số mẩu theo nội dung, không ép bằng nhau.
