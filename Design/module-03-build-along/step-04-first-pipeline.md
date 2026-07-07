# Step 04 — Pipeline: StageContract + BaseStage + SyncLinearExecutor + 2 stage + composition root

## Mục tiêu (2.5h)

Bạn sẽ build mảnh ghép cuối của vision_demo MVP:

1. `kernel/stage_contract.py` — StageResult, StageStatus, IStage protocol, SkipFrameSignal.
2. `runtime/base_stage.py` — BaseStage scaffold.
3. `runtime/sync_linear_executor.py` — Linear pipeline runner.
4. `runtime/stages/brightness_stage.py` — Stage tính brightness.
5. `runtime/stages/dark_filter_stage.py` — Stage filter frame tối.
6. `profiles/demo_pipeline.py` — **Composition root** wire toàn pipeline.

Cuối step: **chạy được** end-to-end pipeline, **13 tests pass** (12 + 1 E-14 context-manager), demo CLI tool work.

---

## Recap kiến trúc

```
[FrameSource] → [BrightnessStage] → [DarkFilterStage] → output
   (adapter)      (stage)              (stage)
       │             │                    │
       │             v                    v
       └→ MediaPacket → MediaPacket(brightness) → MediaPacket OR None
                              ↑                         ↑
                            CoW                       SKIP if dark
```

---

## Phần 1 — StageContract (30 phút)

Tạo `src/vision_demo/kernel/stage_contract.py`:

```python
"""StageResult + StageStatus + base stage contract."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol
from vision_demo.kernel.media_packet import MediaPacket


class StageStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StageResult:
    """Outcome of stage processing 1 packet."""
    status: StageStatus
    packet: Optional[MediaPacket] = None
    skip_reason: Optional[str] = None
    error_type: Optional[str] = None        # type name only — no Exception ref
    error_message: Optional[str] = None     # str(exc) — no traceback ref
    stage: str = ""
    
    @classmethod
    def success(cls, packet: MediaPacket, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SUCCESS, packet=packet, stage=stage)
    
    @classmethod
    def skipped(cls, reason: str, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SKIPPED, skip_reason=reason, stage=stage)
    
    @classmethod
    def error(cls, error: Exception, stage: str = "") -> "StageResult":
        """Build ERROR result without retaining exception reference (no traceback frames)."""
        return cls(
            status=StageStatus.ERROR,
            error_type=type(error).__qualname__,
            error_message=str(error),
            stage=stage,
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome của TOÀN BỘ pipeline cho 1 packet (executor trả về cái này).

    Khác `StageResult` (kết quả 1 stage), `ExecutionResult` tổng hợp kết quả
    chạy hết chuỗi stage. Giữ ĐẦY ĐỦ trạng thái — KHÔNG bóp về `Optional`:
        - status PROCESSED  → packet chạy hết chuỗi, `packet` là kết quả cuối.
        - status SKIPPED    → 1 stage skip (filter chặn), `failed_stage` =
                              stage skip, `reason` = lý do.
        - status ERROR      → 1 stage lỗi, `failed_stage` + error_type/message.
        - status CANCELLED  → pipeline bị huỷ giữa chừng.

    Vì sao cần result-object thay vì `Optional[MediaPacket]`?
        `None` không phân biệt được "filter cố ý bỏ frame" (bình thường) với
        "stage lỗi" (cần đếm vào error metric / alert). Demo cũ count mọi
        `None` thành skipped → ERROR bị giấu thành skip. Result-object giữ
        status rõ ràng để caller route đúng (metric, log, alert).
    """

    status: StageStatus
    packet: Optional[MediaPacket] = None    # set khi PROCESSED
    failed_stage: str = ""                  # stage gây skip/error/cancel
    reason: Optional[str] = None            # skip_reason khi SKIPPED
    error_type: Optional[str] = None        # khi ERROR (string-only)
    error_message: Optional[str] = None     # khi ERROR (string-only)

    @property
    def is_processed(self) -> bool:
        return self.status == StageStatus.SUCCESS

    @classmethod
    def processed(cls, packet: MediaPacket) -> "ExecutionResult":
        return cls(status=StageStatus.SUCCESS, packet=packet)

    @classmethod
    def from_stage_result(cls, result: "StageResult") -> "ExecutionResult":
        """Map kết quả non-SUCCESS của 1 stage thành ExecutionResult của pipeline."""
        return cls(
            status=result.status,
            failed_stage=result.stage,
            reason=result.skip_reason,
            error_type=result.error_type,
            error_message=result.error_message,
        )


class SkipFrameSignal(Exception):
    """Stage raises this to skip frame intentionally (motion gate, ROI filter)."""
    pass


class IStage(Protocol):
    """Sync stage. Process 1 packet → 1 packet (or skip/error)."""
    @property
    def name(self) -> str: ...
    
    def process(self, packet: MediaPacket) -> StageResult: ...
    
    def setup(self) -> None: ...
    
    def teardown(self) -> None: ...
```

