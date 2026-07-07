# 01 — Pipeline Stalls: frame không chảy, không error

## Symptom

- Detection rate giảm về 0.
- Không có exception trong log.
- Process vẫn `is_alive()` trả True.
- Memory stable, không grow.

## Triage 60 giây

### Câu 1: Có thay đổi gần đây?

- Deploy trong 24h qua? → 80% là deploy gây.
- Config change? → check.
- Traffic spike? → check.

→ **Nếu yes**: rollback first, debug second.

### Câu 2: Tất cả camera stall, hay 1?

- **Tất cả**: Inference service hoặc supervisor.
- **1 camera**: camera process / RTSP source.
- **Subset**: shared resource (DB, network).

### Câu 3: Log có gì cuối?

```bash
tail -100 /var/log/vision/*.log | grep -iE "(error|warn|stall|timeout)"
```

→ Last few entries hint at what state things were in.

---

## Decision tree

```
Pipeline stall (no frames)
│
├── Check: process alive?
│   ├── YES (process running, but stuck)
│   │   ├── py-spy dump --pid <pid>  # see thread states
│   │   ├── Stack trace shows: locked → MUTEX POISONING (R5-CRITICAL-01)
│   │   ├── Stack trace shows: socket.recv → ZMQ stuck
│   │   ├── Stack trace shows: queue.put → BACKPRESSURE BLOCK
│   │   └── Stack trace shows: GIL → asyncio stall (R5-HIGH-02)
│   │
│   └── NO (process exited)
│       ├── Check exit code: ps aux | grep python
│       ├── exit -9 → SIGKILL (OOM, manual kill)
│       ├── exit 137 → OOM-killer
│       └── Check supervisor: should restart, why didn't?
│
├── Check: SHM ring state?
│   ├── ls /dev/shm/cvplatform_* (Linux)
│   ├── slot states all FREE → camera not writing
│   ├── slot states all READY → reader not consuming
│   └── slot QUARANTINED → poisoned (R5-CRITICAL-01)
│
├── Check: ZMQ connectivity?
│   ├── netstat -tan | grep 5558  # inference router port
│   ├── No LISTEN → service down
│   ├── Many CLOSE_WAIT → cameras dropped, accumulating
│   └── ESTABLISHED but no traffic → application-level stall
│
└── Check: backpressure metrics?
    ├── grep "queue_depth" /var/log/metrics
    ├── Saturated (== max) → producer faster than consumer
    └── Empty (== 0) → producer not producing
```

---

## Common causes (R1-R5 review)

### Cause 1: Mutex poisoning (R5-CRITICAL-01)

**Symptom**: 1 camera stalls. py-spy shows `lock.acquire()`.

**Verify**:
```bash
# Find camera process
ps aux | grep "vision_demo.*camera"

# Dump stack
py-spy dump --pid <camera_pid>

# Look for: "lock.acquire()" frame stuck
```

**Fix**: 
- Short-term: restart camera process (supervisor should auto-restart).
- Long-term: deploy R5-CRITICAL-01 fix (bounded acquire timeout + QUARANTINED sentinel).

### Cause 2: ZMQ DEALER full HWM

**Symptom**: All cameras stop sending. Queue full warning in log.

**Verify**:
```python
# In repl with debug build
print(socket.get(zmq.SNDHWM))  # default 1000
print(socket.get(zmq.EVENTS))  # check pollin/pollout
```

**Fix**:
- Investigate why receiver (inference) slow.
- Increase HWM if appropriate.
- Apply backpressure policy.

### Cause 3: Asyncio event loop stall (R5-HIGH-02)

**Symptom**: ZMQ recv loop in async pipeline not draining.

**Verify**:
```bash
# py-spy dump shows event loop thread stuck in non-await Python code.
```

**Fix**:
- Identify offending coroutine.
- Move CPU-bound work to thread pool.
- Deploy `EventLoopWatchdog` to alert next time.

### Cause 4: BLOCK policy on RTSP (CR-RT-03)

