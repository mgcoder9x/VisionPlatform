# 03 — ZMQ Patterns Comparison: PUB/SUB vs REQ/REP vs ROUTER/DEALER

## Câu hỏi cốt lõi

> Vision Platform dùng ROUTER/DEALER cho inference. Tại sao không PUB/SUB hoặc REQ/REP? Mỗi pattern phù hợp khi nào?

## TL;DR (30s)

| Pattern | Async? | Correlation? | Multi-recipient? | Use case |
|---------|--------|--------------|------------------|----------|
| **REQ/REP** | ❌ Sync (blocking) | ✓ implicit | ❌ 1-1 | RPC đơn giản |
| **PUB/SUB** | ✓ Fire-forget | ❌ | ✓ broadcast | Health signal, config update |
| **PUSH/PULL** | ✓ Fire-forget | ❌ | ✓ work distribution | Task queue đơn giản |
| **ROUTER/DEALER** | ✓ Async | ✓ explicit (identity) | ✓ N-to-M | RPC với correlation, retry, async |

→ Vision Platform inference = **request/response with correlation, async, retry-able** → ROUTER/DEALER.

---

## Pattern 1: REQ/REP

### Topology

```
[Client REQ] ←──── (sync round trip) ────→ [Server REP]
```

### Code

```python
# Server
import zmq
ctx = zmq.Context()
sock = ctx.socket(zmq.REP)
sock.bind("tcp://*:5555")

while True:
    msg = sock.recv()      # ← BLOCK until request
    response = process(msg)
    sock.send(response)    # ← BLOCK until sent

# Client
sock = ctx.socket(zmq.REQ)
sock.connect("tcp://localhost:5555")

sock.send(b"request")
reply = sock.recv()        # ← BLOCK until reply
```

### Strict ordering

ZMQ REQ/REP enforces **send → recv → send → recv → ...** alternation. Try `sock.send(); sock.send()` → ZMQ error: "Cannot send another request without receiving reply first".

### Pros / Cons

- **Pros**: simple, ordered, automatic correlation (1 reply per 1 request).
- **Cons**:
  - **Synchronous** — single-threaded server can only serve 1 client at a time.
  - **Blocking** — slow server hangs all clients.
  - **No timeout natively** — must use `setsockopt(zmq.RCVTIMEO, ...)`.
  - **No retry** — if server crashes mid-reply, client hangs forever.

### When to use

- RPC đơn giản, low-latency, 1 server.
- Test/dev tool.
- Microservice cần immediate response.

### When NOT to use (Vision Platform inference)

- Multi-camera (16) cần inference đồng thời.
- Inference latency biến động (8-50ms) → block all cameras = thảm hoạ.
- Need retry/timeout.

---

## Pattern 2: PUB/SUB

### Topology

```
                     ┌→ [SUB 1]
[PUB] ──── topics ───┼→ [SUB 2]
                     └→ [SUB 3]
```

### Code

```python
# Publisher
sock = ctx.socket(zmq.PUB)
sock.bind("tcp://*:5556")

while True:
    sock.send_multipart([b"camera.health", msgpack.packb({"queue_depth": 5})])
    time.sleep(1)

# Subscriber
sock = ctx.socket(zmq.SUB)
sock.connect("tcp://localhost:5556")
sock.setsockopt(zmq.SUBSCRIBE, b"camera.health")

while True:
    topic, msg = sock.recv_multipart()
    health = msgpack.unpackb(msg)
    react(health)
```

### Slow Joiner Problem

Publisher publishes 100 messages before subscriber connects → subscriber misses 100 messages. **No replay**.

→ Subscribers connecting late = data loss.

### Pros / Cons

- **Pros**:
  - 1-to-many fan-out.
  - Topic filter at subscriber.
  - Async fire-and-forget.
- **Cons**:
  - **No correlation** — publisher doesn't know who received what.
  - **No reliability** — slow joiner loses, slow consumer drops.
  - **No back-pressure** — publisher continues even if subscriber overloaded.

### When to use

- **Health signal**: inference service → cameras "I'm overloaded".
- **Config update**: control plane → all workers.
- **Metrics**: app → monitoring system.

→ Vision Platform dùng PUB/SUB cho health signal (file 06-resilience).

### When NOT to use

- Need correlation (request → specific response).
- Need reliability (every message must arrive).
- Need order across multiple publishers.

---

## Pattern 3: PUSH/PULL (work distribution)

### Topology

```
[PUSH] ──── round-robin ───→ [PULL 1]
                          └→ [PULL 2]
                          └→ [PULL 3]
```

### Code