**Decisions cực quan trọng**:

### Decision 1: NO `error: Exception` field

Đây là **R5-CRITICAL-02 fix** trực tiếp. Khác với production `StageResult` (có cả `error` cho fatal path), đây simplified:

- **Production**: `error: Optional[Exception]` chỉ khi `fatal=True`. Cần raise lại.
- **vision_demo**: KHÔNG có `error` field. Chỉ string snapshot.

**Lý do**: simpler. vision_demo demo pattern, không cần fatal raise. Pattern truth giữ nguyên.

**Impact**: stage không thể "throw fatal" lên executor. Mọi error trong vision_demo đều **non-fatal** — executor return None. Đủ cho học.

### Decision 2: `SkipFrameSignal` là Exception

Stage muốn skip frame:
```python
def _do_process(self, packet):
    if too_dark(packet):
        raise SkipFrameSignal("too_dark")
    return process(packet)
```

→ BaseStage catch `SkipFrameSignal` → trả `StageResult.skipped(...)`.

**Tại sao không return statement?** Vì stage có thể raise bất cứ chỗ nào (deep call stack). Try/raise idiom trong Python là natural.

### Decision 3: Factory methods (`success`, `skipped`, `error`)

Boilerplate giảm:
```python
# Verbose
return StageResult(status=StageStatus.SUCCESS, packet=p, stage="x")

# Concise
return StageResult.success(p, stage="x")
```

---

## Phần 2 — BaseStage scaffold (15 phút)

Tạo `src/vision_demo/runtime/base_stage.py`:

```python
"""BaseStage - common scaffolding cho stage implementation."""
from abc import ABC, abstractmethod
from vision_demo.kernel.media_packet import MediaPacket
from vision_demo.kernel.stage_contract import (
    StageResult, SkipFrameSignal,
)


class BaseStage(ABC):
    """Scaffold: tự handle SkipFrameSignal + Exception thành StageResult."""
    
    def __init__(self, name: str):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    def setup(self) -> None: ...
    
    def teardown(self) -> None: ...
    
    def process(self, packet: MediaPacket) -> StageResult:
        try:
            result_packet = self._do_process(packet)
            return StageResult.success(result_packet, stage=self._name)
        except SkipFrameSignal as e:
            return StageResult.skipped(reason=str(e), stage=self._name)
        except Exception as e:
            return StageResult.error(error=e, stage=self._name)
    
    @abstractmethod
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        """Subclass implement. Return new MediaPacket (CoW). Raise to skip/error."""
        ...
```

**Decisions**:

- **Template Method pattern**: `process()` (concrete) handles flow + error catching. `_do_process()` (abstract) là điểm subclass implement logic.
- **Subclass chỉ cần implement `_do_process`**: viết business logic, không lo error handling boilerplate. DRY.
- **`setup`/`teardown` default no-op**: subclass override nếu cần (e.g. load model).
- **`Exception` catch broad**: any error → ERROR result. Không re-raise. Đây là demo style. Production phân biệt fatal vs non-fatal.

