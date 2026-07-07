## CR-RT-03 — BLOCK Policy on RTSP → TCP Zero Window Cascade

**Severity**: HIGH. Production-killing.

---

## Setup (3 phút) — Mental experiment

Camera RTSP push 30 fps via TCP. Pipeline consumer slow (GPU thermal throttle). Backpressure policy = BLOCK (default in many frameworks).

```python
class CameraReader:
    def __init__(self, queue, policy=BackpressurePolicy.BLOCK):
        self._cap = cv2.VideoCapture(rtsp_url)
        self._queue = queue
        self._policy = policy
    
    def read_loop(self):
        while True:
            ret, frame = self._cap.read()
            
            if self._policy == BackpressurePolicy.BLOCK:
                self._queue.put(frame)  # ← blocks if queue full
            else:
                # DROP_OLDEST etc.
                ...
```

→ Producer (camera reader) blocks on `queue.put()` waiting consumer.

→ Producer doesn't read TCP socket → kernel buffer fills.

→ Cascade follows...

---

## Bug story

**Production scenario**: 16 RTSP cameras to Vision Platform. GPU usage steady ~70%, latency p99 = 25ms.

- **3:00 AM**: Server room AC fails. GPU temp rises 75°C → 92°C.
- **3:05 AM**: GPU thermal throttle 50%. Inference latency 25ms → 50ms.
- **3:08 AM**: Camera 1 backpressure queue full (BLOCK policy). Camera 1 reader blocks.
- **3:09 AM**: Camera 1 RTSP TCP connection — kernel RX buffer fills (no one reading).
- **3:09 AM**: TCP advertise window=0 to camera firmware. Camera 1 server sees ZERO_WINDOW.
- **3:10 AM**: Camera 1 firmware behavior: drop I-frames server-side. Connection becomes useless (P-frames have no reference).
- **3:11 AM**: Camera 1 firmware times out, **disconnects TCP**.
- **3:11 AM**: Vision Platform reconnects camera 1.
- **3:12 AM**: Camera 2 same scenario (queue still full).
- **3:13 AM**: 16 cameras simultaneously disconnect (all reached threshold same time).
- **3:13 AM**: All 16 cameras simultaneously reconnect → **thundering herd**.
- **3:14 AM**: Server CPU spikes from 16 simultaneous reconnects + TLS handshakes. Inference service starvation.
- **3:15 AM**: Pipeline collapse. Detection rate 0.

### Investigation

- `tcpdump` reveals ZERO_WINDOW from server, server-side dropped frames.
- `iperf3` test confirms TCP RX buffer full.
- Camera firmware logs (vendor): "RTSP client unresponsive, disconnect".

→ Root cause: **BLOCK policy + RTSP** = cascading TCP failure.

---

## Why it happened (root cause)

### Mental model sai

Junior dev assumed:
```
"Backpressure = block producer = stop sending. Simple and lossless."
```

**Reality** for RTSP/network producers:
- Producer = remote camera firmware. Cannot "tell" it to stop.
- Producer pushes via TCP. Backpressure happens at **TCP layer** automatically.
- TCP backpressure = ZERO_WINDOW → camera firmware reaction varies (drop, disconnect, halt).

### TCP Zero Window mechanism

Standard TCP flow control:
1. Receiver advertises **receive window** (RWND) in ACKs.
2. Sender bounded by RWND — won't send more.
3. If receiver process slow → kernel RX buffer fills → RWND shrinks toward 0.
4. RWND = 0 → sender must wait for window update.

For RTSP camera:
- Camera = sender.
- Vision Platform reader = receiver.
- Reader blocks on `queue.put()` → not reading TCP socket → kernel buffer fills → window=0.
- Camera firmware sees ZERO_WINDOW persistent → behavior implementation-specific:
  - **Hikvision**: drop frames server-side, log warning.
  - **Axis**: send keep-alive, eventually disconnect.
  - **Dahua**: reduce framerate, then disconnect.
  - **Generic ONVIF**: depends on implementation.

→ **Vision Platform has NO control** over camera-side behavior. Cannot guarantee lossless.

### Why thundering herd

If event correlated (server thermal, network congestion), all 16 cameras hit ZERO_WINDOW threshold simultaneously. All disconnect within seconds. Reconnect strategy without jitter → all reconnect simultaneously.

= **synchronized failure**. Worse than independent random failures.

---

## Fix (CR-RT-03 implemented)

### Solution: ban BLOCK for RTSP at config time

