# Mẩu 03 — `run()`: spawn ban đầu + vòng monitor + signal handler

**(1) Thuộc về đâu:** `application/supervisor.py`, `Supervisor.run` (+ `_spawn`, `_request_shutdown`).

**(2) Cần biết trước:** mẩu 02 (WorkerSpec); `mp.Process` (tiến trình con); `p.is_alive()`; `signal`
(tín hiệu OS như Ctrl+C=SIGINT); `time.monotonic()` (đồng hồ đo khoảng).

**(3) Code thật (quote rút gọn `application/supervisor.py`):**
```python
def _spawn(self, spec: WorkerSpec) -> mp.Process:
    args = (self._shutdown_event, *spec.args) if spec.uses_shutdown_event else spec.args
    p = mp.Process(target=spec.target, args=args, name=f"worker-{spec.worker_id}", daemon=True)
    p.start()
    return p

def run(self, duration_s: float | None = None) -> dict[str, int]:
    self._shutdown_event = mp.Event()
    try:
        signal.signal(signal.SIGINT, self._request_shutdown)
        signal.signal(signal.SIGTERM, self._request_shutdown)
    except ValueError:
        pass   # Không phải main thread (pytest) → bỏ qua.
    for spec in self.workers:
        self._procs[spec.worker_id] = self._spawn(spec)
        self._restart_counts[spec.worker_id] = 0
    ...
    while not self._shutdown_requested:
        if duration_s is not None and (time.monotonic() - start) >= duration_s:
            break
        for spec in self.workers:
            p = self._procs.get(spec.worker_id)
            if p is None:
                continue
            if not p.is_alive():
                ...   # restart logic (mẩu 04)
        time.sleep(self.poll_interval_s)
    self._cascade_shutdown()   # (mẩu 05)
    return dict(self._restart_counts)
```

**(4) Giải thích từng ý nhỏ:**
- `self._shutdown_event = mp.Event()` → cờ liên-tiến-trình để báo worker cooperative tự thoát (mẩu 05/06).
- `_spawn`: nếu `uses_shutdown_event` → chèn `shutdown_event` làm arg đầu; `daemon=True` (worker chết theo cha); `p.start()`.
- `signal.signal(...)` trong `try/except ValueError` → đăng ký bắt Ctrl+C/SIGTERM; ở thread không phải
  main (pytest) sẽ raise ValueError → bỏ qua an toàn.
- vòng `while not self._shutdown_requested`: mỗi vòng kiểm từng worker `is_alive()`; chết → restart
  (mẩu 04); `time.sleep(poll_interval_s)` giữa các vòng.
- `duration_s` → chạy có thời hạn (dùng test/demo); hết hạn → break → cascade shutdown.

**(5) Là gì:** vòng đời chính: dựng event, đăng ký signal, spawn worker, giám sát định kỳ, rồi cascade shutdown.

**(6) Tại sao signal handler trong `run()` không `__init__`:** signal chỉ set được từ **main thread**;
`run()` là entry point (main thread), còn `__init__` có thể bị gọi từ thread khác. (Design decision.)

**(7) Dùng ở đâu trong project:** `sup.run(duration_s=0.7)` trong mọi test #09; trả `restart_counts` để assert.

**(8) Không có vòng monitor thì sao:** worker crash không được phát hiện/restart → mất camera thầm lặng.

**(9) Ví von:** quản đốc đi tuần mỗi 0.05s: máy nào tắt thì bật lại; nghe còi báo hết ca (signal/duration) thì tắt xưởng theo quy trình.

**(10) Liên kết bức tranh lớn:** `is_alive()` là cách giám sát (giới hạn: chỉ bắt crash, không bắt
hang — mẩu 08). `_shutdown_event` nối cascade cooperative-first (mẩu 05).

**(11) Cạm bẫy:** `try/except ValueError` quanh signal là CỐ Ý (pytest chạy trong thread phụ). `daemon=True`
→ worker không spawn con được. Đừng đăng ký signal trong `__init__`.

**(12) Tự kiểm:**
- Vì sao signal handler đặt trong `run()` chứ không `__init__`?
- Vòng monitor phát hiện worker chết bằng cách nào? Bỏ sót loại "chết" nào? (nối mẩu 08)

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (run/_spawn/_request_shutdown) · Design step-09 (Phần 1 +
Decisions signal). Độ chắc: cao (quote thật + test pass).