---

## Phần 3 — SyncLinearExecutor (15 phút)

Tạo `src/vision_demo/runtime/sync_linear_executor.py`:

```python
"""SyncLinearExecutor - linear pipeline runner."""
from vision_demo.kernel.media_packet import MediaPacket
from vision_demo.kernel.stage_contract import (
    IStage, StageStatus, ExecutionResult,
)


class SyncLinearExecutor:
    """Run packet through stages linearly. Stop on first non-SUCCESS."""
    
    def __init__(self, stages: list[IStage]):
        self._stages = list(stages)
    
    def setup_all(self) -> None:
        for s in self._stages:
            s.setup()
    
    def teardown_all(self) -> None:
        for s in reversed(self._stages):
            try:
                s.teardown()
            except Exception:
                pass
    
    # Context manager (ERRATA E-14): `with SyncLinearExecutor([...]) as ex:` tự setup_all lúc
    # vào + teardown_all lúc ra (kể cả khi thân with raise) → an toàn hơn quên try/finally.
    def __enter__(self) -> "SyncLinearExecutor":
        self.setup_all()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown_all()
        return False  # KHÔNG nuốt exception của thân `with`
    
    def execute(self, packet: MediaPacket) -> ExecutionResult:
        """Drive packet qua chuỗi stage.

        Trả `ExecutionResult` giữ đầy đủ trạng thái:
            - PROCESSED: chạy hết chuỗi, `.packet` là kết quả cuối.
            - SKIPPED/ERROR/CANCELLED: dừng tại stage đầu tiên non-SUCCESS,
              `.failed_stage` + lý do/error được giữ lại để caller route đúng.
        """
        current = packet
        for stage in self._stages:
            result = stage.process(current)
            if result.status == StageStatus.SUCCESS:
                current = result.packet
            else:
                # Giữ NGUYÊN status (skip vs error vs cancel) — không bóp về None.
                return ExecutionResult.from_stage_result(result)
        return ExecutionResult.processed(current)
```

**Decisions**:

- **`stages: list[IStage]`**: structural typing. Bất cứ class implement IStage protocol đều OK.
- **`teardown` reversed order**: LIFO (Last In First Out) — giống cleanup stack. Setup A, B, C → teardown C, B, A.
- **`teardown` swallow exception**: shutdown phải robust. 1 stage cleanup fail không nên block các stage khác.
- **`execute` trả `ExecutionResult`**: PROCESSED → `.packet`. SKIPPED/ERROR/CANCELLED → giữ nguyên status + `failed_stage` + lý do. Caller phân biệt được "filter cố ý bỏ" (skip — bình thường) vs "stage lỗi" (error — cần alert), không bị gộp nhập nhằng như `None`.

### Tại sao "Linear" trong tên?

vs DAG (Directed Acyclic Graph):
- Linear: A → B → C → ...
- DAG: A → B, A → C, B+C → D

Linear cover **>90% pipeline thực tế**. DAG chỉ cần khi có concrete branch (e.g. visualization parallel với detection). vision_demo focus linear vì simpler. Vision Platform có `BranchedExecutor` cho DAG.

---

## Phần 4 — Stages (30 phút)

### BrightnessStage

Tạo `src/vision_demo/runtime/stages/brightness_stage.py`:

```python
"""BrightnessStage: tính brightness trung bình, ghi vào artifact."""
import numpy as np
from vision_demo.kernel.media_packet import MediaPacket
from vision_demo.runtime.base_stage import BaseStage


class BrightnessStage(BaseStage):
    """Tính frame.mean() → packet.artifacts['brightness']."""
    
    def __init__(self):
        super().__init__("brightness")
    
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        frame = packet.media_ref.array
        brightness = float(frame.mean())
        return packet.with_artifact("brightness", brightness)
```

**Decisions**:

