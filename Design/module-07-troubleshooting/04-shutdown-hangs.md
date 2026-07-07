# 04 — Shutdown Hangs: Ctrl+C không tắt

## Symptom

- `Ctrl+C` không phản hồi.
- `docker stop` timeout (10s) → SIGKILL.
- `systemctl stop` slow.
- Worker zombies.


## Triage 60s

```bash
# Check process state
ps aux | grep python
# Look for "T" (stopped), "Z" (zombie), "D" (uninterruptible sleep)

# Check signal handler
strace -p <pid> -e trace=signal
```

## Decision tree

```
Shutdown hangs
│
├── SIGTERM ignored (no handler)
│   ├── Fix: register signal.signal(signal.SIGTERM, handler)
│   └── Common: forgot in main, Windows quirks (B.3 R2 fix)
│
├── Handler set, but stuck in critical section
│   ├── Worker hold lock, signal can't preempt
│   ├── Tools: py-spy dump → see what holding
│   └── Fix: bounded operations + check shutdown_event periodically
│
├── Subprocess not joining
│   ├── Parent sets shutdown_event but child not checking
│   ├── Fix: child checks shutdown_event in loop
│
├── Daemon vs non-daemon mismatch
│   ├── daemon=True children don't get joined cleanly
│   ├── Fix: explicit terminate + join with timeout
│
└── DLQ flush hung
    ├── Disk full, network down
    └── Fix: bounded write timeout
```

## R-fixes related

### B.3 (Round 2) — Windows signal handler not setting event
- Bug: `loop.add_signal_handler` raises NotImplementedError on Windows.
- Fix: `signal.signal(SIGINT, lambda: shutdown_event.set())` + lock-free.
- File: `06-resilience-and-shutdown.md SupervisorApp`.

### Cascade order matters
1. Stop sources (no new frames).
2. Drain in-flight requests.
3. Terminate inference.
4. Flush sinks.
5. Cleanup SHM.
6. Force kill stragglers.

→ Wrong order = data loss.

## Common patterns

### Pattern 1: Loop checks shutdown_event

```python
while not shutdown_event.is_set():
    try:
        item = queue.get(timeout=0.5)  # bounded wait
        process(item)
    except queue.Empty:
        continue
```

→ Worker checks event every 500ms max.

### Pattern 2: Cancel async tasks

```python
async def shutdown_cascade(self):
    for task in self._tasks:
        task.cancel()
    
    await asyncio.gather(*self._tasks, return_exceptions=True)
```

### Pattern 3: Force kill timeout

```python
proc.terminate()  # SIGTERM
proc.join(timeout=5)
if proc.is_alive():
    proc.kill()  # SIGKILL
    proc.join(timeout=1)
```

## Tools

- `py-spy dump --pid <pid>` — what's stuck.
- `strace -p <pid>` — syscalls in progress.
- `gdb -p <pid>` — C-level (last resort).
- `ps -ef --forest` — process tree.

## Tóm tắt

> **Shutdown hang: signal handler missing, critical section stuck, subprocess not joining, DLQ flush. Cascade order: source → drain → inference → sink → cleanup → force kill. Periodic shutdown_event check.**
