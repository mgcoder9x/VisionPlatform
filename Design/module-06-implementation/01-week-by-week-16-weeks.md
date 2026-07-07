# 01 — Roadmap 16 tuần triển khai từ legacy → production

## Câu hỏi cốt lõi

> Có codebase legacy (HeadDetect/main_app/...). Cần refactor sang Vision Platform architecture. Plan thực tế bao lâu?

## TL;DR (30s)

**Realistic 16-24 tuần** với team 2-3 dev. Không thể compress dưới 16 tuần vì production parity testing không rush được.

**Pattern**: Strangler Fig — không big-bang rewrite. Build new bên cạnh old, gradually replace.

---

## Tại sao 16 tuần?

Phân bổ thực tế:

| Phase | Time | % |
|-------|------|---|
| Setup + skeleton + first vertical slice | 2 tuần | 12.5% |
| Migrate sources (RTSP, file, webcam) | 2 tuần | 12.5% |
| Migrate inference + tracking | 3 tuần | 18.75% |
| Migrate sinks + observability | 2 tuần | 12.5% |
| Resilience (backpressure, shutdown, supervisor) | 2 tuần | 12.5% |
| **Production parity test** | 2 tuần | 12.5% |
| Cutover + soak | 1 tuần | 6.25% |
| Soak + cleanup + decommission legacy | 2 tuần | 12.5% |
| **Tổng** | **16 tuần** | **100%** |

→ Buffer (slack cho bug, scope creep, vendor surprises) **đã absorbed** vào soak + cleanup phase (tuần 15-16). Nếu mọi thứ smooth → tuần 15-16 chỉ cần 1 tuần thực, free 1 tuần làm tech debt cleanup. Nếu trục trặc → 2 tuần đủ buffer.

→ Compressing dưới 16 tuần = skip parity hoặc soak = production incident sau 1-2 tháng.

---

## Tuần 1-2: Setup + skeleton

### Goals

- Decision: deployment mode (M1-M5)?
- Setup repo skeleton (4-layer Hexagonal).
- 1 vertical slice end-to-end với fake adapters.
- CI/CD pipeline.

### Deliverables

- Repo `vision_platform_<project>/` với folder structure.
- `pyproject.toml`, venv, lint config.
- 1 minimal use case (read fake → identity stage → log) chạy được.
- GitHub Actions / GitLab CI: lint + pytest.
- README: architecture overview.

### Decision points

**Mode (M1-M5)**:
- M1 real-time multi-camera (24/7).
- M2 batch processing (file).
- M3 desktop UI (Qt).
- M4 web upload.
- M5 background service (no UI).

→ Khác mode → khác composition root + adapter set.

**Inference**:
- Centralized service (M1) hay inline (M2-M5)?
- HA mode opt-in?

**Storage**:
- Postgres? MongoDB? Kafka? S3?

### Common pitfalls

- **Pitfall 1**: Skip CI/CD — accumulates bugs.
- **Pitfall 2**: Build everything before first vertical slice — no feedback loop.
- **Pitfall 3**: Decision paralysis on tech stack — pick reasonable defaults, iterate.

---

## Tuần 3-4: Sources migration

### Goals

- Implement adapter cho mỗi source type cần.
- Contract test pass cho mọi adapter.
- Sources có cleanup, reconnect logic.

### Adapters typical

- `FFmpegRTSPSource` — production RTSP (M1).
- `Cv2VideoFileSource` — file batch (M2).
- `WebcamSource` — desktop dev (M3).
- `HttpUploadSource` — web (M4).
- `FakeSource` — testing.

### Deliverables

- Mỗi adapter implement `IFrameSource` port.
- Contract test parametrized — same suite cho mọi adapter.
- Connection lifecycle: setup, reconnect, teardown idempotent.
- Backpressure policy whitelist enforcement (Module 05 file 03).

### Tests

- Contract test ~30 test cases × N adapters.
- Mock RTSP server cho integration test (e.g. MediaMTX).
- Soak test 1h reading file source.

---

## Tuần 5-7: Inference + Tracking

### Goals

- Inference service (centralized) hoặc inline.
- Detector adapter (YOLO, RTMDet, ...).
- Tracker với scope.
- Request/response correlation.

### Architecture decision

**Option A — centralized inference** (M1):
- 1 process, ZMQ ROUTER, 1 GPU.
- N camera DEALER clients.
- Batching + dedup.
- Circuit breaker per camera.

