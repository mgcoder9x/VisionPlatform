# Mẩu 05 — Failure thống nhất: crash + hang đi CÙNG một đường

**(1) Thuộc về đâu:** `application/supervisor.py`, `run` loop (phần phát hiện + xử lý failure).

**(2) Cần biết trước:** crash-detection #09 (is_alive False → restart, cap `>`); `_is_hung` (mẩu 04); `_terminate_proc`.

**(3) Code thật (quote `application/supervisor.py`):**
```python
reason: Optional[str] = None
exit_code = None
if not p.is_alive():
    reason = "crash"
    exit_code = p.exitcode
    p.join()
elif spec.uses_heartbeat and self._is_hung(spec):
    reason = "hang"
    logger.warning("worker_heartbeat_timeout", worker_id=wid, timeout_s=spec.heartbeat_timeout_s)
    self._terminate_proc(p)

if reason is None:
    continue

# Xử lý failure THỐNG NHẤT (crash + hang): count + cap + backoff.
self._restart_counts[wid] += 1
if self._restart_counts[wid] > spec.max_restarts:
    logger.error("worker_giving_up", worker_id=wid, reason=reason, restart_count=...)
    self._procs.pop(wid, None); self._pending_respawn[wid] = False
    continue
logger.warning("worker_restarting", worker_id=wid, reason=reason, exit_code=exit_code, restart_count=...)
```

**(4) Giải thích từng ý nhỏ:**
- Phát hiện 2 loại failure: `crash` (is_alive False) HOẶC `hang` (alive + `_is_hung`). Hang thì `terminate` trước (vì process còn sống).
- `if reason is None: continue` → worker khoẻ → bỏ qua.
- **CÙNG đường xử lý:** cả crash lẫn hang đều `restart_counts += 1` → kiểm `> max_restarts` (give up) → nếu chưa thì restart. Logic 1 chỗ, không nhân đôi.
- Log phân biệt `reason` (crash/hang) + `worker_heartbeat_timeout` riêng cho hang (observability, mẩu này + R5).

**(5) Là gì:** phần run-loop hợp nhất xử lý mọi kiểu "worker hỏng" (chết hoặc treo) qua cùng cơ chế count/cap/restart.

**(6) Tại sao thống nhất (bản chất):** crash và hang khác nhau ở CÁCH PHÁT HIỆN, nhưng GIỐNG nhau ở CÁCH XỬ
LÝ (restart có giới hạn). Gộp 1 đường → logic nhất quán, cap áp dụng cho cả hai (worker treo lặp lại cũng
bị give-up như crash lặp lại). Tránh 2 nhánh code song song dễ lệch.

**(7) Dùng ở đâu / bằng chứng:** `test_hang_give_up_after_max_restarts` — hang lặp lại, max_restarts=1 → count
cap tại 2 (>1) rồi give up (giống crash give-up #09). Chứng minh cap thống nhất.

**(8) Không thống nhất (2 nhánh riêng) thì sao:** dễ lệch — vd hang không đếm vào cap → treo lặp vô hạn; hoặc log/observability không nhất quán.

**(9) Ví von:** dù nhân viên nghỉ vì ốm (crash) hay ngồi lì không làm (hang) — quản lý dùng CÙNG quy trình
"nhắc + thay ca, quá 3 lần thì cho nghỉ hẳn". Không đẻ 2 bộ quy trình riêng.

**(10) Liên kết bức tranh lớn:** giữ nguyên cap `>` của #09 (mẩu 04 bài #09) + thêm nhánh hang. `_terminate_proc`
tái dùng cascade-style (terminate→kill). ADDITIVE: khi heartbeat tắt, nhánh hang không bao giờ vào → hành vi #09.

**(11) Cạm bẫy:** hang phải `terminate` TRƯỚC khi coi failure (vì process còn sống — khác crash đã tự chết).
`self._procs.pop(wid, None)` khi give-up (không để lại proc chết). reason log để chẩn đoán (crash vs hang khác nguyên nhân gốc).

**(12) Tự kiểm:**
- Crash và hang giống/khác nhau ở phát-hiện vs xử-lý?
- Vì sao hang phải `terminate` trước khi restart, còn crash thì không?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (run) · test give-up · design R4. Độ chắc: cao (quote thật + test pass).
