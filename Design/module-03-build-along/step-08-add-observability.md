# Step 08 — Observability: structlog + log_context + InMemoryMetrics

## Mục tiêu (2h)

Build observability foundation:

1. `runtime/observability.py` — structlog setup + `log_context` ContextManager + `InMemoryMetrics`.

**Đã verify**: 12 test pass.

---

## Recap concept

3 pillars of observability:

| Pillar | Tool | Purpose |
|--------|------|---------|
| **Logs** | structlog | Tracing events, debugging |
| **Metrics** | counter/gauge/histogram | Aggregate behavior |
| **Traces** | OpenTelemetry (production) | Cross-process flow |

vision_demo: logs + metrics. Traces là Module 04 deep dive.

---

## Phần 1 — Cross-process log context (45 phút)

### Vấn đề

Camera 1 process logs:
```
{"event": "frame_received", "timestamp": "..."}
{"event": "detection_started", "timestamp": "..."}
{"event": "frame_processed", "timestamp": "..."}
```

→ Không biết frame nào của camera nào! Cần `camera_id` field.

**Cách dở**: pass `camera_id` mọi log call:
```python
logger.info("frame_received", camera_id="cam_1")
logger.info("detection_started", camera_id="cam_1")
# ... pollute mọi line ...
```

**Cách đúng**: `contextvars` + structlog processor.

```python
# src/vision_demo/runtime/observability.py
"""Observability: structlog setup + log context + metrics."""
from __future__ import annotations
import contextvars
from collections import defaultdict
from threading import Lock
from typing import Any

import structlog


# Context vars cho cross-cutting log fields.
_camera_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "camera_id", default=None,
)
_packet_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "packet_id", default=None,
)
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None,
)


def _add_context_vars(_, __, event_dict: dict) -> dict:
    """structlog processor: inject contextvars vào mỗi log line."""
    cid = _camera_id_var.get()
    pid = _packet_id_var.get()
    rid = _request_id_var.get()
    if cid:
        event_dict["camera_id"] = cid
    if pid:
        event_dict["packet_id"] = pid
    if rid:
        event_dict["request_id"] = rid
    return event_dict


class log_context:
    """Context manager bind contextvars cho duration của block.
    
    Usage:
        with log_context(camera_id="cam_1", packet_id="pkt_42"):
            logger.info("frame_received")
            # → log line tự có camera_id và packet_id
    """
    
    def __init__(self, *, camera_id=None, packet_id=None, request_id=None):
        self._kwargs = {
            "camera_id": camera_id,
            "packet_id": packet_id,
            "request_id": request_id,
        }
        self._tokens: list = []
    
    def __enter__(self):
        if self._kwargs["camera_id"] is not None:
            self._tokens.append(_camera_id_var.set(self._kwargs["camera_id"]))
        if self._kwargs["packet_id"] is not None:
            self._tokens.append(_packet_id_var.set(self._kwargs["packet_id"]))
        if self._kwargs["request_id"] is not None:
            self._tokens.append(_request_id_var.set(self._kwargs["request_id"]))
        return self
    
    def __exit__(self, *args):
        # Reset theo thứ tự LIFO (ngược insertion): token set sau cùng phải
        # được reset trước, để contextvar khôi phục đúng giá trị trước đó khi
        # các log_context lồng nhau. reversed() đảm bảo điều này.
        for token in reversed(self._tokens):
            token.var.reset(token)
```

**Decisions**:

### `contextvars` vs threadlocal

- **threadlocal**: per-thread storage. Async pollute (1 task ~ multiple awaits).
- **contextvars**: per-context (works với asyncio, threading, sync). Modern.

→ Vision Platform có thể chạy async/threaded — `contextvars` consistent.

### Tokens for reset

```python
token = _camera_id_var.set("cam_1")   # returns Token
# ...
token.var.reset(token)  # restore previous value
```