- **`with_artifact()` CoW**: stage không mutate input. Return NEW packet. Pattern fundamental.
- **`float(frame.mean())`**: numpy scalar → Python float. JSON serializable, không gặp issue downstream.

### DarkFilterStage

Tạo `src/vision_demo/runtime/stages/dark_filter_stage.py`:

```python
"""DarkFilterStage: skip frame nếu brightness < threshold."""
from vision_demo.kernel.media_packet import MediaPacket
from vision_demo.kernel.stage_contract import SkipFrameSignal
from vision_demo.runtime.base_stage import BaseStage


class DarkFilterStage(BaseStage):
    """Skip frame nếu artifact 'brightness' < threshold.
    
    Yêu cầu: BrightnessStage phải chạy TRƯỚC stage này.
    """
    
    def __init__(self, threshold: float):
        super().__init__("dark_filter")
        self._threshold = threshold
    
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        brightness = packet.artifacts.get("brightness")
        if brightness is None:
            raise ValueError(
                "DarkFilterStage requires 'brightness' artifact. "
                "Did you forget to add BrightnessStage before this?"
            )
        if brightness < self._threshold:
            raise SkipFrameSignal(f"too_dark (brightness={brightness:.2f})")
        return packet
```

**Decisions**:

- **Stage dependency explicit**: docstring nói "BrightnessStage phải chạy trước". Stage check artifact tồn tại → raise clear error nếu thiếu. **Fail-fast với hint**.
- **`raise SkipFrameSignal`** thay vì `return special_value`: idiom Python, BaseStage catch.
- **Return packet unchanged** khi pass: stage này chỉ filter, không thêm artifact.

### Stage chain pattern

```
packet (no artifact)
    → BrightnessStage._do_process()
    → packet.with_artifact("brightness", 50.0)   # CoW
    → DarkFilterStage._do_process()
    → packet (unchanged) — vì brightness >= threshold
    → OR raise SkipFrameSignal — vì < threshold
```

→ Chain CoW. Mỗi stage **không** mutate input. Original packet vẫn còn.

---

## Phần 5 — Composition root: demo_pipeline (30 phút)

Tạo `src/vision_demo/profiles/demo_pipeline.py`:

