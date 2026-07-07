## R5-CRITICAL-01 — SHM Mutex Poisoning

**Severity**: CRITICAL. Discovered in Round 5 expert review.

> **Platform note**: Reproducer dưới dùng `signal.SIGKILL` — **chỉ chạy trên Linux/macOS**. Windows không có `SIGKILL`; thay bằng `os.kill(pid, signal.SIGTERM)` hoặc `psutil.Process(pid).kill()` để kill process bất ngờ tương tự. Pattern bug mutex poisoning vẫn xảy ra trên Windows (futex/SRWLock đều có thể bị orphan), nhưng repro code cần adapt.

---

## Setup (3 phút) — Minimal reproducer

```python
# Linux/macOS reproducer. On Windows, replace SIGKILL → see bottom of section.
import multiprocessing as mp
import os
import signal
import sys
import time


def worker_holding_lock(lock):
    """Worker acquires lock, then gets SIGKILL'd mid-critical-section."""
    print(f"[Worker {os.getpid()}] acquiring lock", flush=True)
    lock.acquire()
    print(f"[Worker {os.getpid()}] locked, simulating crash", flush=True)
    # Simulate OOM / SIGKILL — process killed without releasing lock.
    os.kill(os.getpid(), signal.SIGKILL)


def main():
    lock = mp.Lock()
    
    # Spawn worker that will die holding lock.
    p = mp.Process(target=worker_holding_lock, args=(lock,))
    p.start()
    p.join()
    
    print(f"[Parent] worker died with exitcode={p.exitcode}")
    print(f"[Parent] trying to acquire lock with timeout=2s...")
    
    acquired = lock.acquire(timeout=2.0)
    print(f"[Parent] acquired={acquired}")  # ← False! Lock poisoned.


if __name__ == "__main__":
    main()
```

**Output**:
```
[Worker 23445] acquiring lock
[Worker 23445] locked, simulating crash
[Parent] worker died with exitcode=-9
[Parent] trying to acquire lock with timeout=2s...
[Parent] acquired=False
```

→ Lock **never released**. Reader after this point would block forever without timeout.

### Windows variant

Trên Windows (`signal.SIGKILL` không tồn tại), thay `os.kill(os.getpid(), signal.SIGKILL)` bằng:

```python
def worker_holding_lock_windows(lock):
    """Same idea, Windows-compatible."""
    print(f"[Worker {os.getpid()}] acquiring lock", flush=True)
    lock.acquire()
    print(f"[Worker {os.getpid()}] locked, simulating crash", flush=True)
    # Windows: TerminateProcess via psutil — same effect as SIGKILL.
    import psutil
    psutil.Process(os.getpid()).kill()
    # Hoặc: os._exit(-9) — bypass cleanup nhưng KHÔNG hold lock cùng cách.
    # `psutil.Process.kill()` mới reliably reproduce mutex poisoning trên Windows.
```

Pattern bug **vẫn đúng** trên Windows: `multiprocessing.Lock` dùng SRWLock (Windows) / futex (Linux) — cả hai đều có thể bị orphan khi process holder bị terminate đột ngột. Quarantine fix (3-layer) áp dụng giống nhau trên cả hai platform.

---

## Bug story

**Production scenario**: Vision Platform 16 cameras × 30 FPS × 24/7 running.

- **Day 1-3**: Everything works. Detection latency p99 = 28ms.
- **Day 4 morning**: Operator reports "1 camera shows last frame from 5 minutes ago, others working fine".
- **Day 4 afternoon**: 2 more cameras stuck. Pipeline progressively dies.
- **Day 5 morning**: All 16 cameras stuck. Detection rate 0.
- Restart fix it. **For 4 days**, then bug reappears.

### Investigation

- `py-spy dump --pid <camera_pid>` → camera process stuck in `multiprocessing.Lock.acquire()`.
- `ps aux | grep python` → 1 inference service process zombie (exit code -9 = SIGKILL).
- **Hypothesis**: inference process OOM-killed by Linux OOM-killer mid-SHM-write → futex lock leaked.

### Confirming

Read SHM segment header from gdb:
- Slot 5: state=WRITING, owner_pid=<dead pid>, lease_deadline_ns=<expired>.
- All cameras trying to read slot 5 → block on lock forever.

