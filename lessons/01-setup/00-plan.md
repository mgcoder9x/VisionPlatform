# Bài 01: Setup — Tạo project chạy được — KẾ HOẠCH

> Nguồn: `Design/module-03-build-along/step-01-project-skeleton.md` (đã verify). Build-first:
> có skeleton chạy được trước, lý thuyết Module 01–02 học sau/đan xen.

## Mục tiêu (sau bài LÀM ĐƯỢC gì)
- Có `vision_demo_workspace/` (project con tách riêng) chạy được: venv + `pyproject.toml` +
  skeleton 6 layer + `import-linter` + `pytest` **2 passed**.
- Biết kiểm môi trường → cài đúng cái thiếu (không thừa).

## Cần học TRƯỚC (concept tiên quyết)
- Chưa bắt buộc. Khái niệm gặp giữa đường (src-layout, Hexagonal 6 layer, import-linter) sẽ
  giải thích tại chỗ; nếu cần sâu → tạo `knowledge-base/<concept>/` và học ở đó.

## Các buổi (mỗi buổi = 1 folder)
1. `01-env-workspace/` — kiểm môi trường + tạo workspace tách riêng + venv.
2. `02-pyproject-deps/` — `pyproject.toml` + cài deps + import-linter (vì sao mỗi quyết định).
3. `03-skeleton-layers/` — dựng skeleton 6 layer (`__init__.py`).
4. `04-smoke-test/` — smoke test → `pytest` 2 passed + `lint-imports` 0 broken.

## Tiêu chí ĐẬU (qua cổng Feynman — AI hỏi ≥2 câu tình huống/trade-off)
- [ ] `pytest` in `2 passed`; `lint-imports` in `0 broken`.
- [ ] Tự giải thích (bằng ngôn từ mình): vì sao **src-layout**, vì sao **import-linter từ Step 01**.
- [ ] Tự dựng lại skeleton từ trí nhớ (không nhìn mẫu).

## Nguồn (đã validate)
- Module 03 step-01 — độ chắc chắn: cao (đọc trực tiếp file trong repo).