```python
"""Composition root: profile demo cho Step 04.

Wire: source → BrightnessStage → DarkFilterStage → print event.
Single process, sync executor.
"""
from __future__ import annotations
import argparse
import sys
import time

from vision_demo.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_demo.kernel.read_result import ReadStatus
from vision_demo.kernel.stage_contract import StageStatus
from vision_demo.runtime.sync_linear_executor import SyncLinearExecutor
from vision_demo.runtime.stages.brightness_stage import BrightnessStage
from vision_demo.runtime.stages.dark_filter_stage import DarkFilterStage


def main() -> int:
    parser = argparse.ArgumentParser(prog="vision_demo.profiles.demo_pipeline")
    parser.add_argument(
        "--source", choices=["fake", "noise"], default="fake",
    )
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--threshold", type=float, default=50.0,
                        help="Brightness threshold for DarkFilterStage")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args()
    
    # ===== Composition root: chỗ DUY NHẤT chọn cụ thể adapter. =====
    if args.source == "fake":
        from vision_demo.adapters.fake_frame_source import FakeFrameSource
        source = FakeFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    elif args.source == "noise":
        from vision_demo.adapters.noise_frame_source import NoiseFrameSource
        source = NoiseFrameSource(
            width=args.width, height=args.height, max_frames=args.frames,
        )
    else:
        parser.error(f"Unknown source: {args.source}")
    
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=args.threshold),
    ])
    
    # ===== Run loop =====
    source.setup()
    executor.setup_all()
    
    seq = 0
    n_processed = 0
    n_skipped = 0
    n_stage_error = 0
    n_cancelled = 0
    n_eof = 0
    n_error = 0
    
    try:
        while True:
            r = source.read()
            
            if r.status == ReadStatus.EOF:
                n_eof += 1
                break
            
            if r.status == ReadStatus.ERROR:
                n_error += 1
                print(f"[seq={seq}] source ERROR: {r.error}", file=sys.stderr)
                continue
            
            if not r.has_data:
                # TIMEOUT / DROPPED / RECONNECTING — skip frame.
                continue
            
            packet = MediaPacket(
                packet_id=f"pkt_{seq}",
                source_id=source.source_id,
                media_ref=InMemoryArrayRef.from_copy(r.data),
                capture_time_ns=time.monotonic_ns(),
            )
            seq += 1
            
            result = executor.execute(packet)
            
            if result.status == StageStatus.SUCCESS:
                n_processed += 1
                final = result.packet
                print(
                    f"[seq={seq:03d}] brightness={final.artifacts['brightness']:.2f} "
                    f"shape={final.media_ref.array.shape}"
                )
            elif result.status == StageStatus.SKIPPED:
                # Filter cố ý bỏ frame — bình thường, KHÔNG phải lỗi.
                n_skipped += 1
            elif result.status == StageStatus.ERROR:
                # Stage lỗi — đếm RIÊNG, log rõ stage + lý do (không giấu thành skip).
                n_stage_error += 1
                print(
                    f"[seq={seq:03d}] stage ERROR in '{result.failed_stage}': "
                    f"{result.error_type}: {result.error_message}",
                    file=sys.stderr,
                )
            else:  # CANCELLED
                n_cancelled += 1
    finally:
        executor.teardown_all()
        source.teardown()
    
    # ===== Summary =====
    print("\n=== Demo summary ===", file=sys.stderr)
    print(f"  Processed: {n_processed}", file=sys.stderr)
    print(f"  Skipped (filter):  {n_skipped}", file=sys.stderr)
    print(f"  Stage errors: {n_stage_error}", file=sys.stderr)
    print(f"  Cancelled: {n_cancelled}", file=sys.stderr)
    print(f"  EOF: {n_eof}", file=sys.stderr)
    print(f"  Source errors: {n_error}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Decisions cực quan trọng**:

### Decision 1: `if args.source == "fake": from ... import ...`

**Lazy import**. Lý do:
- `cv2`/`opencv-python` là optional dep. User chỉ cài nếu chạy `--source webcam` (sau này).
- Lazy import → skip cv2 import khi `--source fake`. Test dev không cần cv2.
- Eager import top-level → fail nếu cv2 chưa cài.

### Decision 2: `InMemoryArrayRef.from_copy(r.data)`

**Defensive copy**. Lý do:
- Source adapter có thể reuse internal buffer (FFmpeg, cv2). `r.data` có thể bị overwrite ở read tiếp theo.
- `from_copy` snapshot frame → safe pass downstream.

Cost: ~6MB copy (1080p frame). Acceptable. Vision Platform real có **SHM zero-copy** (Step 05).

### Decision 3: `try/finally` cho cleanup

Pipeline có thể raise giữa loop (Ctrl+C, error). `finally` ensures `teardown_all()` + `source.teardown()` chạy → resources cleanup.

### Decision 4: Counter + summary in stderr

`stdout` cho **data output** (frame info). `stderr` cho **diagnostic** (summary, error). Convention Unix — pipe-friendly:
```bash
python -m vision_demo.profiles.demo_pipeline --source noise > frames.txt 2> log.txt
```
Frames vào `frames.txt`, summary vào `log.txt`.

### Decision 5: Match-case không dùng

`match r.status:` Python 3.10+ syntax. Đáng dùng nhưng simpler with `if/elif` cho beginner. Tùy bạn refactor sau.

---

## Phần 6 — Tests (30 phút)

Tạo `tests/test_step_04_pipeline.py`:

```python
"""Step 04: stage + executor."""
import numpy as np
import pytest
from vision_demo.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_demo.kernel.stage_contract import (
    StageStatus, StageResult, SkipFrameSignal, ExecutionResult,
)
from vision_demo.runtime.base_stage import BaseStage
from vision_demo.runtime.sync_linear_executor import SyncLinearExecutor
from vision_demo.runtime.stages.brightness_stage import BrightnessStage
from vision_demo.runtime.stages.dark_filter_stage import DarkFilterStage