**Symptom**: Camera readers blocked, RTSP TCP zero window, eventual disconnect.

**Verify**:
```bash
# Config check
grep "policy" /etc/vision/config.yaml | grep -i rtsp

# tcpdump to see TCP zero window
sudo tcpdump -i eth0 'host <camera_ip> and tcp[tcpflags] & tcp-rst != 0'
```

**Fix**:
- Change RTSP backpressure policy to `DROP_OLDEST`.
- Deploy ProfileValidator config-time enforcement.

### Cause 5: Inference service crashed silently

**Symptom**: All cameras stalled at same time.

**Verify**:
```bash
# Check inference service process
ps aux | grep inference_service

# Process exists?
# YES → check stack
# NO → check exit log + supervisor restart attempts
```

**Fix**:
- Check OOM-killer log: `dmesg | grep -i kill`.
- Check Python traceback in service log.
- Verify supervisor restart cap not exceeded.

---

## Quick fixes (when on-call, no time)

### 1. Restart specific camera

```bash
# Identify camera process
ps aux | grep "cam_3"

# Kill - supervisor restarts
kill <pid>

# Verify supervisor restarted
ps aux | grep "cam_3"  # new pid
```

### 2. Restart entire pipeline

```bash
sudo systemctl restart vision-platform
# or:
docker-compose restart vision-platform
```

→ **Last resort** — clears all state, brief downtime.

### 3. Rollback last deploy

```bash
kubectl rollout undo deployment/vision-platform
```

---

## Permanent fix

After mitigating, schedule incident review:

1. **Root cause**: which decision branch.
2. **Why didn't monitoring catch sooner**: alert gap.
3. **Prevention**: code change, alert tuning, runbook update.

---

## Self-check

1. **Process alive but stuck** — top 3 culprits in Vision Platform?

2. **All cameras stall same time** vs **1 camera stall** — different cause classes?

3. **`py-spy dump`** vs **`gdb -p`** — which when?

4. **Restart vs rollback** — decision criteria?

5. **Stall caught at 3am, fixed at 5am** — what doc to write?

<details>
<summary>Đáp án</summary>

1. **Top 3 stuck culprits**:
   - Mutex poisoning (R5-CRITICAL-01).
   - ZMQ HWM saturated.
   - Asyncio event loop blocked (R5-HIGH-02).

2. **Different scope**:
   - **All cameras**: shared resource — inference service, ZMQ broker, DB, network.
   - **1 camera**: per-camera resource — RTSP connection, camera process, dedicated SHM ring slot.
   - **Subset**: partition issue — half cameras share component (e.g. host A vs host B).

3. **py-spy vs gdb**:
   - **py-spy**: Python application. Reads frame state. Non-invasive (no need to attach gdb). Fast.
   - **gdb**: C-level debugging. When py-spy shows native code blocked. Inspect kernel state.
   - **Practice**: py-spy first. gdb if py-spy says "in C code, can't decode".

4. **Restart vs rollback**:
   - **Restart**: clears state, restores from config. Use when transient state corruption.
   - **Rollback**: reverts code/config. Use when bug introduced by recent change.
   - **Decision**:
     - Bug since deploy → rollback.
     - Bug random / first time → restart.
     - Both fail → escalate.

5. **Post-mortem doc**:
   - Timeline (3am alert, 3:15 page, 3:30 investigate, 4:00 hypothesis, 5:00 fix).
   - Root cause analysis.
   - Why monitoring didn't catch earlier.
   - Action items (code, alert, runbook).
   - Distribute to team. Learn collectively.

</details>

---

## Liên kết

- Module 05 file 01 — Mutex poisoning bug detail.
- Module 04 file 04 — Asyncio event loop.

---

## Tóm tắt

> **Stall debug: 1) recent change → rollback first. 2) py-spy dump for thread state. 3) Check SHM, ZMQ, backpressure metrics. Common causes: mutex poisoning, ZMQ HWM, event loop stall, BLOCK on RTSP. Restart immediate, fix permanent later.**
