# Step 09 — Supervisor + shutdown protocol cascade

## Mục tiêu (2h)

Build process supervisor với graceful shutdown:

1. `application/supervisor.py` — `Supervisor`, `WorkerSpec`. Spawn N worker processes, monitor, restart capped, signal-based shutdown.
2. `tests/worker_funcs_for_step_09.py` — worker functions ở module riêng (multiprocessing spawn requires picklable).
3. `tests/test_step_09_shutdown.py` — 6 test bao gồm bulkhead isolation test + cooperative shutdown test.

**Đã verify**: 6 test pass in ~9s (multi-process tests slower).

---

## Recap

- **Module 02 file 03 (Bulkhead)**: mỗi worker = 1 process. Crash isolation.
- **Quan trọng**: Windows `multiprocessing` default mode = **spawn** (re-import module). Worker functions phải ở **module riêng**, KHÔNG ở test file (re-import test → infinite recursion).

---

## Phần 1 — Supervisor + WorkerSpec (60 phút)

```python
# src/vision_demo/application/supervisor.py
"""Supervisor: spawn worker processes, monitor, graceful shutdown."""
from __future__ import annotations
import multiprocessing as mp
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Callable

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WorkerSpec:
    """Spec để spawn worker process."""
    worker_id: str
    target: Callable[..., None]
    args: tuple = ()
    max_restarts: int = 3
    uses_shutdown_event: bool = False
    """True nếu `target` nhận `shutdown_event: mp.Event` làm tham số ĐẦU TIÊN.

    Worker cooperative (tự poll event để thoát + cleanup) đặt True — đây là
    cách graceful shutdown đúng trên CẢ Windows lẫn POSIX (không dựa vào
    SIGTERM, vốn không tồn tại cooperative trên Windows).
    """


@dataclass
class Supervisor:
    """Supervisor process: lifecycle quản lý workers."""
    workers: list[WorkerSpec]
    poll_interval_s: float = 0.5
    shutdown_grace_s: float = 5.0
    
    _procs: dict[str, mp.Process] = field(default_factory=dict)
    _restart_counts: dict[str, int] = field(default_factory=dict)
    _shutdown_requested: bool = False
    _shutdown_event: "mp.Event" = field(default=None, init=False)  # type: ignore[assignment]
    
    def _spawn(self, spec: WorkerSpec) -> mp.Process:
        # Worker cooperative nhận shutdown_event làm arg đầu tiên để tự thoát.
        args = (self._shutdown_event, *spec.args) if spec.uses_shutdown_event else spec.args
        p = mp.Process(
            target=spec.target,
            args=args,
            name=f"worker-{spec.worker_id}",
            daemon=True,
        )
        p.start()
        return p
    
    def _request_shutdown(self, signum: int, _frame) -> None:
        logger.warning("shutdown_signal_received", signal=signum)
        self._shutdown_requested = True
    
    def run(self, duration_s: float | None = None) -> dict[str, int]:
        """Spawn workers, monitor, shutdown.
        
        Returns dict of restart_counts per worker_id.
        """
        # Event phối hợp dừng — worker cooperative poll event này để tự thoát.
        self._shutdown_event = mp.Event()

        # Register signal handlers (best effort).
        try:
            signal.signal(signal.SIGINT, self._request_shutdown)
            signal.signal(signal.SIGTERM, self._request_shutdown)
        except ValueError:
            pass   # Not main thread — signal not supported.
        
        # Spawn initial.
        for spec in self.workers:
            self._procs[spec.worker_id] = self._spawn(spec)
            self._restart_counts[spec.worker_id] = 0
        
        logger.info("supervisor_started", n_workers=len(self.workers), pid=os.getpid())
        
        start = time.monotonic()
        
        while not self._shutdown_requested:
            if duration_s is not None and (time.monotonic() - start) >= duration_s:
                break
            
            for spec in self.workers:
                p = self._procs.get(spec.worker_id)
                if p is None:
                    continue
                
                if not p.is_alive():
                    exit_code = p.exitcode
                    self._restart_counts[spec.worker_id] += 1
                    p.join()
                    
                    if self._restart_counts[spec.worker_id] > spec.max_restarts:
                        logger.error(
                            "worker_giving_up",
                            worker_id=spec.worker_id,
                            restart_count=self._restart_counts[spec.worker_id],
                        )
                        del self._procs[spec.worker_id]
                        continue
                    
                    logger.warning(
                        "worker_restarting",
                        worker_id=spec.worker_id,
                        exit_code=exit_code,
                        restart_count=self._restart_counts[spec.worker_id],
                    )
                    self._procs[spec.worker_id] = self._spawn(spec)
            
            time.sleep(self.poll_interval_s)
        
        # Cascade shutdown.
        logger.info("supervisor_shutting_down")
        self._cascade_shutdown()
        
        return dict(self._restart_counts)
    
    def _cascade_shutdown(self) -> None:
        """Cooperative-FIRST cascade (thứ tự ĐÚNG — xem ERRATA E-10):
        0. Set shutdown_event → worker cooperative tự thoát vòng lặp + cleanup.
        1. JOIN worker cooperative với grace TRƯỚC → cho `finally` cleanup chạy xong.
        2. terminate() mọi worker còn sống (non-cooperative / hang) (Windows: TerminateProcess cứng).
        3. kill() stragglers cuối cùng (force kill).
        """
        deadline = time.monotonic() + self.shutdown_grace_s

        # Step 0: tín hiệu cooperative — cách DUY NHẤT graceful trên Windows.
        # Worker `uses_shutdown_event=True` poll event này và tự thoát sạch.
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        # Step 1: cho worker COOPERATIVE cơ hội tự thoát + chạy `finally` cleanup
        # TRƯỚC khi cứng tay (xem ERRATA E-10 — bug cũ: terminate() ngay → race,
        # cleanup không chạy trên Windows → flaky). Worker non-cooperative không poll
        # event → bỏ qua bước này (khỏi chờ vô ích), sẽ bị terminate ở Step 2.
        coop_ids = {s.worker_id for s in self.workers if s.uses_shutdown_event}
        for wid, p in list(self._procs.items()):
            if wid in coop_ids:
                remaining = max(0.0, deadline - time.monotonic())
                p.join(timeout=remaining)

        # Step 2: terminate() mọi worker còn sống (non-cooperative / coop bị hang).
        for wid, p in self._procs.items():
            if p.is_alive():
                logger.debug("sending_sigterm", worker_id=wid)
                p.terminate()

        # Step 3: kill() stragglers cuối cùng (không chết sau terminate).
        for wid, p in list(self._procs.items()):
            p.join(timeout=1.0)
            if p.is_alive():
                logger.warning("sigkill_straggler", worker_id=wid)
                p.kill()
                p.join(timeout=1.0)
        
        logger.info("supervisor_shutdown_complete")
```

