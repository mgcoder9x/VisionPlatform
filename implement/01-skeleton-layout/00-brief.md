# Vấn đề #01 — Project skeleton + venv + pyproject + smoke test

> **Nguồn Design (đã đọc trực tiếp — độ chắc: cao):** `Design/module-03-build-along/step-01-project-skeleton.md`.
> Mọi quyết định dưới đây trỏ về file đó. Lệch = ghi vào "Deviation" + báo.

## Mục tiêu (xong = gì)
- 1 venv hoạt động.
- `pyproject.toml` chuẩn → `pip install -e .` được + import-linter contracts.
- Skeleton 5 layer Hexagonal: `domain`, `kernel` (+`ports`), `runtime` (+`stages`,+`ipc`),
  `application`, `adapters`, `profiles` — mỗi cái có `__init__.py`.
- 2 smoke test → `pytest` in **2 passed**; `lint-imports` in **0 broken**.

## Deviation có chủ đích so với Design (ghi để chống drift ngầm)
| Điểm | Design gốc | Ở đây | Lý do |
|------|-----------|-------|-------|
| Tên package | `vision_demo` | `vision_platform` *(chờ chốt MT1)* | Dự án THẬT. Cấu trúc + contracts y hệt, chỉ đổi tiền tố (token duy nhất, dễ rename). |
| Nơi đặt code | workspace tách rời | **folder riêng bên ngoài `implement/`** (đề xuất `vision-platform/`) | `implement/` chỉ chứa tài liệu; code tách ra để bulkhead. |
| Số test | "2 passed" (kỳ vọng) | xác nhận bằng chạy thật | Chỉ ✅ khi pytest thật in 2 passed. |

## RENAME PLAYBOOK (đổi tên package sau này KHÔNG lỗi)
Tên package là **1 token duy nhất**, chỉ xuất hiện ở 4 chỗ:
1. Thư mục `src/<pkg>/`.
2. `pyproject.toml`: `[project].name`, `[tool.importlinter].root_package`, tiền tố trong 5 contracts.
3. `import <pkg>...` trong code + test.
4. Docstring `src/<pkg>/__init__.py`.
→ **Đổi tên = tìm-thay toàn bộ token `<pkg>` trong folder dự án + đổi tên 1 thư mục `src/<pkg>` + chạy lại `pytest` & `lint-imports`.**
Vì token duy nhất → find-replace sạch, không sót. Chạy lại validate xác nhận 0 lỗi.

## Micro-task (CỰC NHỎ — làm 1 cái/lần, validate xong mới sang)
- [x] **MT1** — Chốt tên package `vision_platform` + project root `e:\VisionPlatform\vision-platform\`.
- [x] **MT2** — Tạo cây thư mục + 11 `__init__.py` (root có `__version__`).
- [x] **MT3** — `pyproject.toml` (numpy; extras cv2/dev; src layout; 5 contract import-linter + `include_external_packages`).
- [x] **MT4** — `tests/test_smoke.py` (2 test) + `.gitignore`.
- [x] **MT5** — venv + `pip install -e .[dev]` + `pytest` (**2 passed**) + `lint-imports` (**5 kept/0 broken**). ✅ validate THẬT.

## Phát hiện khi validate (design-validation)
- **E-9:** pyproject Step 01 của Design thiếu `include_external_packages = true` → `lint-imports`
  lỗi config với forbidden module ngoài. Đã sửa cả `vision-platform/pyproject.toml` + Design step-01
  + ghi `Design/00-ERRATA.md` E-9. Xác nhận lại: 5 kept/0 broken.

## Trạng thái
- ✅ **XONG** — vấn đề #01 validate thật. Chờ "đi tiếp" để sang #02.