def _make_packet(value: int = 0) -> MediaPacket:
    """Frame uniform với value."""
    arr = np.full((50, 50, 3), fill_value=value, dtype=np.uint8)
    return MediaPacket(
        packet_id=f"p_{value}",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=0,
    )


# ============ Stage individual ============

def test_brightness_stage_computes_mean():
    stage = BrightnessStage()
    packet = _make_packet(value=100)
    
    result = stage.process(packet)
    
    assert result.status == StageStatus.SUCCESS
    assert result.packet.artifacts["brightness"] == pytest.approx(100.0)


def test_brightness_stage_does_not_mutate_input():
    """CoW invariant — input packet unchanged."""
    stage = BrightnessStage()
    packet = _make_packet(value=50)
    
    result = stage.process(packet)
    
    assert "brightness" not in packet.artifacts        # input unchanged
    assert "brightness" in result.packet.artifacts


def test_dark_filter_skips_below_threshold():
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=10).with_artifact("brightness", 10.0)
    
    result = stage.process(packet)
    
    assert result.status == StageStatus.SKIPPED
    assert "too_dark" in result.skip_reason


def test_dark_filter_passes_above_threshold():
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=200).with_artifact("brightness", 200.0)
    
    result = stage.process(packet)
    
    assert result.status == StageStatus.SUCCESS


def test_dark_filter_errors_without_brightness():
    """Stage explicitly errors instead of silently passing."""
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=200)  # no brightness artifact
    
    result = stage.process(packet)
    
    assert result.status == StageStatus.ERROR
    assert "brightness" in result.error_message.lower()
    assert isinstance(result.error_message, str)


def test_stage_error_does_not_retain_exception_object():
    """R5-CRITICAL-02: StageResult must NOT retain live Exception
    (which would retain traceback → frame locals → packet → ndarray).
    
    Design choice: StageResult stores only string snapshot — error_type
    and error_message — never the Exception object itself.
    """
    from dataclasses import fields
    
    stage = DarkFilterStage(threshold=50.0)
    packet = _make_packet(value=100)  # missing brightness artifact
    
    result = stage.process(packet)
    
    # Verify: only string fields, no Exception field.
    assert isinstance(result.error_type, str)
    assert isinstance(result.error_message, str)
    
    # Critical check: NO field of type Exception in dataclass.
    field_names = {f.name for f in fields(StageResult)}
    assert "error" not in field_names, (
        "StageResult must NOT have a dataclass field `error` holding Exception."
    )


# ============ Executor ============

def test_executor_runs_stages_in_order():
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    executor.setup_all()
    
    packet = _make_packet(value=200)
    result = executor.execute(packet)
    
    assert result.status == StageStatus.SUCCESS
    assert result.is_processed
    assert result.packet.artifacts["brightness"] == pytest.approx(200.0)
    
    executor.teardown_all()


def test_executor_stops_on_skip():
    executor = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    executor.setup_all()
    
    packet = _make_packet(value=10)  # too dark
    result = executor.execute(packet)
    
    # Filter chặn → SKIPPED (KHÔNG phải None mơ hồ), giữ stage + lý do.
    assert result.status == StageStatus.SKIPPED
    assert result.packet is None
    assert result.failed_stage == "dark_filter"
    assert "too_dark" in (result.reason or "")
    
    executor.teardown_all()


def test_executor_stops_on_error():
    executor = SyncLinearExecutor([
        DarkFilterStage(threshold=50.0),  # missing brightness → ERROR
    ])
    executor.setup_all()
    
    packet = _make_packet(value=100)
    result = executor.execute(packet)
    
    # ERROR phải PHÂN BIỆT được với SKIPPED — không gộp thành None.
    assert result.status == StageStatus.ERROR
    assert result.packet is None
    assert result.failed_stage == "dark_filter"
    assert isinstance(result.error_message, str)
    assert "brightness" in result.error_message.lower()
    
    executor.teardown_all()