**Decisions cốt lõi**:

### Cascade cooperative-FIRST (thứ tự đúng — ERRATA E-10)

```
0. Set shutdown_event (tín hiệu cooperative).
1. JOIN worker cooperative với grace → để chúng tự thoát + chạy finally cleanup.
2. terminate() worker còn sống (non-cooperative / hang).
3. kill() stragglers (force kill).
```

→ Ý tưởng: worker cooperative (poll `shutdown_event`) được **cleanup sạch TRƯỚC**; chỉ
worker không hợp tác (hoặc hang) mới bị `terminate()`/`kill()` cứng. **Bug cũ** đặt
`terminate()` NGAY sau set event → trên Windows (`TerminateProcess`, không chạy `finally`)
cleanup bị race → test flaky. Sửa: join(grace) cooperative trước, terminate sau.

> **Giới hạn nền tảng (quan trọng):** "graceful" chỉ đúng khi worker **chủ động** bắt tín hiệu dừng.
> - **POSIX (Linux/Mac):** `p.terminate()` gửi `SIGTERM` → nếu worker bind `signal.signal(SIGTERM, handler)` thì cleanup chạy. Worker KHÔNG bind handler → bị kết thúc ngay, không cleanup.
> - **Windows:** `multiprocessing.Process.terminate()` gọi `TerminateProcess` — **không** có `SIGTERM` cooperative; tiến trình bị kết thúc cứng, `finally`/handler **không** chạy. Muốn graceful trên Windows phải dùng kênh phối hợp riêng (shutdown `Event`/control pipe) để worker tự thoát vòng lặp, KHÔNG dựa vào `terminate()`.
>
> Vì vậy bản demo này cung cấp 2 worker mẫu: `ok_worker` (không cleanup — bị force-kill) và `graceful_worker` (poll một `mp.Event` để tự thoát + cleanup — cooperative, chạy đúng trên cả Windows lẫn POSIX). Xem Phần 2.

