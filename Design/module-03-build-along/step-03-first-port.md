# Step 03 — IFrameSource port + 2 adapter + contract test

## Mục tiêu (2h)

Bạn sẽ build:

1. `kernel/ports/frame_source.py` — Protocol `IFrameSource`.
2. `adapters/fake_frame_source.py` — generate frame có pattern.
3. `adapters/noise_frame_source.py` — generate frame random với seed.
4. `tests/test_step_03_frame_source_contract.py` — **contract test** chung cho cả 2 adapter.

Cuối step: **31 tests** (30 pass, 1 skip vì infinite source) — gồm +1 test E-13 (source_id unique).

---

## Recap từ Module 02 file 02

- **Driven port** (driven adapter pattern): app cần data từ outside → định nghĩa interface, adapter implement.
- **Contract test**: 1 bộ test, mọi adapter implement port phải pass cùng test.
- Adapter cụ thể (cv2, RTSP, fake) ở **adapters/** folder. Use case không biết.

---

## Phần 1 — IFrameSource port (15 phút)

Tạo `src/vision_demo/kernel/ports/frame_source.py`:

```python
"""IFrameSource — driven port cho nguồn cung cấp frame."""
from typing import Protocol
import numpy as np
from vision_demo.kernel.read_result import ReadResult


class IFrameSource(Protocol):
    """Inbound source of frames (np.ndarray).
    
    Contract:
        - setup() MUST be called before first read(). Idempotent.
        - read(timeout_ms) returns ReadResult — KHÔNG return None.
        - teardown() releases resources. Idempotent.
        - is_finite True for batch (file ends → EOF), False for stream.
        - source_id unique cho logging/metrics.
    """
    def setup(self) -> None: ...
    
    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]: ...
    
    def teardown(self) -> None: ...
    
    @property
    def is_finite(self) -> bool: ...
    
    @property
    def source_id(self) -> str: ...
```

**Decisions giải thích**:

- **`Protocol` thay vì `ABC`**: structural typing, không cần inherit explicit. Test mock dễ — bất cứ class nào có 5 method này đều satisfy port (theo mypy).
- **`...` trong Protocol body**: đây là cú pháp Python để khai báo "abstract method without default". Equivalent với `pass` nhưng convention Protocol.
- **Lifecycle methods (`setup/teardown`)** — Idempotent rule trong docstring. Caller không nhớ trạng thái.
- **`source_id` là property, không method** — readonly, semantic data.
- **`is_finite` property**: giúp caller biết EOF có là "done" hay "bug".

---

## Phần 2 — FakeFrameSource adapter (30 phút)

Tạo `src/vision_demo/adapters/fake_frame_source.py`:

```python
"""Adapter: generate frames giả - cho test và dev offline."""
import itertools
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from vision_demo.kernel.read_result import ReadResult, ReadStatus

# source_id mặc định DUY NHẤT trong 1 process (ERRATA E-13). Port contract yêu cầu
# source_id unique; default cố định "fake_0" sẽ trùng khi tạo nhiều instance.
_fake_source_counter = itertools.count()


@dataclass
class FakeFrameSource:
    """In-memory frame generator. Implements IFrameSource."""
    width: int = 640
    height: int = 480
    max_frames: Optional[int] = 100
    inject_error_at: Optional[int] = None
    _source_id: str = field(default_factory=lambda: f"fake_{next(_fake_source_counter)}")
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)
    
    def setup(self) -> None:
        self._frame_count = 0
        self._is_setup = True
    
    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")
        
        if self.inject_error_at is not None and self._frame_count == self.inject_error_at:
            self.inject_error_at = None
            return ReadResult(
                status=ReadStatus.ERROR,
                error=RuntimeError("Injected fake error"),
                retry_after_ms=100,
            )
        
        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)
        
        frame = np.full(
            (self.height, self.width, 3),
            fill_value=self._frame_count % 256,
            dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)
    
    def teardown(self) -> None:
        self._is_setup = False
    
    @property
    def is_finite(self) -> bool:
        return self.max_frames is not None
    
    @property
    def source_id(self) -> str:
        return self._source_id
```

**Decisions**:

- **`@dataclass` (mutable!)**: state thay đổi (`_frame_count`). Adapter NOT frozen.
- **`max_frames: Optional[int] = 100`**: None = infinite (stream giả lập), int = batch.
- **`inject_error_at`**: test fault tolerance — set frame N raise error.
- **`_source_id` không underscore-private** trong dataclass init: dataclass treat như field. Để private trong API surface, prefix `_` (Python convention).
- **`field(default=0, init=False)`**: state field không expose qua constructor. Caller không pass `_frame_count`.
- **Frame content predictable**: `np.full(value=count % 256)` — frame N có brightness `N % 256`. Test verify được.

---

## Phần 3 — NoiseFrameSource adapter (15 phút)

Tạo `src/vision_demo/adapters/noise_frame_source.py`:

```python
"""Adapter: generate random noise frames - alternative test source."""
import itertools
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from vision_demo.kernel.read_result import ReadResult, ReadStatus

# source_id mặc định DUY NHẤT trong 1 process (ERRATA E-13).
_noise_source_counter = itertools.count()


@dataclass
class NoiseFrameSource:
    """Random noise generator. Useful cho test detector against random input."""
    width: int = 320
    height: int = 240
    max_frames: Optional[int] = 50
    seed: Optional[int] = 42
    _source_id: str = field(default_factory=lambda: f"noise_{next(_noise_source_counter)}")
    _rng: np.random.Generator = field(default=None, init=False)
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)
    
    def setup(self) -> None:
        self._frame_count = 0
        self._rng = np.random.default_rng(self.seed)
        self._is_setup = True
    
    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")
        
        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)
        
        frame = self._rng.integers(
            0, 256, size=(self.height, self.width, 3), dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)
    
    def teardown(self) -> None:
        self._is_setup = False
        self._rng = None
    
    @property
    def is_finite(self) -> bool:
        return self.max_frames is not None
    
    @property
    def source_id(self) -> str:
        return self._source_id
```

**Decisions**:

- **`np.random.default_rng(seed)`**: modern numpy random API. `seed=42` → reproducible output. Test cần deterministic.
- **`teardown` resets `_rng = None`**: cleanup explicit. Setup lại sẽ tạo Generator mới.
- **Cấu trúc gần giống Fake**: cố tình để show 2 adapter share **shape**, khác **content**. Pattern.

---

## Phần 4 — Contract test (45 phút)

Đây là **technique quan trọng**. 1 test suite cho mọi adapter.

Tạo `tests/test_step_03_frame_source_contract.py`:

```python
"""Step 03: contract test - mọi IFrameSource adapter PHẢI pass cùng test."""
import numpy as np
import pytest
from vision_demo.kernel.read_result import ReadStatus
from vision_demo.adapters.fake_frame_source import FakeFrameSource
from vision_demo.adapters.noise_frame_source import NoiseFrameSource


@pytest.fixture(params=[
    pytest.param(
        lambda: FakeFrameSource(width=320, height=240, max_frames=5),
        id="fake_finite_5",
    ),
    pytest.param(
        lambda: FakeFrameSource(width=160, height=120, max_frames=None),
        id="fake_infinite",
    ),
    pytest.param(
        lambda: NoiseFrameSource(width=320, height=240, max_frames=5),
        id="noise_finite_5",
    ),
])
def source(request):
    """Builder fixture - tạo adapter mới mỗi test (isolation)."""
    src = request.param()
    src.setup()
    yield src
    src.teardown()


class TestFrameSourceContract:
    """Mọi IFrameSource impl PHẢI thỏa các contract sau."""
    
    def test_read_returns_readresult(self, source):
        result = source.read(timeout_ms=100)
        assert hasattr(result, "status")
    
    def test_first_read_returns_valid_status(self, source):
        result = source.read(timeout_ms=100)
        assert result.status in {
            ReadStatus.FRAME, ReadStatus.EOF, ReadStatus.TIMEOUT,
            ReadStatus.RECONNECTING, ReadStatus.DROPPED, ReadStatus.ERROR,
        }
    
    def test_frame_status_implies_data(self, source):
        result = source.read(timeout_ms=100)
        if result.status == ReadStatus.FRAME:
            assert result.data is not None
            assert isinstance(result.data, np.ndarray)
            assert result.data.ndim == 3
            assert result.has_data
    
    def test_non_frame_status_no_data(self, source):
        for _ in range(20):
            result = source.read(timeout_ms=10)
            if result.status != ReadStatus.FRAME:
                assert result.data is None
    
    def test_source_id_is_str(self, source):
        assert isinstance(source.source_id, str)
        assert len(source.source_id) > 0
    
    def test_is_finite_is_bool(self, source):
        assert isinstance(source.is_finite, bool)
    
    def test_setup_idempotent(self, source):
        source.setup()  # already setup in fixture
        source.setup()  # 2nd call must not raise
    
    def test_teardown_idempotent(self, source):
        source.teardown()
        source.teardown()  # 2nd call must not raise
    
    def test_finite_source_eventually_eofs(self, source):
        if not source.is_finite:
            pytest.skip("Source is infinite")
        seen_eof = False
        for _ in range(1000):
            r = source.read(timeout_ms=10)
            if r.status == ReadStatus.EOF:
                seen_eof = True
                break
        assert seen_eof


# ============ Adapter-specific tests ============

def test_fake_frame_content_predictable():
    """Fake source dùng frame_count % 256 — verify."""
    src = FakeFrameSource(width=10, height=10, max_frames=None)
    src.setup()
    
    # Frame 0: all 0
    r0 = src.read()
    assert r0.data[0, 0, 0] == 0
    
    # Frame 1: all 1
    r1 = src.read()
    assert r1.data[0, 0, 0] == 1
    
    src.teardown()


def test_fake_inject_error():
    src = FakeFrameSource(max_frames=10, inject_error_at=2)
    src.setup()
    
    # Frame 0, 1: FRAME
    assert src.read().status == ReadStatus.FRAME
    assert src.read().status == ReadStatus.FRAME
    # Frame 2: ERROR (injected)
    r = src.read()
    assert r.status == ReadStatus.ERROR
    assert "Injected" in str(r.error)
    # Frame 3+: FRAME again (error fires once)
    assert src.read().status == ReadStatus.FRAME
    
    src.teardown()


def test_noise_seed_reproducible():
    """Same seed → same frames."""
    a = NoiseFrameSource(seed=42, max_frames=3)
    b = NoiseFrameSource(seed=42, max_frames=3)
    a.setup(); b.setup()
    
    fa = a.read().data
    fb = b.read().data
    assert np.array_equal(fa, fb)
    
    a.teardown(); b.teardown()


def test_source_id_unique_by_default():
    """ERRATA E-13: 2 instance không truyền id → source_id KHÁC nhau (port yêu cầu unique)."""
    assert FakeFrameSource().source_id != FakeFrameSource().source_id
    assert NoiseFrameSource().source_id != NoiseFrameSource().source_id
    assert FakeFrameSource(_source_id="cam1").source_id == "cam1"  # explicit vẫn giữ
```

### Giới hạn & contract cho adapter THẬT (ERRATA E-13 — đọc khi viết adapter phần cứng)

Fake/Noise là adapter test (in-memory, non-blocking). Khi viết adapter THẬT (OpenCV/RTSP/webcam),
4 điểm sau là **contract bắt buộc** (Fake/Noise không cần vì không có tài nguyên/đa luồng):
- **Thread-safety:** adapter KHÔNG thread-safe; kiến trúc dùng **1 process/nguồn, single-thread**
  (bulkhead — Module 02/Step 09). Đừng gọi `read()`/`teardown()` từ nhiều thread. Cần thì bọc `threading.Lock`.
- **Timeout:** adapter blocking (RTSP) PHẢI tôn trọng `timeout_ms` và trả `ReadStatus.TIMEOUT` thay vì
  block vô hạn. Bổ sung contract test latency-injection khi có adapter blocking.
- **source_id unique:** đã auto-unique theo process; cross-process vẫn nên truyền id tường minh (composition root gán).
- **setup() thất bại nửa chừng:** dùng `try/finally` (hoặc context manager) để thu hồi tài nguyên đã mở (fd/socket/camera bus) nếu khởi tạo lỗi.
<!-- ANCHOR_E13_NOTE -->

**Decisions giải thích**:

- **`@pytest.fixture(params=[...])`**: pytest tự run mỗi test với mỗi adapter. Thêm adapter mới = thêm 1 dòng `pytest.param(lambda: ...)`.
- **`lambda: FakeFrameSource(...)`** thay vì `FakeFrameSource(...)`: builder pattern. Mỗi test gọi lambda → tạo instance mới (isolation). Nếu pass instance → share giữa test → state pollute.
- **Class `TestFrameSourceContract`**: pytest auto-discover class `Test*` với method `test_*`. Class group related tests cho organization.
- **Adapter-specific tests** ở ngoài class: test riêng cho từng adapter (fake content predictable, noise seed reproducible) — không apply cho adapter khác.

**Run**:
```bash
pytest tests/test_step_03_frame_source_contract.py -v
```

Expected:
```
collected 31 items
... 30 passed, 1 skipped ...
```

(Skip vì test "finite source eventually eofs" với `fake_infinite` source.)

---

## Phần 5 — Verify integration (5 phút)

Run all tests:
```bash
pytest
```

Expected (baseline giáo trình): **48 passed, 1 skipped** (2 smoke + 16 step-02 + 31 step-03).
*Trong repo `vision-platform` của ta:* **51 passed, 1 skipped** (2 smoke + 19 step-02 + 31 step-03 —
step-02/03 cộng test E-11/E-12/E-13). Luôn đọc số THẬT khi chạy (E-4).

---

## Self-check

1. **Protocol vs ABC**: 2 ưu điểm Protocol cho IFrameSource?

2. **`@pytest.fixture(params=[lambda: ..., lambda: ...])`** — sao `lambda` không trực tiếp instance?

3. Bạn được giao thêm adapter `WebcamSource`. **Bao nhiêu file** mới tạo? **Bao nhiêu file** modify?

4. Tại sao `setup_idempotent` test quan trọng? Bug gì nếu adapter không idempotent?

5. **Adapter-specific test** vs **contract test** — khác nhau? Tại sao tách?

<details>
<summary>Đáp án</summary>

1. **Protocol pros**:
   - **Structural typing**: adapter không cần `class FakeFrameSource(IFrameSource):`. Bất cứ class nào có 5 method là OK. Pythonic, ít boilerplate.
   - **Test mocking dễ**: tạo class with same methods = adapter. Không cần inherit.

2. **Lambda = builder/factory**:
   - Direct `FakeFrameSource(...)`: pytest evaluate khi load test file → 1 instance share giữa các test → state pollute.
   - `lambda: FakeFrameSource(...)`: pytest call mỗi test → instance mới → isolation.

3. **Thêm WebcamSource**:
   - **Tạo mới**: 1 file (`adapters/webcam_source.py`).
   - **Modify**: 1 file (`tests/test_step_03_frame_source_contract.py` — thêm 1 dòng `pytest.param(lambda: WebcamSource(...), id="webcam")`).
   - **Composition root** (`profiles/demo_pipeline.py`): thêm `--source webcam` branch.
   - **Không động** vào `IFrameSource` port hay use case logic.
   
   → 1 thêm + 2 modify = scope thấp. Đây là **lợi ích Hexagonal**.

4. **Idempotent `setup`**:
   - Bug nếu không idempotent: gọi `setup()` 2 lần → resource leak (mở 2 cv2.VideoCapture, leak fd) hoặc state corrupt (counter reset 2 lần).
   - Caller không nhớ trạng thái — luôn safe gọi `setup()`.
   - Recovery scenario: caller error → cleanup → retry → setup again. Không idempotent = setup 2nd call fail.

5. **Contract test** = ràng buộc CHUNG cho mọi adapter (return ReadResult, status valid, idempotent...). 1 lần viết, mọi adapter pass.
   
   **Adapter-specific test** = ràng buộc RIÊNG cho 1 adapter (Fake content predictable, Noise seed reproducible). Không apply cho adapter khác.
   
   **Tách**: contract test giúp dev mới adapter biết "phải pass test này". Adapter-specific test verify adapter logic riêng. Mix sẽ confusing.

</details>

---

## Liên kết

- **Module 02 file 02** (ports-and-adapters-build-one) — pattern chính.
- **Production**: `Vision_platform_architecture_design/03-data-contracts/02-idatasource-t-readresult.md` — port full.

---

## Tóm tắt 1 câu

> **1 port `IFrameSource` (Protocol) + 2 adapter (Fake, Noise) + 1 contract test suite parametrized với fixture builder. Thêm adapter mới = thêm 1 dòng `pytest.param`.**

➡️ Tiếp theo: [`step-04-first-pipeline.md`](step-04-first-pipeline.md)
