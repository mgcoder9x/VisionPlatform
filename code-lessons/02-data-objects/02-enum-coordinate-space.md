# #02 · Mẩu 02: `Enum` + `CoordinateSpace` — vì sao tag không gian tọa độ

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/domain/bbox.py` · tầng **domain** ·
đây là cái nhãn gắn vào mỗi `BBox` để biết "tọa độ này đo trên ảnh nào".

## 2. Cần biết trước
- [Enum (enumeration)](../../knowledge-base/00-GLOSSARY.md#enum-enumeration) ·
  [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass)
- Mẩu 01 (BBox) — đọc trước; `space` ở BBox chính là kiểu này.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/domain/bbox.py
from enum import Enum


class CoordinateSpace(Enum):
    """Tag bbox coordinates với space để tránh resize/letterbox bug."""
    ORIGINAL_FRAME = "original"   # tọa độ trên frame raw (pre-resize)
    MODEL_INPUT = "model_input"   # tọa độ trên model input (e.g. 640x640)
    NORMALIZED = "normalized"     # 0.0-1.0 (relative to frame)
    DISPLAY = "display"           # tọa độ trên frame UI hiển thị
```

## 4. Giải thích từng phần nhỏ nhất
- `from enum import Enum` → lấy công cụ `Enum` (liệt kê) từ thư viện chuẩn.
- `class CoordinateSpace(Enum):` → định nghĩa một **kiểu liệt kê** tên `CoordinateSpace`: nó chỉ có đúng 4 thành viên dưới đây, không hơn.
- `"""..."""` → docstring: nhãn này để **tránh bug resize/letterbox** (giải thích ở §6).
- 4 dòng thành viên, mỗi dòng `TÊN = "giá trị"`:
  - `ORIGINAL_FRAME = "original"` → tọa độ đo trên frame **gốc** (chưa resize), vd 1920×1080.
  - `MODEL_INPUT = "model_input"` → tọa độ trên ảnh **đưa vào model AI** (vd 640×640).
  - `NORMALIZED = "normalized"` → tọa độ **chuẩn hoá** về 0..1 (tỉ lệ so với frame).
  - `DISPLAY = "display"` → tọa độ trên frame **hiển thị** lên màn hình UI.
- Phần `# ...` cuối mỗi dòng là comment giải thích, Python bỏ qua.
- Cách dùng: `CoordinateSpace.ORIGINAL_FRAME` (một thành viên). Truyền vào `BBox(..., space=CoordinateSpace.ORIGINAL_FRAME)`.

## 5. Là gì (1–2 câu)
`CoordinateSpace` là một **danh sách cố định 4 nhãn** cho biết một bộ tọa độ được đo trên "ảnh nào".
`Enum` là cách Python khai báo "chỉ được chọn 1 trong các giá trị có tên này".

## 6. Tại sao tồn tại / vấn đề nó giải
Trong xử lý ảnh, **cùng một vật** có nhiều bộ tọa độ khác nhau tuỳ ảnh: trên frame gốc (1920×1080),
trên ảnh model (640×640), hay chuẩn hoá 0..1. Nếu không ghi rõ "tọa độ này thuộc ảnh nào", người ta
dễ lấy bbox tính trên ảnh 640×640 đem **vẽ thẳng lên** ảnh 1920×1080 → khung lệch hẳn vị trí
("resize/letterbox bug"). Gắn `space` vào mỗi `BBox` biến giả định ngầm thành **dữ liệu hiện rõ**:
muốn so/vẽ thì phải transform về đúng không gian trước.

## 7. Dùng ở đâu trong project (cụ thể)
- Trường `space: CoordinateSpace` trong `BBox` (mẩu 01) — **bắt buộc** khi tạo bbox.
- Thành viên `NORMALIZED` còn được dùng ở `__post_init__` của BBox để ép tọa độ phải nằm trong [0,1] (mẩu 03 — ERRATA E-12).

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Bỏ `space`, chỉ giữ x,y,w,h: code vẫn chạy, nhưng "không gian" trở thành **giả định ngầm trong đầu lập trình viên**.
Một người đưa tọa độ model, người khác tưởng là tọa độ gốc → vẽ sai, lỗi âm thầm, rất khó tìm vì không có gì báo.

## 9. Ví von đời thường
`CoordinateSpace` như **đơn vị đo ghi kèm con số**: "5" là vô nghĩa, "5 cm" hay "5 inch" mới dùng được.
Gắn nhãn không gian = ghi đơn vị, tránh cộng nhầm cm với inch.

## 10. Liên kết bức tranh lớn
Đây là kỹ thuật "làm hiện rõ cái ngầm" ở tầng `domain`. Cùng tinh thần đó, `ReadStatus` (mẩu 04) cũng
dùng `Enum` để trạng thái đọc nguồn hiện rõ thay vì mơ hồ. `Enum` là công cụ lặp lại nhiều nơi trong dự án.

## 11. Cạm bẫy / lỗi thường gặp
- Nhầm thành viên với giá trị chuỗi: `CoordinateSpace.NORMALIZED` (thành viên) khác `"normalized"` (chuỗi bên trong). So sánh `bbox.space == CoordinateSpace.NORMALIZED`, đừng so với chuỗi.
- Tưởng gắn `space` là "tự động chuyển đổi" — KHÔNG. Nó chỉ **đánh dấu**; việc transform giữa các không gian là code khác phải làm.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: kể 4 thành viên của `CoordinateSpace` + ý nghĩa. Vì sao bbox phải mang `space`?
- Tình huống: có bbox đo trên ảnh model 640×640, muốn vẽ lên frame gốc 1920×1080 — `space` giúp tránh sai thế nào?
- Giải thích lại bằng LỜI MÌNH: "Enum là ... ; tag không gian để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → kể 4 không gian | 1 tuần → tự viết 1 Enum nhỏ | 1 tháng → giải thích "resize/letterbox bug" bằng lời mình.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/domain/bbox.py` (đã ĐỌC LẠI nguyên văn ngay trước khi viết). · Độ chắc: **cao**.
- `enum.Enum` là thư viện chuẩn Python — tài liệu chính thống. · Độ chắc: cao.
- "resize/letterbox bug" là lý do thiết kế ghi trong docstring + Design step-02; [chưa kiểm bằng thực nghiệm tái hiện bug tại mẩu này] — đây là động cơ thiết kế, không phải hành vi cần chạy. · Độ chắc: cao về động cơ.
