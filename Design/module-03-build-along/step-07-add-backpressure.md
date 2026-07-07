# Step 07 — Backpressure: BoundedQueue với 4 policy

## Mục tiêu (2h)

Build core backpressure infrastructure:

1. `kernel/backpressure.py` — `BackpressurePolicy` enum + `BoundedQueue` thread-safe với 4 policy.

**Đã verify**: 11 test pass bao gồm concurrent producer/consumer + threading correctness.

---

## Recap Module 02 file 04

- 6 policy: DROP_OLDEST, DROP_NEWEST, BLOCK, SAMPLE, DEGRADE_QUALITY, REJECT.
- BLOCK forbidden cho RTSP (TCP Zero Window).
- vision_demo build 4 policy (skip SAMPLE và DEGRADE — đặc thù source-side).

---

## Phần 1 — BackpressurePolicy enum (5 phút)

```python
# src/vision_demo/kernel/backpressure.py (phần 1)
from enum import Enum


class BackpressurePolicy(Enum):
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"
    REJECT = "reject"
```

---

## Phần 2 — BoundedQueue (60 phút)

```python
# src/vision_demo/kernel/backpressure.py (phần 2)
from collections import deque
from threading import Condition, Lock
from typing import Generic, Optional, TypeVar


T = TypeVar("T")


class BoundedQueue(Generic[T]):
    """Thread-safe bounded queue với configurable backpressure policy.
    
    Metrics:
        - drops: count of items dropped (DROP_*).
        - rejects: count of REJECT failures.
        - block_timeouts: count of BLOCK timeouts.
    """
    
    def __init__(self, maxsize: int, policy: BackpressurePolicy):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._buf: deque[T] = deque()
        self._maxsize = maxsize
        self._policy = policy
        self._lock = Lock()
        self._not_empty = Condition(self._lock)
        self._not_full = Condition(self._lock)
        self.drops = 0
        self.rejects = 0
        self.block_timeouts = 0
    
    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """Try to put. Return True nếu inserted, False nếu drop/reject/timeout."""
        with self._lock:
            if len(self._buf) < self._maxsize:
                self._buf.append(item)
                self._not_empty.notify()
                return True
            
            if self._policy == BackpressurePolicy.DROP_OLDEST:
                self._buf.popleft()
                self._buf.append(item)
                self.drops += 1
                self._not_empty.notify()
                return True
            
            if self._policy == BackpressurePolicy.DROP_NEWEST:
                self.drops += 1
                return False
            
            if self._policy == BackpressurePolicy.REJECT:
                self.rejects += 1
                return False
            
            if self._policy == BackpressurePolicy.BLOCK:
                if not self._not_full.wait_for(
                    lambda: len(self._buf) < self._maxsize,
                    timeout=timeout,
                ):
                    self.block_timeouts += 1
                    return False
                self._buf.append(item)
                self._not_empty.notify()
                return True
            
            raise ValueError(f"Unknown policy: {self._policy}")
    
    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """Block waiting for item. Return None on timeout.
        
        WARNING: if your queue can legitimately contain `None` values, this
        sentinel collides with timeout. Prefer `get_or_raise(timeout)` in
        that case (raises `queue.Empty`).
        """
        with self._lock:
            if not self._not_empty.wait_for(
                lambda: len(self._buf) > 0,
                timeout=timeout,
            ):
                return None
            item = self._buf.popleft()
            self._not_full.notify()
            return item
    
    def get_or_raise(self, timeout: Optional[float] = None) -> T:
        """Block for item; raise queue.Empty on timeout (no None ambiguity)."""
        import queue as _queue
        with self._lock:
            if not self._not_empty.wait_for(
                lambda: len(self._buf) > 0,
                timeout=timeout,
            ):
                raise _queue.Empty
            item = self._buf.popleft()
            self._not_full.notify()
            return item
    
    def qsize(self) -> int:
        with self._lock:
            return len(self._buf)
    
    @property
    def policy(self) -> BackpressurePolicy:
        return self._policy
    
    @property
    def maxsize(self) -> int:
        return self._maxsize
```

**Decisions cốt lõi**:

### `Condition` over `Event`

`Condition` cho phép **nhiều condition** trên cùng lock:
- `_not_empty`: signal khi có item (consumer wake up).
- `_not_full`: signal khi có chỗ (BLOCK producer wake up).

`Event` chỉ 1 boolean → không phân biệt được "ai" đang chờ.

### `wait_for(predicate, timeout)` — robust

```python
self._not_full.wait_for(
    lambda: len(self._buf) < self._maxsize,
    timeout=timeout,
)
```

→ Wait until predicate True OR timeout. Tránh **spurious wakeup** (Python `Condition` có thể wake không lý do — `wait_for` re-check predicate).

### Metrics under lock

`self.drops += 1` được protect bởi `self._lock` (đã acquire). **Thread-safe** mà không cần atomic primitive.

→ R5 audit fix HI-OBS-01 (`type(self)._drops += 1` race condition) — nhưng ở đây mọi access đều under lock nên OK.

### Return semantics consistent