### `daemon=True`

```python
p = mp.Process(target=..., daemon=True)
```

→ Daemon worker tự kill khi parent supervisor exit. Safety net nếu supervisor crash without cascade — workers vẫn chết.

→ Production có thể KHÔNG dùng daemon nếu cần worker survive supervisor restart (rare).

### Signal handler in __init__ vs run

```python
# Hiện tại: trong run().
def run(self, duration_s):
    signal.signal(signal.SIGINT, self._request_shutdown)
    ...
```

→ **Tại sao trong `run()` không `__init__`**: signal handler chỉ work nếu được set từ **main thread**. `__init__` có thể được gọi từ thread khác. `run()` là entry point → main thread.

### `try/except ValueError` cho signal

```python
try:
    signal.signal(signal.SIGINT, self._request_shutdown)
except ValueError:
    pass
```

→ Test runner (pytest) chạy trong worker thread → `signal.signal` raise. Skip an toàn.

### Restart cap

```python
if self._restart_counts[spec.worker_id] > spec.max_restarts:
    # Give up.
    del self._procs[spec.worker_id]
```

→ Worker eternally crashing (camera config sai, model file corrupt) → supervisor tránh **restart loop vô tận** (CPU 100% spawn/exit).

→ Production có **exponential backoff**: `sleep(2^n)` giữa restarts. vision_demo simplified.

### Restart count "giving up" test

5 attempts, max=2:
- Attempt 1 fails → restart_count=1 → restart.
- Attempt 2 fails → restart_count=2 → restart.
- Attempt 3 fails → restart_count=3 (>2) → giving up. Supervisor không restart nữa.

→ `>` not `>=` — give up **after** exceeding max.

---

## Phần 2 — Worker functions in separate module (15 phút)

**Quan trọng cho Windows**: `multiprocessing` default = **spawn** mode. Spawn mode re-imports the module containing target function. Nếu target ở **test file** → re-import test file → invoke pytest fixtures → infinite recursion.

→ Tách worker functions ra **module riêng**:

```python
# tests/worker_funcs_for_step_09.py
"""Worker functions for Step 09 shutdown tests.

Separate module so multiprocessing spawn (Windows default) can pickle them
without re-importing the test module.
"""
import sys
import time


def ok_worker(work_path):
    """Heartbeat worker — writes alive marker, runs forever."""
    while True:
        with open(work_path, "a") as f:
            f.write(f"alive_{time.time():.3f}\n")
        time.sleep(0.05)


def crash_worker(work_path, crash_after_s):
    """Crashes after N seconds."""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > crash_after_s:
            sys.exit(1)
        with open(work_path, "a") as f:
            f.write(f"alive_{elapsed:.3f}\n")
        time.sleep(0.05)


def short_lived_worker(work_path, run_for_s):
    """Runs for N seconds then exits cleanly."""
    start = time.time()
    while time.time() - start < run_for_s:
        with open(work_path, "a") as f:
            f.write("ok\n")
        time.sleep(0.05)


def eternally_failing_worker(_):
    """Crashes immediately, every time."""
    sys.exit(1)


def graceful_worker(shutdown_event, work_path):
    """Cooperative worker: poll shutdown_event để tự thoát + cleanup.

    Đây là pattern graceful đúng trên CẢ Windows lẫn POSIX — KHÔNG dựa vào
    SIGTERM (Windows không có cooperative SIGTERM). `shutdown_event` là
    `mp.Event` do Supervisor truyền vào (arg đầu tiên khi
    `WorkerSpec.uses_shutdown_event=True`).
    """
    try:
        while not shutdown_event.is_set():
            with open(work_path, "a") as f:
                f.write(f"alive_{time.time():.3f}\n")
            # Sleep ngắn + responsive: thoát trong <=0.05s sau khi event set.
            shutdown_event.wait(timeout=0.05)
    finally:
        # Cleanup chạy được vì worker tự thoát vòng lặp (không bị kill cứng).
        with open(work_path, "a") as f:
            f.write("cleanup_done\n")
```

