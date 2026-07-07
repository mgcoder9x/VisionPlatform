# Mẩu 02 — `python -m build`: wheel + sdist + fresh-install verify

**(1) Thuộc về đâu:** `pyproject.toml` (`[build-system]`) + lệnh `python -m build` + `dist/`.

**(2) Cần biết trước:** wheel (gói binary `.whl` cài nhanh) vs sdist (source `.tar.gz`); `pip install`;
venv sạch; `__version__`.

**(3) Bằng chứng thật (quote `pyproject.toml` + output):**
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"
```
Output `python -m build` (đã chạy thật):
```
Successfully built vision_platform-0.1.0.tar.gz and vision_platform-0.1.0-py3-none-any.whl
```
Fresh-install (venv tạm): `import vision_platform; print(__version__)` → `0.1.0`.

**(4) Giải thích từng ý nhỏ:**
- `[build-system].requires` → công cụ cần để DỰNG gói (setuptools + wheel). `build-backend` → ai dựng.
- `python -m build` → dựng cả **sdist** (`.tar.gz`, source) + **wheel** (`.whl`, binary cài nhanh) vào `dist/`.
- Fresh-install: cài wheel vào **venv sạch** rồi `import` → chứng minh gói dùng được ở máy khác (không dựa source dev).
- `build` (công cụ) cài riêng (`pip install build`) — KHÔNG vào `[project] dependencies` (K-022): nó là
  dev/ship tool, không phải thứ runtime cần.

**(5) Là gì:** bước biến source thành gói phân phối chuẩn Python + kiểm gói cài được thật.

**(6) Tại sao fresh-install (không chỉ build):** build thành công ≠ cài được. Wheel có thể thiếu file /
sai layout → `import` lỗi ở máy sạch. Cài vào venv tạm + import + kiểm version = bằng chứng thật "ship được".

**(7) Dùng ở đâu trong project:** `dist/vision_platform-0.1.0-py3-none-any.whl` (59KB) + `.tar.gz`
(85KB). `dist/`+`build/`+`*.egg-info/` đã gitignore (không commit artifacts).

**(8) Không build/verify thì sao:** giao source thô → máy khác phải tự dựng, dễ lỗi môi trường; hoặc
wheel lỗi layout mà không ai phát hiện tới lúc deploy.

**(9) Ví von:** đóng hàng vào thùng chuẩn (wheel) + **thử mở thùng ở kho khác** (fresh-install) xem đủ
đồ không — thay vì chỉ đóng rồi tin.

**(10) Liên kết bức tranh lớn:** wheel là đầu ra "shippable". Layout `src/` + `[tool.setuptools.packages.find]`
(bài #01) đảm bảo package đóng gói đúng. Fresh-install nối DoD (mẩu 01).

**(11) Cạm bẫy:** đừng thêm `build` vào runtime deps (K-022). Đừng commit `dist/`/`build/` (gitignore).
Nhớ XOÁ venv tạm sau verify (cleanup — đã làm). Version trong `__init__.py` phải khớp `pyproject`.

**(12) Tự kiểm:**
- wheel vs sdist khác gì? Vì sao fresh-install verify quan trọng hơn "build thành công"?
- `build` nên ở [project] deps hay không? Vì sao?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `pyproject.toml` + output `python -m build` thật · Design step-10 (Phần 3). Độ chắc:
cao (wheel 0.1.0 dựng + fresh-install verify thật).