**Option B — inline inference** (M2-M5):
- Detector trong cùng process pipeline.
- No IPC overhead.
- Simpler.

### Deliverables

- `IDetector` port + adapters.
- `IInferenceClient` port + adapters (inline + ZMQ).
- `ITrackerFactory` + `TrackerScope` (per source/session).
- Inference service (M1): batching, dedup, HEARTBEAT, HA.

### Tests

- Detector contract test.
- ZMQ ROUTER/DEALER round-trip test.
- Tracker scope isolation test (multi-source no leak).
- Soak: 1h × 4 cameras inference.

---

## Tuần 8-9: Sinks + Observability

### Goals

- Event sink chain (decorator pattern).
- Privacy filtering.
- DLQ.
- structlog + metrics + traces.

### Sink chain (CR-PRV-01 pattern)

```python
sink = (
    DLQDecoratorSink(
        inner=BufferedRetryingSink(
            inner=PrivacyFilteredSink(
                inner=KafkaSink(brokers=[...]),
            ),
        ),
        dlq=FileDLQHandler(path="..."),
    )
)
```

→ Order critical — privacy filter MUST be inside DLQ (otherwise DLQ leaks PII to disk).

### Observability

- structlog với `log_context` — cross-cutting fields.
- Metrics: counter/gauge/histogram. Bounded cardinality labels.
- OpenTelemetry tracer (optional).

### Deliverables

- Sink chain composition.
- DLQ replay tool.
- Metrics dashboard.
- Log shipping (Loki/ELK/Datadog).

---

## Tuần 10-11: Resilience

### Goals

- Backpressure policies enforced.
- Health signal (PUB/SUB).
- Adaptive source wrapper.
- Supervisor + cascade shutdown.

### Deliverables

- `BoundedQueue` với 6 policies.
- ProfileValidator config-time enforcement.
- Health subscriber + adaptive policy switching.
- Supervisor with restart cap, jitter.
- `EventLoopWatchdog` for async pipelines.

### Chaos tests

- Kill -9 random camera every minute.
- Inject GPU OOM.
- Disconnect Kafka mid-flow.
- Verify supervisor recovery + no data corruption.

---

## Tuần 12-13: Production parity test

### Critical phase. KHÔNG skip.

### Goals

- Run new + legacy in parallel.
- Compare outputs (event count, latency, accuracy).
- Identify divergences.

### Setup

```
        Camera RTSP
           │
   ┌───────┴────────┐
   │                │
[Legacy]      [New (vision_platform)]
   │                │
   ├─ events_legacy ├─ events_new
   └─ logs_legacy   └─ logs_new
                  
   ┌────────────┐
   │ Comparator │ → diff report
   └────────────┘
```

### Comparison metrics

- **Event count**: same period, ±5% tolerance.
- **Latency p50/p95/p99**: ±20% tolerance.
- **Detection accuracy**: % match with golden labels (need labels).
- **Track ID continuity**: % tracks survive same time window.

### Mismatches → investigate

Common sources:
- Different YOLO version → different bbox coords.
- Different tracker → different IDs.
- Different timestamp source → different event timing.
- Different coord space → bbox lệch.

### Hard rule

**Don't promote** until parity within tolerance for ≥3 days continuous.

---

## Tuần 14: Cutover

### Strangler Fig final step

- Keep legacy code, add **env flag**:
  ```
  USE_NEW_PIPELINE=true python main.py    # new
  USE_NEW_PIPELINE=false python main.py   # legacy fallback
  ```
- Deploy: switch flag for 1 camera first. Monitor 24h.
- Rollback if any incident → flip flag back.
- Gradually increase: 1 → 4 → 16 cameras.

### Watch for

- p99 latency drift.
- Memory growth (long-running).
- Detection rate drop.
- Sink errors (DLQ growth).

### Don't kill legacy yet

Keep `main_legacy.py` for 2-4 weeks post-cutover. Allow operational rollback.

---

## Tuần 15-16: Soak + cleanup

### Goals

- 1-2 week soak test.
- Address minor bugs.
- Documentation.
- Knowledge transfer.

### Deliverables

- Soak report: latency, memory, error rates.
- Updated runbook.
- Operations dashboard.
- On-call playbook.

### Decommission legacy (after soak)

- Remove `main_legacy.py`.
- Delete legacy dependencies.
- Final commit "v2.0 release".

---

## Buffer note

Buffer (slack) đã absorbed vào tuần 15-16 (soak + cleanup). Nếu cần buffer riêng:

