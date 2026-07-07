# 05 — "Tôi tìm 3 ngày, không ra": systematic approach

## Symptom

- Bug exist nhưng không reproduce reliably.
- 3+ days debugging, no progress.
- Stress, frustration.


## Step 1: Stop, take a day off if possible

Stress → tunnel vision. 1 day rest often = 5 min insight on return.

## Step 2: Document what you've tried

Write down systematically:

```
Tried:
- [x] git bisect (commit X-Y) → no signal
- [x] Print debug in stage A → printed but no insight
- [x] Run tests in isolation → all pass
- [x] Reproduce on staging → can't reproduce
- [ ] Profile under load → not yet
- [ ] Compare logs against legacy → not yet
```

→ Reveals gaps. Often "haven't tried obvious thing".

## Step 3: Question assumptions

- "Library X works as expected" → maybe not? Read source.
- "Test isolation OK" → maybe state pollution? Add fresh fixtures.
- "Race condition unlikely" → maybe always there, just rare? Add stress test.

## Step 4: Ask senior + bring write-up

- 30 min "show what I've tried" with senior.
- Often new perspective = quick insight.
- Pride < time wasted.

## Step 5: Consider the bug isn't where you think

### Common displacement

- Bug in **caller**, not callee.
- Bug in **config**, not code.
- Bug in **environment** (OS, lib version).
- Bug in **test setup**, not production code.

### Tactics

- Reproduce against fresh checkout (no local mods).
- Reproduce in fresh Docker container.
- Pair with peer doing review on different machine.

## Step 6: Add monitoring, wait for next occurrence

If sporadic, can't reproduce:
- Add detailed structured logging in suspected paths.
- Deploy to staging.
- Wait for symptom.
- When happens, logs tell more than debugging.

## Step 7: Reduce + re-attack

- Drop optional features.
- Disable parallelism.
- Run with single source/single iteration.
- Often reveals real bug hidden by complexity.

## Anti-patterns

### "Just add try/except everywhere"

❌ Hide error. Bug remains. Latency tax + harder debug.

### "Add sleep to fix race"

❌ "I added time.sleep(1), now passes." Race still there.

✅ Find actual sync point. Lock, event, future.

### "Config change in prod might fix it"

❌ Untested config in prod = new bug.

✅ Test config in staging first.

## Time discipline

- **Day 1**: full focus debug.
- **Day 2**: pair with senior, half-day each.
- **Day 3**: write up + escalate to architect.
- **Day 4**: stop. Step away. Different problem.

→ 3 days max. Bring fresh eyes after.

## Tóm tắt

> **Stuck 3 days = stop. Document what tried. Question assumptions. Pair. Consider bug elsewhere. Add monitoring + wait. Reduce complexity. Don't try-except hide. Don't sleep-fix race.**