→ **Root cause**: `multiprocessing.Lock` in Python = futex (POSIX) without `PTHREAD_MUTEX_ROBUST`. Process holding lock dies → futex stays locked.

### Reviewer simulation

R5 reviewer ran chaos test: `kill -9` random camera process every 1 hour for 24 hours. Reproduced bug 8/24 times.

---

## Why it happened (root cause)

### Mental model sai

Code reviewer tưởng:
```
"multiprocessing.Lock = OS resource. Process dies → OS cleans up."
```

**Reality**:
- OS cleans up FILE descriptors, MEMORY, SIGNALS.
- OS does NOT clean up futex semaphore state.
- Linux POSIX has `PTHREAD_MUTEX_ROBUST` flag for this exact case — but Python's `mp.Lock` does NOT use it.

### Why Python doesn't use ROBUST

CPython source: `multiprocessing/synchronize.py` uses `Semaphore` with simple `pthread_mutex_init` (no robust attr).

Reasons:
- ROBUST adds overhead.
- Cross-platform compat (Windows has different mutex semantics).
- Most Python code single-process — robust unnecessary.

→ Vision Platform multi-process inherent → bumps into this.

### Statistical inevitability

10-50µs window between `acquire` and `release` per critical section. At 30 FPS × 16 cameras × 5 stages × 4 lock acquires/stage = ~10k acquires/second. Over 24h = 864M acquires. P(SIGKILL hit window) ~ 50µs / 1s = small but non-zero. Multiply by 864M → **expected** several hits over 24h.

→ Not "if", but "when".

---

## Fix (R5-CRITICAL-01 implemented)

### 3-layer defense

#### Layer 1: bounded acquire

```python
class ShmFrameWriter:
    _LOCK_ACQUIRE_TIMEOUT_S = 2.0
    
    def write(self, frame):
        for slot_idx in range(...):
            lock = self._ring.slot_lock(slot_idx)
            
            if not lock.acquire(timeout=self._LOCK_ACQUIRE_TIMEOUT_S):
                # Poisoned futex — skip slot.
                self._quarantined_slots.add(slot_idx)
                continue
            
            try:
                # ... critical section ...
            finally:
                lock.release()
```

→ Workers never block forever. 2s timeout = pragmatic threshold (should be <100ms in healthy state).

#### Layer 2: Cross-process QUARANTINED sentinel

```python
class SlotState(IntEnum):
    FREE = 0
    WRITING = 1
    READY = 2
    READING = 3
    DONE = 4
    QUARANTINED = 0xFFFF_FFFF   # ← sticky, set lock-free via atomic store
```

Reader peek state lock-free first:
```python
def read(self, slot_idx, expected_gen):
    # Lock-free peek BEFORE attempting lock.
    peek_state, *_ = struct.unpack_from(HEADER_FMT, buf, 0)
    if peek_state == SlotState.QUARANTINED:
        return None  # skip without trying poisoned lock
    
    # ... normal read flow with bounded acquire ...
```

#### Layer 3: Supervisor recovery sweep

```python
class ShmRingBuffer:
    def quarantine_poisoned_slot(self, slot_idx):
        """Permanently retire poisoned slot.
        
        IMPORTANT: cannot REPLACE the lock cross-process.
        Children hold original lock object via Process(args=...).
        Supervisor's swap is invisible to children.
        
        Honest answer: poisoned futex IS irrecoverable without restart.
        Quarantine the slot. Bump gen so in-flight readers fail safe.
        """
        # Verify owner is dead (prevent racing with legit writer).
        state, gen, owner_pid, ... = struct.unpack_from(HEADER_FMT, ...)
        if owner_pid > 0 and _pid_is_alive(owner_pid):
            return False  # don't quarantine alive owner
        
        # Atomic state field write (4-byte aligned, atomic on x86-64).
        struct.pack_into("<I", meta.buf, 0, SlotState.QUARANTINED)
        # Bump generation in separate aligned 8-byte store.
        struct.pack_into("<Q", meta.buf, 4, gen + 1)
        
        return True
```

### Why these 3 layers together

- **Layer 1 alone**: workers timeout, but no signal to operator. Slot stays poisoned.
- **Layer 2 alone**: cross-process visible, but workers may still try lock first.
- **Layer 3 alone**: supervisor knows, but workers don't.

→ Combined: workers fail-fast (Layer 1) → discover quarantine (Layer 2) → supervisor formalizes (Layer 3) → operator alerted via metric `shm_ring_capacity_degraded`.

