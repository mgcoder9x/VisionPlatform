# 05 — Promotion Checklist: trước deploy production

## Câu hỏi cốt lõi

> "Em xong rồi, deploy được chưa?" Sếp hỏi: "Đã check gì?" Bạn đáp...

## TL;DR (30s)

**30+ items checklist**. Pass tất cả = ready promote staging → production.

---

## Pre-deployment checklist

### Code (5 items)

- [ ] All tests pass (unit + integration + E2E + contract).
- [ ] Coverage ≥80% on changed code.
- [ ] No `TODO`/`FIXME` without ticket reference.
- [ ] Lint clean (`ruff`, `mypy --strict`).
- [ ] No hardcoded secrets/paths.

### Architecture (5 items)

- [ ] Dependency direction respected (import-linter pass).
- [ ] No circular imports.
- [ ] Composition root in `profiles/`, not scattered.
- [ ] Adapter contracts pass.
- [ ] Risk register reviewed; all critical risks have owner + mitigation + evidence.

### Performance (5 items)

- [ ] Latency p99 within budget.
- [ ] Throughput meets spec.
- [ ] Memory stable in 1h soak.
- [ ] CPU usage acceptable (< 80% sustained).
- [ ] No memory leaks (tracemalloc diff < 10MB / 1h).

### Resilience (5 items)

- [ ] Backpressure policies enforced.
- [ ] Timeouts on all external calls.
- [ ] Circuit breakers configured.
- [ ] Graceful shutdown tested (SIGTERM + 30s grace).
- [ ] Restart cap (no restart-storm).

### Security (5 items)

- [ ] Credentials in env / secrets manager (not code).
- [ ] PII filtering applied (CR-PRV-01 fix pattern).
- [ ] Auth on IPC channels (CURVE for cross-host).
- [ ] HMAC signatures on control commands.
- [ ] Rate limit on public endpoints.

### Observability (5 items)

- [ ] Logs structured (JSON), shipped to aggregator.
- [ ] Metrics exposed (Prometheus / StatsD).
- [ ] Dashboards exist for golden signals.
- [ ] Alerts configured on key thresholds.
- [ ] Distributed tracing (if multi-service).

### Operations (5 items)

- [ ] Runbook updated.
- [ ] On-call playbook written.
- [ ] Rollback plan documented.
- [ ] Deployment automation tested.
- [ ] Health check endpoint.

### Compliance (3 items)

- [ ] Privacy policy met (PII redaction).
- [ ] Audit logging.
- [ ] Data retention policy.

→ **Total ~37 items**. Pass all = green light.

---

## Production-only checks

### Resource

- [ ] Server provisioned (CPU/RAM/GPU sized).
- [ ] Disk space allocated (logs + DLQ overflow).
- [ ] Network bandwidth verified (RTSP × N cameras).

### Capacity

- [ ] Load test at 100% expected traffic.
- [ ] Headroom 30% (peak burst).
- [ ] Auto-scaling rules (if cloud).

### Disaster recovery

- [ ] Backup procedure tested.
- [ ] Recovery procedure tested (not just documented).
- [ ] RTO/RPO defined and measured.

---

## Go/no-go meeting

### Attendees

- Engineer (you).
- Tech lead.
- SRE / Ops.
- Product (if customer-facing).

### Agenda

1. Walk through checklist (5 min).
2. Risk discussion (10 min):
   - Worst case scenario.
   - Detection method.
   - Mitigation.
   - Open critical risks and owners.
3. Rollback plan review (5 min).
4. Decision: Go / No-go / Conditional go.

### Common no-go reasons

- Test coverage < 80%.
- Performance degradation > 20%.
- No rollback plan.
- Significant change with no soak test.
- On-call not staffed.

---

## During deployment

### Time-box

- Deploy window: typically 1-4h off-peak.
- Hard rollback time: 30 min after issue detected.

### Monitor

- Error rate.
- Latency (p50/p95/p99).
- Throughput.
- Memory.
- Sink errors.

### Rollback triggers

- Error rate > 2× baseline for 5+ min.
- p99 latency > 3× baseline.
- Memory growth > 100MB/min.
- Critical alert.

---

## Post-deployment

### First 24h

- Operator on-watch.
- Monitor every 1-2h.
- No new deploys.

### First week

- Daily review of metrics.
- Incident retrospective if issues.
- Document anything unexpected.

### After 1 week stable

- Decommission legacy (if applicable).
- Knowledge transfer to broader team.
- Update operations doc.

---

## Anti-patterns

### "Deploy on Friday afternoon"

❌ Deploy when half team off-call. Bug in evening = no support.

✅ Deploy mid-week, mid-day. Maximum support availability.

### "Deploy and walk away"

❌ Push and go home.

✅ Stay on for first 1-2h post-deploy. Watch metrics.

### "Skip checklist for small changes"

❌ "It's just a config change."

→ Config changes broke production countless times.

✅ Checklist for every change. Some items skip-able for hotfix, but explicitly noted.

### "Rollback is hard, just fix forward"

❌ "We'll fix it in production."

→ Fixed in panic, often makes worse.

✅ Rollback first, debug calmly, redeploy when ready.

---

## Self-check

1. **Conditional go** — example scenario?

2. **Soak test 24h passes** — đủ chưa? Cho 1 case không cover.

3. **"Friday deploy"** — luôn cấm? Exception?

4. **Rollback plan** — viết bao chi tiết?

5. **First week post-deploy** — engineer mới có nên touch code không?

<details>
<summary>Đáp án</summary>

1. **Conditional go example**:
   - "Go for 1 camera in production today. Monitor 24h. Promote to all 16 cameras tomorrow if metrics stable."
   - Or: "Go without optional feature X. Add X in v1.1 next week."
   - Useful when most criteria met, 1-2 items deferrable.

2. **24h soak misses**:
   - Weekly patterns (weekend low traffic, Monday burst).
   - Time-of-day (peak hours different load).
   - Slow leaks ( <1MB/hour but compounds over weeks).
   - **Better**: 1 week soak in pre-prod for high-stakes systems.

3. **Friday deploy exception**:
   - **Hot security patch** (zero-day).
   - **Customer-blocking incident** with fix ready.
   - Otherwise: avoid. Friday = weekend on-call burden.

4. **Rollback plan detail**:
   - Step-by-step commands.
   - Expected output at each step.
   - Time estimate.
   - Decision points (when to escalate).
   - Test in staging FIRST.
   - Sample:
     ```
     1. SSH to host (30s).
     2. `kubectl rollout undo deployment/vision-platform` (1min).
     3. Verify pods running: `kubectl get pods` (30s, expect READY 16/16).
     4. Verify traffic: `curl health.example.com/v1/health` (5s, expect 200).
     5. If step 4 fails, escalate to <on-call> within 5 min.
     ```

5. **First week post-deploy code freeze**:
   - **Yes**, code freeze for non-critical changes.
   - **Critical bug fix**: minimal change, urgent review, deploy.
   - **Reason**: any change can mask post-deploy issues. Stable baseline needed to identify bugs.
   - After 1 week: normal flow.

</details>

---

## Liên kết

- Module 06 file 02 — DoD complementary to promotion checklist.
- Module 06 file 06 — risk register & design review.
- Module 07 — troubleshooting if go-live issues.

---

## Tóm tắt

> **30+ items checklist: code, architecture, performance, resilience, security, observability, operations, compliance. Go/no-go meeting với rollback plan. Don't deploy Friday. Watch metrics 1-2h post-deploy. Code freeze first week.**

➡️ Tiếp theo: [`06-risk-register-and-design-review.md`](06-risk-register-and-design-review.md)