→ Nested `log_context` work correctly:
```python
with log_context(camera_id="A"):
    # camera_id = "A"
    with log_context(camera_id="B"):
        # camera_id = "B"
        ...
    # camera_id = "A" (restored)
# camera_id = None (restored)
```

### Processor pattern

structlog processors là **chain functions**:
```python
log_record → add_log_level → TimeStamper → _add_context_vars → JSONRenderer → output
```

Mỗi processor mutate event_dict, pass downstream. `_add_context_vars` inject contextvar values.

---

## Phần 2 — setup_logging (15 phút)

```python
def setup_logging(level: str = "INFO") -> None:
    """Configure structlog. Call once per process at startup."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context_vars,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), level.upper(), 20),
        ),
        cache_logger_on_first_use=True,
    )
```

**Decisions**:

- **JSONRenderer**: structured output. Loki/ELK/Datadog parse được.
- **`cache_logger_on_first_use=True`**: performance. Logger object cached per name.
- **`make_filtering_bound_logger`**: filter by level early (don't format if WARNING level + DEBUG message).

### Note vs production

vision_demo simplified. Production Vision Platform (file `08-observability.md`):
- `_BoundedQueueHandler` non-blocking enqueue (HI-OBS-01 fix).
- `RotatingFileHandler` size-based rotation (HI-OBS-02 fix).
- `LoggingHandle.shutdown()` flush queue on cascade.

vision_demo skip cho gọn — đủ học pattern `contextvars` + processor.

---

## Phần 3 — InMemoryMetrics (45 phút)

```python
class InMemoryMetrics:
    """Simple in-memory metrics. Threadsafe.
    
    For production: replace with Prometheus / StatsD adapter.
    """
    
    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
    
    def counter(self, name: str, value: float = 1.0, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += int(value)
    
    def gauge(self, name: str, value: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value
    
    def histogram(self, name: str, value: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
    
    def get_counter(self, name: str, **labels) -> int:
        with self._lock:
            return self._counters[self._key(name, labels)]
    
    def get_gauge(self, name: str, **labels) -> float | None:
        with self._lock:
            return self._gauges.get(self._key(name, labels))
    
    def get_histogram(self, name: str, **labels) -> list[float]:
        # MUST hold lock — list(deque) iterates; concurrent histogram() append
        # would race (RuntimeError: deque mutated during iteration).
        with self._lock:
            return list(self._histograms[self._key(name, labels)])
    
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: list(v) for k, v in self._histograms.items()},
            }
    
    @staticmethod
    def _key(name: str, labels: dict) -> str:
        if not labels:
            return name
        labelstr = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{labelstr}}}"
```

**Decisions**:

### Counter / Gauge / Histogram — 3 types

- **Counter**: only increases (frames_processed_total).
- **Gauge**: can go up/down (queue_depth).
- **Histogram**: distribution of values (stage_latency_ms).

→ Mỗi type có aggregation khác nhau. Prometheus exporter tương tự.

### Labels for cardinality

```python
metrics.counter("frames_processed", camera_id="cam_1", status="success")
metrics.counter("frames_processed", camera_id="cam_1", status="dropped")
metrics.counter("frames_processed", camera_id="cam_2", status="success")
```

→ 3 keys riêng biệt:
```
frames_processed{camera_id=cam_1,status=success}: count
frames_processed{camera_id=cam_1,status=dropped}: count
frames_processed{camera_id=cam_2,status=success}: count
```

→ Compatible với Prometheus query: `sum by (camera_id) (rate(frames_processed[1m]))`.

### Cardinality budget

**Đừng dùng** unbounded labels:
```python
metrics.counter("frames_processed", packet_id=packet_id)  # ← BAD
```

→ Mỗi packet_id = 1 unique key → millions of keys → Prometheus OOM.

→ Quy tắc: labels phải là **bounded set** (camera_id < 100, status < 10, ...).

### `snapshot()` independent copy

```python
def snapshot(self):
    with self._lock:
        return {
            "counters": dict(self._counters),   # ← copy dict
            "histograms": {k: list(v) for k, v in self._histograms.items()},  # ← copy list
        }
```

→ Caller nhận snapshot không phụ thuộc internal state. Mutate snapshot không ảnh hưởng metrics.

---

## Phần 4 — Tests (15 phút)

12 test bao gồm:

### Metrics (6)

- counter basic, counter with labels, gauge overwrites, histogram appends.
- thread-safe (10 threads × 100 ops = 1000 expected, no lost increments).
- snapshot independent copy.

### log_context (4)

- set/restore, nested, multi-field, partial fields.

### Logger integration (2)

- `setup_logging` doesn't crash.
- Logger output includes context vars (use captured processor).

Test threading:
```python
def test_metrics_thread_safe():
    """Concurrent counter increments must not lose updates."""
    m = InMemoryMetrics()
    n_threads = 10
    n_per_thread = 100
    
    def worker():
        for _ in range(n_per_thread):
            m.counter("ops")
    
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert m.get_counter("ops") == n_threads * n_per_thread
```

→ Without lock = race condition = lost increments. **Lock provides atomicity**.

**Run**:
```bash
pytest tests/test_step_08_observability.py -v
```

Expected: **12 passed in ~0.5s**.

---

## Self-check

1. **`contextvars` vs `threading.local`** — khi nào không thể dùng threading.local?

2. **`log_context` nested** — sao restore đúng order matter?

3. **Cardinality**: bạn được giao log mỗi detection. Đặt detection bbox coords vào label OK không? Tại sao?

4. **Counter vs Gauge** — list 3 metric Vision Platform mỗi loại.

5. **`snapshot()` copy lists** — sao quan trọng? Cho 1 bug nếu trả ref trực tiếp.

<details>
<summary>Đáp án</summary>

1. **threading.local KHÔNG dùng được khi**:
   - **asyncio**: 1 thread chạy nhiều task (coroutine). threading.local share giữa task → context bleed.
   - **Concurrent futures**: thread-pool re-uses thread → state pollute task khác.
   - **Process pool**: subprocess không inherit threading.local của parent.
   
   `contextvars` (Python 3.7+) work cho cả async + thread + process boundaries (mỗi process tự có context tree).

2. **Restore order**:
   - LIFO order. `with A: with B: ...` exit → reset B trước A.
   - Nếu reset A trước B: token A's `previous_value` đã stale (bị B overwrite).
   - Code: token list đẩy theo order set, exit pop reverse.

3. **Bbox coords as label = BAD**:
   - Cardinality explosion. Bbox `(x=12.345, y=67.890, ...)` ~ unique mỗi frame.
   - 30 fps × 60 sec × 16 cam = 28800 unique labels/min → Prometheus OOM trong vài giờ.
   - **Đúng**: label `camera_id`, `class` (bounded). Coords vào **logs** (high cardinality OK trong logs).

4. **Counter** (only increase):
   - `frames_processed_total{camera_id, status}`
   - `inference_requests_total{result}`
   - `dlq_writes_total{error_type}`
   
   **Gauge** (up/down):
   - `inference_queue_depth`
   - `gpu_memory_used_bytes`
   - `active_camera_count`

5. **Snapshot bug nếu return ref**:
   ```python
   def snapshot(self):
       return {
           "counters": self._counters,   # ← ref, not copy
           ...
       }
   
   snap = m.snapshot()
   snap["counters"]["test"] = 999  # ← mutate caller's dict
   m.get_counter("test")  # → 999! Polluted!
   
   # Worse: concurrent mutations during read.
   for k, v in snap["counters"].items():   # iterate
       process(k, v)   # ← if other thread adds key during iter → RuntimeError
   ```
   
   → Defensive copy in snapshot() makes caller's view stable.

</details>

---

## Liên kết

- **Module 02 file 05** — context vars là pattern immutability cho per-request data.
- **Production**: `Vision_platform_architecture_design/08-observability/`.

---

➡️ Tiếp theo: [`step-09-add-shutdown.md`](step-09-add-shutdown.md)
