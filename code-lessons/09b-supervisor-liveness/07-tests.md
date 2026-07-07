# Mẩu 07 — 4 test + regression #09

**(1) Thuộc về đâu:** `tests/test_supervisor_liveness.py` + `tests/liveness_workers.py`. Bằng chứng mẩu 01–06.

**(2) Cần biết trước:** spawn worker module (#09 mẩu 07); `mp.Value`; test logic in-process vs cross-process; guard win32.

**(3) Code thật — worker treo + test hang (quote):**
`tests/liveness_workers.py`:
```python
def heartbeat_then_hang_worker(heartbeat, beats=2):
    for _ in range(beats):
        heartbeat.value = time.time()
        time.sleep(0.05)
    time.sleep(3600)   # hang: sống nhưng không beat nữa
```
`tests/test_supervisor_liveness.py`:
```python
def test_hang_detected_and_restarted():
    sup = Supervisor(workers=[WorkerSpec(worker_id="hang", target=heartbeat_then_hang_worker,
        args=(2,), uses_heartbeat=True, heartbeat_timeout_s=0.4, max_restarts=10)], poll_interval_s=0.05)
    counts = sup.run(duration_s=2.5)
    assert counts["hang"] >= 1   # đã phát hiện hang + restart
```

**(4) Giải thích 4 test:**
- **backoff-logic** (in-process, deterministic): `_backoff_for` ra 0.1/0.2/0.4/cap + base=0→0. Không spawn → không flaky.
- **beat-đều-không-restart** (Property 2): `heartbeat_ok_worker` beat mỗi 0.05s, timeout 0.5s → `counts["ok"]==0` (không false-positive).
- **hang→restart** (Property 1, đóng K-020): worker beat 2 lần rồi `sleep(3600)` (vẫn alive) → supervisor phát hiện hang qua heartbeat → restart. `counts["hang"] >= 1`. **is_alive KHÔNG bắt được (process còn sống) — chỉ heartbeat bắt.**
- **give-up** (Property 5): hang lặp + max_restarts=1 → count cap tại 2 (>1) rồi bỏ → `counts["hg"]==2`.

**(5) Là gì:** bộ 4 test biến khẳng định heartbeat/backoff thành bằng chứng chạy thật (§5) + backoff logic deterministic.

**(6) Tại sao test hang QUAN TRỌNG NHẤT:** chứng minh điểm cốt lõi — worker `sleep(3600)` là ALIVE (is_alive
=True) suốt, nên #09 (chỉ crash-detection) sẽ KHÔNG bao giờ restart nó. Test xanh = heartbeat thực sự bắt
được hang mà is_alive bỏ sót → đóng K-020 bằng bằng chứng, không phải lời hứa.

**(7) Kết quả thật:** `pytest tests/test_supervisor_liveness.py` = **4 passed** (9.76s); `test_step_09_shutdown.py`
= **6 passed** (regression additive OK); full **304 passed/1 skipped**; lint **5 kept/0 broken**. Guard win32.

**(8) Không có test hang thì sao:** không chứng minh K-020 đóng — chỉ "đọc code thấy đúng" = CHƯA verify (§5).

**(9) Ví von:** diễn tập THẬT: cho 1 "nhân viên" ngồi lì không làm (nhưng vẫn ngồi đó) xem hệ giám sát có
phát hiện + thay ca không — thay vì tin lý thuyết "chắc phát hiện được".

**(10) Liên kết bức tranh lớn:** test cross-process tái dùng pattern spawn #09/#05b. backoff test in-process
(deterministic) — chọn đúng công cụ cho từng thứ (timing cross-process dễ flaky → test logic thuần). Regression
#09 (6 pass) chứng minh Property 3 (additive).

**(11) Cạm bẫy:** test timing (hang/give-up) cần `duration_s` đủ + `heartbeat_timeout_s` nhỏ (0.4-0.5) cho
nhanh; assert `>= 1` (hang) / `== 2` (give-up cap) chọn ngưỡng an toàn. backoff test in-process tránh flaky.
Guard win32 (spawn; POSIX chưa verify).

**(12) Tự kiểm:**
- Test hang chứng minh gì mà #09 không? Vì sao `sleep(3600)` là ca test hang đúng?
- Vì sao backoff test in-process (không spawn)?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_supervisor_liveness.py` + `tests/liveness_workers.py` (4 test pass) · design Testing Strategy. Độ chắc: cao (output pytest thật: 4 passed + #09 6 passed / full 304 passed, 1 skipped).
