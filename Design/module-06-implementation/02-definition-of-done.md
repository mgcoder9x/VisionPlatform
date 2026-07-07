# 02 — Definition of Done: khi nào 1 feature "xong"?

## Câu hỏi cốt lõi

> "Em xong feature X." Sếp hỏi: "Test? Doc? Performance?" Bạn đáp gì?

## TL;DR (30s)

**Definition of Done (DoD) = checklist cụ thể** cho biết feature thật sự ready ship. Không subjective.

Vision Platform DoD = ~12 items. Pass tất cả = ship.

---

## Standard DoD checklist

### Code
- [ ] Code passes lint (`ruff`, `mypy --strict`).
- [ ] Public function/class có type hints.
- [ ] Public function có docstring (purpose + 1-line semantics).
- [ ] No `TODO` / `FIXME` / `XXX` comments without ticket reference.
- [ ] No hardcoded credentials, paths, magic numbers.

### Architecture
- [ ] Dependency direction respected (layer-import-linter).
- [ ] No imports vào layer cao hơn (Domain không import cv2).
- [ ] Port + adapter pattern dùng đúng (no `from adapters.x import` in use case).
- [ ] Composition root chỉ ở `profiles/` (không rải rác).

### Tests
- [ ] Unit tests pass (`pytest`).
- [ ] **Coverage** ≥80% trên code mới.
- [ ] Contract tests cho mọi port mới.
- [ ] Integration test 1 happy path.
- [ ] Edge cases (empty input, error path) tested.

### Performance
- [ ] Latency budget verified (`pytest-benchmark` hoặc manual).
- [ ] Memory budget verified (no leak in 1h soak).
- [ ] Throughput meets spec.

### Observability
- [ ] structlog calls có context (camera_id, packet_id).
- [ ] Metrics emitted (counter/gauge/histogram).
- [ ] Errors logged với enough context để debug.

### Documentation
- [ ] README/docstrings updated.
- [ ] ADR if architectural decision.
- [ ] Operations runbook updated nếu changes deployment.

### Review
- [ ] PR reviewed by ≥1 peer.
- [ ] CI passes.
- [ ] No security regressions (e.g. credential leak).

→ **All boxes checked = Done**.

---

## DoD per feature type

### New adapter

```
- [ ] Implement port (IFrameSource, IDetector, ...).
- [ ] Pass contract test suite.
- [ ] Adapter-specific tests (handle vendor quirks).
- [ ] Setup/teardown idempotent.
- [ ] Reconnect logic tested (network adapter).
- [ ] Memory cleanup verified (no leak after teardown).
- [ ] Composition root updated.
- [ ] Operations doc: install + config.
```

### New stage

```
- [ ] Inherit BaseStage.
- [ ] _do_process pure (no I/O).
- [ ] CoW preserved (with_artifact, no mutate input).
- [ ] Stage isolation test (1 stage with mock packet).
- [ ] Integration with executor.
- [ ] Performance: <budget time.
- [ ] Metrics: stage_processed_total, stage_latency_ms.
```

### New backpressure policy

```
- [ ] Add to BackpressurePolicy enum.
- [ ] Implementation in BoundedQueue.
- [ ] Whitelist update for source types.
- [ ] ProfileValidator enforcement.
- [ ] Metric: counter for policy actions.
- [ ] Contract test: behavior matches spec.
```

### Shutdown logic change

```
- [ ] Cascade order documented.
- [ ] SIGTERM + SIGINT handlers.
- [ ] Timeout per step.
- [ ] Force kill stragglers.
- [ ] Cleanup verified (SHM, file lock, port).
- [ ] Test: kill in middle of operation, no data corruption.
```

---

## DoD anti-patterns

### "Ship now, test later"

❌ Skip tests → "we'll add later".

→ Bug ship to prod. "Later" never comes. Production fire-fighting.

✅ Test as part of DoD. PR rejected without tests.

### "Coverage 80% so we're good"

❌ Cherry-pick easy code to test, hit 80%, hard parts untested.

→ Bug in untested edge case.

✅ Coverage = lower bound, not target. Add tests for **risk areas** (concurrency, error handling), not "easy code".

### "Performance is QA's job"

❌ Don't run benchmark. Ship to QA. QA finds slowness. Late iteration.

→ Performance issue 1 week before deploy. Stress.

✅ Performance test in DoD. Benchmark runs in CI.

### "Observability later"

❌ Skip metrics/logs. Ship. Production incident: no visibility.

→ 4h debug instead of 30min.

✅ Observability from day 1. Metrics + structured logs DoD item.

---

## Self-check

1. **80% coverage** — đủ chưa? Cho ví dụ bug trong 20% còn lại.

2. **Performance test in CI** — pros/cons?

3. **DoD strict** vs **agile flexibility** — mâu thuẫn không? Resolve thế nào?

4. **Adapter contract test** — sao mandatory?

5. **"Done" mean ship to prod or merge to main**? Khác biệt?

<details>
<summary>Đáp án</summary>

1. **80% coverage không đủ**:
   - Easy paths covered (happy flow).
   - Untested 20%: error handlers, race conditions, edge cases (empty input, zero-day boundaries).
   - **Real bug example**: NumPy `mean()` on empty ndarray returns NaN. Untested → production crash on first empty frame.
   - **Better metric**: branch coverage + mutation testing (e.g. `mutmut`). Force tests to actually catch logic.

2. **Performance test in CI**:
   - **Pros**: catch regressions early, ratchet up baseline.
   - **Cons**: CI machine variability (different CPU, load) → flaky. Slow CI runs.
   - **Solution**: nightly perf test, not per-PR. Compare against rolling baseline (last 7 days median). Alert on >20% regression.

3. **DoD vs agility**:
   - DoD = quality bar, NOT deliverable.
   - Agility = small batches, fast iteration.
   - **Compatible**: small features ship more often, but each meets DoD.
   - **Incompatible**: huge features bypass DoD "this once". Slippery slope.
   - Pragmatic: tighten DoD over time as system matures. Initial v0.1 may have looser DoD.

4. **Adapter contract test mandatory**:
   - Without: each adapter has own bug pattern. Reviewer mental load increases.
   - With: 1 contract test, every adapter must pass → guaranteed semantic compatibility.
   - **Replacement**: when adapter X replaces Y, only need to verify contract test passes. No regression in callers.
   - **Vision Platform**: 30 contract tests for IFrameSource. Adding new adapter = inheriting all 30 = compliance guaranteed.

5. **"Done" = merge to main**:
   - Production deploy is **separate concern** (cutover plan, rollout, monitoring).
   - Merge ≠ deploy. Trunk-based dev: merge frequently, deploy gated.
   - **Production-ready** is stricter: also needs runbook, on-call, dashboard.
   - DoD covers code-quality. Production-ready covers operations.

</details>

---

## Liên kết

- Module 06 file 03 — testing strategy detail.
- Module 06 file 05 — promotion checklist.

---

## Tóm tắt

> **DoD = checklist cụ thể, không subjective. ~12 items: code, architecture, tests, performance, observability, docs, review. Strict không có "exceptions". Sustained quality = compounding ship velocity.**

➡️ Tiếp theo: [`03-testing-strategy.md`](03-testing-strategy.md)