- Team experienced + scope tight → 16 tuần đủ.
- Team mới + scope creep risk → plan **18-20 tuần** (thêm 2-4 tuần buffer riêng).
- Reality: bugs, scope creep, vendor surprises ALWAYS xảy ra. **Plan 16 tuần expect 18** an toàn hơn "plan 16 hard deadline".

→ **Don't compress dưới 16 tuần** — production parity (2w) + soak (1w) là **non-negotiable**. Compress = production incident.

---

## Anti-patterns to avoid

### 1. Big bang rewrite

❌ "We'll write everything new in 6 months, switch over."

→ 6 months turns into 18. Old features missed. Cutover terrifying.

✅ Strangler Fig: incremental, parallel run, gradual switch.

### 2. Skip production parity

❌ "Tests pass, ship it."

→ Production has edge cases tests don't cover. Latency profile differ. Resource contention differ.

✅ 2 weeks parity test mandatory.

### 3. Compress timeline by skipping observability

❌ "We'll add metrics/logging after."

→ Production incident: no visibility. Debug time 10×.

✅ Observability from week 1. Every component logs structured.

### 4. Single camera test = production-ready

❌ "Works with 1 camera, scale to 16."

→ Bulkhead bugs only show with N cameras. Backpressure cascade only with concurrent load.

✅ Multi-camera load test from week 5.

### 5. Skip chaos tests

❌ "Bugs will happen, we'll fix them."

→ 3am incident = high stress, slow fix.

✅ Chaos test in week 10-11. Find bugs in dev hours.

---

## Self-check

1. **16 tuần với team 5 dev** — có thể compress xuống 10 tuần không? Tại sao?

2. **Strangler Fig** — pros/cons vs big-bang rewrite?

3. **Production parity test** — sao cần 2 tuần? Cho 3 ví dụ divergence khó phát hiện < 1 tuần.

4. **Cutover gradual** — sao 1 camera trước, không phải tất cả?

5. **Sau cutover**, sếp hỏi "khi nào xóa legacy?" — bạn đáp gì?

<details>
<summary>Đáp án</summary>

1. **5 dev không = 1.5x speed**:
   - Brooks's Law: "adding manpower to a late software project makes it later".
   - Communication overhead grows quadratically.
   - Some phases (parity test, soak) cannot be parallelized.
   - **Realistic**: 5 dev → 12-14 tuần (1.3x speedup). Not 10.
   - More dev → cheaper buffer (specialization), not faster baseline.

2. **Strangler Fig vs big-bang**:
   - **Strangler pros**: incremental risk, can rollback, learn as you go.
   - **Strangler cons**: longer total timeline, dual-maintain old + new.
   - **Big-bang pros**: faster on paper, single mental model.
   - **Big-bang cons**: cutover terrifying, all-or-nothing, often slips 2-3x.
   - **Industry data**: big-bang rewrite of moderate-complexity system has ~50% chance of complete failure.

3. **Hard divergences**:
   - **Frame timestamp ordering**: legacy uses capture time, new uses receive time → events ordered differently → "same content different IDs".
   - **NMS threshold rounding**: tiny float diff → 1% bbox diff → 0.5% extra/missing detections.
   - **Tracker initialization**: legacy starts ID at 1, new at 0 → all events have different IDs forever.
   - All require domain expert + log analysis. <1 week not enough.

4. **Gradual cutover**:
   - 1 camera = 6% of load. Issues caught with 6% blast radius.
   - 16 simultaneously = 100% blast radius. Issue → entire fleet down.
   - 24h soak per stage = ensures real load, real time-of-day patterns.

5. **"Khi nào xóa legacy?"**:
   - Sau **2-4 tuần stable** post-cutover.
   - **No incidents** in that window.
   - **Operations team comfortable** with new system.
   - **Stakeholder sign-off**.
   - **Premature delete** = no rollback path nếu bug latent xuất hiện sau.

</details>

---

## Liên kết

- **Production**: `Vision_platform_architecture_design/12-migration/` — Strangler Fig migration full guide.
- Module 02 file 01 — Hexagonal pattern is what enables Strangler Fig.

---

## Tóm tắt

> **16 tuần realistic. Strangler Fig pattern (parallel run + gradual switch). Phase: setup → sources → inference → sinks → resilience → parity (2w mandatory) → cutover → soak. Don't compress < 16 tuần unless skip parity (= production incident).**

➡️ Tiếp theo: [`02-definition-of-done.md`](02-definition-of-done.md)
