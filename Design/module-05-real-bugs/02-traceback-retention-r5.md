## R5-CRITICAL-02 — Traceback Memory Retention

**Severity**: CRITICAL. Slow OOM over hours/days.

---

## Setup (3 phút) — Minimal reproducer

```python
import gc
import sys
import weakref
import numpy as np


class StageResult:
    """BAD pattern: stores Exception object directly."""
    def __init__(self, error):
        self.error = error  # ← Exception with __traceback__


def stage_processes_packet(big_array):
    """Stage that fails. big_array is 6MB local var."""
    try:
        raise RuntimeError("processing failed")
    except RuntimeError as e:
        return StageResult(error=e)


# Simulate DLQ buffer holding 50 results.
results = []
weak_refs = []

for i in range(50):
    big = np.zeros((1080, 1920, 3), dtype=np.uint8)  # 6MB each
    weak_refs.append(weakref.ref(big))
    results.append(stage_processes_packet(big))
    # `big` goes out of scope at iteration end.

gc.collect()  # try to clean up

n_alive = sum(1 for w in weak_refs if w() is not None)
print(f"ndarrays alive: {n_alive}/50")  # → 50/50 — ALL leaked!

memory_mb = sum(
    sys.getsizeof(w()) for w in weak_refs if w() is not None
) / (1024 * 1024)
print(f"memory leaked: ~{memory_mb:.0f} MB")  # → ~300 MB
```

→ 50 errors × 6MB = **300 MB leaked**. Each Exception holds traceback → frame → frame.f_locals → packet → ndarray.

---

## Bug story

**Production scenario**: Vision Platform 16 cameras, 24/7 deployment.

- **Day 1-2**: Memory stable around 8GB.
- **Day 3 morning**: Memory at 12GB. Operator notes "slowly growing".
- **Day 4**: Memory at 18GB. Performance degrading.
- **Day 5**: OOM-killer triggers, supervisor restart.
- Cycle repeats every 4-5 days.

### Investigation

- `tracemalloc.snapshot()` diff over 24h shows 6GB growth.
- Top allocator: `numpy.ndarray.__init__` (frame data).
- Top retainer: `traceback.TracebackType` objects.
- `objgraph.show_backrefs([sample_ndarray])` reveals chain:
  ```
  ndarray ← MediaPacket ← f_locals['packet'] ← frame ← traceback ← Exception ← StageResult.error ← DLQ buffer
  ```

### Reviewer R5 finding

R5 reviewer noticed: every transient stage error (network blip, model timeout) → DLQ buffer accumulates. Each entry holds full ndarray.

**Math**:
- 16 cameras × 1% error rate × 30 fps × 86400s = 414,720 errors/day.
- × 6MB ndarray = ~2.5 TB referenced.
- Mostly GC'd quickly (deque maxsize), but **DLQ retry buffer** holds longer.
- DLQ buffer 1000 entries × 6MB = 6 GB always live.

→ Confirmed root cause.

---

## Why it happened (root cause)

### Mental model sai

Reviewer assumed:
```
"frozen=True dataclass + str(error) message = no Exception ref kept"
```

Reality:
```python
@dataclass(frozen=True)
class StageResult:
    error: Optional[Exception] = None  # ← LIVE Exception object
```

`Exception` object's `__traceback__` retains:
1. Traceback chain (TracebackType linked list).
2. Each TracebackType has `tb_frame` (FrameType).
3. Each FrameType has `f_locals` (dict).
4. f_locals has every local variable in that frame at error time.
5. Including `packet` (MediaPacket) → `media_ref` → `ndarray` (6MB).

→ **Cascading retention**.

### Why didn't Python GC clean up?

GC handles **cycles** but needs all references to be gone first. Issue:
- `dlq_buffer.append(result)` → strong ref to result.
- `result.error = e` → strong ref to Exception.
- `e.__traceback__` → frame → f_locals → packet → ndarray.

→ Strong reference chain, no cycle. GC sees as "live data".

### CPython implementation detail

`frame.f_locals` is **a snapshot copy** for some access patterns, but **the original locals dict** when frame is alive (in traceback). Python keeps frame alive for debugging.

PEP 558 (Python 3.12+) changes some semantics, but `__traceback__` retention remains.

---

## Fix (R5-CRITICAL-02 implemented)

### Pattern: ErrorSummary

```python
@dataclass(frozen=True)
class ErrorSummary:
    """Lightweight error record. NO Exception ref."""
    error_type: str
    error_message: str
    is_fatal: bool = False
    traceback_str: Optional[str] = None  # string, not live frames
    
    @classmethod
    def from_exception(cls, exc, *, capture_traceback=False):
        import traceback as _tb
        tb_str = None
        if capture_traceback and exc.__traceback__:
            tb_str = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
        # CRITICAL: clear frame locals BEFORE returning.
        if exc.__traceback__:
            _tb.clear_frames(exc.__traceback__)
        return cls(
            error_type=type(exc).__qualname__,
            error_message=str(exc),
            traceback_str=tb_str,
        )


@dataclass(frozen=True)
class StageResult:
    status: StageStatus
    packet: Optional["MediaPacket"] = None
    error: Optional[Exception] = None  # ← only set when fatal=True (raise path)
    error_summary: Optional[ErrorSummary] = None  # ← always set
    ...
    
    @classmethod
    def error(cls, error, stage, fatal=False, capture_traceback=None):
        if capture_traceback is None:
            capture_traceback = fatal
        summary = ErrorSummary.from_exception(error, capture_traceback=capture_traceback)
        return cls(
            status=StageStatus.ERROR,
            error=error if fatal else None,  # only retain for re-raise
            error_summary=summary,
            stage=stage,
            is_fatal=fatal,
        )
```

