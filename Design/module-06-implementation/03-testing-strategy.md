# 03 — Testing Strategy: pyramid + tỉ lệ + tools

## Câu hỏi cốt lõi

> Bao nhiêu unit test? Bao nhiêu integration? Khi nào E2E? Bao nhiêu chaos?

## TL;DR (30s)

**Test pyramid** (Vision Platform):

```
           ╱───────────╲          
          ╱ Soak (24h)  ╲          1 test, manual
         ╱─────────────╲           
        ╱   Chaos       ╲          ~10 tests
       ╱─────────────────╲         
      ╱    E2E            ╲        ~10 tests
     ╱───────────────────╲        
    ╱   Integration       ╲        ~50 tests
   ╱─────────────────────╲        
  ╱   Contract             ╲      ~30 × N adapters
 ╱─────────────────────────╲      
╱     Unit                  ╲      ~500 tests
─────────────────────────────
       Pyramid base = many fast tests
```

→ Many fast tests at base, few slow tests at top.

---

## Layer 1: Unit tests (~500)

### Scope
- Single class/function.
- No I/O.
- Mock all dependencies.
- Run < 100ms each.
- Total < 30s.

### Examples Vision Platform

```python
# Test pure logic.
def test_bbox_area():
    b = BBox(0, 0, 10, 20, CoordinateSpace.ORIGINAL)
    assert b.area == 200


# Test with mock.
def test_use_case_calls_detector():
    mock_detector = Mock()
    mock_detector.detect.return_value = [Detection(...)]
    
    use_case = ProcessFrameUseCase(detector=mock_detector)
    result = use_case.execute(frame)
    
    mock_detector.detect.assert_called_once()
```

### When NOT enough

Unit tests alone catch ~70% of bugs. Misses:
- Integration bugs (wrong data shape).
- Race conditions.
- Resource leaks (memory, fd).
- Performance regressions.

→ Need higher layers.

---

## Layer 2: Contract tests (~30 × N adapters)

### Scope

For each port, write **1 contract test suite**. Every adapter implementing port must pass.

### Example

```python
# tests/test_frame_source_contract.py
@pytest.fixture(params=[
    pytest.param(lambda: FakeFrameSource(...), id="fake"),
    pytest.param(lambda: VideoFileSource(...), id="file"),
    pytest.param(lambda: WebcamSource(...), id="webcam"),
])
def source(request):
    src = request.param()
    src.setup()
    yield src
    src.teardown()


class TestFrameSourceContract:
    def test_read_returns_readresult(self, source): ...
    def test_setup_idempotent(self, source): ...
    # ... 30 tests apply to ALL adapters ...
```

→ Adding new adapter = `pytest.param(lambda: NewAdapter(), id="new")` → 30 tests applied for free.

### Power

- **Semantic compatibility guaranteed**.
- Adapters never drift from contract.
- Catch contract violations early.

---

## Layer 3: Integration tests (~50)

### Scope

- 2-3 components together.
- Real (not mock) for tested components.
- Mock external (DB, network, GPU).

### Examples

```python
def test_pipeline_executor_with_real_stages():
    """Real stages, mock source/sink."""
    source = FakeFrameSource(...)
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50),
    ])
    
    source.setup()
    executor.setup_all()
    
    packet = build_packet_from_source(source)
    final = executor.execute(packet)
    
    assert final is not None
    # ...


def test_shm_writer_reader_cross_process():
    """Real SHM, real subprocess writer."""
    ring = ShmRingBuffer(create=True)
    
    proc = mp.Process(target=writer_fn, args=(ring.slot_locks_for_children, ...))
    proc.start()
    proc.join()
    
    reader = ShmFrameReader(ring)
    frame = reader.read(slot=0, expected_gen=1)
    assert frame is not None
```

### Run time

< 1 minute total. Slower than unit but still fast feedback.

---

## Layer 4: E2E tests (~10)

### Scope

- Full pipeline.
- Real source (e.g. test video file).
- Real inference (or fake but inline).
- Real sink (e.g. file writer).

### Example

```python
def test_pipeline_processes_video_file_to_events():
    """Run full pipeline against test video, verify output events."""
    config = AppConfig.load("test_config.yaml")  # points to test video
    
    app = build_app_from_config(config)
    app.run(duration_s=10)
    
    # Verify events produced.
    events = read_event_log("output/events.jsonl")
    assert len(events) > 0
    assert all(e.has("camera_id") for e in events)
```

### Run time

5-30 seconds each. Total < 5 min.

### Cost

- Fragile (real files, real network).
- Maintain test data (golden labels, video).
- But catches integration bugs unit/integration miss.

---

## Layer 5: Chaos tests (~10)

### Scope

- Inject failures: kill process, drop network, fill disk.
- Verify graceful degradation + recovery.

### Examples

```python
def test_pipeline_survives_camera_crash():
    """Kill camera process mid-stream, verify others continue."""
    supervisor = build_supervisor(n_cameras=3)
    supervisor.start()
    time.sleep(2)  # let pipeline warm up
    
    # Kill camera 0.
    supervisor.kill_worker("cam_0")
    time.sleep(5)  # supervisor restart
    
    # Verify cam_1, cam_2 still producing events.
    events = read_recent_events()
    sources = {e.source_id for e in events}
    assert "cam_1" in sources
    assert "cam_2" in sources
    
    supervisor.shutdown()


def test_inference_service_oom():
    """Inject CUDA OOM, verify circuit breaker trips, cameras recover."""
    ...
```

