# Mẩu 04 — Restart cap `>` (không `>=`): give up sau khi vượt max

**(1) Thuộc về đâu:** `application/supervisor.py`, khối restart trong `run()`.

**(2) Cần biết trước:** mẩu 03 (vòng monitor); restart loop vô tận (CPU 100%); `>` vs `>=`.

**(3) Code thật (quote khối restart `run()`):**
```python
if not p.is_alive():
    exit_code = p.exitcode
    self._restart_counts[spec.worker_id] += 1
    p.join()

    if self._restart_counts[spec.worker_id] > spec.max_restarts:
        logger.error("worker_giving_up", worker_id=spec.worker_id,
                     restart_count=self._restart_counts[spec.worker_id])
        del self._procs[spec.worker_id]
        continue

    logger.warning("worker_restarting", worker_id=spec.worker_id,
                   exit_code=exit_code, restart_count=self._restart_counts[spec.worker_id])
    self._procs[spec.worker_id] = self._spawn(spec)
```

**(4) Giải thích từng ý nhỏ:**
- `self._restart_counts[...] += 1` → tăng đếm mỗi lần worker chết.
- `p.join()` → thu dọn process đã chết (tránh zombie).
- `if restart_count > max_restarts:` → **vượt** ngưỡng → `del self._procs[...]` (bỏ, không spawn nữa) + `continue`.
- ngược lại → `_spawn` lại (restart).

**(5) Là gì:** cơ chế giới hạn số lần khởi động lại một worker, tránh restart vô tận.

**(6) Tại sao `>` không `>=` (semantics):** với `max_restarts=3`:
- chết lần 1 → count=1, 1>3? không → restart
- chết lần 2 → count=2 → restart
- chết lần 3 → count=3, 3>3? không → restart
- chết lần 4 → count=4, 4>3? CÓ → bỏ.
→ "max 3 restarts" = restart **đúng 3 lần** (thân thiện: số nói đúng số lần restart). `>=` sẽ chỉ cho 2 lần.

**(7) Dùng ở đâu trong project:** test `test_supervisor_gives_up_after_max_restarts` (eternally_failing,
max=2 → restart_count cap tại **3** rồi bỏ). Test restart (`_restarts_crashed_worker`) assert count>=1.

**(8) Không có cap thì sao:** worker hỏng cấu hình (model corrupt, RTSP sai) crash ngay mỗi lần →
spawn/exit dồn dập → **CPU 100%, log ngập** → hệ tê liệt. Cap chặn điều đó.

**(9) Ví von:** thử khởi động xe chết máy: thử vài lần, không nổ thì DỪNG gọi thợ — chứ không đề máy vô tận cháy đề.

**(10) Liên kết bức tranh lớn:** đây là resilience "tự phục hồi CÓ giới hạn". Production còn thêm
**exponential backoff** (chờ 2^n giữa lần restart — K-021, chưa làm).

**(11) Cạm bẫy:** đừng dùng `>=` nếu tài liệu nói "max N restarts" (lệch 1). `p.join()` sau khi chết
là bắt buộc (thu zombie). Sau give-up, worker bị xoá khỏi `_procs` → vòng sau `p is None` → bỏ qua.

**(12) Tự kiểm:**
- `max_restarts=2` thì worker crash liên tục sẽ restart mấy lần rồi bỏ? restart_count cuối = ?
- Vì sao dùng `>` mà không `>=`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (run — restart block) · test `test_supervisor_gives_up_after_max_restarts`
(assert ==3) · Design step-09 (Restart cap + Self-check #4). Độ chắc: cao (quote thật + test pass).