### `traceback.clear_frames` — what it does

Per Python docs:
> Clears the local variables of all the stack frames in a traceback by calling the `clear()` method of each frame object.

- Each frame's `f_locals` becomes empty dict.
- Frame **shape** (file path, function name, line number) preserved.
- Reference chain broken: `frame.f_locals` no longer holds `packet`.

→ ndarray now reachable only via direct refs (which are gone after iteration). GC reclaims.

### Empirical verification

`bench_traceback_retention.py` runs this:

```
=== BAD: store live Exception (traceback retention) ===
  iterations: 50
  ndarrays still alive: 50/50
  memory growth: 296.7 MB

=== GOOD: store ErrorSummary (strings only) ===
  iterations: 50
  ndarrays still alive: 1/50
  memory growth: 6.0 MB
```

**49× memory difference**. Verified.

`bench_clear_frames.py` runs this:
```
=== Without clear_frames ===
  ndarray alive: True
  exception still has traceback: True

=== With clear_frames ===
  ndarray alive: False
  exception still has traceback shape: True
```

→ `clear_frames` does its job.

---

## Alternative fixes (rejected)

### Reject 1: `del exc.__traceback__`

```python
exc.__traceback__ = None  # destroy traceback entirely
```

Pros: simple, fully releases.
Cons: **lose** debugging info (line numbers, function names). Operator inspecting fatal error has no stack.

→ **Rejected**. clear_frames keeps shape.

### Reject 2: weakref to Exception

```python
import weakref
class StageResult:
    def __init__(self, error):
        self.error_ref = weakref.ref(error)
```

Pros: doesn't hold strong ref → GC works.
Cons:
- Exception garbage-collected immediately (no other strong ref) → caller can't access.
- Stage's `try/except` block exits → Exception out of scope → weakref returns None.
- Useless.

→ **Rejected**.

### Reject 3: Force GC after every error

```python
gc.collect()
```

Pros: aggressive cleanup.
Cons:
- Cannot break strong ref chain → won't help.
- Performance hit (gc.collect() = stop the world).

→ **Rejected**.

### Reject 4: Only log, don't store

```python
except Exception as e:
    logger.error("stage_error", error=str(e))
    return StageResult.skipped(...)  # no error stored
```

Pros: zero retention.
Cons:
- No retry possible (lose context).
- DLQ requires error metadata.
- Operator dashboards lose error breakdown.

→ **Acceptable** for some flows, but production needs retain semantics → use ErrorSummary instead.

---

## Prevention

### Test pattern

```python
def test_stage_error_does_not_retain_packet():
    """R5-CRITICAL-02 regression test."""
    import weakref
    
    weak_packet = None
    
    def stage_fail():
        big = np.zeros((1080, 1920, 3), dtype=np.uint8)
        nonlocal weak_packet
        weak_packet = weakref.ref(big)
        try:
            raise RuntimeError("fail")
        except RuntimeError as e:
            return StageResult.error(error=e, stage="test")
    
    result = stage_fail()
    gc.collect()
    
    # ndarray should be GC'd despite result being stored.
    assert weak_packet() is None, "ndarray leaked via traceback retention"
```

### Code review checklist

- [ ] Long-lived buffers (DLQ, retry, error_budget) store **ErrorSummary**, not Exception.
- [ ] Exception caught + stored → `traceback.clear_frames()` called or `from_exception()` factory used.
- [ ] Async tasks process exceptions promptly (call `task.exception()`).
- [ ] No Exception passed across thread/process boundary (pickle preserves traceback).

### Lint rule (custom)

```python
# AST visitor: detect `dataclass field with type Exception or BaseException`.
# Flag for review.
```

### Tracing memory in production

```python
# In production, periodic check:
import tracemalloc
tracemalloc.start()
# ... run for 24h ...
snap = tracemalloc.take_snapshot()
top_stats = snap.statistics("filename")
for stat in top_stats[:10]:
    print(stat)
```

→ Run in dev env mimic-prod. Catch regressions.

---

## Liên kết production

- `Vision_platform_architecture_design/04-pipeline-and-concurrency/01-pipeline-engine.md` — `ErrorSummary` + `StageResult.error` factory.
- `Vision_platform_architecture_design/00-README.md` Round 5 fix table.
- Module 04 file 06 — `06-traceback-memory-retention.md` deep dive với benchmark.

---

## Tóm tắt

> **Python Exception giữ traceback → frame → locals → MediaPacket → ndarray (6MB). Long-lived storage (DLQ, retry list) leak 6MB/error. Fix: ErrorSummary với strings + `traceback.clear_frames()`. Verified 296.7 MB vs 6 MB (49×).**

➡️ Tiếp theo: [`03-block-policy-rtsp-r1.md`](03-block-policy-rtsp-r1.md)
