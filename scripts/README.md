# scripts/ — Dev-env launcher (chạy giống nhau trên mọi máy)

> Mục đích: xóa ma sát "đổi máy phải làm lại tay" (dò Python, dựng venv, chọn extras theo GPU,
> lint qua workaround). Xem journal K-013/K-044/K-047/K-048/K-049/K-052/K-057.

## Dùng (Windows)
```
scripts\vp.cmd env      :: in môi trường đã phát hiện (Python / venv / GPU / extras)
scripts\vp.cmd setup    :: dựng/sửa venv (vision-platform\.venv) + pip install -e .[EXTRAS]
scripts\vp.cmd test     :: pytest -q  (dùng venv dự án)
scripts\vp.cmd lint     :: import-linter qua importlinter.api (né AV chặn .exe — K-044)
scripts\vp.cmd check    :: drift-check (nhất quán bộ nhớ + RULES_VERSION)
scripts\vp.cmd verify   :: test + lint + check (cổng "mọi thứ xanh")
```
Exit code: `0` = OK; khác 0 = bước tương ứng fail (propagate).

## Vì sao chạy được trên máy khác nhau
- **Tự dò interpreter theo KHẢ NĂNG** (`--version` exit 0), thứ tự `py -3` → venv → `python` —
  không hardcode tên (Windows Store-alias `python` tồn tại mà hỏng → tự loại). Cùng pattern
  `tests/drift_check.cmd`.
- **GPU** dò qua `nvidia-smi` (chỉ để INFORM; KHÔNG tự cài torch — tránh bẫy torch-CPU K-049).

## Profile riêng theo máy (không đụng file chung)
Copy `scripts\env.local.cmd.example` → `scripts\env.local.cmd` (**đã .gitignore**), bỏ comment:
```
set "VP_PYTHON=py -3.11"            :: ép interpreter nếu auto-detect chọn sai
set "VP_EXTRAS=dev,onnx,cv2,web,pt" :: máy CÓ GPU muốn chạy torch → thêm 'pt'
```
`vp.cmd` `call` file này TRƯỚC auto-detect → biến ở đây GHI ĐÈ. Mỗi máy 1 bản riêng; file
tracked vẫn chạy mọi nơi nhờ auto-detect.

## Ghi chú
- Linux: `vp.cmd` là Windows-only; lõi Python (pytest/importlinter/drift_check.py) đã cross-OS
  → thêm `vp.sh` tương đương khi có máy dev Linux (chưa cần — YAGNI).
- `setup` khi gặp venv HỎNG (python trong venv chạy lỗi) tự dời sang `.venv_broken` rồi tạo mới.