→ Test file imports từ đây. Spawn mode pickle function reference (qua module path) → re-import `worker_funcs_for_step_09` (small, no fixtures) → OK.

---

## Phần 3 — Tests (45 phút)

```python
# tests/test_step_09_shutdown.py
"""Step 09: supervisor + shutdown protocol cascade."""
import pytest
from vision_demo.application.supervisor import Supervisor, WorkerSpec
from tests.worker_funcs_for_step_09 import (
    ok_worker as _ok_worker,
    crash_worker as _crash_worker,
    eternally_failing_worker as _eternally_failing_worker,
    graceful_worker as _graceful_worker,
)


def test_supervisor_spawns_and_terminates_workers(tmp_path):
    """Spawn 2 workers, run 0.7s, shutdown clean."""
    log1 = tmp_path / "w1.log"
    log2 = tmp_path / "w2.log"
    
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="w1", target=_ok_worker, args=(str(log1),)),
            WorkerSpec(worker_id="w2", target=_ok_worker, args=(str(log2),)),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    
    restart_counts = sup.run(duration_s=0.7)
    
    assert restart_counts["w1"] == 0
    assert restart_counts["w2"] == 0
    
    assert log1.exists() and log1.stat().st_size > 0
    assert log2.exists() and log2.stat().st_size > 0


def test_supervisor_isolation_one_worker_crash_does_not_kill_others(tmp_path):
    """Bulkhead: w1 crash doesn't stop w2."""
    log1 = tmp_path / "w1.log"
    log2 = tmp_path / "w2.log"
    
    sup = Supervisor(
        workers=[
            WorkerSpec(
                worker_id="crashing",
                target=_crash_worker,
                args=(str(log1), 0.3),
                max_restarts=10,
            ),
            WorkerSpec(
                worker_id="stable",
                target=_ok_worker,
                args=(str(log2),),
            ),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    
    sup.run(duration_s=1.5)
    
    # w2 stable produced output continuously.
    assert log2.exists()
    w2_lines = log2.read_text().strip().split("\n")
    assert len(w2_lines) > 5
```

→ **`test_supervisor_isolation_one_worker_crash_does_not_kill_others`** = **bulkhead test**. Verify rằng:
- Worker `crashing` chết → restart → chết → restart...
- Worker `stable` không bị ảnh hưởng → tiếp tục heartbeat.

→ Đây là bulkhead in action.

### Cooperative shutdown test (graceful đúng nghĩa)

```python
def test_supervisor_graceful_worker_runs_cleanup_on_shutdown(tmp_path):
    """Worker cooperative (poll shutdown_event) phải chạy cleanup khi dừng.

    Đây là pattern graceful đúng trên CẢ Windows lẫn POSIX — supervisor set
    shutdown_event, worker tự thoát vòng lặp và chạy `finally` cleanup. Khác
    `ok_worker` (bị force-kill, không cleanup).
    """
    log = tmp_path / "graceful.log"

    sup = Supervisor(
        workers=[
            WorkerSpec(
                worker_id="graceful",
                target=_graceful_worker,
                uses_shutdown_event=True,   # nhận shutdown_event làm arg đầu
                args=(str(log),),
            ),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )

    sup.run(duration_s=0.5)   # chạy 0.5s rồi cascade shutdown

    content = log.read_text()
    assert "alive_" in content              # đã chạy
    assert "cleanup_done" in content        # ĐÃ cleanup (không bị kill cứng)
```

→ Test này chứng minh worker cooperative **thực sự cleanup**, thay vì chỉ tin vào `terminate()` (không graceful trên Windows).

**Run**:
```bash
pytest tests/test_step_09_shutdown.py -v
```

