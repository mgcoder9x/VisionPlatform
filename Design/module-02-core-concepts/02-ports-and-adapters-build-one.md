# 02 — Ports & Adapters trong Vision context — Build 1 cái thật

## TL;DR (30 giây)

> File 01 đã dạy concept. File này bạn **build 1 port + 3 adapter cho frame source** trong Python — code thật, có test, chạy được. Bạn sẽ có code dùng lại được cho `vision_demo_workspace/` ở Module 03.
>
> **Lưu ý naming**: trong file này `vision_demo/` (path) = Python package name. Khi build chính thức ở Module 03, package này sẽ nằm trong `vision_demo_workspace/src/vision_demo/` (folder workspace chứa package). Đây là exercise standalone — bạn có thể build trong folder bất kỳ tên gì để học, miễn import path là `vision_demo`.

---

## Mental hook

Bạn đang code `process_one_frame` trong project HeadDetect. Test bị stuck vì:

```python
def test_process_one_frame():
    # ...làm sao có 1 frame để test?...
    frame = ???
```

Cách 1 — đọc từ RTSP thật:
- Cần camera RTSP hoạt động.
- Test chậm, flaky (camera disconnect random).
- Cần config IP camera trong CI.
- Khi test fail, không biết do logic hay do network.

Cách 2 — đọc từ video file:
- Có file `test_video.mp4` trong repo.
- Test reproducible.
- Nhưng test code phải biết cách đọc cả RTSP lẫn video file → có nhánh `if rtsp else file`.

Cách 3 — frame mock numpy array:
- Tạo `np.zeros((1080, 1920, 3))` — fast.
- Test logic không cần đọc file.
- Nhưng code production của bạn dùng cách nào để consume frame?

→ Cả 3 case đều cần **cùng 1 abstraction** — `IFrameSource`. Cách bạn xây nó quyết định test có dùng được hay không.

---

## Spec — chính xác bạn sẽ build gì

Yêu cầu:

1. **1 port `IFrameSource`** — abstraction cho "nguồn cung cấp frame".
2. **3 adapter** implement port:
   - `VideoFileSource` — đọc từ file video (cv2).
   - `WebcamSource` — đọc từ webcam USB (cv2).
   - `FakeFrameSource` — generate frame giả (cho test).
3. **1 contract test suite** — 1 bộ test, mọi adapter PHẢI pass.
4. **1 use case `ProcessOneFrameUseCase`** — minimal logic dùng port.
5. **Composition root** — wire cho dev (FakeFrameSource) và production (VideoFileSource hoặc WebcamSource).

Sau bài này, bạn có code dùng được cho Module 03.

---

## Step 1: Define ReadResult — error handling từ đầu

Đầu tiên, port `read()` trả gì?

**Cách dở**: `Optional[Frame]` — None nghĩa là gì? EOF? Network error? Timeout?

```python
# Anti-pattern
class IFrameSource(Protocol):
    def read(self) -> Optional[Frame]: ...

# Caller
frame = source.read()
if frame is None:
    # do gì? log? retry? exit?
    ...
```

→ Caller không biết **vì sao** None. Phải đoán hoặc dùng try/except với hierarchy lộn xộn.

**Cách đúng**: explicit status enum. Đây chính là pattern Vision Platform dùng.

```python
# vision_demo/kernel/read_result.py
"""ReadResult — explicit status, no Optional ambiguity."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Generic, TypeVar
import numpy as np


class ReadStatus(Enum):
    FRAME = "frame"             # data có sẵn
    EOF = "eof"                 # source hết (file batch)
    TIMEOUT = "timeout"         # không có data trong deadline
    RECONNECTING = "reconnecting"  # source mất kết nối, đang retry
    DROPPED = "dropped"         # frame bị drop chủ động (backpressure)
    ERROR = "error"             # source error (có thể recoverable)


T = TypeVar("T")


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """Generic explicit-status result for source reads.
    
    Caller MUST handle each status explicitly. Pattern matching:
        match result.status:
            case ReadStatus.FRAME: ...
            case ReadStatus.EOF: ...
            case ReadStatus.TIMEOUT: ...
            case _: ...
    """
    status: ReadStatus
    data: Optional[T] = None
    error: Optional[Exception] = None
    retry_after_ms: Optional[int] = None

    @property
    def has_data(self) -> bool:
        return self.status == ReadStatus.FRAME and self.data is not None
```

