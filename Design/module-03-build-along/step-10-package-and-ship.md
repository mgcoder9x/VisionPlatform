# Step 10 — Package and ship

## Mục tiêu (1h)

Bạn vừa build vision_demo qua 9 step. Step 10 = **package + verify ready to ship**.

1. Run full test suite → expect **110 passed, 1 skipped** (111 collected; 1 skip có chủ đích — xem step 03).
2. Build wheel package.
3. Smoke test demo end-to-end.
4. Document.

**Đã verify**: full test suite pass (`pytest` → `110 passed, 1 skipped` trong ~10s).

---

## Phần 1 — Run full test suite (5 phút)

```bash
cd vision_demo_workspace
pytest
```

Expected:
```
============================= test session starts =============================
collected 111 items

tests/test_smoke.py::test_package_importable PASSED                    [  0%]
tests/test_smoke.py::test_package_has_layers PASSED                    [  1%]
tests/test_step_02_domain.py::test_bbox_basic PASSED                   [  2%]
... (110 tests pass, 1 skipped) ...
tests/test_step_09_shutdown.py::test_supervisor_shutdown_terminates_workers PASSED [100%]

======================= 110 passed, 1 skipped in 10.11s =======================
```

→ Đây là **definition of done** cho vision_demo MVP.

---

## Phần 2 — End-to-end demo (10 phút)

Test demo CLI:

```bash
# Pipeline: source → BrightnessStage → DarkFilterStage
python -m vision_demo.profiles.demo_pipeline --source noise --frames 10 --threshold 100.0
```

Expected output (stderr summary in stderr, frames in stdout):
```
[seq=001] brightness=127.33 shape=(240, 320, 3)
...

=== Demo summary ===
  Processed: 10
  Skipped (filter): 0
  Stage errors: 0
  Cancelled: 0
  EOF: 1
  Source errors: 0
```

Test với high threshold (all skipped):
```bash
python -m vision_demo.profiles.demo_pipeline --source fake --frames 5 --threshold 100.0
```

Expected:
```
=== Demo summary ===
  Processed: 0
  Skipped (filter): 5
  Stage errors: 0
  Cancelled: 0
  EOF: 1
  Source errors: 0
```

→ End-to-end working.

---

## Phần 3 — Build distribution package (15 phút)

```bash
python -m pip install build
python -m build
```

Expected:
```
* Building sdist...
* Building wheel from sdist
* Created vision_demo-0.1.0-py3-none-any.whl
* Created vision_demo-0.1.0.tar.gz
```

→ `dist/` chứa:
- `vision_demo-0.1.0-py3-none-any.whl` — wheel binary.
- `vision_demo-0.1.0.tar.gz` — sdist source.

Test install fresh:

```bash
# Tạo venv riêng cho test install
python -m venv /tmp/test_install_venv
source /tmp/test_install_venv/bin/activate    # Linux/Mac
# /tmp/test_install_venv/Scripts/activate    # Windows

pip install dist/vision_demo-0.1.0-py3-none-any.whl

# Verify import works.
python -c "import vision_demo; print(vision_demo.__version__)"
# → 0.1.0
```

→ Package distributable.

---

## Phần 4 — README (15 phút)

Tạo `vision_demo_workspace/README.md`:

```markdown
# vision_demo

Minimal vision platform demo — build từ Learning_path Module 03.

## Architecture

4-layer Hexagonal (+ adapter rim + profiles composition root):
- `domain/` — pure logic (BBox, CoordinateSpace).
- `kernel/` — DTO + ports (MediaPacket, ReadResult, IFrameSource, IDetector).
- `runtime/` — executors + stages (SyncLinearExecutor, BrightnessStage).
- `application/` — orchestrators (Supervisor).
- `adapters/` — implementations (FakeFrameSource, NoiseFrameSource, FakeDetector, InlineInferenceClient).
- `profiles/` — composition roots (demo_pipeline.py).

## Patterns implemented

- Hexagonal (ports + adapters).
- Bulkhead (multi-process supervisor).
- Backpressure (BoundedQueue with 4 policies).
- Immutability + CoW (MediaPacket).
- ABA prevention (SHM generation counter).
- Process supervisor with cascade shutdown.

## Quick start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\Activate.ps1 on Windows
pip install -e .[dev]

# Run tests
pytest

# Run demo
python -m vision_demo.profiles.demo_pipeline --source noise --frames 10 --threshold 100.0
```

## Test count

111 test collected (110 pass + 1 skip có chủ đích — test "finite source eventually EOFs" bị skip với `fake_infinite` source ở Step 03):
- Smoke: 2
- Step 02 (domain + DTO): 16
- Step 03 (frame source contract): 30 (29 pass + 1 skip)
- Step 04 (pipeline): 12
- Step 05 (SHM): 13 (incl. cross-process)
- Step 06 (inference): 9
- Step 07 (backpressure): 11
- Step 08 (observability): 12
- Step 09 (supervisor): 6

Total runtime: ~10s.

Ngoài ra, Module 01-02 có 17 test validate empirical claims (`tests_validate/`) — bạn không cần chạy ở vision_demo MVP, chỉ là evidence cho lý thuyết Module 01-02.

## Trade-offs vs production Vision Platform

