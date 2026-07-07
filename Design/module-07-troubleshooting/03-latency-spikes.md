# 03 — Latency Spikes: p99 tăng nhưng p50 OK

## Symptom

- p50 latency stable (~10ms).
- p99 latency spikes to 100-500ms intermittent.
- p50 vs p99 ratio > 5x = abnormal.

## Triage 60s

Trả lời 2 câu hỏi trước khi dive sâu:

1. **Pattern**: spike random, periodic, hay sau specific event (deploy, GC, GPU thermal)?
2. **Correlation**: spike align với traffic pattern, batch boundary, log flush, network blip?

→ Pattern quyết định branch nào trong decision tree dưới.

## Decision tree

```
p99 spike (p50 OK)
│
├── Periodic (every N seconds)
│   ├── Likely: GC pause
│   ├── Tools: PYTHONMALLOCSTATS, gc.callbacks, py-spy
│   └── Fix: gc.disable() + manual gc.collect() at safe time
│
├── Random spikes
│   ├── Likely: lock contention
│   ├── Resource starvation (file fd, mem alloc)
│   ├── Disk write pause (log file flush)
│   └── Tools: py-spy --threads, strace
│
├── After specific events
│   ├── Inference batch boundary (waiting for batch fill)
│   ├── Network blip (RTSP reconnect)
│   ├── Cache eviction (cold cache reload)
│   └── Fix: depends — pre-warm, jitter, retry
│
└── Trend (slowly increasing)
    ├── Memory pressure → GC pressure
    ├── Cache pollution
    └── Fix: investigate memory growth (file 02)
```

## Common culprits

### Python GC pause

- Default: triggers when count thresholds hit (700, 10, 10).
- Pause: 1-50ms typical; longer khi heap lớn (1000+ objects gen2).
- Fix:
  - `gc.disable()` + manual `gc.collect()` at quiet time (e.g., between batch boundary).
  - Or tune thresholds: `gc.set_threshold(700, 10, 10)` → tăng nếu allocation rate cao.
- Verify: `gc.callbacks.append(...)` log mỗi GC start/stop với timestamp.

### Lock contention

- Multiple threads compete for shared resource (SHM slot lock, queue lock, log lock).
- Symptom: p99 = lock wait time + actual work.
- Tools: `py-spy --threads` shows blocked threads với stack pointing to `acquire`.
- Fix: more slots, less critical-section work, lock-free patterns nơi có thể (atomic counter, CAS).

### Backpressure block timeout

- Thread blocked waiting queue (BLOCK policy with high `block_timeout_ms`).
- Symptom: spike khi downstream slow → upstream block → p99 = block timeout.
- Fix: tune queue size, switch to DROP_OLDEST policy nếu data freshness > completeness.

### Inference batch wait

- Inference service waits for batch to fill (`max_wait_ms` reached or batch full).
- Symptom: 1 frame waits for 7 more = ~33ms wait nếu rate 30 fps × 7 frames.
- Fix: tune `max_wait_ms` (lower → less wait but smaller batch → less GPU efficiency).

### Disk/log flush

- structlog/print với sync writer → mỗi log call flush to disk.
- Symptom: spike correlates với log volume burst.
- Fix: async logger với buffer (HI-OBS-01 fix), batch flush.

## Tools

- **`pytest-benchmark`** — perf regression detection in CI.
- **`py-spy --top`** — sampling profiler, low overhead, production-safe.
- **`py-spy --threads`** — see blocked threads.
- **`cProfile`** — function-level breakdown (offline analysis).
- **`line_profiler`** — line-level (need decorator, dev only).
- **Real-time observability**: GC stats (`gc.get_stats()`), lock stats (custom counter), queue stats (depth + drops).

## Pattern recognition

Quan sát 30 phút metrics → assign category:

| Pattern | Likely cause | Branch decision tree |
|---------|--------------|----------------------|
| Spike every ~30-60s | GC gen2 collection | Periodic |
| Spike align với log volume | Sync logger flush | Random (disk write) |
| Spike khi camera count tăng | Lock contention | Random (lock) |
| Spike sau deploy | Cold cache, untuned config | After event |
| p99 trending up over hours | Memory pressure → GC slow | Trend |

## Tóm tắt

> **p99 spike investigation: periodic = GC, random = lock or disk flush, after-event = batch boundary or cache miss, trend = memory pressure feedback. Tools: py-spy + cProfile. Fix theo root cause; thường là tuning, đôi khi algorithmic. Quan sát 30 phút metrics + correlation analysis trước khi fix.**