`put()` return:
- `True`: item inserted (có thể drop oldest, nhưng cuối cùng item caller's vào queue).
- `False`: caller's item KHÔNG vào queue (DROP_NEWEST, REJECT, BLOCK timeout).

→ Caller dễ check: `if not q.put(item): handle_failure()`.

---

## Phần 3 — Tests (45 phút)

11 test bao gồm:

### Policy basic (4)

```python
def test_drop_oldest_basic():
    q = BoundedQueue[int](maxsize=3, policy=BackpressurePolicy.DROP_OLDEST)
    
    for i in range(5):
        result = q.put(i)
        assert result is True   # always inserts (drops oldest)
    
    # Queue contains [2, 3, 4] (0 and 1 dropped).
    assert q.qsize() == 3
    assert q.drops == 2
    
    assert q.get() == 2
    assert q.get() == 3
    assert q.get() == 4
```

→ Test invariant: **5 puts → 3 in queue, 2 drops, FIFO preserved**.

### BLOCK behavior (2)

```python
def test_block_returns_when_consumer_takes():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.BLOCK)
    q.put(1)   # full
    
    def consumer():
        time.sleep(0.1)
        q.get()
    
    t = threading.Thread(target=consumer)
    t.start()
    
    start = time.monotonic()
    result = q.put(2, timeout=1.0)
    elapsed = time.monotonic() - start
    
    t.join()
    
    assert result is True
    assert 0.05 < elapsed < 0.5   # blocked, but not full timeout


def test_block_timeout_when_no_consumer():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.BLOCK)
    q.put(1)
    
    start = time.monotonic()
    result = q.put(2, timeout=0.2)
    elapsed = time.monotonic() - start
    
    assert result is False
    assert q.block_timeouts == 1
    assert 0.18 < elapsed < 0.5
```

→ Test BLOCK actually **blocks** + responds to consumer + respects timeout. Bug-free implementation.

### Concurrent stress (1)

```python
def test_concurrent_producer_consumer():
    """Producer thread + consumer thread → all items received correctly."""
    q = BoundedQueue[int](maxsize=10, policy=BackpressurePolicy.BLOCK)
    n = 100
    received = []
    
    def producer():
        for i in range(n):
            q.put(i, timeout=2.0)
    
    def consumer():
        for _ in range(n):
            item = q.get(timeout=2.0)
            if item is not None:
                received.append(item)
    
    p = threading.Thread(target=producer)
    c = threading.Thread(target=consumer)
    
    p.start()
    c.start()
    
    p.join(timeout=5)
    c.join(timeout=5)
    
    assert len(received) == n
    assert received == list(range(n))   # FIFO preserved
```

→ Stress test: 100 items, queue max 10 → producer block thường xuyên. **Nếu lock bug** → deadlock or lost items. Test pass = correctness.

### Run

```bash
pytest tests/test_step_07_backpressure.py -v
```

Expected: **11 passed in ~0.7s**.

---

## Self-check

1. **`Condition` vs `Event`** — khi nào chọn cái nào?

2. **`wait_for(predicate, timeout)`** — sao không dùng plain `wait()`? Spurious wakeup là gì?

3. **DROP_OLDEST có bug** nếu consumer cũng đang `get()` lúc producer `put()`?

4. **Sao test `test_block_returns_when_consumer_takes` cần `time.sleep(0.1)`** trong consumer?

5. **Bạn được giao thêm policy `SAMPLE rate=N`** — process every Nth item, drop rest. Logic đặt ở `BoundedQueue` hay producer code? Tại sao?

<details>
<summary>Đáp án</summary>

1. **Condition vs Event**:
   - **Event**: 1 boolean. "Ready or not". Wake all waiters.
   - **Condition**: gắn với Lock + predicate. Có thể `notify()` 1, `notify_all()`. Predicate-based wait.
   - **Khi**:
     - Event: "shutdown_requested" — toàn cục.
     - Condition: "queue not full" / "queue not empty" — predicate cụ thể.
   - Trong BoundedQueue: 2 condition (not_full, not_empty) cùng lock. Event không support pattern này.

2. **`wait_for` robust**:
   - **Spurious wakeup**: OS thread scheduler có thể wake thread without `notify()` (rare nhưng exists, đặc biệt POSIX `pthread_cond_wait`).
   - Plain `wait()` returns → caller phải re-check predicate. Code lặp `while not predicate: wait()` — verbose.
   - `wait_for(pred)` = `while not pred: wait()` built-in. Robust.

3. **No bug** — vì:
   - `put()` và `get()` đều acquire `self._lock`.
   - Tại 1 thời điểm chỉ 1 thread holds lock.
   - DROP_OLDEST: under lock, `popleft()` rồi `append()`. Atomic.
   - Consumer `get()` waits on `not_empty` → producer notify after append → consumer wake up → acquire lock → popleft.
   
   → Lock serialize all queue mutations. **Race-free**.

4. **`time.sleep(0.1)` purpose**:
   - Producer's `put(2, timeout=1.0)` blocks because queue full.
   - Consumer thread spawn → wait 0.1s → `get()` (frees space) → notify_full.
   - Producer wakes → acquire lock → put(2) → return True.
   - **Without sleep**: race — consumer might `get()` BEFORE producer's `put()` reaches blocking state. Test flaky.
   - 0.1s gives producer time to enter `wait_for` block first. Deterministic.

5. **SAMPLE policy placement**:
   - **Producer-side** (preferred): producer counter, skip every k-1 items. Don't even call `put()`. Save lock acquisition cost.
   - **Queue-side**: queue logic become complex (decide "skip" inside put?). Couples policy with queue.
   - Reason: SAMPLE = **source decision** ("I'll only emit 1/N"). Not queue's concern (queue knows about full/not-full).
   - DROP_OLDEST/NEWEST = queue policy (queue full → decide).
   - SAMPLE = source policy (source overproducing → throttle self).
   
   → Single Responsibility Principle. Queue handles "full", source handles "rate limit".

</details>

---

## Liên kết

- **Module 02 file 04** — backpressure theory.
- **Production**: `Vision_platform_architecture_design/06-resilience-and-shutdown/01-backpressurepolicy-per-source-enforcement.md`.

---

➡️ Tiếp theo: [`step-08-add-observability.md`](step-08-add-observability.md)