### Run time

1-5 min each.

### When run

- Nightly CI.
- Before major release.
- Not every PR (slow).

---

## Layer 6: Soak tests (manual, 24h)

### Scope

- Run pipeline 24h.
- Real load (or load generator).
- Monitor: memory, latency, error rate.

### Pass criteria

- Memory stable (< +5% growth over 24h).
- p99 latency stable (no degradation).
- Error rate < 0.1%.
- No deadlocks (process responsive).

### Tools

- `psutil` for memory tracking.
- Prometheus/Grafana for metrics.
- Alert if any metric out of band.

### Run frequency

- Before production deploy.
- Quarterly stress test.

---

## Distribution

For Vision Platform mature codebase:

| Layer | Tests | Time/run | Frequency |
|-------|-------|----------|-----------|
| Unit | ~500 | 30s | Every commit |
| Contract | ~30 × adapters | 1 min | Every commit |
| Integration | ~50 | 1 min | Every PR |
| E2E | ~10 | 5 min | PR + nightly |
| Chaos | ~10 | 5 min | Nightly |
| Soak | 1 | 24h | Pre-release |

→ **Total CI**: ~3 min per PR. Nightly: ~10 min. Manual: 24h.

---

## Tools

### Python ecosystem

- `pytest` — runner.
- `pytest-cov` — coverage.
- `pytest-xdist` — parallel.
- `pytest-benchmark` — perf regression.
- `pytest-asyncio` — async support.
- `hypothesis` — property-based.
- `tracemalloc` — memory leak.
- `mutmut` — mutation testing.

### Infrastructure

- GitHub Actions / GitLab CI / Jenkins.
- Docker for E2E (real services).
- LocalStack for AWS-mock.

---

## Common mistakes

### 1. Test pyramid inverted

❌ 90% E2E, 10% unit.

→ Slow CI, brittle tests, debugging hell.

✅ 70% unit, 25% integration, 5% E2E.

### 2. Contract test missing

❌ Each adapter has own ad-hoc tests.

→ Adapters drift. Replace one breaks callers.

✅ Contract test mandatory per port.

### 3. Skip chaos

❌ "Production failures rare."

→ When happens, no muscle memory. 4h debug.

✅ Chaos test monthly.

### 4. Real services in unit tests

❌ Unit tests connect to real DB/network.

→ Slow, flaky, parallel-unsafe.

✅ Mock externals in unit. Real in integration.

---

## Self-check

1. **PR vs nightly tests** — phân biệt?

2. **Contract test khi nào fail** — example case?

3. **Soak test phát hiện gì** mà E2E không phát hiện được?

4. **Mock vs fake** — khác biệt?

5. **Property-based testing** (hypothesis) — đáng đầu tư cho stage logic?

<details>
<summary>Đáp án</summary>

1. **PR tests**: every PR. Fast (<5 min). Catch most bugs. Block merge.
   **Nightly tests**: scheduled. Slow (longer). Chaos + E2E full suite. Catch issues missed by PR tests.
   **Goal**: PR test fast feedback, nightly catch slow-burn issues.

2. **Contract test fail**: e.g. new adapter `WebcamSource.read()` returns `None` instead of `ReadResult`.
   - Contract test: `assert hasattr(result, "status")` → fails.
   - Without contract: caller crashes in production with `AttributeError`.

3. **Soak finds**:
   - Memory leaks growing 5MB/hour (1h E2E doesn't show).
   - Latency drift over time (GC, cache pollute).
   - Resource exhaustion (file descriptors, ports).
   - Race conditions occurring with low probability.
   - **E2E** runs ~10s — too short.

4. **Mock vs Fake**:
   - **Mock**: stub object with predefined responses (e.g. `MagicMock`).
   - **Fake**: working implementation, but simplified (e.g. `InMemoryDb` instead of Postgres).
   - **Mock** for unit tests (verify interaction).
   - **Fake** for integration tests (verify behavior).
   - **Vision Platform**: `FakeFrameSource` is a fake (real frame generator), `Mock(spec=IFrameSource)` is a mock.

5. **Property-based testing**:
   - **Yes** for: pure logic (BBox math, coordinate transform, config parsing).
   - **No** for: I/O-heavy, stateful systems (overhead > benefit).
   - **Example**: `@given(x=floats(), y=floats(), w=floats(min_value=0), h=floats(min_value=0))` then `assert BBox(x, y, w, h).area >= 0`. Hypothesis generates 100s of edge cases.
   - **Vision Platform**: useful for `CoordinateTransformer`, `BBox.iou`, schema versioning.

</details>

---

## Liên kết

- Module 03 each step has tests — sample patterns.
- Module 06 file 02 — DoD includes tests.

---

## Tóm tắt

> **Pyramid: many fast unit (500), fewer slow E2E (10), 1 manual soak (24h). Contract test mandatory per port. Chaos nightly. Tools: pytest + extensions. CI < 5 min per PR. Don't invert pyramid.**

➡️ Tiếp theo: [`04-when-stuck-decision-tree.md`](04-when-stuck-decision-tree.md)