```python
# config validator
class ProfileValidator:
    """Enforce backpressure policy whitelist per source type."""
    
    POLICY_WHITELIST = {
        "rtsp": {DROP_OLDEST, DROP_NEWEST, SAMPLE, DEGRADE_QUALITY},  # NOT BLOCK
        "video_file": {BLOCK, DROP_OLDEST, DROP_NEWEST, SAMPLE},      # BLOCK OK for file
        "webcam": {DROP_OLDEST, DROP_NEWEST, SAMPLE},                 # BLOCK risky
        "image_folder": {BLOCK, REJECT},                              # BLOCK OK
        "http_upload": {REJECT, BLOCK},                               # REJECT preferred
    }
    
    @classmethod
    def validate(cls, config):
        for source in config.sources:
            policy = source.backpressure.policy
            allowed = cls.POLICY_WHITELIST.get(source.type, set())
            if policy not in allowed:
                raise ConfigError(
                    f"Source '{source.id}' (type={source.type}): "
                    f"policy={policy} not allowed. Allowed: {allowed}"
                )
```

→ **Config-time validation**. Operator cannot accidentally configure BLOCK for RTSP.

### Why config-time, not runtime warning

- Runtime warning: ignored, may slip to prod.
- Config-time error: **blocks deployment**. Force fix.

### Why DROP_OLDEST default for RTSP

- "Real-time view": new frame more useful than old.
- Bounded memory.
- Bounded latency.
- Predictable behavior.

---

## Alternative fixes (rejected)

### Reject 1: Increase queue size

```python
queue = Queue(maxsize=10_000)  # huge buffer
```

Pros: BLOCK rarely triggers.
Cons:
- 10000 × 6MB = 60GB memory.
- Latency: 10000 frames / 30fps = 5+ minutes "old" frames.
- Detection of 5 minutes ago = useless for security.

→ **Rejected**. Buffer is delay, not solution.

### Reject 2: Use UDP RTSP

Pros: no TCP backpressure.
Cons:
- UDP packet loss. Frame loss probabilistic.
- Some cameras don't support.
- NAT traversal harder.

→ **Acceptable for specific deployments**. Not general solution.

### Reject 3: Buffer to disk

Pros: bounded memory.
Cons:
- Disk fill. Extreme latency.
- I/O cost rivals real-time budget.

→ **Rejected**. Disk is not real-time.

### Reject 4: Runtime warning + recover

```python
if policy == BLOCK and source_type == "rtsp":
    logger.warning("BLOCK on RTSP risky, monitor")
```

Pros: flexibility.
Cons: warning ignored, prod incident still happens.

→ **Rejected**. Hard error preferred.

---

## Prevention

### Test pattern

```python
def test_profile_validator_rejects_block_on_rtsp():
    """CR-RT-03 regression test."""
    config = AppConfig(
        sources=[
            SourceConfig(
                id="cam_1", type="rtsp",
                backpressure=BackpressureConfig(policy=BackpressurePolicy.BLOCK),
            ),
        ],
    )
    
    with pytest.raises(ConfigError, match="BLOCK.*rtsp.*not allowed"):
        ProfileValidator.validate(config)


def test_profile_validator_accepts_drop_oldest_on_rtsp():
    config = AppConfig(
        sources=[
            SourceConfig(
                id="cam_1", type="rtsp",
                backpressure=BackpressureConfig(policy=BackpressurePolicy.DROP_OLDEST),
            ),
        ],
    )
    ProfileValidator.validate(config)  # no raise
```

### Operations checklist

- [ ] All RTSP sources use DROP_OLDEST/DROP_NEWEST/SAMPLE/DEGRADE_QUALITY.
- [ ] Backpressure metrics monitored (drops_per_sec, queue_depth, queue_full_blocks).
- [ ] Reconnect logic has jitter (avoid thundering herd).
- [ ] Camera firmware behavior documented per vendor.
- [ ] Soak test: simulate slow consumer, verify graceful degradation.

---

## Liên kết production

- `Vision_platform_architecture_design/06-resilience-and-shutdown/01-backpressurepolicy-per-source-enforcement.md`
- `Vision_platform_architecture_design/06-resilience-and-shutdown/05-block-policy-banned-cho-rtsp.md`
- Module 02 file 04 — backpressure theory.

---

## Tóm tắt

> **BLOCK policy + RTSP = TCP Zero Window → camera firmware drop/disconnect → thundering herd reconnect → pipeline collapse. Fix: config-time validate whitelist `{DROP_OLDEST, DROP_NEWEST, SAMPLE, DEGRADE_QUALITY}` for RTSP. NOT runtime warning. Hard error blocks deployment.**

➡️ Tiếp theo: [`04-frozen-dataclass-with-mutable-dict.md`](04-frozen-dataclass-with-mutable-dict.md)
