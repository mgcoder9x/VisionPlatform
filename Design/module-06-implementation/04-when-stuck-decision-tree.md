# 04 — Khi feature "stuck": decision tree

## Câu hỏi cốt lõi

> Implement 2 ngày, code không chạy. Stuck. Làm gì?

## TL;DR (30s)

**Decision tree** trong file này dán lên tường. 6-step systematic approach. Không random debug.

---

## Step 0: Don't panic, take 5 min break

Stress → tunnel vision → miss obvious. Walk away 5 min. Come back fresh.

→ **Required**. Not optional.

---

## Step 1: Define the problem precisely (10 min)

### Write down

- **Expected**: "I expect X to happen when Y."
- **Actual**: "Instead, Z happens."
- **Reproducer**: minimal steps to trigger.

```
Expected: pytest passes test_step_05_shm.
Actual: test_writer_recycles_done_slot fails with AssertionError on slot index.
Reproducer: pytest tests/test_step_05_shm.py::test_writer_recycles_done_slot
```

→ Vague problem definition = vague debugging.

---

## Step 2: Bisect (15 min)

### Was it working before?

- **Yes**: `git bisect` between last working commit and now.
- **No**: never worked, design issue.

```bash
git bisect start
git bisect bad HEAD
git bisect good <last-known-good>
# git auto-checks middle commit, you test
git bisect good   # if ok
git bisect bad    # if not
# repeat until found
git bisect reset
```

→ Pinpoints commit that broke. ~log2(N) tests.

---

## Step 3: Read the error (15 min)

### Don't skim. Read carefully.

- Stack trace top-to-bottom.
- Error message word by word.
- File names + line numbers.

### Common traps

- "Expected X, got Y" — verify what X and Y actually are. Print both.
- "AssertionError" without message — add message: `assert x == y, f"x={x}, y={y}"`.
- Mismatched types (`'NoneType' object has no attribute 'data'`) — the thing was None somewhere unexpected.

---

## Step 4: Print debug (20 min)

### Add prints, run, observe.

```python
def write(self, frame):
    print(f"[DEBUG] write: shape={frame.shape}", flush=True)
    
    for slot_idx in range(...):
        print(f"[DEBUG] try slot {slot_idx}", flush=True)
        # ...
        state, gen, pid = struct.unpack_from(...)
        print(f"[DEBUG] slot {slot_idx} state={state}", flush=True)
```

→ `flush=True` important — buffered output disappears on crash.

### Better: structlog with context

```python
import structlog
log = structlog.get_logger()

def write(self, frame):
    log.debug("write_attempt", shape=frame.shape)
    
    for slot_idx in range(...):
        log.debug("try_slot", slot_idx=slot_idx, state=state)
```

→ Search log: `grep "try_slot" output.log`. Filter by slot_idx, by state.

---

## Step 5: Reduce to minimal reproducer (30 min)

### Strip away irrelevant code

If full pipeline fails, isolate:
1. Just the failing component.
2. Just the failing function.
3. Just the failing line.

### Tactic

```python
# Original — complex.
def big_function():
    data = load_complex_data()
    result = transform(data, config_loaded_from_file)
    save_to_db(result, db_connection_from_pool)


# Simplified for debug.
def repro():
    data = make_minimal_data()
    result = transform(data, hardcoded_config)
    print(result)  # not save
```

→ Smaller surface = clearer signal.

### Extra: write as **failing test**

```python
def test_repro_bug():
    """Reproduces bug: ... description ..."""
    # minimal setup
    actual = thing_that_fails(...)
    assert actual == expected   # currently fails
```

→ Now have permanent regression test once fixed.

---

## Step 6: Search for similar issues (15 min)

### Order

1. **Internal**: `git log --grep="similar issue"`. Reviewer catches.
2. **Project issues** (GitHub, JIRA): "search bar".
3. **Stack Overflow**: error message + library name.
4. **Library docs + GitHub issues**: bug or expected behavior?

### Caveat

Random GitHub issue with "I have same problem" + 5 suggestions — not all apply. Read CAREFULLY before applying suggestion.

---

## Step 7: Ask for help (when stuck > 30 min)

### How to ask

❌ Bad: "My code doesn't work."

✅ Good:
> "I'm trying X. Expected Y, got Z. I tried A, B, C. Source code: <link>. Error: <full traceback>. What am I missing?"

### Rubber duck

Explain to colleague (or rubber duck — literally a duck on desk). Often you find the answer mid-explanation.

### Pair debugging

If stuck >30 min, pair with someone. Fresh eyes catch things you miss.

---

## Common stuck-points + their solutions