**Tại sao 6 status thay vì 2?**

Mỗi status có **action khác nhau** ở caller side:
- `FRAME` → process.
- `EOF` → stop (file mode) hoặc reconnect (stream mode — bug?).
- `TIMEOUT` → continue (transient, đếm metric).
- `RECONNECTING` → sleep `retry_after_ms` rồi retry.
- `DROPPED` → continue, đếm metric.
- `ERROR` → log + check fatal, có thể stop.

Nếu chỉ `Optional[Frame]` → 1 nhánh `if None: ...` không đủ smart.

---

## Step 2: Define IFrameSource port

```python
# vision_demo/kernel/ports/frame_source.py
"""Driven port: app cần frame từ outside."""
from typing import Protocol
import numpy as np
from vision_demo.kernel.read_result import ReadResult


class IFrameSource(Protocol):
    """Inbound source of frames.

    Not async — caller decides threading. Adapter implementations
    typically wrap blocking I/O (cv2.VideoCapture, file read).
    
    Contract:
        - `setup()` MUST be called before first `read()`.
        - `read(timeout_ms)` returns ReadResult with status; never None.
        - `teardown()` releases resources. Idempotent.
        - `is_finite` True for batch sources (file ends → EOF), False for streams.
        - `source_id` unique identifier for logging/metrics.
    """
    def setup(self) -> None: ...
    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]: ...
    def teardown(self) -> None: ...
    
    @property
    def is_finite(self) -> bool: ...
    
    @property
    def source_id(self) -> str: ...
```

**Quan sát**:
- **Không** `def __init__` trong Protocol. Protocol định nghĩa **interface** (method shape), không constructor.
- `is_finite` & `source_id` là properties — semantics, không state.
- `setup()` / `teardown()` lifecycle. Không dùng `__enter__`/`__exit__` vì caller có thể không dùng `with`.

---

## Step 3: Adapter 1 — `FakeFrameSource` (đơn giản nhất, dùng cho test)

Build adapter đơn giản nhất TRƯỚC. Sai lầm thường thấy: build adapter phức tạp (RTSP) trước → debug khổ vì lẫn lộn "lỗi do logic" vs "lỗi do network".

```python
# vision_demo/adapters/fake_frame_source.py
"""Adapter: generate frames giả - cho test và dev offline."""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from vision_demo.kernel.read_result import ReadResult, ReadStatus


@dataclass
class FakeFrameSource:
    """In-memory frame generator.
    
    Modes:
        - max_frames=N: trả N frame rồi EOF (giả lập batch).
        - max_frames=None: vô hạn (giả lập stream).
        - inject_error_at: trả ERROR ở frame N (giả lập transient bug).
    """
    width: int = 640
    height: int = 480
    max_frames: Optional[int] = 100
    inject_error_at: Optional[int] = None
    _source_id: str = "fake_0"
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)

    def setup(self) -> None:
        if self._is_setup:
            return
        # Reset counter on setup (cho test re-run).
        self._frame_count = 0
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")
        
        # Inject error?
        if self.inject_error_at is not None and self._frame_count == self.inject_error_at:
            self.inject_error_at = None  # only once
            return ReadResult(
                status=ReadStatus.ERROR,
                error=RuntimeError("Injected fake error"),
                retry_after_ms=100,
            )
        
        # EOF?
        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)
        
        # Generate frame: gradient theo frame number cho dễ verify.
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
- `dataclass` — boilerplate constructor. `field(init=False)` cho internal state.
- `setup()` idempotent — gọi 2 lần không crash.
- `inject_error_at` tự reset sau khi fired (test reproducibility).
- `np.full(value=count % 256)` — frame có nội dung verify được.

---

## Step 4: Adapter 2 — `VideoFileSource` (cv2 file)

```python
# vision_demo/adapters/video_file_source.py
"""Adapter: đọc từ file video qua cv2."""
from typing import Optional
import numpy as np

try:
    import cv2  # type: ignore
except ImportError as e:
    cv2 = None  # type: ignore
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

from vision_demo.kernel.read_result import ReadResult, ReadStatus


