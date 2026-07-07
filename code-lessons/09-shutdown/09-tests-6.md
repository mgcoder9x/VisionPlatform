# Mẩu 09 — 6 test: bulkhead + graceful cleanup + restart/give-up

**(1) Thuộc về đâu:** `tests/test_step_09_shutdown.py`. Bằng chứng cho mẩu 01–08.

**(2) Cần biết trước:** `tmp_path` (pytest fixture — thư mục tạm); multi-process (test spawn chậm ~vài giây); assert file content.

**(3) Code thật — hai test cốt lõi (quote `tests/test_step_09_shutdown.py`):**

Bulkhead (cách ly crash):
```python
def test_supervisor_isolation_one_worker_crash_does_not_kill_others(tmp_path):
    sup = Supervisor(workers=[
        WorkerSpec(worker_id="crashing", target=_crash_worker, args=(str(log1), 0.3), max_restarts=10),
        WorkerSpec(worker_id="stable", target=_ok_worker, args=(str(log2),)),
    ], poll_interval_s=0.05, shutdown_grace_s=2.0)
    sup.run(duration_s=1.5)
    w2_lines = log2.read_text().strip().split("\n")
    assert len(w2_lines) > 5   # stable chạy liên tục dù crashing chết/restart
```

Give-up sau max (cap restart):
```python
def test_supervisor_gives_up_after_max_restarts(tmp_path):
    sup = Supervisor(workers=[
        WorkerSpec(worker_id="ef", target=_eternally_failing_worker, args=(None,), max_restarts=2),
    ], poll_interval_s=0.05, shutdown_grace_s=2.0)
    restart_counts = sup.run(duration_s=5.0)
    assert restart_counts["ef"] == 3   # cap đúng tại max+1 rồi bỏ
```

**(4) Giải thích 6 test:**
1. **spawns_and_terminates** — 2 ok worker, restart 0, file có nội dung → happy path + shutdown sạch.
2. **isolation (bulkhead)** — crashing chết/restart nhiều lần; stable vẫn heartbeat >5 dòng → **cách ly crash**.
3. **graceful cleanup** — cooperative worker → file có `cleanup_done` → Step 1 cascade chạy (E-10).
4. **restarts_crashed** — crash sau 0.2s → `restart_count >= 1` (đã restart).
5. **gives_up_after_max** — crash ngay mọi lần, max=2 → `restart_count == 3` (cap `>` rồi bỏ).
6. **non_coop_terminated** — ok_worker (non-coop) bị terminate lúc shutdown; `run()` trả về, restart 0, file có nội dung.

**(5) Là gì:** bộ 6 test phủ spawn/monitor/restart/cap/cascade/bulkhead/cooperative.

**(6) Tại sao tồn tại / vấn đề nó giải:** biến các khẳng định ("bulkhead cách ly", "cleanup chạy",
"cap đúng") thành **bằng chứng chạy thật** (§5) — đặc biệt cascade E-10 giờ verify THẬT tại #09 (test 3), không còn chỉ suy luận.

**(7) Dùng ở đâu / kết quả thật:** `pytest tests/test_step_09_shutdown.py -q` → **6 passed** (~10s,
multi-process spawn); full **290 passed, 1 skipped**; `lint-imports` **5 kept, 0 broken**.

**(8) Không có test bulkhead/graceful thì sao:** không chứng minh cách ly crash + cleanup cooperative;
bug E-10 (mất cleanup) có thể tái xuất mà không ai biết.

**(9) Ví von:** diễn tập cháy thật: đốt 1 phòng (crash) xem phòng khác có an toàn không (bulkhead), và
kiểm người có kịp mang đồ ra (cleanup) không — thay vì tin lý thuyết.

**(10) Liên kết bức tranh lớn:** test 3 (graceful) chốt E-10; test 2 (bulkhead) chốt kiến trúc process-
per-camera. Nối §5 verify-bằng-chạy-thật. Multi-process chậm (~10s) là bình thường trên Windows spawn.

**(11) Cạm bẫy:** test give-up cần `duration_s` đủ dài (5s) để 3 lần crash+detect kịp (spawn Windows
chậm). Assert `== 3` deterministic (cap tại max+1). Test dùng file làm kênh quan sát cross-process (worker ghi, test đọc).

**(12) Tự kiểm:**
- Test bulkhead chứng minh gì? Dòng `assert len(w2_lines) > 5` nghĩa là gì?
- Vì sao give-up test assert `== 3` với `max_restarts=2`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_step_09_shutdown.py` (6 test, đã chạy pass) · Design step-09 (Phần 3). Độ
chắc: cao (output pytest thật: 6 passed / full 290 passed, 1 skipped).