### Stuck 1: Test passes locally, fails in CI

- **Hypothesis**: env difference.
- **Check**: Python version, OS, deps versions.
- **Common cause**: time-dependent test (race condition triggered on slower CI).
- **Fix**: `pytest -n 1` (single-process), reproduce locally with low-spec env.

### Stuck 2: Sometimes test passes, sometimes fails

- **Hypothesis**: race condition / non-determinism.
- **Check**: time, random, threads, async tasks order.
- **Fix**: seed random (`random.seed(42)`), explicit task await order, use `asyncio.gather(return_exceptions=True)`.

### Stuck 3: Code "should" work, doesn't

- **Hypothesis**: false assumption about library/API.
- **Check**: read docs (not Stack Overflow). Print intermediate values. Compare with simple example from docs.
- **Common cause**: API misuse (e.g. `multiprocessing.Lock` vs `threading.Lock`).

### Stuck 4: Memory grows, no obvious leak

- **Hypothesis**: traceback retention (Module 05 file 02), reference cycle, cache unbounded.
- **Check**: `tracemalloc.snapshot()` diff. `objgraph.show_backrefs([sample_obj])`.
- **Fix**: depends. Often `clear_frames`, `weakref`, bounded cache.

### Stuck 5: Performance unexpected

- **Hypothesis**: profiling required, not guessing.
- **Tool**: `cProfile`, `py-spy`, `line_profiler`.
- **Common**: GIL contention (use `py-spy --threads`), I/O wait, GC pause.

---

## When to give up + ask architect

After **3-4 hours stuck** without progress:

1. **Stop** debugging.
2. Write up: "I've tried A, B, C, D. Hit walls X, Y, Z."
3. Talk to senior/architect.
4. Maybe **wrong approach**, not just bug.

→ Ego aside. Time wasted is worse than asking.

---

## Self-check

1. **`git bisect` không work** khi commit history rebase / merge. Workaround?

2. **Print debug vs logger.debug** — pros/cons?

3. **Failing test as repro** — sao tốt hơn ad-hoc script?

4. **Stuck 4 hours** then giải quyết: ghi gì về incident?

5. **"Đồng nghiệp giải trong 5 phút thay tôi 4 giờ"** — reaction?

<details>
<summary>Đáp án</summary>

1. **Bisect alternative**:
   - **Linear search**: checkout each commit since last good, test, narrow.
   - **Tag known-good states**: `git tag good-2024-W30` periodically, fewer commits to bisect.
   - **Reflog**: `git reflog` shows local history even after rebase.
   - Best: clean history, regular tags.

2. **Print vs logger**:
   - **Print pros**: instant, no setup.
   - **Print cons**: leak to prod, no level filter, no context.
   - **Logger pros**: filter by level, context fields, structured.
   - **Logger cons**: setup overhead.
   - **Practice**: print for 1-shot debug. Logger for "I'll keep this in production".

3. **Failing test as repro**:
   - **Permanent record**: regression test catches bug if reintroduced.
   - **Documentation**: someone else fixing similar bug sees existing test.
   - **CI catches automatically**: don't rely on manual repro.
   - **Forces minimal reproducer**: must isolate to write test.
   - vs ad-hoc script: lost after fix, no regression coverage.

4. **Post-mortem 4h debug**:
   - **What happened**: bug description.
   - **Root cause**: technical.
   - **Why didn't I find faster**: process gaps (e.g. didn't read docs first).
   - **Prevention**: lint rule? Test? Doc update?
   - **Time analysis**: 1h on wrong path, 1h on right but slow, 2h applying fix.
   - Share post-mortem in team. Others learn.

5. **Reaction "5 min vs 4h"**:
   - **Step 1**: Don't ego. They had context I lacked.
   - **Step 2**: Ask "what did you check first?" → learn pattern.
   - **Step 3**: Document the pattern in personal notes.
   - **Step 4**: Identify why I didn't ask sooner. Pride? Fear?
   - **Step 5**: Lower asking threshold next time. 2h max stuck → ask.
   - **Long-term**: build mental library of "fastest path to answer" patterns.

</details>

---

## Liên kết

- Module 07 — troubleshooting decision trees.
- Module 04 file 06 — debug memory issues.

---

## Tóm tắt

> **Stuck = 7 steps systematic: define precisely, bisect, read error, print debug, minimize reproducer, search prior art, ask for help. Don't random-poke. Failing test = permanent regression coverage. Stuck 3-4h = ask architect, ego aside.**

➡️ Tiếp theo: [`05-promotion-checklist.md`](05-promotion-checklist.md)
