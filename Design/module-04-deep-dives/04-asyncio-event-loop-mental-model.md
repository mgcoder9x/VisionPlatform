# 04 — Asyncio Event Loop Mental Model

## Câu hỏi cốt lõi

> Asyncio coroutine vs thread vs process — khi nào chọn cái nào? Tại sao R5-HIGH-02 cần `EventLoopWatchdog`?

## TL;DR (30s)

**Event loop** = single-threaded scheduler. Chạy 1 coroutine until it `await` (yield control), rồi chạy coroutine khác.

- **Coroutine**: collaborative concurrency. Cooperative `await` → yield. Cheap (~few KB/coroutine).
- **Thread**: preemptive concurrency. OS scheduler. Heavier (~MB stack).
- **Process**: bulkhead + GIL bypass. Heaviest (~tens of MB).

**Trap**: 1 coroutine làm work CPU-bound (no `await`) trong 1 second → BLOCK toàn bộ event loop. Tất cả coroutine khác wait.

→ R5-HIGH-02 `EventLoopWatchdog` detect stalls → alert.

---

## Theory: event loop step by step

### Single-threaded scheduler

```python
async def producer():
    for i in range(5):
        await asyncio.sleep(0.1)
        print(f"Produced {i}")


async def consumer():
    for i in range(5):
        await asyncio.sleep(0.15)
        print(f"Consumed {i}")


async def main():
    await asyncio.gather(producer(), consumer())


asyncio.run(main())
```

Output (interleaved):
```
Produced 0     (t=0.1)
Consumed 0     (t=0.15)
Produced 1     (t=0.2)
Produced 2     (t=0.3)
Consumed 1     (t=0.3)
...
```

→ 2 coroutines on **1 thread**. They take turns.

### Mental model

```
┌─────────── Event Loop (single thread) ───────────┐
│                                                   │
│   ┌──────────┐                                    │
│   │Task queue│   [coro_A, coro_B, coro_C, ...]    │
│   └──────────┘                                    │
│        ↓                                           │
│   Pick task → run until await → push timer/IO     │
│        ↓                                           │
│   Wait until any timer fires or IO ready          │
│        ↓                                           │
│   Re-add to task queue                             │
│        ↑                                           │
│        └────────── (loop) ─────────────────────┐   │
│                                                 │   │
└─────────────────────────────────────────────────┘   │
                                                      │
   IO events:                                         │
   ┌─────────┐  ┌─────────┐  ┌─────────┐              │
   │ socket1 │  │ socket2 │  │ timer1  │  ← syscall   │
   └─────────┘  └─────────┘  └─────────┘   epoll/kqueue
```

**Single thread**. **No GIL contention** giữa các coroutines (chỉ 1 chạy 1 lần).

### Critical: `await` is yield point

Coroutines **CHỈ** yield khi gặp `await something_that_actually_yields`:
- `await asyncio.sleep(...)` ✓
- `await socket.recv()` ✓ (I/O)
- `await asyncio.gather(...)` ✓
- `await Future` ✓