class VideoFileSource:
    """Đọc frame từ file video (mp4, avi, ...).
    
    is_finite=True: hết file → EOF, KHÔNG loop.
    """

    def __init__(self, path: str, source_id: Optional[str] = None):
        if cv2 is None:
            raise RuntimeError(
                f"cv2 not available: {_IMPORT_ERROR}. "
                f"Install: pip install opencv-python"
            )
        self._path = path
        self._source_id = source_id or f"file_{path}"
        self._cap: Optional["cv2.VideoCapture"] = None  # type: ignore

    def setup(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return  # idempotent
        self._cap = cv2.VideoCapture(self._path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video: {self._path}")

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("setup() must be called before read()")
        
        # cv2.VideoCapture.read() là blocking. Timeout không enforce ở đây
        # — tuỳ adapter wrap; cv2 file thì gần instant cho file local.
        ret, frame = self._cap.read()
        if not ret:
            # cv2 không phân biệt EOF vs corruption — assume EOF cho file.
            return ReadResult(status=ReadStatus.EOF)
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_finite(self) -> bool:
        return True

    @property
    def source_id(self) -> str:
        return self._source_id
```

**Decisions**:
- `try/except ImportError` — adapter degrade gracefully nếu cv2 không cài. **Quan trọng** với multi-adapter design: 1 user không cần cv2 (chỉ test với fake) phải install được package.
- Idempotent setup — gọi 2 lần OK.
- Teardown set `_cap = None` để setup lại được sau teardown.
- `is_finite=True` — cv2 file ends → EOF (không loop). Stream behavior muốn loop = caller wrap thêm decorator `LoopingFrameSource`.

---

## Step 5: Adapter 3 — `WebcamSource`

```python
# vision_demo/adapters/webcam_source.py
"""Adapter: đọc từ webcam USB qua cv2."""
from typing import Optional
import time
import numpy as np

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

from vision_demo.kernel.read_result import ReadResult, ReadStatus


class WebcamSource:
    """Đọc frame từ webcam USB.
    
    is_finite=False: stream vô hạn. Reconnect on transient failure.
    """

    def __init__(self, device_index: int = 0, source_id: Optional[str] = None):
        if cv2 is None:
            raise RuntimeError("cv2 not available; install opencv-python")
        self._device_index = device_index
        self._source_id = source_id or f"webcam_{device_index}"
        self._cap: Optional["cv2.VideoCapture"] = None
        self._consecutive_failures = 0

    def setup(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return
        self._cap = cv2.VideoCapture(self._device_index)
        # Webcam-specific: set frame buffer size = 1 (giảm latency,
        # luôn lấy frame mới nhất).
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {self._device_index}")
        self._consecutive_failures = 0

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("setup() must be called before read()")
        
        ret, frame = self._cap.read()
        if not ret:
            self._consecutive_failures += 1
            # 3 failure liên tiếp → giả định disconnect.
            if self._consecutive_failures >= 3:
                # Nếu không reconnect được → ERROR; nếu reconnect được → RECONNECTING.
                self._cap.release()
                try:
                    self._cap = cv2.VideoCapture(self._device_index)
                    if self._cap.isOpened():
                        self._consecutive_failures = 0
                        return ReadResult(
                            status=ReadStatus.RECONNECTING,
                            retry_after_ms=500,
                        )
                except Exception as e:
                    return ReadResult(
                        status=ReadStatus.ERROR,
                        error=e,
                        retry_after_ms=2000,
                    )
                return ReadResult(
                    status=ReadStatus.ERROR,
                    error=RuntimeError("Webcam disconnected"),
                    retry_after_ms=2000,
                )
            # Transient failure — TIMEOUT (caller có thể retry).
            return ReadResult(status=ReadStatus.TIMEOUT)
        
        self._consecutive_failures = 0
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_finite(self) -> bool:
        return False  # webcam = stream

    @property
    def source_id(self) -> str:
        return self._source_id
```

**Decisions phức tạp hơn `VideoFileSource`**:
- Webcam **disconnect** thường xuyên (USB lỏng, driver hiccup) → có reconnect logic.
- 3 failure liên tiếp → reconnect attempt → trả `RECONNECTING` để caller biết sleep.
- `is_finite=False` → caller biết EOF không phải normal flow.

→ **Cùng port `IFrameSource`**, semantics khác. Đây là điểm mạnh của Hexagonal: caller không quan tâm chi tiết.

---

## Step 6: Use case `ProcessOneFrameUseCase`

```python
# vision_demo/application/process_one_frame.py
"""Minimal use case dùng IFrameSource."""
from dataclasses import dataclass
from typing import Optional
from vision_demo.kernel.ports.frame_source import IFrameSource
from vision_demo.kernel.read_result import ReadStatus


@dataclass(frozen=True)
class ProcessFrameResult:
    """Kết quả xử lý 1 frame."""
    success: bool
    frame_shape: Optional[tuple] = None  # (h, w, c)
    mean_brightness: Optional[float] = None
    status_seen: str = ""
    error_msg: Optional[str] = None


class ProcessOneFrameUseCase:
    """Đọc 1 frame, tính brightness trung bình.
    
    Dùng làm 'building block' đơn giản nhất chứng minh port-adapter pattern.
    """
    def __init__(self, source: IFrameSource):
        self._source = source

    def execute(self, timeout_ms: int = 100) -> ProcessFrameResult:
        """Đọc 1 frame, xử lý, return kết quả."""
        result = self._source.read(timeout_ms=timeout_ms)
        
        match result.status:
            case ReadStatus.FRAME:
                frame = result.data
                return ProcessFrameResult(
                    success=True,
                    frame_shape=frame.shape,
                    mean_brightness=float(frame.mean()),
                    status_seen="frame",
                )
            case ReadStatus.EOF:
                return ProcessFrameResult(success=False, status_seen="eof")
            case ReadStatus.TIMEOUT:
                return ProcessFrameResult(success=False, status_seen="timeout")
            case ReadStatus.RECONNECTING:
                return ProcessFrameResult(success=False, status_seen="reconnecting")
            case ReadStatus.DROPPED:
                return ProcessFrameResult(success=False, status_seen="dropped")
            case ReadStatus.ERROR:
                return ProcessFrameResult(
                    success=False,
                    status_seen="error",
                    error_msg=str(result.error),
                )
            case _:
                # Defensive: status enum mở rộng tương lai.
                return ProcessFrameResult(
                    success=False, status_seen=f"unknown_{result.status}",
                )
```

**Quan sát quan trọng**: `ProcessOneFrameUseCase` **không** import `cv2`, `numpy.lib`, `requests`. Chỉ port. **Tested without cv2 installed** — pass mock source.

---

## Step 7: Contract test — bộ test 1 lần, mọi adapter pass

Đây là pattern **vital** với multi-adapter setup. Một bộ test `test_frame_source_contract.py` mà MỌI adapter phải pass.

```python
# tests/test_frame_source_contract.py
"""Contract test: mọi IFrameSource implementation phải pass."""
import pytest
import numpy as np
from vision_demo.adapters.fake_frame_source import FakeFrameSource
from vision_demo.kernel.read_result import ReadStatus


# Parametrize danh sách adapter. Để thêm adapter mới = thêm 1 dòng.
@pytest.fixture(params=[
    pytest.param(
        lambda: FakeFrameSource(width=320, height=240, max_frames=5),
        id="fake_finite",
    ),
    pytest.param(
        lambda: FakeFrameSource(width=320, height=240, max_frames=None),
        id="fake_infinite",
    ),
    # Khi bạn build VideoFileSource (Step 4), thêm 1 dòng:
    # pytest.param(lambda: VideoFileSource("tests/data/sample.mp4"), id="video_file"),
    # → Cùng contract test sẽ tự động chạy cho adapter mới — đây chính là power
    #   của Hexagonal: 1 contract, N adapters validate.
])
def source(request):
    """Builder fixture — tạo adapter mới mỗi test."""
    src = request.param()
    src.setup()
    yield src
    src.teardown()


class TestFrameSourceContract:
    """Mọi adapter PHẢI thoả các contract sau."""

    def test_read_returns_readresult(self, source):
        result = source.read(timeout_ms=100)
        assert hasattr(result, "status"), "read() phải trả ReadResult"

    def test_first_read_returns_frame_or_valid_status(self, source):
        result = source.read(timeout_ms=100)
        assert result.status in {
            ReadStatus.FRAME, ReadStatus.EOF, ReadStatus.TIMEOUT,
            ReadStatus.RECONNECTING, ReadStatus.DROPPED, ReadStatus.ERROR,
        }, f"Status không hợp lệ: {result.status}"

    def test_frame_status_implies_data(self, source):
        result = source.read(timeout_ms=100)
        if result.status == ReadStatus.FRAME:
            assert result.data is not None
            assert isinstance(result.data, np.ndarray)
            assert result.data.ndim in (2, 3)  # gray hoặc color
            assert result.has_data

    def test_non_frame_status_implies_no_data(self, source):
        """Status != FRAME → data = None."""
        for _ in range(20):  # try multiple reads
            result = source.read(timeout_ms=10)
            if result.status != ReadStatus.FRAME:
                assert result.data is None, (
                    f"status={result.status} nhưng data không None"
                )

    def test_source_id_is_str(self, source):
        assert isinstance(source.source_id, str)
        assert len(source.source_id) > 0

    def test_is_finite_is_bool(self, source):
        assert isinstance(source.is_finite, bool)

    def test_setup_idempotent(self, source):
        """Gọi setup() 2 lần không raise."""
        source.setup()  # đã setup ở fixture
        source.setup()  # lần 2

    def test_teardown_idempotent(self, source):
        source.teardown()
        source.teardown()  # lần 2 không raise

    def test_finite_source_eventually_eof(self, source):
        """Source finite phải EOF sau hữu hạn read."""
        if not source.is_finite:
            pytest.skip("Source infinite, skip")
        
        seen_eof = False
        for _ in range(1000):  # bound
            result = source.read(timeout_ms=10)
            if result.status == ReadStatus.EOF:
                seen_eof = True
                break
        assert seen_eof, "Source finite không bao giờ EOF sau 1000 reads"
```

**Cấu trúc**:
- `@pytest.fixture(params=[...])` — pytest tự run mỗi test với mỗi adapter.
- Thêm adapter mới? Thêm 1 dòng `pytest.param(lambda: NewAdapter(...), id="...")`.
- **9 contract test** áp dụng cho mọi adapter.

→ **Khi viết adapter mới, run pytest. Pass = adapter conform contract.**

---

## Step 8: Use case test (logic test, không cần adapter thật)

```python
# tests/test_process_one_frame.py
"""Test use case logic, dùng FakeFrameSource."""
from vision_demo.application.process_one_frame import ProcessOneFrameUseCase
from vision_demo.adapters.fake_frame_source import FakeFrameSource


def test_processes_one_frame_successfully():
    src = FakeFrameSource(width=100, height=80, max_frames=10)
    src.setup()
    uc = ProcessOneFrameUseCase(src)
    
    result = uc.execute()
    
    assert result.success
    assert result.frame_shape == (80, 100, 3)
    assert result.status_seen == "frame"
    assert 0.0 <= result.mean_brightness <= 255.0
    
    src.teardown()


def test_eof_returns_failure():
    src = FakeFrameSource(max_frames=0)  # empty
    src.setup()
    uc = ProcessOneFrameUseCase(src)
    
    result = uc.execute()
    
    assert not result.success
    assert result.status_seen == "eof"
    assert result.frame_shape is None


def test_error_propagates_message():
    src = FakeFrameSource(max_frames=10, inject_error_at=0)
    src.setup()
    uc = ProcessOneFrameUseCase(src)
    
    result = uc.execute()
    
    assert not result.success
    assert result.status_seen == "error"
    assert "Injected" in result.error_msg
```

→ Use case test < 1ms. Không cần cv2, không cần file, không cần webcam.

---

## Step 9: Composition root

```python
# vision_demo/__main__.py
"""Composition root — chỗ duy nhất biết cụ thể adapter nào."""
import argparse
import sys
from vision_demo.application.process_one_frame import ProcessOneFrameUseCase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=["fake", "file", "webcam"],
        default="fake",
        help="Frame source type",
    )
    parser.add_argument("--path", help="File path (for --source=file)")
    parser.add_argument(
        "--device", type=int, default=0,
        help="Webcam device index (for --source=webcam)",
    )
    args = parser.parse_args()
    
    # Ở đây — chỗ DUY NHẤT trong code biết cụ thể adapter nào.
    if args.source == "fake":
        from vision_demo.adapters.fake_frame_source import FakeFrameSource
        source = FakeFrameSource(max_frames=10)
    elif args.source == "file":
        from vision_demo.adapters.video_file_source import VideoFileSource
        if not args.path:
            parser.error("--path required for --source=file")
        source = VideoFileSource(args.path)
    elif args.source == "webcam":
        from vision_demo.adapters.webcam_source import WebcamSource
        source = WebcamSource(device_index=args.device)
    else:
        parser.error(f"Unknown source: {args.source}")
    
    source.setup()
    try:
        use_case = ProcessOneFrameUseCase(source)
        for i in range(5):
            result = use_case.execute(timeout_ms=200)
            print(
                f"[{i}] success={result.success} "
                f"status={result.status_seen} "
                f"shape={result.frame_shape} "
                f"brightness={result.mean_brightness}"
            )
            if result.status_seen == "eof":
                break
    finally:
        source.teardown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Key idea**: `if args.source == ...` LOGIC CHỌN ADAPTER là **duy nhất trong file này**. Mọi nơi khác dùng `IFrameSource` interface.

---

## Code-along (45 phút)

```bash
mkdir -p ports_adapters_workspace
cd ports_adapters_workspace
py -m venv .venv
.venv\Scripts\activate

mkdir -p vision_demo/{kernel/ports,adapters,application}
mkdir tests
echo. > vision_demo/__init__.py
echo. > vision_demo/kernel/__init__.py
echo. > vision_demo/kernel/ports/__init__.py
echo. > vision_demo/adapters/__init__.py
echo. > vision_demo/application/__init__.py

pip install pytest opencv-python numpy
```

Tự gõ lại các file ở Step 1-9. **KHÔNG copy-paste**.

Run:

```bash
# Test
py -m pytest tests/ -v

# Run với fake source
py -m vision_demo --source fake

# Run với video file (cần file thật)
py -m vision_demo --source file --path some_video.mp4

# Run với webcam (cần webcam)
py -m vision_demo --source webcam
```

Expected:
- Test pass tất cả.
- Fake mode in 5 dòng frame info.
- File mode đọc 5 frame đầu của video.

### Bài tập mở rộng

**Bài 1: Adapter `LoopingFrameSource` (decorator)**

Build adapter wrap `IFrameSource` khác, khi gặp EOF thì **restart** (đọc lại từ đầu). Hữu ích để loop video file vô hạn.

```python
class LoopingFrameSource:
    """Decorator: wrap finite source, loop khi EOF."""
    def __init__(self, inner: IFrameSource):
        self._inner = inner
    
    def setup(self) -> None:
        self._inner.setup()
    
    def read(self, timeout_ms=100) -> ReadResult:
        result = self._inner.read(timeout_ms)
        if result.status == ReadStatus.EOF:
            # Reset & re-read
            self._inner.teardown()
            self._inner.setup()
            return self._inner.read(timeout_ms)
        return result
    
    def teardown(self) -> None: 
        self._inner.teardown()
    
    @property
    def is_finite(self) -> bool: 
        return False  # loop = infinite
    
    @property
    def source_id(self) -> str: 
        return f"loop({self._inner.source_id})"
```

→ Compose: `LoopingFrameSource(VideoFileSource("video.mp4"))` — file lặp vô hạn.

**Bài 2: Adapter giả lập network failure**

Tạo `FlakySource` wrap source khác, random `inject` lỗi 10% time:

```python
class FlakySource:
    def __init__(self, inner: IFrameSource, error_rate: float = 0.1):
        self._inner = inner
        self._rate = error_rate
    
    def read(self, timeout_ms=100) -> ReadResult:
        import random
        if random.random() < self._rate:
            return ReadResult(
                status=ReadStatus.ERROR,
                error=RuntimeError("Flaky network"),
                retry_after_ms=200,
            )
        return self._inner.read(timeout_ms)
    
    # ... setup/teardown delegate ...
```

→ Run use case với `FlakySource` — verify use case xử lý error đúng.

**Bài 3: Đo coupling**

Mở folder bạn vừa code, đếm:
1. Bao nhiêu file import `cv2`?
2. Bao nhiêu file import `numpy`?
3. Bao nhiêu file import từ `vision_demo.adapters`?

Expected:
- `cv2`: chỉ trong `adapters/video_file_source.py`, `adapters/webcam_source.py`.
- `numpy`: nhiều (kernel + adapter) — OK vì numpy là math infrastructure.
- `vision_demo.adapters`: chỉ trong `__main__.py` (composition root).

→ Nếu thấy `vision_demo/application/*.py` import `cv2` hay `vision_demo.adapters` → **vi phạm Hexagonal**.

---

## Checkpoint

Mở `_my_answers.md`:

1. Tại sao `read()` trả `ReadResult` thay vì `Optional[Frame]`? Cho 2 lý do.

2. `is_finite=True` vs `False` — hành vi caller phải khác nhau như thế nào? Cho code snippet.

3. Adapter `WebcamSource` có logic reconnect (3 failures → reconnect). Tại sao logic này đặt ở **adapter**, không ở **use case**?

4. Bạn được giao "thêm adapter `RTSPSource` cho RTSP camera". Plan các step (3-5 step). Test bằng cách nào không cần camera RTSP thật?

5. Trong contract test, tại sao `pytest.fixture(params=[lambda: ...])` thay vì `params=[FakeFrameSource()]`?

<details>
<summary>Đáp án</summary>

1. **Lý do 1**: `Optional[Frame]` — `None` nghĩa gì? Caller phải đoán. ReadResult có 6 status explicit, mỗi status có action khác nhau. **Lý do 2**: error handling. `Optional` không carry exception/retry hint. ReadResult có `error` field + `retry_after_ms`.

2. ```python
   if source.is_finite:
       # Batch mode: EOF = done
       while True:
           r = source.read()
           if r.status == ReadStatus.EOF:
               break
           if r.status == ReadStatus.FRAME:
               process(r.data)
   else:
       # Stream mode: EOF không bình thường, có thể là bug
       while not should_stop:
           r = source.read()
           if r.status == ReadStatus.EOF:
               logger.error("Stream returned EOF — unexpected")
               break
           if r.status == ReadStatus.RECONNECTING:
               time.sleep(r.retry_after_ms / 1000)
               continue
           ...
   ```

3. **Reasoning**: 
   - Reconnect là **detail của webcam adapter** — file source không reconnect (file ends = EOF, không bug).
   - Use case không nên biết "webcam có thể disconnect, file thì không". Use case chỉ biết status enum.
   - Khác adapter có khác strategy reconnect (RTSP có exponential backoff, webcam có fixed 500ms). Logic theo adapter.
   - **Hexagonal principle**: I/O concern ở adapter, business concern ở use case. Reconnect = I/O concern.

4. **Plan**:
   1. Tạo `vision_demo/adapters/rtsp_source.py`. Implement `IFrameSource` dùng `cv2.VideoCapture("rtsp://...")`.
   2. Logic timeout — RTSP đôi khi block lâu, dùng `cv2.CAP_PROP_OPEN_TIMEOUT_MSEC` set 5s.
   3. Logic reconnect tương tự `WebcamSource` — 3 failures → reconnect.
   4. **Test không cần camera thật**: 
      - Setup MediaMTX (open-source RTSP server) trên localhost serving 1 video file.
      - Test runs against `rtsp://localhost:8554/stream`.
      - Hoặc đơn giản hơn: skip integration test, chỉ test contract bằng mock.
   5. Add vào composition root: `--source rtsp --url ...`.
   
   Quan trọng: cùng `IFrameSource` contract. Use case không sửa.

5. **Lý do dùng lambda (factory)**:
   - `params=[FakeFrameSource()]` — instantiate **1 lần**, share giữa các test → state pollute.
   - `params=[lambda: FakeFrameSource()]` — instantiate **mỗi test** → isolated.
   - Test #1 đọc 5 frame, test #2 đọc tiếp 5 nữa thay vì từ đầu = bug nguy hiểm.
   - Test isolation là vital.

</details>

---

## Trade-offs

### "Quá nhiều layer cho 1 task đơn giản?"

Bạn vừa viết **~300 dòng code** cho task "đọc frame từ source". Có thể chỉ cần `cap = cv2.VideoCapture(...)`.

**Khi nào KHÔNG cần đến mức này**:
- Script 1 file, throw-away.
- 1 source duy nhất, không bao giờ đổi.

**Khi nào CẦN**:
- 2+ source type (file, webcam, RTSP, fake).
- Test mà không cần infrastructure.
- Đội có 2+ dev, cần ranh giới rõ.

→ Vision Platform có 5+ source type tiềm năng (RTSP, file, webcam, HTTP upload, WebRTC). **Đáng đầu tư**.

### "Performance overhead của Protocol?"

Python `Protocol` (typing) là **structural typing** — không runtime check. Cost = 0 lúc runtime. Chỉ là hint cho mypy/IDE.

→ Không có overhead. Yên tâm.

### "Adapter có nên kế thừa từ Protocol?"

```python
# Cách 1: structural — không kế thừa
class FakeFrameSource:   # không base
    def setup(self): ...

# Cách 2: explicit
class FakeFrameSource(IFrameSource):
    def setup(self): ...
```

**Trade-off**:
- **Cách 1**: ngắn hơn, structural typing "duck-typing strict". Mypy check đủ. **Khuyến nghị**.
- **Cách 2**: explicit, dễ đọc với người Java/C# background. Có cost nhỏ về MRO. Pythonic ít hơn.

Vision Platform dùng cách 1 (Protocol structural).

---

## Pitfalls

### Pitfall 1: Adapter có business logic

```python
# Sai
class VideoFileSource:
    def read(self) -> ReadResult:
        ret, frame = self._cap.read()
        if frame is not None:
            # ← business logic LEAK vào adapter
            if frame.mean() < 30:
                return ReadResult(status=ReadStatus.DROPPED)
        return ReadResult(status=ReadStatus.FRAME, data=frame)
```

→ "Filter frame tối" là **business logic**, không phải I/O. Đặt ở **stage** (preprocessing), không phải adapter.

**Đúng**:
```python
# adapter chỉ I/O
class VideoFileSource:
    def read(self) -> ReadResult:
        ret, frame = self._cap.read()
        return ReadResult(status=ReadStatus.FRAME, data=frame)


# stage business logic
class FilterDarkFrameStage:
    def process(self, frame):
        if frame.mean() < 30:
            raise SkipFrameSignal("too_dark")
        return frame
```

### Pitfall 2: Use case import adapter

```python
# Sai
from vision_demo.adapters.video_file_source import VideoFileSource   # ← LEAK

class ProcessFrameUseCase:
    def __init__(self):
        self._source = VideoFileSource("...")   # tự tạo
```

→ Use case khoá vào VideoFileSource. Test phải có file thật.

**Đúng**: nhận `IFrameSource` từ ngoài (DI). Composition root quyết định adapter cụ thể.

### Pitfall 3: Adapter gọi adapter khác trực tiếp

```python
# Sai
class VideoFileSource:
    def setup(self):
        ...
        # Adapter này gửi event log:
        from vision_demo.adapters.kafka_sink import KafkaSink
        sink = KafkaSink(...)   # ← adapter A khoá adapter B
        sink.emit({"event": "video_opened"})
```

→ 2 adapter coupling. Đổi 1 = đổi cả 2.

**Đúng**: adapter chỉ implement port của mình. Composition root wire chéo. Hoặc dùng **decorator** chính thức:

```python
class LoggingFrameSourceDecorator:
    def __init__(self, inner: IFrameSource, sink: IEventSink):
        self._inner = inner; self._sink = sink
    
    def setup(self):
        self._inner.setup()
        self._sink.emit({"event": "source_opened", "id": self._inner.source_id})
```

### Pitfall 4: Kit too generic

```python
# Sai
class IFrameSource(Protocol):
    def get(self, key: str) -> Any: ...
```

→ Port quá generic, không **dạy** caller cách dùng. Test không có shape. Không type-safe.

**Đúng**: port có method **theo business operation**. `read(timeout_ms)`, `is_finite`, `source_id` — semantic rõ.

---

## Liên kết

- File 03 (`03-bulkhead-pattern.md`) — sao mỗi camera 1 process.
- Production: `Vision_platform_architecture_design/03-data-contracts/02-idatasource-t-readresult.md` — port `IDataSource[T]` với generic, support cả frame và audio packet.
- Module 03 step 03 — sẽ dùng `IFrameSource` này, build thêm vào `vision_demo`.

---

## Tóm tắt 1 câu

> **1 port + N adapter + 1 contract test suite + use case không biết adapter cụ thể = pattern chuẩn. Composition root là chỗ duy nhất biết cụ thể adapter. Test logic không cần infrastructure.**

➡️ Tiếp theo: [`03-bulkhead-pattern.md`](03-bulkhead-pattern.md)
