# 05 — Circuit Breaker Math: jitter, half-open, staggered recovery

## Câu hỏi cốt lõi

> Circuit breaker = hidden in CR-INF-04 fix. Threshold tính bằng formula gì? Tại sao cần jitter? "Staggered recovery" giải quyết vấn đề gì?

## TL;DR (30s)

**Circuit breaker** = pattern để bảo vệ caller khỏi gọi service đang chết.

3 state:
- **CLOSED**: bình thường, gọi service.
- **OPEN**: service down (failures > threshold) → caller skip, fail-fast.
- **HALF_OPEN**: thử probe lần đơn để check service phục hồi chưa.

**Recovery jitter** ngăn 16 camera đồng thời probe → thundering herd.

→ Vision Platform: `StaggeredCircuitBreaker` với deterministic jitter per camera.

---


## Theory

### State machine

```
        ┌───── (failure_count >= threshold) ─────┐
        ↓                                        │
     ┌──────┐                                ┌────────┐
     │CLOSED│ ←── (probe success) ──────────│ HALF_  │
     │      │                                │ OPEN   │
     │normal│                                └────────┘
     │  op  │                                    ↑
     └──────┘                                    │
        │                                  (recovery_deadline reached)
        │                                        │
        ↓                                  ┌─────┴─────┐
        └──── (>= threshold failures) ────→│   OPEN    │
                                           │skip fast  │
                                           └───────────┘
```

### Why threshold?

Without circuit breaker:
- Service crashes.
- Camera 1 send request → timeout (5s).
- Camera 1 retry → timeout (5s).
- ... after 60s timeout cumulative, camera mới detect "service down".

With circuit breaker (threshold=5 failures):
- 5 failures → OPEN.
- Camera skip subsequent requests **without sending** → fail-fast (~ms).
- After recovery_period (default 30s) → HALF_OPEN → probe.
- Probe success → CLOSED.
- Probe fail → back to OPEN.

→ **Saves**: 16 cameras × 5s/timeout × 100 retries = thousands of wasted seconds.

### Threshold tuning

```python
threshold = max(3, expected_concurrent_requests * 0.05)
```

Logic:
- 5% of typical concurrent requests = "transient" rate.
- Above that → systemic problem.
- Min 3 to avoid trigger on flaky single request.

For Vision Platform:
- 16 cameras × 1 request in flight = 16 concurrent.
- 5% × 16 = 0.8 → use min 3.
- → `failure_threshold = 3` per camera works.

### Recovery period

```python
recovery_period = base_recovery_seconds + uniform(0, jitter_range_seconds)
```

- `base_recovery_seconds = 30` (typical).
- `jitter_range_seconds = 5` → random 0-5s additional.

### Why jitter?

Without jitter:
- 16 cameras hit threshold together (e.g. inference service crash).
- ALL go OPEN at t=0.
- ALL go HALF_OPEN at t=30 → 16 probe requests simultaneously.
- Service barely recovered → 16 simultaneous load → re-crash.
- → **Thundering herd**.

With jitter:
- 16 cameras OPEN at t=0.
- HALF_OPEN times: t=30+rand(0,5) → spread across 30-35s.
- Probe requests staggered → service handles 1-3/sec → no overload.

### Vision Platform: deterministic jitter per camera

```python
import hashlib

class StaggeredCircuitBreaker:
    def __init__(self, camera_id: str, base_recovery_s: float = 30.0,
                 jitter_range_s: float = 5.0):
        # Deterministic jitter — same camera always gets same offset,
        # ổn định CẢ GIỮA CÁC PROCESS và giữa các lần restart.
        seed = int.from_bytes(
            hashlib.sha256(camera_id.encode("utf-8")).digest()[:8], "big"
        )
        rng = random.Random(seed)
        self._jitter = rng.uniform(0, jitter_range_s)
```

→ Mỗi camera là 1 OS process riêng (bulkhead). Seed phải deterministic **cross-process**.

> ⚠️ **KHÔNG dùng `hash(camera_id)` cho mục đích này.** Python bật **hash randomization**
> (PYTHONHASHSEED) mặc định cho `str` từ 3.3 → `hash("cam_1")` **khác nhau mỗi lần khởi
> động process**. Vì mỗi camera chạy ở 1 process riêng, dùng `hash()` sẽ cho jitter **khác
> nhau mỗi lần restart** và **không reproducible trong test** — đúng ngược với mục tiêu.
> Verify nhanh: chạy `python -c "print(hash('cam_1'))"` hai lần → 2 giá trị khác nhau.
> Cách đúng: hàm hash ổn định như `hashlib.sha256(...)` (ở trên) hoặc `zlib.crc32(camera_id.encode())`.

→ **Reproducible**: với `hashlib`/`crc32`, test deterministic + production load distribution ổn định.

---

## Half-open probe pattern

### Why half-open?

Without half-open:
- After recovery_period → directly go CLOSED → send all requests.
- If service still down → all fail → back to OPEN immediately.
- Yo-yo: open ↔ closed every 30s.

With half-open:
- Send **single probe request**.
- Probe success → CLOSED (allow normal load).
- Probe fail → back to OPEN (extend recovery).
- Saves bulk traffic from hitting still-broken service.

### CR-INF-04 fix detail

Original bug: circuit breaker counted only retryable errors. Non-retryable (CUDA OOM, model corrupt) **didn't count** → never tripped breaker → cameras flooded broken service.

