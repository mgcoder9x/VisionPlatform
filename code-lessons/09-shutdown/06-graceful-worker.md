# Mẩu 06 — `graceful_worker`: cooperative (poll event) + `finally` cleanup

**(1) Thuộc về đâu:** `tests/worker_funcs_for_step_09.py`, `graceful_worker`. Mẫu worker graceful đúng nghĩa.

**(2) Cần biết trước:** mẩu 05 (cascade); `mp.Event` (`.is_set()`, `.wait(timeout)`); `try/finally`
(cleanup luôn chạy khi thoát vòng — trừ khi bị kill cứng).

**(3) Code thật (quote `tests/worker_funcs_for_step_09.py`):**
```python
def graceful_worker(shutdown_event, work_path):
    try:
        while not shutdown_event.is_set():
            with open(work_path, "a") as f:
                f.write(f"alive_{time.time():.3f}\n")
            shutdown_event.wait(timeout=0.05)   # responsive: thoát <=0.05s sau khi set
    finally:
        # Cleanup chạy được vì worker tự thoát vòng lặp (không bị kill cứng).
        with open(work_path, "a") as f:
            f.write("cleanup_done\n")
```

**(4) Giải thích từng ý nhỏ:**
- `graceful_worker(shutdown_event, work_path)` → arg ĐẦU là `shutdown_event` (Supervisor tự chèn khi
  `uses_shutdown_event=True`, mẩu 02).
- `while not shutdown_event.is_set():` → vòng làm việc, dừng khi event được set.
- `shutdown_event.wait(timeout=0.05)` → ngủ ngắn NHƯNG **responsive**: nếu event set giữa chừng, `wait`
  trả về ngay (không phải chờ hết 0.05s) → thoát nhanh.
- `finally: ... "cleanup_done"` → dọn dẹp **luôn chạy** khi thoát vòng bình thường.

**(5) Là gì:** worker "hợp tác": chủ động kiểm tín hiệu dừng, tự thoát, tự dọn dẹp.

**(6) Tại sao tồn tại / vấn đề nó giải:** đây là cách graceful DUY NHẤT chạy đúng trên CẢ Windows lẫn
Linux. Vì Windows `terminate()` = giết cứng (không chạy `finally`), muốn cleanup chắc chắn thì worker
phải **tự thoát** (nhờ poll event) → `finally` mới chạy. `ok_worker` (non-cooperative) không poll →
bị terminate cứng → KHÔNG cleanup.

**(7) Dùng ở đâu trong project:** `WorkerSpec(target=graceful_worker, uses_shutdown_event=True, ...)`.
Test `test_supervisor_graceful_worker_runs_cleanup_on_shutdown` assert `cleanup_done` có trong file.

**(8) Không có nó (chỉ ok_worker + terminate) thì sao:** trên Windows không có cleanup → mất dữ liệu/
kết nối dở. Đây là toàn bộ lý do phải có cooperative pattern.

**(9) Ví von:** nhân viên nghe loa "hết giờ" thì tự tắt máy, khoá tủ, ghi sổ bàn giao (cleanup) rồi về
— khác người bị bảo vệ lôi ra giữa chừng (terminate), bỏ dở mọi thứ.

**(10) Liên kết bức tranh lớn:** cặp đôi với `_cascade_shutdown` Step 0+1 (mẩu 05): supervisor set
event + join grace; worker poll event + cleanup. Hai bên phối hợp = graceful thật.

**(11) Cạm bẫy:** dùng `event.wait(timeout)` thay `time.sleep(timeout)` để **responsive** (sleep sẽ
chờ hết mới kiểm lại → chậm thoát). `finally` chỉ chạy khi thoát vòng — nếu worker này bị `kill()`
cứng (Step 3) thì `finally` KHÔNG chạy (nên grace phải đủ để nó tự thoát trước).

**(12) Tự kiểm:**
- Vì sao `graceful_worker` cleanup được mà `ok_worker` thì không (trên Windows)?
- Vì sao dùng `event.wait(timeout)` chứ không `time.sleep`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/worker_funcs_for_step_09.py` (graceful_worker) · Design step-09 (Phần 2) · test graceful cleanup.
Độ chắc: cao (quote thật + test pass).