Expected: **6 passed in ~9s** (multi-process spawn slow trên Windows).

---

## Self-check

1. **Daemon process** — pros/cons?

2. **3-step shutdown cascade** — sao không SIGKILL ngay (faster)?

3. **Worker module separate** — bug gì xảy ra trên Windows nếu để trong test file?

4. **Restart cap > max** vs `>= max` — khác biệt?

5. **Supervisor health check**: hiện tại check `is_alive()`. Bug gì nếu worker đang **hang** (process alive nhưng stuck)?

<details>
<summary>Đáp án</summary>

1. **Daemon**:
   - **Pros**:
     - Auto-cleanup nếu supervisor crash without cascade.
     - Không leave zombie process.
     - Config đơn giản.
   - **Cons**:
     - Worker không thể spawn child processes (Python restriction).
     - Nếu chỉ dựa vào `terminate()`/kernel kill thì cleanup không graceful — nên kết hợp cooperative `shutdown_event` để worker tự cleanup trước khi bị kill.
     - Nếu worker cần survive supervisor restart → daemon=False, manage lifecycle khác.

2. **Why graceful first**:
   - Worker có **state cần cleanup**: DB connection, file write buffer, network connection.
   - SIGKILL = no chance to cleanup → corrupt state.
   - **Graceful đúng = cooperative**: supervisor set `shutdown_event`, worker tự poll → thoát vòng lặp → chạy `finally` cleanup. Đây là cách hoạt động trên CẢ Windows lẫn POSIX.
   - **SIGTERM chỉ graceful trên POSIX VÀ khi worker bind handler**: `p.terminate()` gửi SIGTERM → handler flush/close. Trên **Windows** `terminate()` = `TerminateProcess` (kill cứng, KHÔNG chạy handler/`finally`) → muốn graceful BẮT BUỘC dùng cooperative event, không dựa vào terminate.
   - 5s grace = đủ cho most cleanup.
   - SIGKILL (`p.kill()`) chỉ khi worker **hang** sau grace (không response cả cooperative event lẫn SIGTERM) → không còn lựa chọn.

3. **Bug Windows separate module**:
   - Spawn mode pickle target function → unpickle in child requires module import.
   - If target in `test_step_09_shutdown.py` → child imports test file → pytest collection logic runs → infinite recursion / undefined behavior.
   - Linux fork mode: copy-on-write fork → no re-import → OK. **But fork removed in Python 3.14+ on macOS** (security).
   - **Best practice**: target functions ở module riêng, no top-level side effects.

4. **`>` vs `>=`**:
   - `> max_restarts`: give up **after** exceeding. With max=3:
     - Attempt 1 → restart_count=1 → 1 > 3? No → restart.
     - Attempt 2 → restart_count=2 → 2 > 3? No → restart.
     - Attempt 3 → restart_count=3 → 3 > 3? No → restart.
     - Attempt 4 → restart_count=4 → 4 > 3? Yes → give up.
     - **Total 4 restarts** (1 original spawn + 3 restarts).
   - `>= max_restarts`: give up **at** count.
     - max=3 → give up at restart_count=3 → only 2 restarts allowed.
   - vision_demo dùng `>` → user-friendly: "max 3 restarts" = restart 3 lần.
   - Either OK if documented. Don't mix.

5. **Hang detection bug**:
   - `is_alive()` chỉ check OS process state. Process can be `S` (sleeping) or `D` (uninterruptible sleep) — both "alive".
   - Worker stuck in deadlock: alive=True, but doing nothing.
   - **Fix**: heartbeat. Worker writes timestamp to file every N sec. Supervisor checks file mtime. If mtime > threshold → kill (process hang).
   - Vision Platform production có **liveness probe** qua ZMQ heartbeat reply.
   - vision_demo simplified — chỉ detect crash (exit code).

</details>

---

## Liên kết

- **Module 02 file 03** — bulkhead theory.
- **Production**: `Vision_platform_architecture_design/06-resilience-and-shutdown/08-shutdown-protocol.md`.

---

➡️ Tiếp theo: [`step-10-package-and-ship.md`](step-10-package-and-ship.md)
