# #02 · Mẩu 01: `dataclass` + `frozen=True` qua `BBox`

## 1. Thuộc về đâu
Vấn đề #02 · file code thật: `vision-platform/src/vision_platform/domain/bbox.py` · tầng **domain** ·
đây là kiểu "value object" (đối tượng giá trị) đầu tiên — một khung chữ nhật bất biến.

## 2. Cần biết trước
- [dataclass](../../knowledge-base/00-GLOSSARY.md#dataclass) ·
  [frozen (frozen=True)](../../knowledge-base/00-GLOSSARY.md#frozen-frozentrue) ·
  [immutable](../../knowledge-base/00-GLOSSARY.md#immutable-bất-biến)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/src/vision_platform/domain/bbox.py
from dataclasses import dataclass
from enum import Enum

# ... (CoordinateSpace ở mẩu 02) ...

@dataclass(frozen=True)
class BBox:
    """Bounding box với coordinate space tag.

    BBox(x=10, y=20, w=100, h=50, space=CoordinateSpace.ORIGINAL_FRAME).

    `space` là quan trọng — KHÔNG thể compare 2 bbox khác space mà chưa transform.
    """
    x: float
    y: float
    w: float
    h: float
    space: CoordinateSpace
```

## 4. Giải thích từng phần nhỏ nhất
- `from dataclasses import dataclass` → lấy công cụ `dataclass` từ thư viện chuẩn Python.
- `@dataclass(frozen=True)` → một **decorator** (dấu `@` = "gắn thêm phép thuật cho lớp ngay dưới").
  - `dataclass`: tự sinh hàm khởi tạo `__init__` từ danh sách trường → khỏi viết tay.
  - `frozen=True`: khoá đối tượng — sau khi tạo, gán lại trường (vd `b.x = 5`) sẽ **báo lỗi**.
- `class BBox:` → định nghĩa kiểu mới tên `BBox`.
- `"""..."""` → docstring mô tả lớp + ví dụ cách tạo.
- 5 dòng `x: float` ... `space: CoordinateSpace` → khai báo **các trường** + kiểu của chúng:
  - `x, y, w, h` kiểu `float` (số thực): vị trí góc + chiều rộng/cao.
  - `space` kiểu `CoordinateSpace`: nhãn không gian tọa độ (mẩu 02) — **bắt buộc truyền**, không có mặc định.
- Nhờ `@dataclass`, ta tạo được: `BBox(x=10, y=20, w=100, h=50, space=CoordinateSpace.ORIGINAL_FRAME)`.

## 5. Là gì (1–2 câu)
`BBox` là một **đối tượng giá trị bất biến** gói 4 con số (x, y, w, h) + 1 nhãn không gian. `dataclass`
giúp khai báo gọn; `frozen=True` làm nó không sửa được sau khi tạo.

## 6. Tại sao tồn tại / vấn đề nó giải
- Không có `dataclass`: phải tự viết `__init__`, `__repr__`, `__eq__`... dài dòng, dễ sai.
- Không có `frozen`: một bbox đã tạo có thể bị bước sau lén sửa `x` → kết quả detect "biến hình" giữa
  đường, bug cực khó lần. `frozen=True` chặn điều đó: bbox là **một sự thật cố định**, ai cần khác thì tạo bbox mới.

## 7. Dùng ở đâu trong project (cụ thể)
- `BBox` sống ở tầng `domain` (thuần, không I/O) — sẽ là kiểu kết quả khi bước suy luận (AI) trả về các khung detect.
- Vì bất biến, một `BBox` có thể được nhiều bước/nhiều tiến trình dùng chung mà không sợ bị sửa.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Dùng tuple `(10, 20, 100, 50)` hay dict tự do thay cho `BBox`: (a) không ai chắc số nào là w hay h;
(b) thiếu nhãn `space` → vẽ nhầm không gian; (c) dict sửa được → mất an toàn. `BBox` đặt tên rõ + khoá lại.

## 9. Ví von đời thường
`frozen=True` như **đổ bê tông**: đổ khuôn (tạo bbox) xong là cứng; muốn hình khác thì đúc khuôn mới,
không đục lại khối cũ.

## 10. Liên kết bức tranh lớn
Đây là viên gạch dữ liệu thuần đầu tiên ở `domain`. Cùng kiểu "bất biến" này lặp lại ở `ReadResult`
(mẩu 04) và `MediaPacket` (mẩu 08) — cả hệ thống ưu tiên dữ liệu bất biến để an toàn khi chia sẻ.

## 11. Cạm bẫy / lỗi thường gặp
- Tưởng `frozen=True` khoá được mọi thứ: nó chặn **gán lại trường**, nhưng nếu trường là vật mutable
  (vd dict) thì nội dung bên trong vẫn đổi được → đó là lý do `MediaPacket` phải bọc thêm `MappingProxyType` (mẩu 08).
- Quên truyền `space` → lỗi thiếu tham số ngay khi tạo (vì `space` không có giá trị mặc định).

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `@dataclass` tự sinh ra cái gì? `frozen=True` chặn điều gì?
- Giải thích lại bằng LỜI MÌNH: "BBox là ... ; frozen=True để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → tự khai báo 1 dataclass frozen nhỏ | 1 tuần → giải thích vì sao bất biến an toàn hơn | 1 tháng → phân biệt frozen-trường vs nội-dung-mutable.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/domain/bbox.py` (đã đọc nguyên văn). · Độ chắc: **cao**.
- Hành vi tạo/bất biến của `BBox`: có test thật `tests/test_step_02_domain.py` (nằm trong 64 passed/1 skipped đã chạy). · Độ chắc: **cao** (chưa trích từng assert ở mẩu này — [chưa kiểm chi tiết từng test-case tại đây], sẽ trích ở mẩu 03 phần validate).
- `dataclasses`/`frozen` là thư viện chuẩn Python — tài liệu chính thống. · Độ chắc: cao.