def test_executor_skip_and_error_are_distinguishable():
    """Invariant chính của ExecutionResult: skip ≠ error (demo cũ gộp cả 2 thành None)."""
    # Skip: brightness có, nhưng dưới ngưỡng.
    skip_exec = SyncLinearExecutor([
        BrightnessStage(),
        DarkFilterStage(threshold=50.0),
    ])
    skip_exec.setup_all()
    skip_result = skip_exec.execute(_make_packet(value=10))
    skip_exec.teardown_all()

    # Error: thiếu brightness artifact (không có BrightnessStage trước).
    err_exec = SyncLinearExecutor([DarkFilterStage(threshold=50.0)])
    err_exec.setup_all()
    err_result = err_exec.execute(_make_packet(value=100))
    err_exec.teardown_all()

    assert skip_result.status == StageStatus.SKIPPED
    assert err_result.status == StageStatus.ERROR
    assert skip_result.status != err_result.status   # phân biệt được


def test_executor_idempotent_setup():
    executor = SyncLinearExecutor([BrightnessStage()])
    executor.setup_all()
    executor.setup_all()  # 2nd call must not crash
    executor.teardown_all()
    executor.teardown_all()


def test_custom_stage_via_subclass():
    """Subclass BaseStage works for custom logic."""
    class CountStage(BaseStage):
        def __init__(self):
            super().__init__("count")
            self.count = 0
        
        def _do_process(self, packet):
            self.count += 1
            return packet.with_artifact("count", self.count)
    
    s = CountStage()
    p = _make_packet()
    
    r1 = s.process(p)
    r2 = s.process(p)
    
    assert r1.packet.artifacts["count"] == 1
    assert r2.packet.artifacts["count"] == 2
    assert "count" not in p.artifacts  # original unchanged


def test_executor_context_manager_setup_teardown():
    """ERRATA E-14 (Risk 4): `with` tự setup_all lúc vào + teardown_all lúc ra (kể cả khi raise)."""
    calls = []

    class TrackStage(BaseStage):
        def __init__(self):
            super().__init__("track")
        def setup(self):
            calls.append("setup")
        def teardown(self):
            calls.append("teardown")
        def _do_process(self, packet):
            return packet

    with SyncLinearExecutor([TrackStage()]) as ex:
        assert calls == ["setup"]
        ex.execute(_make_packet(0))
    assert calls == ["setup", "teardown"]

    calls.clear()
    with pytest.raises(RuntimeError):
        with SyncLinearExecutor([TrackStage()]):
            raise RuntimeError("boom")
    assert calls == ["setup", "teardown"]   # teardown vẫn chạy khi thân with raise
```

**Run all**:
```bash
pytest
```

Expected (baseline giáo trình): **61 passed, 1 skipped** (2 smoke + 16 step-02 + 30 step-03 + 13 step-04).
*Trong repo `vision-platform` của ta:* **64 passed, 1 skipped** (2 smoke + 19 step-02 + 31 step-03 + 13 step-04 —
cộng test E-11/E-12/E-13/E-14). Luôn đọc số THẬT khi chạy (E-4).

---

## Phần 7 — End-to-end demo (15 phút)

Run demo:

```bash
# Noise source, 5 frames, threshold 100 (random ≈ 127, all pass)
python -m vision_demo.profiles.demo_pipeline --source noise --frames 5 --threshold 100.0
```

Expected:
```
[seq=001] brightness=127.33 shape=(240, 320, 3)
[seq=002] brightness=127.47 shape=(240, 320, 3)
[seq=003] brightness=127.68 shape=(240, 320, 3)
[seq=004] brightness=127.44 shape=(240, 320, 3)
[seq=005] brightness=127.80 shape=(240, 320, 3)

