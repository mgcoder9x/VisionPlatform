# Vấn đề #10 — Package + ship + re-run all (PHA 1 valid) — CUỐI Module 03

> **Nguồn Design:** `Design/module-03-build-along/step-10-package-and-ship.md` (đọc nguyên văn).
> **Trạng thái:** PHA 1 valid. #10 KHÔNG code mới — là verify/package/ship + README + DoD.
> **Cập nhật lúc:** 2026-07-04.

## 1. Mục tiêu #10 (theo Design)
1. Re-run full test suite (definition of done).
2. Smoke test demo end-to-end (`demo_pipeline` với --source noise/fake).
3. Build wheel package (`python -m build`).
4. README (kiến trúc + quick start + test count + trade-offs).
5. .gitignore + DoD checklist.

## 2. Đối chiếu Design ↔ CODE THẬT (chống bịa — KHÁC BIỆT QUAN TRỌNG)
| Design (blueprint vision_demo) | THẬT (vision_platform) | Kết luận |
|---|---|---|
| package `vision_demo`, "110 passed, 1 skipped" | `vision_platform`, **290 passed, 1 skipped** (đã tiến hoá: production-hardening #05 + switchover #05b + #06–#09) | README dùng SỐ THẬT, KHÔNG copy 110 (C-009) |
| smoke `import vision_demo; __version__` | `vision_platform/__init__.py` có `__version__="0.1.0"` | ✅ |
| demo CLI `--source noise --frames 10 --threshold 100.0` | `demo_pipeline.py` có đúng `--source{fake,noise} --frames --threshold --width --height` | ✅ khớp |
| `python -m build` → wheel | `build` CHƯA cài (kiểm khi chạy) | thêm bước cài `build` (dev tool) |
| adapter list (InlineInferenceClient ở adapters) | THẬT: InlineInferenceClient ở **application** (E-06-1) | README ghi đúng vị trí thật |

## 3. Đánh giá (chống bịa số liệu)
- **Số test:** Design nói 110 (blueprint). Dự án THẬT đã vượt xa (thêm hardening/switchover/observability/backpressure/supervisor). Con số verify hiện tại = **290 passed, 1 skipped** (Entry #164). README + DoD PHẢI dùng số thật, ghi rõ "khác blueprint vì đã production-hardening".
- **1 skipped:** có chủ đích (test cần môi trường khác — vd ARM/POSIX guard skip trên Windows). Không phải lỗi.
- **Vị trí file:** README mô tả layer theo THẬT (InlineInferenceClient ở application — E-06-1; observability ở runtime; backpressure ở kernel).

## 4. Điều NÊN BIẾT (ghi journal)
- **C-009:** README/DoD dùng số test THẬT (290/1) thay blueprint (110) — vì dự án đã tiến hoá vượt vision_demo MVP.
- **K-022 (build tool):** `python -m build` cần package `build` (+ thường `wheel`). Là dev/ship tool, cài khi cần; KHÔNG thêm vào [project] dependencies (không phải runtime dep).
- Optional extensions trong Design (cv2 adapter / async executor / ZMQ client) = NGOÀI scope #10 (tương lai/production). ZMQ là phần production đã hoãn từ #06.

## 5. Kế hoạch PHA 2 (verify + package)
1. Re-run `pytest -q` (xác nhận 290/1) + `lint-imports` (5/0).
2. Smoke demo: `python -m vision_platform.profiles.demo_pipeline --source noise --frames 10 --threshold 100.0` + `--source fake --frames 5 --threshold 100.0` → đọc summary thật.
3. `pip install build` → `python -m build` → verify `dist/*.whl` + `*.tar.gz` tạo ra.
4. Tạo `vision-platform/README.md` (số thật, layer thật, trade-offs).
5. Verify .gitignore đủ (đã có ở repo). DoD checklist đánh dấu theo bằng chứng thật.
