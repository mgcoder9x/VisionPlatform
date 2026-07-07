# Bài #09 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung: worker chết/tắt-sạch/Windows-no-SIGTERM → cooperative cascade).
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + code verify. Cột Feynman = riêng (user học sau).
> Bám code thật: `application/supervisor.py` + `tests/worker_funcs_for_step_09.py` +
> `tests/test_step_09_shutdown.py` — **6 passed**, full **290/1 skipped** · lint **5 kept/0 broken**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-supervisor-bulkhead.md` | Bức tranh: mỗi camera 1 process (bulkhead); supervisor spawn/monitor/restart/shutdown | `application/supervisor.py` (docstring) | ✅ |
| 02 | `02-workerspec.md` | `WorkerSpec`: target/args/max_restarts/uses_shutdown_event | `application/supervisor.py` (WorkerSpec) | ✅ |
| 03 | `03-run-spawn-monitor.md` | `run()`: spawn ban đầu + vòng monitor is_alive + signal handler best-effort | `application/supervisor.py` (run) | ✅ |
| 04 | `04-restart-cap.md` | Restart cap `>` (không `>=`): give up sau khi vượt max | `application/supervisor.py` (run — restart block) | ✅ |
| 05 | `05-cascade-cooperative-first.md` | `_cascade_shutdown` 4 bước (set event→join coop→terminate→kill) — ERRATA E-10 | `application/supervisor.py` (_cascade_shutdown) | ✅ |
| 06 | `06-graceful-worker.md` | `graceful_worker`: poll shutdown_event + finally cleanup; giới hạn Windows terminate | `tests/worker_funcs_for_step_09.py` (graceful_worker) | ✅ |
| 07 | `07-windows-spawn-worker-module.md` | Worker ở module riêng (spawn re-import); vì sao không để trong test file | `tests/worker_funcs_for_step_09.py` | ✅ |
| 08 | `08-gioi-han-hang-backoff.md` | **K-020** is_alive chỉ bắt crash không bắt hang; **K-021** thiếu backoff | `application/supervisor.py` (is_alive) | ✅ |
| 09 | `09-tests-6.md` | 6 test: spawns+terminate · bulkhead · graceful cleanup · restart · give-up · non-coop | `tests/test_step_09_shutdown.py` | ✅ |

> ✅ **ĐỦ 9/9 MẨU** — quote nguyên văn code + neo test đã pass (6 passed, full 290/1). Template 14 mục.
> **Cổng Feynman:** user tự giải thích lại (học sau). AI KHÔNG tự chấm. Không dán lesson vào chat.