=== Demo summary ===
  Processed: 5
  Skipped (filter):  0
  Stage errors: 0
  Cancelled: 0
  EOF: 1
  Source errors: 0
```

Try fake source với high threshold:
```bash
# Fake source generates frame N with brightness N (0,1,2,3,4) — all < 100 → all skipped
python -m vision_demo.profiles.demo_pipeline --source fake --frames 5 --threshold 100.0
```

Expected:
```
=== Demo summary ===
  Processed: 0
  Skipped (filter):  5
  Stage errors: 0
  Cancelled: 0
  EOF: 1
  Source errors: 0
```

→ **End-to-end pipeline working**.

---

## Self-check

1. **Template Method pattern** trong `BaseStage` — tại sao `process()` concrete và `_do_process()` abstract? Lợi ích?

2. **`SkipFrameSignal` là Exception** — sao không return special enum value như `SkipResult`?

3. **Composition root** trong `demo_pipeline.py` — list 3 dòng code DUY NHẤT biết về adapter cụ thể.

4. **CoW invariant**: nếu `BrightnessStage._do_process()` mutate `packet.artifacts` thay vì `with_artifact()`, test nào fail?

5. **Lazy import** — pros/cons? Khi nào KHÔNG dùng?

<details>
<summary>Đáp án</summary>

1. **Template Method**:
   - **`process()` concrete**: handle error catching boilerplate (try/except SkipFrameSignal, except Exception). Mọi stage cần.
   - **`_do_process()` abstract**: business logic riêng từng stage.
   - **Lợi ích**: DRY (subclass không lặp try/except). Consistent error handling. Nếu sửa error handling logic → 1 chỗ.

2. **`SkipFrameSignal` Exception** vs return value:
   - Stage có thể skip ở **deep call stack** (function A → B → C, C decide skip).
   - Return value bắt buộc unwind từng layer → boilerplate `if ... return SKIP`.
   - Exception unwind tự động.
   - Python idiom — exception cho control flow. **Performance OK** vì rare path.

3. **3 dòng**:
   - `from vision_demo.adapters.fake_frame_source import FakeFrameSource` (lazy import).
   - `from vision_demo.adapters.noise_frame_source import NoiseFrameSource` (lazy import).
   - `source = FakeFrameSource(...)` / `source = NoiseFrameSource(...)` (instantiate).
   
   Mọi nơi khác trong codebase: dùng `IFrameSource` protocol type. Không biết cụ thể.

4. **`test_brightness_stage_does_not_mutate_input`** sẽ fail. Test asserts `"brightness" not in packet.artifacts` — nếu mutate, sẽ fail vì input đã có brightness.
   
   Cũng có thể fail ở runtime với `TypeError`: `MappingProxyType` block mutation.

5. **Lazy import**:
   - **Pros**:
     - Module không cần dep tới khi gọi.
     - Startup nhanh.
     - Optional deps: `cv2` chỉ load khi `--source webcam`.
   - **Cons**:
     - Import error xảy ra **muộn** (khi gọi function thay vì khi load module).
     - mypy/IDE khó analyze.
     - Test cần mock từng path lazy.
   - **KHÔNG dùng**:
     - Top-level imports critical (always need).
     - Performance hot path (lazy có overhead lookup mỗi call — but Python caches).
     - Module nhỏ với few deps — không value.

</details>

---

## Liên kết

- **Module 02** files 02, 04, 05 — pattern foundations.
- **Production**: `Vision_platform_architecture_design/04-pipeline-and-concurrency/01-pipeline-engine.md`.

---

## Tóm tắt 1 câu

> **StageResult với error string-only (R5-CRITICAL-02), BaseStage Template Method scaffold, SyncLinearExecutor stops on first non-SUCCESS, composition root lazy-import adapter cụ thể duy nhất 1 chỗ. End-to-end demo chạy được.**

➡️ Tiếp theo: [`step-05-add-shm.md`](step-05-add-shm.md)
