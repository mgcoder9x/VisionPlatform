# Mẩu 07 — Worker ở module riêng (Windows spawn re-import)

**(1) Thuộc về đâu:** `tests/worker_funcs_for_step_09.py` (module riêng) + cách test import nó.

**(2) Cần biết trước:** spawn vs fork (2 cách tạo process con); pickle (đóng gói để gửi qua process);
pytest collection (quét file test).

**(3) Code thật (quote docstring `tests/worker_funcs_for_step_09.py` + import trong test):**
```python
"""Worker functions cho test Step 09 shutdown.
Module RIÊNG để multiprocessing spawn (mặc định trên Windows) pickle được (qua module path)
mà KHÔNG re-import test module. Không có side-effect top-level.
"""
```
```python
# tests/test_step_09_shutdown.py
from tests.worker_funcs_for_step_09 import (
    ok_worker as _ok_worker, crash_worker as _crash_worker, ...
)
```

**(4) Giải thích từng ý nhỏ:**
- Windows mặc định dùng **spawn**: process con **re-import** module chứa hàm target (để unpickle hàm theo đường dẫn module).
- Nếu target ở **test file** → con re-import file test → có thể kích hoạt logic thu thập test → hành vi
  không mong muốn / đệ quy.
- → Tách worker ra **module riêng** không có side-effect top-level → con re-import an toàn.
- `from tests.worker_funcs_for_step_09 import ...` chạy được vì `tests/` là **package** (có `__init__.py`).

**(5) Là gì:** quy ước đặt các hàm worker ở module độc lập để multiprocessing spawn dùng an toàn.

**(6) Tại sao tồn tại / vấn đề nó giải:** trên Windows (và macOS/Python mới), spawn cần pickle + re-import
target. Đặt worker ở module sạch → tránh lỗi re-import test / đệ quy; hàm picklable qua module path.

**(7) Dùng ở đâu trong project:** mọi test #09 import worker từ đây. (So với test cross-process #05
để worker module-level TRONG file test — cũng chạy vì re-import test module không kích hoạt collection,
nhưng để module riêng là best-practice + đúng Design.)

**(8) Không có (để worker trong test file) thì sao:** rủi ro trên spawn (re-import test → collection/
đệ quy). Design cảnh báo rõ; module riêng loại bỏ rủi ro.

**(9) Ví von:** đưa cho xưởng vệ tinh (process con) **bản vẽ rời** (module worker) thay vì bắt họ đọc
lại toàn bộ sổ tay nhà máy (test file) — nhanh, không lẫn.

**(10) Liên kết bức tranh lớn:** ràng buộc nền tảng Windows xuyên suốt (như #05 SHM cross-process, #05b
T-B spawn). `tests/__init__.py` tồn tại → import package hoạt động cả khi spawn.

**(11) Cạm bẫy:** module worker KHÔNG được có side-effect top-level (chạy khi import) — sẽ chạy lại ở
mỗi spawn. Chỉ định nghĩa hàm. `fork` (Linux) không re-import nhưng Python bỏ dần fork mặc định (macOS) → module riêng là an toàn nhất.

**(12) Tự kiểm:**
- Vì sao spawn cần worker ở module riêng? Bug gì nếu để trong test file?
- Vì sao `from tests.worker_funcs...` import được? (nối `tests/__init__.py`)

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/worker_funcs_for_step_09.py` + `tests/test_step_09_shutdown.py` (import) · Design
step-09 (Phần 2 + Self-check #3). Độ chắc: cao (quote thật + 6 test spawn pass trên Windows).
