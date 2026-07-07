# Bài #10 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (ship = đóng gói + DoD + tổng kết). #10 không có code pattern mới.
> Trạng thái: ✅ đã viết + verify thật. Cột Feynman = riêng (user học sau).
> Bám: `README.md` + `pyproject.toml` + output thật (`pytest` 290/1 · lint 5/0 · wheel 0.1.0).

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Nguồn thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-ship-dod.md` | Ship = gói phân phối + Definition of Done (bằng chứng chạy thật) | `README.md` (DoD) | ✅ |
| 02 | `02-build-wheel.md` | `python -m build` → wheel/sdist; build-system; fresh-install verify; `build` là dev tool | `pyproject.toml` + output build | ✅ |
| 03 | `03-re-run-so-that.md` | Re-run full suite = DoD; SỐ THẬT 290/1 (không blueprint 110); lint gate | output pytest/lint | ✅ |
| 04 | `04-module-03-tong-ket.md` | Bản đồ pattern #01–#10 + trade-offs hoãn cho production | toàn Module 03 | ✅ |

> ✅ **ĐỦ 4/4 MẨU** — bám bằng chứng chạy thật. **Cổng Feynman:** user tự giải thích lại (học sau).
> AI KHÔNG tự chấm. Không dán lesson vào chat.
