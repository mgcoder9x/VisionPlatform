# #01 · Mẩu 04: optional-dependencies `[cv2]`/`[dev]` + `packages.find where=src`

## 1. Thuộc về đâu
Vấn đề #01 (skeleton) · file code thật: `vision-platform/pyproject.toml` (mục `[project.optional-dependencies]`
và `[tool.setuptools.packages.find]`) · đây là "thư viện cài THÊM tùy nhu cầu" + "tìm package ở đâu".

## 2. Cần biết trước
- [pip](../../knowledge-base/00-GLOSSARY.md#pip) ·
  [pyproject.toml](../../knowledge-base/00-GLOSSARY.md#pyprojecttoml) ·
  [src layout](../../knowledge-base/00-GLOSSARY.md#src-layout) ·
  [pytest](../../knowledge-base/00-GLOSSARY.md#pytest) ·
  [import-linter](../../knowledge-base/00-GLOSSARY.md#import-linter)

## 3. Code thật (quote NGUYÊN VĂN — không sửa)
```toml
[project.optional-dependencies]
cv2 = ["opencv-python>=4.8"]
dev = ["pytest>=7.4", "import-linter>=2.0"]

[tool.setuptools.packages.find]
where = ["src"]
```

## 4. Giải thích từng phần nhỏ nhất
- `[project.optional-dependencies]` → các nhóm thư viện **cài thêm khi cần**, không bắt buộc.
  - `cv2 = ["opencv-python>=4.8"]` → nhóm tên `cv2` gồm thư viện `opencv-python` (đọc/xử lý ảnh). Chỉ ai cần mới cài.
  - `dev = ["pytest>=7.4", "import-linter>=2.0"]` → nhóm `dev` (cho người phát triển) gồm `pytest` (chạy test) và `import-linter` (kiểm luật import).
- Cách cài một nhóm: thêm `[tên-nhóm]` sau dấu chấm khi cài, ví dụ `pip install -e .[dev]`.
- `[tool.setuptools.packages.find]` + `where = ["src"]` → đã gặp ở mẩu 02: bảo setuptools tìm package trong `src/`.

## 5. Là gì (1–2 câu)
**optional-dependencies** = các "gói phụ" theo tên, cài thêm khi cần (vd `[dev]` để code/test, `[cv2]`
để xử lý ảnh thật). Khác với `dependencies` (luôn cài, ở mẩu 03).

## 6. Tại sao tồn tại / vấn đề nó giải
Không phải ai dùng dự án cũng cần MỌI thư viện. Người chỉ chạy thật thì không cần `pytest`/`import-linter`
(chỉ dân phát triển cần). Máy chưa có camera thì chưa cần `opencv-python` nặng. Gom tất cả vào
`dependencies` bắt buộc → ai cũng phải tải đồ thừa, máy nhẹ/CI chậm hơn. Tách thành nhóm tùy chọn →
**chỉ cài cái mình cần**.

## 7. Dùng ở đâu trong project (cụ thể)
- Lệnh build dự án dùng `pip install -e .[dev]` (mẩu 07) → kéo về `numpy` (bắt buộc) + `pytest` +
  `import-linter` (nhóm dev) để chạy test và `lint-imports`.
- Nhóm `cv2` để dành cho khi cắm camera/đọc ảnh thật ở các bước sau — hiện chưa cài.

## 8. Nếu KHÔNG có nó thì sao (phản chứng)
Bỏ optional-deps, nhét hết vào `dependencies`: ai cài cũng phải tải `opencv-python` (nặng) +
công cụ dev → môi trường chạy thật phình to, lệ thuộc thư viện không cần. Hoặc ngược lại, không khai
báo `pytest`/`import-linter` ở đâu cả → mỗi người tự cài tay, dễ lệch phiên bản.

## 9. Ví von đời thường
optional-dependencies như **combo gọi thêm ở quán**: phần chính (numpy) luôn có; muốn "topping dev"
(pytest, linter) hay "topping cv2" thì gọi thêm đúng tên — không ăn thì không trả tiền.

## 10. Liên kết bức tranh lớn
Nhóm `dev` chính là thứ kích hoạt 2 công cụ giữ chất lượng của dự án: `pytest` (mẩu 07) và
`import-linter` (mẩu 06 — trọng tài ép hướng phụ thuộc 6 tầng). `where=["src"]` nối lại với src layout (mẩu 02).

## 11. Cạm bẫy / lỗi thường gặp
- Quên `[dev]` khi cài (`pip install -e .` không kèm nhóm) → gõ `pytest`/`lint-imports` báo "không tìm thấy lệnh".
- Dấu ngoặc vuông `.[dev]` trên một số shell cần đặt trong dấu nháy (`".[dev]"`) kẻo bị hiểu nhầm.

## 12. Tự kiểm (retrieval + Feynman) — đạt mới ✅
- Hỏi nhớ lại: vì sao tách `pytest`/`import-linter` ra nhóm `dev` thay vì để chung `dependencies`?
- Giải thích lại bằng LỜI MÌNH: "optional-dependencies để ... , cài bằng cách ..." (viết vào đây): ____

## 13. Mốc ôn (spaced repetition)
1 ngày → nói tên 2 nhóm optional + nội dung | 1 tuần → tự thêm 1 nhóm optional mới | 1 tháng → giải thích deps vs optional-deps.

## 14. Nguồn (đã verify) + độ chắc chắn
- Code thật: `vision-platform/pyproject.toml` (`[project.optional-dependencies]` + `[tool.setuptools.packages.find]`, đã đọc nguyên văn). · Độ chắc: **cao**.
- Hành vi `.[dev]` kéo pytest+import-linter: đã CHẠY `pip install -e .[dev]` + dùng được `pytest`/`lint-imports` thật. · Độ chắc: **cao**.
- Cú pháp optional-deps PEP 621: tài liệu chính thống. · Độ chắc: cao.
