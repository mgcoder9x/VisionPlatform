# Bài #09b — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (crash→hang, K-020/K-021). Rồi mẩu dưới.
> Trạng thái: ✅ đã viết + code verify. Cột Feynman = riêng (user học sau).
> Bám code thật: `application/supervisor.py` + `tests/liveness_workers.py` + `tests/test_supervisor_liveness.py`
> — **4 test pass** · #09 giữ **6 pass** · full **304 passed/1 skipped** · lint **5 kept/0 broken**.

| Mẩu | File | Nội dung (mẩu nhỏ nhất) | Code thật | TT |
|-----|------|-------------------------|-----------|----|
| 01 | `01-vi-sao-heartbeat.md` | is_alive chỉ bắt crash, KHÔNG bắt hang → "chết thầm" (K-020); vì sao heartbeat | `supervisor.py` (docstring) | ✅ |
| 02 | `02-workerspec-additive.md` | 4 field additive default TẮT → giữ 6 test #09 (K-020/K-021 opt-in) | `supervisor.py` (WorkerSpec) | ✅ |
| 03 | `03-mp-value-heartbeat.md` | `mp.Value('d')` wall-clock + prepend `_spawn`; vì sao wall-clock không monotonic | `supervisor.py` (_spawn) | ✅ |
| 04 | `04-is-hung-startup-grace.md` | `_is_hung` + startup grace (hb=0 → spawn_walltime) → không false-positive | `supervisor.py` (_is_hung) | ✅ |
| 05 | `05-failure-thong-nhat.md` | crash + hang → CÙNG đường xử lý (count/cap `>`); refactor run-loop additive | `supervisor.py` (run) | ✅ |
| 06 | `06-backoff-non-blocking.md` | `_backoff_for` (base·2^(n-1) cap) + `_next_spawn_ok` deadline (không sleep chặn) | `supervisor.py` (_backoff_for/run) | ✅ |
| 07 | `07-tests.md` | 4 test: hang→restart · beat-đều-không-restart · backoff-logic · give-up; #09 6 pass | `tests/test_supervisor_liveness.py` | ✅ |

> ✅ **ĐỦ 7/7 MẨU** — quote code thật + neo test đã pass (4 liveness + #09 6, full 304/1). Template 14 mục.
> **Cổng Feynman:** user tự giải thích lại (học sau). AI KHÔNG tự chấm. Không dán lesson vào chat.
