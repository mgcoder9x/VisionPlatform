# #01 · Mẩu 01: `package` & `__init__.py` là gì

## 1. Thuộc về đâu
Vấn đề #01 (skeleton) · file code thật: `vision-platform/src/vision_platform/__init__.py` (và các
`__init__.py` rỗng trong mỗi tầng) · đây là viên gạch nền: biến thư mục thành "package" Python import được.

## 2. Cần biết trước
- [package](../../knowledge-base/00-GLOSSARY.md#package-thư-viện--library) ·
  [src layout](../../knowledge-base/00-GLOSSARY.md#src-layout)

## 3. Code thật (quote NGUYÊN VĂN)
```python
# vision-platform/src/vision_platform/__init__.py
"""vision_platform - Vision platform thật (kiểm chứng thiết kế Design/, theo Module 03)."""

__version__ = "0.1.0"
```
Các tầng con (vd `domain/__init__.py`) thì **rỗng** — chỉ là file đánh dấu.

## 4. Giải thích từng phần nhỏ nhất
- Dòng `# ...` → **comment** (chú thích), Python bỏ qua khi chạy; ở đây ghi đường dẫn file cho dễ theo dõi.
- `"""..."""` đầu file → **docstring**: một chuỗi mô tả "package này là gì". Đặt ngay đầu file = mô tả cho cả package.
- `__version__ = "0.1.0"` → một **biến** tên `__version__`, gán chuỗi `"0.1.0"` = phiên bản dự án.
  Code khác có thể đọc `vision_platform.__version__` để biết version.
- Tên file `__init__.py` (hai gạch dưới mỗi bên) → tên ĐẶC BIỆT: Python thấy nó thì coi thư mục chứa nó là một **package**.

## 5. Là gì (1–2 câu)
**Package** = một thư mục chứa code Python mà nơi khác có thể `import`. `__init__.py` là file báo cho
Python: "thư mục này là package, hãy cho import".

## 6. Tại sao tồn tại / vấn đề nó giải
`__init__.py` đánh dấu một thư mục là **"regular package"**. Lưu ý chính xác: từ Python 3.3, vẫn có
loại **namespace package** import được mà KHÔNG cần `__init__.py` — nên nói "thiếu nó là Python không
import được" là *chưa đủ đúng*. Lý do thật ở dự án NÀY: `pyproject.toml` khai báo
`[tool.setuptools.packages.find] where = ["src"]`, mà `find` (mặc định) **chỉ gom thư mục CÓ
`__init__.py`** thành package khi `pip install`. Vậy `__init__.py` ở đây để: (a) thư mục được
setuptools nhận là package + cài đúng, (b) chỗ khai báo metadata nhẹ như `__version__`.

## 7. Dùng ở đâu trong project (cụ thể)
- File test gõ `import vision_platform` được là nhờ `src/vision_platform/__init__.py` tồn tại
  (xem `tests/test_smoke.py` — `assert vision_platform.__version__ == "0.1.0"`).
- Mỗi tầng (`domain`, `kernel`, ...) có `__init__.py` rỗng → để `import vision_platform.domain` chạy được.

## 8. Nếu KHÔNG có nó thì sao
Trong dự án này (setuptools `packages.find where=["src"]`): thiếu `__init__.py` ở một tầng → setuptools
**không gom** thư mục đó thành package khi `pip install -e .` → `import vision_platform.<tầng>` **lỗi
ModuleNotFoundError**. Đó là lý do skeleton tạo `__init__.py` cho MỌI tầng ngay từ đầu. (Còn nếu dùng
`find_namespace` thì khác — nhưng ở đây KHÔNG dùng.)

## 9. Ví von đời thường
`__init__.py` như **tấm biển tên đặt trước cửa một căn phòng**: có biển → người ngoài biết "đây là
phòng dùng được, gõ cửa vào được"; không biển → chỉ là khoảng trống, không ai biết vào kiểu gì.

## 10. Liên kết bức tranh lớn
Đây là bước biến 6 thư mục tầng thành 6 package import-được. Nhờ vậy `import-linter` mới "nhìn thấy"
`vision_platform.domain`, `vision_platform.kernel`... để kiểm luật hướng phụ thuộc (mẩu 06).

## 11. Cạm bẫy / lỗi thường gặp
- Để code nặng / side-effect trong `__init__.py` → dễ gây **circular import** + chậm. Best practice:
  giữ `__init__.py` **rỗng** (hoặc chỉ khai báo nhẹ như `__version__`).
- Quên 1 `__init__.py` ở tầng con → ImportError khó hiểu.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `__init__.py` báo cho Python điều gì? Vì sao mỗi tầng cần một cái?
- Giải thích lại bằng LỜI MÌNH: "package là ... , `__init__.py` để ..." (viết vào đây): ____

## 13. Mốc ôn
1 ngày → nói lại định nghĩa package | 1 tuần → tự tạo 1 package rỗng + import thử.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/src/vision_platform/__init__.py` (đọc nguyên văn) + `domain/__init__.py` rỗng (đã đọc). · Độ chắc: **cao**.
- Hành vi `import` + `__version__`: đã CHẠY thật — `tests/test_smoke.py::test_package_importable` + `test_package_has_layers` PASS. · Độ chắc: **cao**.
- Luật `packages.find` cần `__init__.py`: đối chiếu `pyproject.toml` (`[tool.setuptools.packages.find] where=["src"]`) + hành vi setuptools **có tài liệu** (`find` = regular package). · Độ chắc: cao (chưa thử nghiệm xoá file để tái hiện lỗi — [chưa kiểm bằng thực nghiệm]).