Coroutines **KHÔNG** yield khi:
- Pure Python compute loop (no await).
- C extension call (numpy, cv2 — even if release GIL, doesn't yield event loop).
- Sync `time.sleep()` (BLOCKS thread!).
- Sync file I/O (`open(...).read()`).

→ **CPU-bound trong async function = block event loop**.

---

## R5-HIGH-02: event loop starvation

### Bug scenario

```python
async def detection_stage(packet):
    # Innocent-looking pure-Python work:
    detections = []
    for box in packet.candidate_boxes:
        if polygon_intersection(box, self._roi):  # ← CPU-bound, ~10ms
            detections.append(box)
    return detections


# In another coroutine:
async def zmq_receiver():
    while True:
        msg = await self._socket.recv()  # ← stuck waiting because event loop blocked!
        ...
```

→ `polygon_intersection` runs 10ms in pure Python. **No await**. Event loop blocked.

→ `zmq_receiver` cannot poll socket → message backlog → maybe heartbeat missed → HA failover triggered.

→ **1 slow coroutine kéo cả async runtime**.

### Fix: EventLoopWatchdog (R5-HIGH-02)

```python
class EventLoopWatchdog:
    """Detect event loop stalls."""
    
    def __init__(self, interval_ms=10, latency_alert_ms=20):
        self._interval_s = interval_ms / 1000.0
        self._alert_ns = latency_alert_ms * 1_000_000
    
    async def _loop(self):
        next_wake_ns = time.monotonic_ns() + int(self._interval_s * 1e9)
        while True:
            await asyncio.sleep(self._interval_s)
            now = time.monotonic_ns()
            late_ns = now - next_wake_ns
            
            if late_ns >= self._alert_ns:
                logger.warning(
                    "event_loop_stall",
                    late_ms=late_ns / 1e6,
                    threshold_ms=self._alert_ns / 1e6,
                )
            
            next_wake_ns += int(self._interval_s * 1e9)
```

→ Watchdog `await asyncio.sleep(10ms)`. Khi wake up, check `now - expected`. Nếu > 20ms → log warning.

→ Operator alert. Engineer dùng `py-spy dump` để identify offending coroutine.

---

## Coroutine vs Thread vs Process

| Aspect | Coroutine | Thread | Process |
|--------|-----------|--------|---------|
| **Scheduling** | Cooperative (`await`) | Preemptive (OS) | OS process scheduler |
| **GIL** | Single-threaded — N/A | Shared GIL | Each has own GIL |
| **Memory** | ~5-10 KB/task | ~1-8 MB stack | ~30-50 MB Python |
| **Cost spawn** | ~microseconds | ~milliseconds | ~10-100 ms |
| **CPU-bound scaling** | NO | NO (GIL) | YES |
| **I/O scaling** | YES (1000s tasks) | YES (~100s threads) | YES (limited by spawn) |
| **Crash isolation** | NO | NO (kills process) | YES (bulkhead) |
| **Communication** | Direct memory | Direct memory | IPC (SHM/ZMQ) |
| **Determinism** | High (no preemption) | Low (race) | Low (race) |
| **Debugging** | Stack traces clean | Stack interleave | Multi-pid traces |

### When to use which

**Coroutine** cho:
- I/O-heavy với 1000s concurrent connections (web server).
- Single-thread state cần determinism.
- Vision Platform: ZMQ recv loop, async stage that awaits inference.

**Thread** cho:
- I/O-bound (file, network) với fewer (~10-100) concurrent.
- GUI main thread + worker thread.
- Vision Platform: thread inside inference service for ZMQ recv + GPU compute.

**Process** cho:
- CPU-bound (need GIL bypass).
- Crash isolation needed.
- Vision Platform: each camera + inference service.

### Hybrid (Vision Platform)

```
Supervisor (process)
├── Camera 1 process
│   └── Async runtime (event loop)
│       ├── Coroutine: capture loop
│       ├── Coroutine: pipeline executor (sync stages in thread pool!)
│       └── Coroutine: ZMQ inference client
│
├── Camera 2 process (same structure)
└── Inference service process
    ├── Thread: GPU inference (releases GIL)
    └── Thread: ZMQ ROUTER recv + send
```

→ Mix all three.

---

## Common asyncio mistakes

### Mistake 1: Forget `await`

```python
# Sai
async def get_data():
    asyncio.sleep(1)   # ← creates coroutine, doesn't run!
    return "data"

# Đúng
async def get_data():
    await asyncio.sleep(1)
    return "data"
```

→ `asyncio.sleep(1)` returns **coroutine object**. Without `await`, never scheduled. Code "runs" immediately, returning "data" without sleep.

→ Linter `pyflakes`/`ruff` catches "unawaited coroutine" warning.

### Mistake 2: Block event loop with `time.sleep`

```python
# Sai — blocks event loop
async def slow_op():
    time.sleep(1)   # ← BLOCK, all coroutines wait!
    return "data"

# Đúng
async def slow_op():
    await asyncio.sleep(1)   # ← yields to other coroutines
    return "data"
```

### Mistake 3: CPU-bound work in async

```python
# Sai — blocks event loop for 1+ seconds
async def detect(frame):
    return run_yolo(frame)   # ← pure Python pre/post-process, ~50ms

# Đúng
async def detect(frame):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_yolo, frame)
    # Run in thread pool, event loop continues.
```

### Mistake 4: Mix sync libraries in async code

```python
# Sai
async def process():
    response = requests.get(url)   # ← sync HTTP, blocks!
    ...

# Đúng
async def process():
    async with aiohttp.ClientSession() as s:
        response = await s.get(url)   # ← async HTTP
```

---

## Real-world: Python `asyncio` performance

### Single-thread benchmark

10000 coroutines each `await asyncio.sleep(0.001)`:

```
asyncio: 1.5 seconds (close to ideal 1s + overhead)
threading: ~5 seconds (thread spawn overhead)
multiprocessing: minutes (process spawn overhead)
```

→ Asyncio scales **dramatically** for I/O.

### Limit: ~10,000 coroutines

Beyond ~10k coroutines, Python overhead (event loop scheduling, garbage collection) becomes significant. **Different language** (Go, Rust) better at 100k+ concurrent.

---

## Self-check

1. **`async def f(): time.sleep(1)`** — runs how on event loop với 5 other coroutines?

2. **`asyncio.gather(*coros)`** — concurrent or sequential?

3. **`run_in_executor`** — what type of work suitable? Why?

4. **R5-HIGH-02 watchdog `latency_alert_ms < interval_ms`** — bug gì? Tại sao constructor raise?

5. **Coroutine vs goroutine (Go)** — khác biệt fundamental?

<details>
<summary>Đáp án</summary>

1. `time.sleep(1)` is **synchronous** → blocks the entire event loop for 1 second. All other coroutines wait.
   - To make non-blocking: `await asyncio.sleep(1)` instead.
   - Or wrap: `await asyncio.get_event_loop().run_in_executor(None, time.sleep, 1)` (uses thread pool).

2. **`asyncio.gather(*coros)` is concurrent** — all coros scheduled simultaneously, run interleaved on single thread (when each yields).
   - **NOT parallel** — only 1 runs at a time (single thread).
   - Sequential equivalent: `for c in coros: await c` — wait each before starting next.

3. **`run_in_executor` for**:
   - CPU-bound work (release GIL via numpy/C ext, scale with threads).
   - Blocking I/O without async equivalent (legacy lib).
   - Subprocess execution.
   - **Why**: keeps event loop responsive while heavy work happens in thread pool.
   - **NOT for**: pure Python CPU-bound (GIL → no benefit).

4. **`latency_alert_ms < interval_ms`**:
   - watchdog wakes every `interval_ms`. Always slightly late (scheduler jitter).
   - If alert threshold < interval → every wake triggers alert.
   - Constructor: `if latency_alert_ms < interval_ms: raise ValueError(...)`.
   - User must set `latency_alert_ms >= interval_ms` (typically 2-3x).

5. **Coroutine (Python) vs goroutine (Go)**:
   - Python coroutine: cooperative, single-thread event loop, requires `await` keyword.
   - Goroutine: preemptive (Go runtime preempts long-running goroutines), multi-thread M:N scheduler, no special syntax.
   - Goroutine: spawn 100k+ feasible.
   - Python coroutine: ~10k limit before overhead.
   - **Goroutine bypasses GIL** (Go has no GIL).

</details>

---

## Liên kết

- **Module 04 file 01** (GIL).
- **Production**: `Vision_platform_architecture_design/04-pipeline-and-concurrency/03-sync-async-stages.md` — EventLoopWatchdog code.
- **Reference**: PEP 492 (async/await), `asyncio` docs.

---

## Tóm tắt 1 câu

> **Event loop = single-thread scheduler. Coroutines yield qua `await`. CPU-bound trong async function block all other coroutines. R5-HIGH-02 watchdog detects stalls > 20ms. Hybrid Vision Platform: process bulkhead + thread for I/O + coroutine inside.**

➡️ Tiếp theo: [`05-circuit-breaker-math.md`](05-circuit-breaker-math.md)
