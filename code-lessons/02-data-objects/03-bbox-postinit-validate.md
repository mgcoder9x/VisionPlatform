# #02 · Mẩu 03: `__post_init__` validate + `@property` của `BBox`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/domain/bbox.py` · tầng **domain** ·
đây là phần "tự kiểm khi sinh ra" + "giá trị tính sẵn" của `BBox`.

## 2. Cần biết trước
- [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [Enum (enumeration)](../../knowledge-base/00-GLOSSARY.md#enum-enumeration)
- Mẩu 01 (BBox + frozen) và mẩu 02 (CoordinateSpace) — đọc trước.

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/domain/bbox.py  (trong class BBox)
    def __post_init__(self):
        if self.w < 0 or self.h < 0:
            raise ValueError(
                f"width/height must be non-negative, got w={self.w} h={self.h}"
            )
        # NORMALIZED space: mọi tọa độ phải trong [0,1] (ERRATA E-12, Risk 3).
        # Bắt lỗi kiểu "bbox 100.0 trong normalized space" ngay lúc khởi tạo.
        if self.space == CoordinateSpace.NORMALIZED:
            for name, val in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
                if not (0.0 <= val <= 1.0):
                    raise ValueError(
                        f"NORMALIZED bbox cần {name} trong [0,1], got {name}={val}"
                    )

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h
```

## 4. Giải thích từng phần nhỏ nhất
- `def __post_init__(self):` → hàm **đặc biệt của dataclass**: chạy NGAY SAU khi đối tượng được tạo. Dùng để kiểm tra/điều chỉnh giá trị.
- `if self.w < 0 or self.h < 0:` → nếu rộng hoặc cao âm...
- `raise ValueError(...)` → ...thì **ném lỗi** dừng việc tạo. `f"...{self.w}..."` là f-string: chèn giá trị thật vào thông báo lỗi.
- `if self.space == CoordinateSpace.NORMALIZED:` → CHỈ khi không gian là NORMALIZED mới kiểm thêm.
  - `for name, val in (("x", self.x), ...):` → lặp qua 4 tọa độ, kèm tên để báo lỗi rõ.
  - `if not (0.0 <= val <= 1.0):` → nếu giá trị NẰM NGOÀI đoạn [0,1] thì ném `ValueError`.
- `@property` → biến một hàm thành **thuộc tính đọc**: gọi `b.x2` (không có ngoặc) thay vì `b.x2()`.
  - `x2` = `x + w` (cạnh phải), `y2` = `y + h` (cạnh dưới), `area` = `w * h` (diện tích). Tính khi cần, không lưu sẵn.

## 5. Là gì (1–2 câu)
`__post_init__` là chốt **tự kiểm tính hợp lệ ngay khi tạo** bbox. `@property` cho phép đọc các giá trị
suy ra (x2, y2, area) như thuộc tính, mà không phải lưu trữ trùng lặp.

## 6. Tại sao tồn tại / vấn đề nó giải
- **Validate sớm:** một bbox rộng âm, hay bbox "NORMALIZED" nhưng x=100, là dữ liệu sai. Nếu để lọt,
  nó đi sâu vào hệ rồi mới gây lỗi ở chỗ khác — rất khó truy. `__post_init__` chặn **ngay lúc tạo**,
  lỗi nổ đúng nơi sinh ra (nguyên tắc "fail fast").
- **`@property` thay vì lưu sẵn:** nếu lưu `x2` thành trường, nó có thể lệch với `x`/`w` khi tính sai.
  Tính từ nguồn (`x+w`) đảm bảo luôn nhất quán; lại không phá `frozen` (không cần thêm trường).

## 7. Dùng ở đâu trong project (cụ thể)
- Test thật `tests/test_step_02_domain.py` kiểm đúng các hành vi này (đã CHẠY pass):
  - `test_bbox_basic`: `assert b.x2 == 110`, `b.y2 == 70`, `b.area == 5000` (với `BBox(10,20,100,50,...)`).
  - `test_bbox_negative_size_rejected`: `with pytest.raises(ValueError): BBox(0,0,-10,50,...)`.
  - `test_bbox_normalized_out_of_range_rejected`: `BBox(100.0,0.0,0.5,0.5, NORMALIZED)` → raise; `BBox(0.1,0.2,0.5,0.5, NORMALIZED)` hợp lệ.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Bỏ `__post_init__`: tạo được bbox rác (rộng âm / normalized = 100) mà không ai báo → bug âm thầm khi vẽ/so sánh.
- Bỏ `@property`, lưu x2/y2 thành trường: dễ lệch với x/w; lại đụng `frozen` (phải set thêm trường lúc tạo).

## 9. Ví von đời thường
`__post_init__` như **khâu kiểm tra cuối chuyền** trong nhà máy: sản phẩm lỗi bị loại NGAY, không cho ra kho.
`@property` như **máy tính tiền tự cộng**: bạn không ghi sẵn tổng, nó tính lại từ giá lúc bạn hỏi → luôn đúng.

## 10. Liên kết bức tranh lớn
Đây là tinh thần "dữ liệu hợp lệ ngay từ gốc" ở tầng `domain`. `MediaPacket` (mẩu 08) cũng dùng
`__post_init__` — nhưng để bọc metadata read-only, không phải validate số. Cùng một móc, hai mục đích.

## 11. Cạm bẫy / lỗi thường gặp
- ERRATA **E-12**: nếu quên kiểm NORMALIZED [0,1], bbox "100.0 normalized" lọt qua → sai lệch khi quy đổi. Test `test_bbox_normalized_out_of_range_rejected` canh đúng chỗ này.
- Gọi property kèm ngoặc: `b.area()` sai (nó là property, viết `b.area`).
- `__post_init__` chỉ chạy khi tạo qua dataclass init — KHÔNG chạy lại khi unpickle (đây là gốc của E-11 ở `InMemoryArrayRef`, mẩu 07).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `__post_init__` chạy khi nào? Vì sao validate lúc tạo tốt hơn để lỗi nổ muộn?
- Tình huống: tạo `BBox(0,0,-5,10, ORIGINAL_FRAME)` → chuyện gì xảy ra? Còn `BBox(2.0,0,0.5,0.5, NORMALIZED)`?
- Giải thích lại bằng LỜI MÌNH: "`__post_init__` để ... ; `@property` để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 2 điều kiện validate | 1 tuần → tự thêm 1 property tính sẵn | 1 tháng → giải thích "fail fast" bằng lời mình.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/domain/bbox.py` (đã ĐỌC LẠI nguyên văn `__post_init__` + 3 property). · Độ chắc: **cao**.
- Hành vi validate + property: đã CHẠY THẬT `pytest tests/test_step_02_domain.py -k bbox` → **5 passed** (gồm 3 test trích ở §7). · Độ chắc: **cao**.
- E-12: ghi trong `Design/00-ERRATA.md` + có test canh. · Độ chắc: **cao**.
