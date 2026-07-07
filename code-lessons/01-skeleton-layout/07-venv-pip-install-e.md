# #01 · Mẩu 07: venv + `pip install -e .[dev]` + smoke test

## 1. Thuộc về đâu
Vấn đề #01 (skeleton) · file code thật: `vision-platform/tests/test_smoke.py` + lệnh môi trường
(`venv`, `pip install -e .[dev]`) · đây là bước "biến khung tĩnh thành môi trường chạy được + bằng chứng nó chạy".

## 2. Cần biết trước
- [venv](../../knowledge-base/00-GLOSSARY.md#venv) ·
  [pip](../../knowledge-base/00-GLOSSARY.md#pip) ·
  [src layout](../../knowledge-base/00-GLOSSARY.md#src-layout) ·
  [pytest](../../knowledge-base/00-GLOSSARY.md#pytest) ·
  [package](../../knowledge-base/00-GLOSSARY.md#package-thư-viện--library)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```python
# vision-platform/tests/test_smoke.py
"""Smoke test: verify package importable + version present."""
import vision_platform


def test_package_importable():
    """Package phải import được sau khi pip install -e."""
    assert vision_platform.__version__ == "0.1.0"


def test_package_has_layers():
    """All layer subpackages phải tồn tại (4 layer + adapter rim + profiles)."""
    import vision_platform.domain
    import vision_platform.kernel
    import vision_platform.kernel.ports
    import vision_platform.runtime
    import vision_platform.application
    import vision_platform.adapters
    import vision_platform.profiles
```
Lệnh môi trường thật (chạy trong thư mục `vision-platform/`):
```
py -m venv .venv               # tạo "hộp" Python riêng
.venv\Scripts\python.exe -m pip install -e .[dev]   # cài package + nhóm dev
.venv\Scripts\python.exe -m pytest                  # chạy test
```

## 4. Giải thích từng phần nhỏ nhất
- `py -m venv .venv` → tạo môi trường ảo tên `.venv` (hộp Python riêng cho dự án này).
- `pip install -e .[dev]`:
  - `.` → cài package ở thư mục hiện tại (đọc `pyproject.toml`).
  - `-e` → "editable": cài kiểu LIÊN KẾT tới `src/`, sửa code là dùng ngay, không cần cài lại.
  - `[dev]` → kèm nhóm optional `dev` (mẩu 04): `pytest` + `import-linter`.
- `test_smoke.py`:
  - `import vision_platform` → import được = package đã cài đúng (nhờ src layout + `where=["src"]`).
  - `assert vision_platform.__version__ == "0.1.0"` → kiểm version khớp `__init__.py` (mẩu 01). `assert` = "phải đúng, sai thì test fail".
  - `test_package_has_layers` → import lần lượt cả 6 tầng + `kernel.ports`; nếu thiếu `__init__.py` ở tầng nào, dòng import đó sẽ lỗi → bắt được khung dựng sót.

## 5. Là gì (1–2 câu)
**venv** = môi trường Python cô lập cho dự án. **`pip install -e .[dev]`** = cài package ở chế độ sửa-được
kèm công cụ dev. **smoke test** = test "khói" tối thiểu chỉ để xác nhận "khung dựng xong và import được".

## 6. Tại sao tồn tại / vấn đề nó giải
- venv: tránh thư viện dự án này đụng dự án khác (mỗi dự án một hộp riêng).
- `-e` (editable): khung sẽ còn sửa liên tục qua #02→#10; nếu cài kiểu thường thì mỗi lần sửa phải cài lại → chậm. `-e` cho sửa-là-chạy.
- smoke test: với src layout, "import được" KHÔNG hiển nhiên — phải cài đúng mới import được. Smoke test cho **bằng chứng chạy thật** rằng khung đã dựng xong, không chỉ "nhìn thấy đúng".

## 7. Dùng ở đâu trong project (cụ thể)
- Mọi bước build (#01→#10) đều chạy trong `.venv` này.
- `pytest` đọc cấu hình `[tool.pytest.ini_options]` trong `pyproject.toml` (`testpaths=["tests"]`) → tự tìm test trong `tests/`.
- Bài #01 kết thúc bằng việc smoke test PASS = bằng chứng khung hợp lệ trước khi sang #02.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
- Không venv: cài thẳng vào Python hệ thống → lẫn thư viện giữa các dự án, dễ vỡ.
- Không `-e`: sửa code phải cài lại mỗi lần.
- Không smoke test: dựng khung xong chỉ "tin là đúng" — tới #02 import lỗi mới phát hiện khung sai từ đầu, tốn công truy ngược.

## 9. Ví von đời thường
- venv = **bếp riêng** cho mỗi món (không xài chung gia vị).
- `-e` = **liên kết tới bản gốc** thay vì photo: sửa bản gốc là thấy ngay.
- smoke test = **bật thử bếp xem có lên lửa không** trước khi nấu món chính.

## 10. Liên kết bức tranh lớn
Đây là mẩu KHÉP LẠI bài #01: gom src layout (02) + pyproject (03) + optional `[dev]` (04) + 6 tầng (05) +
import-linter (06) thành một môi trường chạy được, có bằng chứng PASS. Từ đây mới đủ điều kiện sang #02.

## 11. Cạm bẫy / lỗi thường gặp
- Quên kích hoạt/đúng python của venv → cài nhầm vào Python hệ thống. (Cách chắc ăn: gọi thẳng `.venv\Scripts\python.exe`.)
- Quên `[dev]` → `pytest`/`lint-imports` "không tìm thấy lệnh".
- Trên một số shell phải để `".[dev]"` trong dấu nháy.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `-e` để làm gì? Vì sao "import được" là một bằng chứng đáng giá với src layout?
- Tình huống: nếu lỡ xóa `application/__init__.py`, test nào sẽ fail, ở dòng nào? Vì sao bắt được lỗi sớm là tốt?
- Giải thích lại bằng LỜI MÌNH: "venv để ... , smoke test để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói lại 3 lệnh môi trường | 1 tuần → tự dựng venv + cài editable 1 dự án nhỏ | 1 tháng → giải thích vì sao smoke test có giá trị.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/tests/test_smoke.py` (đã đọc nguyên văn). · Độ chắc: **cao**.
- Hành vi: smoke test PASS thật (phiên #01: `pytest` 2 passed; toàn bộ hiện 64 passed/1 skipped). · Độ chắc: **cao**.
- `venv`/`pip -e`/PEP 660 editable: công cụ chuẩn, có tài liệu chính thống. · Độ chắc: cao.
