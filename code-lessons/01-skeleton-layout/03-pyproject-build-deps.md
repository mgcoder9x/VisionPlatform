# #01 · Mẩu 03: `pyproject.toml` — build-system + project + dependencies

## 1. Thuộc về đâu
Vấn đề #01 (skeleton) · file code thật: `vision-platform/pyproject.toml` (phần đầu) · đây là "lý lịch"
khai báo dự án tên gì, chạy trên Python nào, cần thư viện nào, build bằng công cụ gì.

## 2. Cần biết trước
- [pyproject.toml](../../knowledge-base/00-GLOSSARY.md#pyprojecttoml) ·
  [package](../../knowledge-base/00-GLOSSARY.md#package-thư-viện--library) ·
  [pip](../../knowledge-base/00-GLOSSARY.md#pip)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vision_platform"
version = "0.1.0"
description = "Vision platform thật - kiểm chứng thiết kế Design/ (theo Module 03)"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
]
```

## 4. Giải thích từng phần nhỏ nhất
- `[build-system]` → khai báo "dựng (build) package này bằng gì".
  - `requires = ["setuptools>=68", "wheel"]` → để build cần có `setuptools` (phiên bản ≥ 68) và `wheel`. Đây là công cụ build, không phải thư viện chạy của dự án.
  - `build-backend = "setuptools.build_meta"` → chọn `setuptools` làm "động cơ" build.
- `[project]` → thông tin chính của dự án.
  - `name = "vision_platform"` → tên package khi cài/import.
  - `version = "0.1.0"` → phiên bản (khớp `__version__` ở mẩu 01).
  - `description = "..."` → mô tả một dòng.
  - `requires-python = ">=3.11"` → yêu cầu Python từ 3.11 trở lên mới cài được.
  - `dependencies = [...]` → danh sách thư viện BẮT BUỘC để chạy. Ở đây chỉ `numpy>=1.26` (numpy ≥ 1.26).
- Dấu `>=` → "phiên bản này TRỞ LÊN". `numpy>=1.26` = numpy 1.26 hoặc mới hơn.

## 5. Là gì (1–2 câu)
`pyproject.toml` = file tiêu chuẩn khai báo metadata + cách build một dự án Python. Phần `[build-system]`
nói "build bằng gì", phần `[project]` nói "dự án là gì + cần gì để chạy".

## 6. Tại sao tồn tại / vấn đề nó giải
Ngày xưa mỗi dự án dùng kiểu khai báo riêng (`setup.py` chạy code tùy ý) → công cụ khó đoán, dễ loạn.
`pyproject.toml` là **một chuẩn chung** (PEP 518/621): mọi công cụ (`pip`, `build`, IDE) đọc cùng một
chỗ, cùng một định dạng → cài đặt đoán được, lặp lại được. `dependencies` để `pip` tự kéo đúng thư viện
về, người khác không phải đoán "dự án này cần cài thêm gì".

## 7. Dùng ở đâu trong project (cụ thể)
- Khi chạy `pip install -e .[dev]` (mẩu 07), `pip` đọc đúng file này: build bằng setuptools, cài `numpy`,
  rồi cài luôn nhóm phụ `dev` (mẩu 04).
- `requires-python = ">=3.11"` chặn cài trên Python quá cũ.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Không có `pyproject.toml` → `pip` không biết dự án tên gì, cần gì, build sao → không cài được package,
`import vision_platform` thất bại. Mỗi người phải tự đoán và cài tay từng thư viện → dễ sai phiên bản.

## 9. Ví von đời thường
`pyproject.toml` như **tờ khai + công thức** dán trên hộp đồ ăn: tên món, hạn dùng, nguyên liệu cần,
lò nướng nào. Ai cầm hộp cũng làm ra đúng món đó.

## 10. Liên kết bức tranh lớn
Đây là gốc của mọi thứ: chính file này còn chứa cấu hình `pytest` và luật `import-linter` (mẩu 06).
Một file khai báo, nhiều công cụ cùng đọc.

## 11. Cạm bẫy / lỗi thường gặp
- Nhầm thư viện BUILD (`setuptools`, `wheel`) với thư viện CHẠY (`numpy`): cái ở `[build-system].requires`
  chỉ để dựng package; cái ở `[project].dependencies` mới đi cùng khi chạy.
- Đặt phiên bản quá lỏng/quá chặt: `>=` cho linh hoạt nhưng có thể kéo bản mới gây vỡ; đây là trade-off.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: `[build-system]` và `[project].dependencies` khác nhau ở chỗ nào? `>=1.26` nghĩa là gì?
- Giải thích lại bằng LỜI MÌNH: "pyproject.toml để ... , `dependencies` để ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → liệt kê 4 khóa trong `[project]` | 1 tuần → tự viết `[project]` cho 1 dự án nhỏ | 1 tháng → giải thích build-system vs dependencies.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/pyproject.toml` (đã đọc nguyên văn phần `[build-system]` + `[project]`). · Độ chắc: **cao**.
- Hành vi cài đặt: đã CHẠY `pip install -e .[dev]` thật + test pass. · Độ chắc: **cao**.
- Chuẩn PEP 518/621: có tài liệu chính thống (Python Packaging). · Độ chắc: cao (dẫn nguyên lý, [chưa kiểm] số PEP từng chữ).