Fix:
```python
async def call_inference(self, client, request):
    if self._state == CircuitState.OPEN:
        if time.monotonic() < self.recovery_deadline:
            return CircuitBreakerOutcome.skip_circuit_open()
        self._state = CircuitState.HALF_OPEN
    
    try:
        response = await client.infer(request)
        if response.error is None:
            # SUCCESS — reset.
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failures = 0
            return CircuitBreakerOutcome.success(response)
        
        # ERROR — count BOTH retryable AND non-retryable.
        self._record_failure()
        return CircuitBreakerOutcome.inference_error(response)
    except (TimeoutError, ConnectionError) as e:
        self._record_failure()
        return CircuitBreakerOutcome.transport_error(e)
```

→ **Every error path** records failure. Reset only on `error is None`.

---

## Common mistakes

### Mistake 1: Reset on first success after open

```python
# WRONG
if response.error is None:
    self._failures = 0   # reset everywhere
```

→ During HALF_OPEN, single success may be coincidence (service partially recovered). Should reset only **after multiple successes** OR transition CLOSED first.

Vision Platform: success in HALF_OPEN → **transition to CLOSED**, then reset failures.

### Mistake 2: No jitter

→ Thundering herd as explained above.

### Mistake 3: Sync probe blocks

```python
# WRONG (blocks event loop)
def is_recovered(self):
    response = sync_probe()   # ← blocking
    return response.success
```

→ Vision Platform `StaggeredCircuitBreaker` is async-aware: probe via `await client.infer(...)`.

---

## Self-check

1. **Threshold = 3 failures** thay 100 — pros/cons?

2. **Jitter range too large** (e.g. 60s) — bug gì?

3. **HALF_OPEN cho 16 cameras đồng thời** — vẫn bug nếu probe fail? Tại sao?

4. **Half-open phụ thuộc 1 probe** — sao không probe 3 lần?

5. **CR-INF-04 fix**: tại sao non-retryable error CŨNG count? Phản ví dụ?

<details>
<summary>Đáp án</summary>

1. **Threshold 3**:
   - **Pros**: fast detect outage. Save 97% wasted retries (vs threshold 100).
   - **Cons**: false positive. Single transient blip (timeout) → trip → 30s wait. Annoying.
   - **Tuning**: depends on workload. Health-critical service: low threshold. Best-effort: higher.
   - Vision Platform: 3 OK because per-camera (16 cameras parallel = aggregate 48 retries before trip).

2. **Jitter 60s**:
   - Cameras OPEN simultaneously at t=0.
   - HALF_OPEN times spread 30-90s.
   - Detection latency for some cameras = 90s. Operator alert frustrated.
   - **Right size**: jitter ~ 10-20% of base_recovery. 30s base → 5-6s jitter typical.

3. **Probe fail in HALF_OPEN**:
   - Single failure in HALF_OPEN → back to OPEN. Add new recovery_period (30s + jitter).
   - **Bug-free** — system designed for this. State machine clean.
   - But if **always probe fail** → camera permanently OPEN. Operator must investigate (alert).

4. **Probe N=1**:
   - **Pros**: 1 probe = minimal load. Recover service from 1 success — efficient.
   - **Cons**: false positive (1 lucky success while service still broken).
   - **Workaround**: reset `failures = max(0, failures - 1)` per probe success → need 3 successes to fully reset. Or transition CLOSED but keep `_consecutive_successes` counter.
   - Vision Platform: simple "1 success → CLOSED". Production trusted because retry logic at higher layer also catches.

5. **Non-retryable count**:
   - **Without count**: CUDA OOM = service down → never trips breaker → camera always send → all fail.
   - **With count**: 3 CUDA OOM → trip → save next 30s of failed requests.
   - **Phản ví dụ — bad-input error**: input shape error là caller's bug, không phải service's. Nếu nhiều requests có bad shape, breaker trip → other valid requests bị blocked oan.
   - **Vision Platform's pragmatic decision**: count cả 2 loại to be safe. Lý do:
     - Đa số "non-retryable" thật sự là service-side (CUDA OOM, model crash, GPU thermal). Đây nên trip breaker.
     - Bad-input errors hiếm trong production (callers đã pass schema validation). Nếu xảy ra → 1 caller's bug → trip breaker → operator alert sớm = positive signal.
     - Refinement tương lai: dùng `InferenceError.retryable=False` + `error_type` whitelist (`InvalidInputShape`, `UnsupportedFormat`) → không count. Khi traffic mix có nhiều bad-input legit (e.g. multi-tenant), refinement có giá trị.
   - **Code thực tế** (xem block code ở trên): every error counts. Tradeoff đã chọn = simplicity + safety bias over precision.

</details>

---

## Liên kết

- **Production**: `Vision_platform_architecture_design/05-inference-and-ipc/09-ha-mode.md` — full StaggeredCircuitBreaker implementation.
- **Reference**: Hystrix (Netflix) circuit breaker pattern.

---

## Tóm tắt 1 câu

> **Circuit breaker = 3 state (CLOSED/OPEN/HALF_OPEN). Threshold tunable per workload. Jitter ngăn thundering herd 16 cameras simultaneous probe. R5: every error counts, reset only on success.**

➡️ Tiếp theo: [`06-traceback-memory-retention.md`](06-traceback-memory-retention.md)
