# Bài #10 — Package + ship: câu chuyện (đóng gói + kiểm cuối + tổng kết Module 03)

> Đọc file này TRƯỚC. #10 KHÔNG thêm code pattern mới — nó là bước **đóng gói + chứng minh "sẵn sàng
> giao"** (definition of done) và **tổng kết** cả hành trình #01→#09. Bám bằng chứng THẬT đã chạy.
> Bám: `vision-platform/README.md` + `pyproject.toml` + output `pytest`/`lint-imports`/`python -m build`
> (trạng thái: **290 passed, 1 skipped · lint 5 kept/0 broken · wheel 0.1.0** dựng được + fresh-install OK).

---

## Nhịp 1 — Tổng quan: "ship" nghĩa là gì?

Sau #01→#09 ta có code chạy được + test xanh. Nhưng "chạy trên máy tôi" ≠ "giao được". **Ship** =
biến source thành **gói phân phối** (wheel/sdist) mà máy khác `pip install` được, kèm bằng chứng nó
đạt chuẩn (**Definition of Done — DoD**): test xanh, không rò rỉ layer, demo chạy, đóng gói được, có README.

```
source code ──(pytest + lint)──► bằng chứng đạt chuẩn
            ──(python -m build)──► dist/*.whl + *.tar.gz ──(pip install)──► máy khác dùng được
```

---

## Nhịp 2 — Vấn đề & TẠI SAO nó là vấn đề

- **"Xong" mơ hồ:** không có tiêu chí rõ thì ai cũng nói "xong" — rồi vỡ lúc giao. Cần **DoD** = danh
  sách kiểm đóng, mỗi mục có **bằng chứng chạy thật** (không nói suông — luật §5).
- **Số liệu bịa:** Design (blueprint `vision_demo`) ghi "110 test". Dự án THẬT đã tiến hoá xa hơn
  (production-hardening #05 + switchover #05b + #06–#09) → **290 passed, 1 skipped**. Copy 110 vào
  README = **bịa**. Nỗi đau: tài liệu sai làm mất niềm tin + kiểm chứng sai về sau.
- **Đóng gói lỗi:** import được lúc dev (chạy từ source) không đảm bảo wheel cài ra máy sạch cũng import
  được (thiếu file, sai package layout). Phải **fresh-install verify** thật.

---

## Nhịp 3–4 — Cách làm + tại sao

1. **Re-run full suite là DoD chính** — `pytest` phải xanh THẬT + `lint-imports` 5 kept/0 broken (ranh
   giới layer không rò rỉ). Đây là "chân lý", không phải kỳ vọng.
2. **README dùng SỐ THẬT** (290/1) — ghi rõ khác blueprint vì đã hardening. Trung thực + kiểm chứng được.
3. **`python -m build`** dựng wheel + sdist; **cài vào venv sạch** rồi `import` + kiểm `__version__` →
   chứng minh gói dùng được ở máy khác (không chỉ "chạy từ source").
4. **`build` là dev/ship tool**, KHÔNG phải runtime dependency (không nhét vào `[project] dependencies`).
5. **.gitignore** loại artifacts (dist/build/egg-info/pycache) — không commit thứ sinh ra.

---

## Nhịp 5–6 — Triển khai + tổng kết

Đọc các mẩu (`00-muc-luc.md`): vì-sao ship/DoD → build wheel + fresh-install → re-run & số-thật →
**tổng kết Module 03** (bản đồ mọi pattern #01–#10 + trade-offs hoãn cho production).

- ✅ **NÊN:** DoD mỗi mục có bằng chứng chạy thật; README số thật; fresh-install verify wheel.
- ⛔ **TRÁNH:** copy số blueprint vào tài liệu (bịa); commit artifacts (dist/build); coi "import được từ source" = "ship được".