This is **mini Vision Platform** for learning. Skip:
- ZMQ ROUTER/DEALER (use inline client).
- Wire DTOs (single-process — no IPC serialize).
- Quarantined SHM slot (R5-CRITICAL-01).
- Async logging with rotation (HI-OBS-01/02).
- CURVE auth (HI-SEC-09).
- Circuit breaker, error budget, DLQ, Strangler migration.
- **Secrets management**: vision_demo dùng fake source / fake detector → không có RTSP credentials. Production cần `.env` + `python-dotenv` hoặc KMS/Vault, `mask_rtsp_url()` trước log. Xem Module 06 file 05 promotion checklist mục Security.
- **SHM placement**: vision_demo đặt transport SHM ở `runtime/ipc/shm_frame_ring.py` và DTO `ShmFrameRefData` ở `kernel/shm_frame_ref.py` — đúng layer boundary (kernel không import `multiprocessing`). Đây là vị trí giống production; điểm khác biệt với production chỉ là độ phức tạp (không có lease deadline, QUARANTINED state, multi-reader pinning).
- **Tracker scope**: vision_demo bỏ qua track-id; production cần `TrackerScope` per source/session để tránh cross-camera ID collision (H-06 trong Vision Platform review).

For production, refer to `Vision_platform_architecture_design/`.
```

---

## Phần 5 — `.gitignore` + commit (5 phút)

```bash
# .gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
build/
dist/

# Test artifacts
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
```

Init git và commit:

```bash
git init
git add .
git commit -m "Initial vision_demo MVP: Step 1-10 from Learning_path Module 03"
```

→ Project shippable.

---

## Phần 6 — Definition of Done checklist

Verify all items:

- [x] **Tests pass**: `pytest` → 110 passed, 1 skipped.
- [x] **Type hints**: mọi public function có type hint.
- [x] **No deps leak**: domain/ + kernel/ không import cv2/torch/zmq/structlog.
- [x] **CoW invariant**: stage không mutate input packet.
- [x] **Idempotent setup/teardown**: gọi 2 lần không crash.
- [x] **Process isolation**: 1 worker crash không kéo cả app.
- [x] **Backpressure policies**: 4 policy work đúng spec.
- [x] **End-to-end demo**: `demo_pipeline.py` chạy với `--source fake` và `--source noise`.
- [x] **Package builds**: `python -m build` produce wheel.
- [x] **README**: documents architecture + quick start.

→ ✅ Done.

---

## Phần 7 — Bài tập mở rộng (optional)

Nếu bạn muốn deepen:

### 1. Add `cv2`-based real adapter

Build `adapters/video_file_source.py` để đọc frame từ file video qua cv2:

```python
import cv2
class VideoFileSource:
    def __init__(self, path: str):
        self._path = path
        self._cap = None
    
    def setup(self):
        if self._cap is None:
            self._cap = cv2.VideoCapture(self._path)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open video: {self._path}")
    
    def read(self, timeout_ms=100):
        ret, frame = self._cap.read()
        if not ret:
            return ReadResult(status=ReadStatus.EOF)
        return ReadResult(status=ReadStatus.FRAME, data=frame)
    
    def teardown(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
    
    @property
    def is_finite(self):
        return True
    
    @property
    def source_id(self):
        return f"file:{self._path}"
```

→ Add vào contract test `pytest.fixture(params=[...])`. **Same contract test passes for new adapter.** Đây là power của Hexagonal.

### 2. Add async pipeline executor

Build `runtime/async_linear_executor.py`. Same interface as `SyncLinearExecutor`. Stages can be `async def _do_process()`. Use `asyncio.run()`.

### 3. Replace InlineInferenceClient with ZMQ

Build `adapters/zmq_inference_client.py` + `application/inference_service.py`. Same `IInferenceClient` interface. Production ready.

→ Đây là path natural từ vision_demo → Vision_platform production. Pattern không đổi, chỉ swap adapter.

---

## Tổng kết Module 03

Bạn vừa build từ folder rỗng:

- **4-layer** clean architecture (domain → kernel → runtime → application) + **adapter rim** + **profiles composition root** = 6 packages.
- **3 ports** (IFrameSource, IDetector, IStage).
- **5+ adapters** (Fake/Noise frame source, Fake detector, Inline inference, 2 stages).
- **111 test** (110 pass + 1 skip có chủ đích) verify mọi pattern.
- **End-to-end** pipeline chạy được.
- **Multi-process** supervisor với cascade shutdown.
- **Bulkhead isolation** verified qua test.
- **Cross-process SHM** transport verified.

**Khả năng bạn vừa có**:
- Đọc Vision_platform_architecture_design/ và **hiểu mọi trang**.
- Implement custom Vision Platform cho dự án thực tế.
- Code review pattern violations (coupling, dependency direction, immutability).
- Debug production issues bằng pattern recognition (SHM ABA, backpressure, bulkhead).

---

## Liên kết tiếp theo

- **Module 04 (Deep dives)**: GIL truth, SHM atomicity explained, ZMQ patterns, asyncio mental model, circuit breaker math, traceback retention.
- **Module 05 (Real bugs)**: walkthrough 12+ bug từ R1-R5 review của Vision Platform.
- **Module 06 (Implementation)**: 16-week plan triển khai dự án thật.
- **Module 07 (Troubleshooting)**: decision trees khi production bug.

---

## Tóm tắt 1 câu

> **vision_demo MVP done: 4-layer Hexagonal + 3 ports + 5 adapters + supervisor + 110 tests pass (1 skip có chủ đích) + end-to-end demo. Pattern foundation đủ để hiểu và triển khai Vision Platform production.**

✅ **Hoàn thành Module 03**.
