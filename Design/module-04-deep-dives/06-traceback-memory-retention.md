# 06 — Traceback Memory Retention: R5-CRITICAL-02 deep dive với numbers

## Câu hỏi cốt lõi

> Tại sao Python `Exception` giữ MediaPacket sống? `traceback.clear_frames()` cách nào fix? Cost thật vs benefit?

## TL;DR (30s)

Python Exception object `e` có `e.__traceback__` → traceback frames → frame's `f_locals` → references đến biến local trong frame → MediaPacket → ndarray ~6MB.

→ Lưu `e` trong list (DLQ buffer, retry list) → giữ sống 6MB ndarray per error.

→ R5-CRITICAL-02 fix: `traceback.clear_frames()` empty `f_locals` → break chain → ndarray GC'd.

**Đã verify** với `bench_traceback_retention.py`: 50 errors leak **296.7 MB** vs **6 MB** với fix. **49× memory difference**.


---

## Theory: Python exception lifecycle

```python
def stage_processes_packet(packet):  # ← `packet` = local var in this frame
    try:
        raise RuntimeError("processing failed")
    except RuntimeError as e:
        # e.__traceback__ → traceback object
        # traceback.tb_frame → frame of stage_processes_packet
        # frame.f_locals → {"packet": <MediaPacket>, "self": ..., ...}
        # MediaPacket.media_ref.array → 6MB ndarray
        return BadResult(error=e)   # ← Stored! All chain alive.
```

When `BadResult` is in `dlq_buffer` (list of 1000+ results), all 1000 ndarrays alive → memory bloat.

### Why does Python keep frame locals?

`__traceback__` is a **debugging aid**. Python keeps frame state for:
- `traceback.format_exc()` to print stack.
- `pdb` post-mortem debugging.
- `inspect.trace()` introspection.

→ Designed for **dev convenience**. Bad for production.

---

## Empirical verification

### Run experiment

```bash
cd vision_demo_workspace
.venv\Scripts\python.exe experiments\bench_traceback_retention.py
```

### Real numbers

```
=== BAD: store live Exception (traceback retention) ===
  iterations: 50
  ndarrays still alive: 50/50
  memory growth: 296.7 MB
  result count: 50

=== GOOD: store ErrorSummary (strings only) ===
  iterations: 50
  ndarrays still alive: 1/50
  memory growth: 6.0 MB
  result count: 50

=== Conclusion ===
BAD pattern: ndarrays stay alive → memory grows.
GOOD pattern: ndarrays get GC'd → memory stable.
```

### Analysis

- **BAD**: 50 ndarray × 6MB = 300MB. Each iteration's `big_array` alive because Exception traceback retains frame → frame.f_locals['big_array'].
- **GOOD**: only 1 ndarray alive (current loop iteration). Previous iterations GC'd.
- **49× memory difference**.

In production: 1000 errors over 24h = 6GB difference.

---

## R5-CRITICAL-02 fix: ErrorSummary + clear_frames

### Pattern

```python
@dataclass(frozen=True)
class ErrorSummary:
    error_type: str
    error_message: str
    is_fatal: bool = False
    traceback_str: Optional[str] = None
    
    @classmethod
    def from_exception(cls, exc, *, capture_traceback=False):
        import traceback as _tb
        tb_str = None
        if capture_traceback and exc.__traceback__ is not None:
            tb_str = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
        # Critical: clear frame locals BEFORE returning.
        if exc.__traceback__ is not None:
            _tb.clear_frames(exc.__traceback__)
        return cls(
            error_type=type(exc).__qualname__,
            error_message=str(exc),
            traceback_str=tb_str,
        )
```

### What `clear_frames` does

Per Python docs (`traceback.clear_frames`):
> Clears the local variables of all the stack frames in a traceback by calling the `clear()` method of each frame object.

→ Sets each frame's `f_locals = {}`. Breaks `frame → locals → packet → ndarray` chain.

### Verification: clear_frames works

`bench_clear_frames.py`:

```
=== Without clear_frames ===
  ndarray alive (after del + gc.collect): True
  exception still has traceback: True

=== With clear_frames ===
  ndarray alive (after del + gc.collect): False
  exception still has traceback shape: True
```

→ **ndarray GC'd** sau `clear_frames`. Traceback **shape** (line numbers, function names) **preserved** cho debugging.

→ **Best of both**: keep diagnostic info, drop heavy refs.

---

## Decision: when to capture traceback string

`from_exception(capture_traceback=False)` default.

### Why default False

Stringifying traceback costs:
- 50-200µs CPU per call.
- ~500-2000 bytes string.
- Pollute log size.

For **non-fatal** errors (transient retry path): waste.
For **fatal** errors (supervisor inspect): need.

→ `StageResult.error()` factory: `capture_traceback = fatal` default.

```python
@classmethod
def error(cls, error: Exception, stage: str, fatal: bool = False,
          capture_traceback: Optional[bool] = None) -> "StageResult":
    if capture_traceback is None:
        capture_traceback = fatal
    summary = ErrorSummary.from_exception(error, capture_traceback=capture_traceback)
    return cls(
        status=StageStatus.ERROR,
        error=error if fatal else None,  # ← keep Exception only for raise
        error_summary=summary,
        ...
    )
```

