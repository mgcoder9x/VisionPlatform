# 02 — Memory Grows: OOM crash sau 24h

## Symptom

- Memory tăng dần theo giờ.
- p99 latency tăng (GC pause).
- 24-48h sau: OOM-killer.


## Triage 60s

```bash
# Memory trend
ps -p <pid> -o rss --watch

# tracemalloc snapshot if running
py-spy dump --pid <pid>  # see hot frames
```

## Decision tree

```
Memory growing
│
├── Linear growth (constant rate)
│   ├── Likely: cache unbounded
│   ├── Hot suspects: dedup map (HI-IPC-04), event log
│   └── Fix: bound cache, sweeper, TTL
│
├── Step growth (jumps then plateau)
│   ├── Likely: workload spike causing buffer growth
│   └── Fix: bounded queue, backpressure
│
├── Slow leak (~1MB/h)
│   ├── Likely: traceback retention (R5-CRITICAL-02)
│   ├── Reference cycle, listener accumulation
│   └── Fix: ErrorSummary pattern, weakref, gc.collect periodic
│
└── Sudden spike then drop
    ├── Likely: large frame batch
    └── Not actually a leak, just transient
```

## Common causes (R1-R5)

### Cause 1: R5-CRITICAL-02 traceback retention
- Symptom: linear growth, ~6MB per error.
- Tools: `tracemalloc.statistics("traceback")`.
- Fix: ErrorSummary + clear_frames.

### Cause 2: HI-IPC-04 dedup unbounded
- Symptom: linear growth proportional to request rate.
- Fix: bounded `OrderedDict` with TTL eviction + sweeper.

### Cause 3: DLQ buffer unbounded
- Symptom: grows during error storm.
- Fix: rotate file at size limit (R5 + C.7 fix).

### Cause 4: Asyncio Task accumulation
- Symptom: thousands of pending tasks.
- Tools: `len(asyncio.all_tasks())`.
- Fix: bounded `asyncio.Semaphore`, task groups.

## Tools

- `tracemalloc` — Python builtin, snapshot diff.
- `objgraph` — show ref chain.
- `pympler` — detailed object stats.
- `psutil` — RSS over time.
- `py-spy dump --gil` — see what's holding memory.

## Tóm tắt

> **Memory growth: linear cache, step buffer, slow traceback. Tools: tracemalloc + objgraph. Common: R5-CRITICAL-02, HI-IPC-04, DLQ unbounded, async task pile-up.**