---

## Alternative fixes (rejected)

### Reject 1: Use `posix_ipc` with PTHREAD_MUTEX_ROBUST

Pros: actual robust mutex.
Cons:
- POSIX-only (Windows doesn't have).
- 3rd-party dep.
- Extensive code change.
- Vision Platform supports both Linux + Windows → must work on both.

→ **Rejected**. 3-layer defense works cross-platform.

### Reject 2: Switch to seqlock entirely

Pros: lock-free reader.
Cons:
- Single writer constraint (multi-writer needs lock anyway).
- Python no native atomics → require `atomics` lib (also 3rd-party).
- Complex implementation, high bug surface.

→ **Rejected** as default. Available as optional Option B.

### Reject 3: Just restart everything on poisoning

Pros: simple.
Cons:
- 16 cameras restart + reconnect RTSP = ~30-60s downtime.
- During downtime, missing detections = security incident in production.
- Cascade effect: 1 poisoning → all stop.

→ **Rejected**. Quarantine slot keeps system running with degraded capacity (n_slots-1).

---

## Prevention

### Test pattern

```python
def test_writer_skips_poisoned_slot():
    """Verify writer skips slot whose lock cannot be acquired."""
    ring = ShmRingBuffer(n_slots=4, ..., create=True)
    writer = ShmFrameWriter(ring)
    
    # Manually acquire slot 0 lock and don't release.
    lock_0 = ring.slot_lock(0)
    lock_0.acquire()
    
    # Writer should skip slot 0 → write to slot 1.
    ref = writer.write(np.zeros((..., 3), dtype=np.uint8))
    assert ref is not None
    assert ref.slot != 0  # skipped poisoned
    
    # Cleanup.
    lock_0.release()
    ring.cleanup_all()


def test_reader_skips_quarantined_slot():
    """Verify reader skips QUARANTINED slot without blocking."""
    ring = ShmRingBuffer(...)
    
    # Manually mark slot 0 as QUARANTINED.
    struct.pack_into("<I", ring._meta_shms[0].buf, 0, SlotState.QUARANTINED)
    
    reader = ShmFrameReader(ring)
    out = reader.read(slot_idx=0, expected_gen=1)
    
    assert out is None  # skipped quarantined, no block
```

### Code review checklist

- [ ] Every `lock.acquire()` has `timeout=` parameter.
- [ ] Cross-process lock has cleanup story (sentinel, supervisor sweep).
- [ ] State updates are single aligned store (≤8 bytes) where possible.
- [ ] Multi-byte struct writes are under lock.

### Lint rule (custom)

```python
# Custom AST visitor for `lock.acquire()` without timeout.
# Ruff/flake8 plugin: pylint-multiprocessing.
```

(Vision Platform doesn't have this lint yet — manual review.)

### Chaos engineering

```python
# Production-like soak test (Linux/macOS):
def chaos_test():
    for _ in range(100):
        spawn_pipeline()
        time.sleep(random.uniform(60, 600))
        os.kill(random.choice(camera_pids), signal.SIGKILL)
        verify_other_cameras_still_running(timeout=10)


# Windows variant: psutil.Process(pid).kill() = TerminateProcess.
def chaos_test_windows():
    import psutil
    for _ in range(100):
        spawn_pipeline()
        time.sleep(random.uniform(60, 600))
        psutil.Process(random.choice(camera_pids)).kill()
        verify_other_cameras_still_running(timeout=10)
```

→ Run in CI for hours. Catches regressions.

---

## Liên kết production

- `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-lock-per-slot-ho-c-seqlock.md`
- `Vision_platform_architecture_design/05-inference-and-ipc/03-shm-frame-bus-slot-lifecycle-protocol.md`
- `Vision_platform_architecture_design/00-README.md` Round 5 fix table.

---

## Tóm tắt

> **Mutex poisoning = SIGKILL hit lock holder. `multiprocessing.Lock` không robust. Fix 3-layer: bounded acquire timeout + cross-process QUARANTINED sentinel via atomic state write + supervisor recovery sweep. Honest: poisoned futex is irrecoverable; quarantine slot, keep running with n-1 capacity.**

➡️ Tiếp theo: [`02-traceback-retention-r5.md`](02-traceback-retention-r5.md)