→ Non-fatal: drop `error` field, keep `error_summary` strings only. Memory friendly.
→ Fatal: keep `error` for re-raise. Traceback intact (will be cleared on raise next time).

---

## Other places frame retention bites

### 1. asyncio Task exception

```python
async def task():
    raise RuntimeError(...)

t = asyncio.create_task(task())
# ... t completes with exception ...
# t._exception = e → e.__traceback__ → frames → ...
```

→ Long-lived tasks accumulate. asyncio docs recommend: process exception promptly OR call `task.exception()` to extract.

### 2. logger.exception()

```python
try:
    ...
except Exception:
    logger.exception("oops")  # ← formats traceback string
```

→ structlog converts to string at processor stage. Original Exception not retained in log handler. Safe.

### 3. unittest cleanup

```python
class MyTest(unittest.TestCase):
    def test_x(self):
        # If test fails, framework keeps traceback for reporting.
        ...
```

→ Test runner keeps tracebacks for failure report. Test isolation relies on per-test setup/teardown to reset state.

---

## When to skip the fix

### Acceptable to keep Exception ref

- **Short lifecycle**: ReadResult — consumed immediately by caller.
- **No big locals**: Exception in helper function with primitive locals only.
- **Synchronous stack**: `try/except` with immediate handle.

### Must apply fix

- **Long-lived buffer**: DLQ, retry list, error_budget deque.
- **Cross-thread/process**: pickle Exception across boundary.
- **Heavy locals**: any frame with ndarray/large object reference.

→ Vision Platform applies fix in `StageResult` (long-lived in DLQ chain). NOT in `ReadResult` (consumed immediately).

---

## Self-check

1. **Why does `e.__traceback__` retain frame locals?** Python design intent?

2. **`gc.collect()` not enough** — sao? Cycle reference?

3. **`clear_frames` vs `__traceback__ = None`** — khác biệt?

4. **Đo memory leak in dev** — best tools?

5. **R5-CRITICAL-02 vision_demo simplification**: tại sao vision_demo `StageResult` không có `error: Exception` field gì cả? Trade-off?

<details>
<summary>Đáp án</summary>

1. **Frame retention by design**:
   - Python wants `traceback.format_exc()` and `pdb` post-mortem to work.
   - Frame's `f_locals` provides "what were the variables when error happened?" — invaluable for debugging.
   - **Trade-off**: dev convenience vs production memory.
   - C-API `PyTraceBack_Type` deliberately keeps frame ref.

2. **`gc.collect()` not enough**:
   - GC handles **cycles** (reference cycles).
   - Traceback chain: e → traceback → frame → e (in `f_locals['e']` if `as e` clause). YES it's a cycle!
   - But: gc.collect() detect cycles. Should free... unless **other strong reference exists** (e.g. `BadResult.error = e` from outside).
   - In experiment: `BadResult` list holds `e` strong → gc cannot free.
   - **`del big`** removes outer reference, but `e.__traceback__.frame.f_locals['big_array']` still holds it.
   - **`clear_frames`**: empties f_locals → no more reference to `big_array` from anywhere.

3. **`clear_frames` vs `__traceback__ = None`**:
   - `clear_frames(tb)`: keeps traceback **shape** (line numbers, file paths). Empty frame locals only.
   - `e.__traceback__ = None`: removes traceback entirely. **Lose** debugging info.
   - **Best**: `clear_frames` — keep shape, drop locals.
   - Production rule: clear_frames before storing, format_exc before clearing if need string.

4. **Memory leak detection tools**:
   - **`tracemalloc`** (stdlib): take_snapshot diff before/after. Used in `bench_traceback_retention.py`.
   - **`objgraph`**: show object reference chain. `objgraph.show_backrefs([obj])`.
   - **`memory_profiler`**: line-by-line memory usage.
   - **`pympler`**: detailed object stats.
   - Production: `psutil.Process().memory_info().rss` over time. Trend analysis.

5. **vision_demo no `error` field**:
   - **Pros**:
     - Simpler — 1 field less.
     - Type system enforces "no Exception leak" (compile time).
     - Idiomatic for stage error pattern.
   - **Cons**:
     - Cannot re-raise fatal Exception with original stack.
     - Production needs both: `error_summary` for non-fatal, `error: Exception` for fatal raise.
   - **Trade-off**: vision_demo focuses on pattern + memory hygiene. Production has both for flexibility.

</details>

---

## Liên kết

- **Production**: `Vision_platform_architecture_design/04-pipeline-and-concurrency/01-pipeline-engine.md` — `ErrorSummary` + StageResult.error factory.
- **Reference**: Python docs `traceback.clear_frames`.

---

## Tóm tắt 1 câu

> **Python Exception giữ traceback → frame → locals → MediaPacket → ndarray. Long-lived storage (DLQ, retry) leaks 6MB/error. Fix: ErrorSummary với strings + `traceback.clear_frames()`. Verified: 296.7 MB leaked vs 6 MB fixed (49× difference).**

✅ Hoàn thành Module 04.

➡️ Tiếp theo: [`../module-05-real-bugs/`](../module-05-real-bugs/)