```python
# Producer (PUSH)
sock = ctx.socket(zmq.PUSH)
sock.bind("tcp://*:5557")

for task in tasks:
    sock.send(task)

# Worker (PULL)
sock = ctx.socket(zmq.PULL)
sock.connect("tcp://localhost:5557")

while True:
    task = sock.recv()
    result = process(task)
    # ... where to send result? PUSH/PULL is one-way!
```

### Pros / Cons

- **Pros**: simple round-robin task distribution, fair load balancing.
- **Cons**:
  - **One-way** — no reply path.
  - **No correlation** — workers don't know which task they got.
  - **No back-pressure** at producer (HWM but no signal back).

### When to use

- Embarrassingly parallel work distribution (image batch processing where workers independent).
- Need fair load balance.

### When NOT to use Vision Platform inference

- Need response back (detection results).
- Need correlation (which camera's request).

---

## Pattern 4: ROUTER/DEALER (Vision Platform's choice)

### Topology

```
[DEALER 1 (cam_1)] ──┐                       ┌──→ same cam_1
[DEALER 2 (cam_2)] ──┼──→ [ROUTER (service)]─┼──→ same cam_2
[DEALER N (cam_N)] ──┘                       └──→ same cam_N
```

### Key feature: identity

ROUTER tracks each connection's **identity** (auto-generated or set explicitly). When ROUTER receives message, frame 0 = sender identity. When ROUTER replies, frame 0 = recipient identity.

→ Server can address specific client. Multi-client async.

### Code

```python
# Server (ROUTER)
sock = ctx.socket(zmq.ROUTER)
sock.bind("tcp://*:5558")

while True:
    identity, _empty, payload = sock.recv_multipart()
    # ... process async ...
    sock.send_multipart([identity, b"", response])

# Client (DEALER)
sock = ctx.socket(zmq.DEALER)
sock.setsockopt(zmq.IDENTITY, b"cam_1")  # explicit ID
sock.connect("tcp://localhost:5558")

# Send N requests in flight (no wait!)
for i in range(N):
    sock.send_multipart([b"", msgpack.packb({"req_id": i, ...})])

# Receive responses (any order)
for _ in range(N):
    _empty, payload = sock.recv_multipart()
    response = msgpack.unpackb(payload)
    # response["req_id"] = which one
```

### Pros / Cons

- **Pros**:
  - **Async** — DEALER send N requests, receive N responses any order.
  - **Identity** — server can target specific client.
  - **Correlation** via custom `request_id` field — client matches reply.
  - **Multi-server** — DEALER round-robin across multiple ROUTER (HA setup).
  - **Backpressure** via HWM (high water mark) at socket.
- **Cons**:
  - More complex (manual identity, multi-frame messages).
  - Programmer responsible for correlation logic.

### Vision Platform usage

```python
# Camera (DEALER)
self._dealer = ctx.socket(zmq.DEALER)
self._dealer.setsockopt(zmq.IDENTITY, f"cam_{cam_id}".encode())
self._dealer.connect(inference_endpoint)

async def infer(self, request: InferenceRequest) -> InferenceResponse:
    request_id = str(uuid.uuid4())
    future = asyncio.Future()
    self._pending[request_id] = future
    
    await self._dealer.send_multipart([b"", request_to_wire(request, request_id)])
    
    # Async wait for response.
    return await asyncio.wait_for(future, timeout=request.deadline_budget_ms / 1000)


# Receive loop (separate task)
async def _receive_loop(self):
    while True:
        _empty, payload = await self._dealer.recv_multipart()
        response = response_from_wire(payload)
        # Lookup pending future by request_id and resolve.
        future = self._pending.pop(response.request_id, None)
        if future is not None:
            future.set_result(response)
```

→ N requests in flight. Each future resolves when matching response arrives. **Async + correlated**.

---

## Quick decision tree

```
Need response back?
├─ NO → 1-to-many?
│       ├─ YES → PUB/SUB
│       └─ NO  → PUSH/PULL
│
└─ YES → Sync OK?
         ├─ YES → REQ/REP
         └─ NO  → ROUTER/DEALER
```

For Vision Platform inference: **NO sync OK** (multi-camera concurrent, latency bound) → ROUTER/DEALER.
For Vision Platform health signal: **NO response needed** + 1-to-many → PUB/SUB.
For Vision Platform shutdown command: 1 broadcast + ack → PUB/SUB or REQ/REP per worker.

---

## Real Vision Platform setup

```
┌────────────────────────────────────────────────────────────┐
│ Inference Service (process)                                │
│ ┌────────────┐                              ┌──────────┐   │
│ │ ROUTER     │←──── tcp://*:5558 ─────────→│ Detector │   │
│ │ recv loop  │                              │  (GPU)   │   │
│ │ batch      │                              └──────────┘   │
│ │ respond    │                                              │
│ └────────────┘                                              │
│       ↑                                                     │
│       │  PUB ── tcp://*:5559 ──→ health signal             │
│       │                                                     │
└───────┴─────────────────────────────────────────────────────┘
        ↑
        │ DEALER N camera processes
        │
┌───────┼─────────────────────────────────────────────────────┐
│       │                                                     │
│ Camera 1 process     Camera 2 process    ...                │
│ ┌────────────┐       ┌────────────┐                        │
│ │ DEALER     │       │ DEALER     │                        │
│ │ id=cam_1   │       │ id=cam_2   │                        │
│ │ pending    │       │ pending    │                        │
│ │ correlate  │       │ correlate  │                        │
│ └────────────┘       └────────────┘                        │
│                                                             │
│ + SUB ←── tcp://...:5559 ──── health signal                 │
└─────────────────────────────────────────────────────────────┘
```

→ Tham khảo `Vision_platform_architecture_design/05-inference-and-ipc/06-zmq-router-dealer.md`.

---

## Self-check

1. **REQ/REP strict ordering** — bug gì xảy ra khi violate (`send; send` no recv)?

2. **PUB/SUB slow joiner** — cách nào ngăn data loss?

3. **PUSH/PULL** sao không phù hợp cho Vision Platform inference?

4. **ROUTER tracks identity** — có thể N camera DEALER cùng identity không? Bug gì?

5. **HWM (high water mark)** — là gì? PUB/SUB vs ROUTER/DEALER xử lý HWM khác nhau ra sao?

<details>
<summary>Đáp án</summary>

1. **REQ/REP violation**:
   - ZMQ REQ socket strict state machine: send → wait → recv → send → ...
   - `send; send` → ZMQ error EFSM ("Operation cannot be performed in this state").
   - **Fix**: dùng DEALER thay REQ nếu cần multiple in-flight requests.

2. **Slow joiner mitigation**:
   - **Late join LWM (Last Will Message)**: subscriber declares "send me last N messages on connect" — but ZMQ doesn't support natively.
   - **Replay log**: publisher logs to disk, subscriber on connect requests replay. Complex.
   - **Snapshot + delta**: publisher periodically dumps full state via REQ/REP, then deltas via PUB/SUB. Pattern named **Clone** (ZMQ guide chapter 5).
   - **For Vision Platform health**: NOT critical — health signal is rolling (next message in 100ms). Slow joiner gets next message OK.

3. **PUSH/PULL inference**:
   - One-way → no response path. Detection results need to return to camera process.
   - No correlation → camera doesn't know which response is its request.
   - Workaround: PUSH/PULL request channel + PULL/PUSH response channel — but then 2 sockets per camera → complex.
   - ROUTER/DEALER built for this exact use case.

4. **N camera same identity**:
   - ZMQ ROUTER auto-generates identity if not set. With explicit `cam_1`:
     - 2 DEALER both `id=cam_1` connect to same ROUTER.
     - Older connection drops (default) — last wins. ZMQ_ROUTER_HANDOVER socket option.
     - Or with `zmq.ROUTER_HANDOVER=0` (default off): ROUTER raises error on duplicate.
   - **Bug**: camera 1 disconnect+reconnect (network blip) → new connection drops old. Pending replies lost.
   - **Fix**: unique identity per connection (e.g. `f"cam_{cam_id}_{uuid4()}"`).

5. **HWM (high water mark)**:
   - Per-socket buffer cap. Once reached, ZMQ either:
     - **PUB/SUB**: drops messages silently.
     - **PUSH/DEALER/REQ**: blocks send (default) or returns EAGAIN.
   - Set: `sock.setsockopt(zmq.SNDHWM, 1000)` / `zmq.RCVHWM`.
   - **Vision Platform**: explicit HWM tuning per socket. Default 1000 messages. Adjust based on testing.
   - **PUB/SUB**: drop = data loss → fine for health signals (rolling).
   - **ROUTER/DEALER**: block = backpressure → caller's `send_multipart` can fail/block. Important.

</details>

---

## Liên kết

- **Production**: `Vision_platform_architecture_design/05-inference-and-ipc/06-zmq-router-dealer.md`.
- **Reference**: ZMQ Guide (zguide.zeromq.org) — chapters 1-3 cover patterns.

---

## Tóm tắt 1 câu

> **REQ/REP sync — RPC đơn giản. PUB/SUB async fire-forget — broadcast. PUSH/PULL one-way work distribution. ROUTER/DEALER async với identity-based correlation — Vision Platform inference.**

➡️ Tiếp theo: [`04-asyncio-event-loop-mental-model.md`](04-asyncio-event-loop-mental-model.md)
