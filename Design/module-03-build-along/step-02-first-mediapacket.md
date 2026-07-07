# Step 02 — Domain BBox + Kernel ReadResult + MediaPacket

## Mục tiêu (2h)

Bạn sẽ build **3 thành phần kiến trúc cốt lõi** đầu tiên:

1. `domain/bbox.py` — Pure value object với coordinate space tag.
2. `kernel/read_result.py` — Generic explicit-status return type.
3. `kernel/media_packet.py` — Immutable DTO với CoW (apply Module 02 file 05).

Cuối step: **19 tests pass** (16 gốc + 3 bổ sung: E-11 pickle/typecheck + E-12 normalized-validate). Mọi file đã verify chạy được.

---

## Recap từ Module 02

Trước khi gõ code, đọc lại:

- **File 02-05** (immutability + CoW): `frozen=True` chỉ shallow. Cần `MappingProxyType` cho dict, `setflags(write=False)` cho ndarray.
- **File 01-03** (dependency direction): Domain pure (no I/O). Kernel có DTO + ports. **Không** import cv2/torch trong 2 layer này.

Nếu bạn quên — quay lại đọc trước.

---

## Phần 1 — Domain: BBox + CoordinateSpace (30 phút)

### Tại sao CoordinateSpace là tag mandatory?

Đây là **bug kinh điển** trong CV pipeline:

```python
# Bug:
def detect(frame_resized):
    return [BBox(10, 20, 100, 50)]   # bbox in resized space

bbox = detect(cv2.resize(frame, (640, 640)))
draw(frame_original, bbox)   # ← lệch! Frame original 1920x1080
```

→ bbox ở **MODEL_INPUT space** (640x640), draw lên frame **ORIGINAL_FRAME space** (1920x1080) → lệch.

→ Type system phải **bắt buộc** tag space, không default.

### Tạo `src/vision_demo/domain/bbox.py`

```python
"""Pure domain value objects. NO I/O imports allowed here."""
from dataclasses import dataclass
from enum import Enum


class CoordinateSpace(Enum):
    """Tag bbox coordinates với space để tránh resize/letterbox bug."""
    ORIGINAL_FRAME = "original"   # tọa độ trên frame raw (pre-resize)
    MODEL_INPUT = "model_input"   # tọa độ trên model input (e.g. 640x640)
    NORMALIZED = "normalized"     # 0.0-1.0 (relative to frame)
    DISPLAY = "display"           # tọa độ trên frame UI hiển thị


@dataclass(frozen=True)
class BBox:
    """Bounding box với coordinate space tag.
    
    BBox(x=10, y=20, w=100, h=50, space=CoordinateSpace.ORIGINAL_FRAME).
    
    `space` là quan trọng — KHÔNG thể compare 2 bbox khác space mà chưa transform.
    """
    x: float
    y: float
    w: float
    h: float
    space: CoordinateSpace
    
    def __post_init__(self):
        if self.w < 0 or self.h < 0:
            raise ValueError(f"width/height must be non-negative, got w={self.w} h={self.h}")
        # NORMALIZED: mọi tọa độ phải trong [0,1] (ERRATA E-12). Bắt lỗi "bbox 100.0
        # trong normalized space" ngay lúc khởi tạo.
        if self.space == CoordinateSpace.NORMALIZED:
            for name, val in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
                if not (0.0 <= val <= 1.0):
                    raise ValueError(f"NORMALIZED bbox cần {name} trong [0,1], got {name}={val}")
    
    @property
    def x2(self) -> float:
        return self.x + self.w
    
    @property
    def y2(self) -> float:
        return self.y + self.h
    
    @property
    def area(self) -> float:
        return self.w * self.h
```

**Decisions giải thích**:

- `Enum` cho space — không str, vì str lỗi chính tả đến runtime mới phát hiện. Enum lỗi compile time.
- `@dataclass(frozen=True)` — mọi field immutable.
- `__post_init__` validate (negative w/h = invalid bbox).
- `space: CoordinateSpace` **KHÔNG default** — buộc caller pass explicit. (Đây là decision chính.)
- Properties `x2`, `y2`, `area` derived — không lưu (CoW friendly, không drift).

### Tại sao **không** dùng tuple `(x, y, w, h)`?

Tuple plain:
```python
bbox = (10, 20, 100, 50)
```

Không tag space. Không validate. Không method. **Hoàn toàn dữ liệu raw.**

→ Trong domain, dùng dataclass + tag = **type-safe**.

---

## Phần 2 — Kernel: ReadResult (30 phút)

### Recap từ Module 02 file 02

`Optional[Frame]` — None nghĩa gì? EOF? Timeout? Error? **Caller phải đoán**.

→ ReadResult với 6 status explicit. Caller bắt buộc handle.

### Tạo `src/vision_demo/kernel/read_result.py`

```python
"""ReadResult — explicit-status return từ IDataSource.read()."""
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Optional, TypeVar


class ReadStatus(Enum):
    FRAME = "frame"
    EOF = "eof"
    TIMEOUT = "timeout"
    RECONNECTING = "reconnecting"
    DROPPED = "dropped"
    ERROR = "error"


T = TypeVar("T")


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """Explicit status. Caller MUST handle each status."""
    status: ReadStatus
    data: Optional[T] = None
    error: Optional[Exception] = None
    retry_after_ms: Optional[int] = None
    
    @property
    def has_data(self) -> bool:
        return self.status == ReadStatus.FRAME and self.data is not None
```

**Decisions giải thích**:

- **Generic `Generic[T]`** — `ReadResult[np.ndarray]` cho frame, `ReadResult[bytes]` cho audio packet... Reuse cùng class.
- **`error: Optional[Exception]`** — ReadResult vẫn keep Exception ref. Khác `StageResult` (R5-CRITICAL-02) vì:
  - ReadResult life cycle ngắn — không lưu vào DLQ buffer hay error_budget deque.
  - ReadResult được consume ngay sau read.
  - Không có cascading retention chain.
- **`retry_after_ms`** — hint cho RECONNECTING / ERROR transient. Caller có thể sleep.
- **`has_data`** — convenience property cho check hot path.

---

## Phần 3 — Kernel: MediaPacket + InMemoryArrayRef (45 phút)

Đây là **pattern quan trọng nhất** của Module 02 file 05. Đọc lại nếu chưa rõ.

### Tạo `src/vision_demo/kernel/media_packet.py`

```python
"""MediaPacket — immutable frame packet với CoW semantics.

"Immutable" ở đây = container immutable: metadata/artifacts wrap MappingProxyType
(chặn mutate qua packet), media_ref read-only by contract. Lưu ý phần ndarray là
read-only theo convention (xem InMemoryArrayRef), không phải bảo đảm tuyệt đối nếu
còn alias writable.
"""
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping
import numpy as np


@dataclass(frozen=True)
class InMemoryArrayRef:
    """Frame data, read-only BY CONTRACT (không phải immutability tuyệt đối).

    `setflags(write=False)` chặn ghi qua *chính ndarray này*. Nhưng nếu còn
    một alias/base array khác (writable) trỏ vào cùng buffer, dữ liệu vẫn có
    thể bị đổi qua alias đó. Vì vậy đây là **convention "đừng ghi nữa"**, không
    phải bảo đảm tuyệt đối. Hai factory làm rõ ý định của caller:

    - `from_owned_array(arr)`: caller TRAO quyền sở hữu — cam kết không giữ
      alias writable và không mutate `arr` nữa. Zero-copy → nhanh. Dùng trong
      pipeline (sau khi đọc xong, không ai khác giữ `arr`).
    - `from_copy(arr)`: defensive copy — caller được tự do tiếp tục mutate
      `arr`; ref giữ snapshot riêng. An toàn nhất, tốn ~một lần copy.

    Trong giáo trình ưu tiên `from_copy` khi còn nghi ngờ về ownership.
    """
    array: np.ndarray
    
    def __post_init__(self):
        if not isinstance(self.array, np.ndarray):
            raise TypeError(
                f"array phải là numpy.ndarray, nhận {type(self.array).__name__}"
            )
        if self.array.flags.writeable:
            self.array.setflags(write=False)

    def __setstate__(self, state):
        # pickle KHÔNG chạy lại __post_init__, và numpy KHÔNG giữ cờ write=False qua
        # pickle (đã verify thật: numpy 2.4.6 → writeable=True sau round-trip → mảng
        # ghi đè được ở process nhận = vỡ contract read-only). Re-lock tại đây để giữ
        # convention qua ranh giới process/pickle. (ERRATA E-11)
        object.__setattr__(self, "array", state["array"])
        if self.array.flags.writeable:
            self.array.setflags(write=False)
    
    @classmethod
    def from_owned_array(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Nhận quyền sở hữu array (zero-copy). Caller cam kết KHÔNG mutate nữa."""
        return cls(array=array)

    @classmethod
    def from_copy(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Defensive copy — caller can keep mutating original safely."""
        snapshot = np.ascontiguousarray(array.copy())
        return cls(array=snapshot)


@dataclass(frozen=True)
class MediaPacket:
    """Immutable MediaPacket with CoW semantics.
    
    Mutation antipattern (BLOCKED):
        packet.metadata["new"] = "value"   # raises
    
    CoW pattern (CORRECT):
        new_packet = packet.with_metadata("new", "value")
    """
    packet_id: str
    source_id: str
    media_ref: InMemoryArrayRef
    capture_time_ns: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Wrap dict-like fields in MappingProxyType với defensive copy.
        # `object.__setattr__` bypass `frozen=True` block — chỉ dùng trong __post_init__.
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(
                self, "metadata",
                MappingProxyType(dict(self.metadata)),
            )
        if not isinstance(self.artifacts, MappingProxyType):
            object.__setattr__(
                self, "artifacts",
                MappingProxyType(dict(self.artifacts)),
            )
    
    # ---- CoW operations ----
    def with_artifact(self, key: str, value: Any) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts[key] = value
        return replace(self, artifacts=MappingProxyType(new_artifacts))
    
    def with_metadata(self, key: str, value: Any) -> "MediaPacket":
        new_metadata = dict(self.metadata)
        new_metadata[key] = value
        return replace(self, metadata=MappingProxyType(new_metadata))
    
    def without_artifact(self, key: str) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts.pop(key, None)
        return replace(self, artifacts=MappingProxyType(new_artifacts))
```

**Decisions giải thích**:

- **`InMemoryArrayRef` riêng class** thay vì `MediaPacket.frame: np.ndarray` direct: Vision Platform support nhiều **media ref type** (SHM, file, bytes...). `InMemoryArrayRef` là **sum type variant**. Đơn giản hoá ở đây để tập trung pattern.
- **`__post_init__` setflags read-only**: in-place mutate flag. Caller pass array → array trở read-only. **Caller phải hiểu contract** này.
- **`from_owned_array` vs `from_copy`**: hai factory đặt tên rõ ý định. `from_owned_array` (zero-copy, caller trao quyền sở hữu) dùng trong pipeline; `from_copy` (defensive copy, caller giữ quyền mutate) dùng khi còn nghi ngờ ownership. Gọi `InMemoryArrayRef(arr)` trực tiếp tương đương `from_owned_array` (vẫn setflags read-only).
- **`metadata` và `artifacts` là `Mapping`**: protocol type, không `dict`. `MappingProxyType` là `Mapping`. Type hint chính xác.
- **`__post_init__` wrap với defensive copy**: `MappingProxyType(dict(self.metadata))` — copy first, wrap second. Nếu chỉ wrap không copy → caller mutate underlying dict sẽ leak.
- **`object.__setattr__`** trong `__post_init__`: dataclass `frozen=True` block normal `self.metadata = ...`. `object.__setattr__` bypass — đây là pattern chính thức cho frozen dataclass post-init transformation.
- **CoW methods**: `dict(self.artifacts)` defensive copy → mutate copy → wrap MappingProxyType → `replace(self, artifacts=...)`. Original packet unchanged.

### Giới hạn đã biết (ERRATA E-12 — đọc kỹ)

- **Risk 1 — Immutability NÔNG (shallow):** `MappingProxyType(dict(...))` chỉ copy + khoá ở
  **mức nông**. Nếu metadata/artifacts chứa object lồng MUTABLE (list/dict con), downstream **vẫn
  sửa được**: `packet.metadata["lst"].append(x)` chạy; và caller mutate nested sau khi tạo packet
  cũng leak vào packet (đã verify thật). → **KHÔNG** auto `deepcopy` (artifacts hay chứa ndarray/
  detections lớn → tốn + có thứ không deepcopy được; production dùng typed `ArtifactKey`). **Quy ước:**
  đừng đặt nested-mutable cần bảo vệ vào metadata/artifacts; nếu cần, caller tự copy hoặc dùng giá trị immutable (tuple/frozenset).
- **Risk 2 — Buffer reuse tearing:** camera SDK (OpenCV/GStreamer/RTSP) hay ghi đè tuần hoàn lên 1
  ndarray cố định. `setflags(write=False)` chặn downstream sửa qua *ndarray này*, nhưng KHÔNG chặn
  SDK ghi native lên cùng buffer ở frame kế → đổi ngầm data packet cũ. → **Adapter camera PHẢI dùng
  `InMemoryArrayRef.from_copy(...)`** (không `from_owned_array`) trừ khi chắc chắn buffer không tái dùng;
  hoặc dùng SHM frame bus có quản lý vòng đời (Step 05). (Đây là contract cho Step 03 adapters.)

### Pitfall thường thấy

**Sai 1 — quên `dict()` lúc copy**:
```python
# Sai
def with_artifact(self, key, value):
    self.artifacts[key] = value   # FAIL — MappingProxyType readonly
    return ???
```

**Sai 2 — wrap không copy**:
```python
# Sai
new_artifacts = self.artifacts   # ← chỉ alias, không copy
new_artifacts[key] = value        # FAIL
```

**Đúng**:
```python
new_artifacts = dict(self.artifacts)   # plain dict, mutable
new_artifacts[key] = value             # mutate plain dict OK
return replace(self, artifacts=MappingProxyType(new_artifacts))  # wrap final
```

**Sai 3 — tưởng `MediaPacket` hashable**:
```python
# Sai — sẽ raise TypeError lúc runtime
seen = set()
seen.add(packet)              # TypeError: unhashable type: 'numpy.ndarray'
cache = {packet: result}      # cũng FAIL
```

`@dataclass(frozen=True)` **tự sinh `__hash__`** từ **mọi field**. `MediaPacket` chứa
`InMemoryArrayRef(array=ndarray)`, mà `ndarray` **không hashable** → `hash(packet)` raise
`TypeError`. Đừng dùng `MediaPacket` làm key của `dict`/`set`.

→ Cần khóa theo packet? Dùng **`packet.packet_id`** (str, hashable) làm key:
```python
cache = {packet.packet_id: result}   # OK
```
→ Nếu thật sự cần `MediaPacket` hashable (hiếm), khai `@dataclass(frozen=True, eq=False)`
để dùng identity-hash (`id()`), nhưng cân nhắc kỹ vì mất value-equality.

---

## Phần 4 — Test (30 phút)

Tạo `tests/test_step_02_domain.py`:

```python
"""Step 02 tests: domain BBox + kernel ReadResult + MediaPacket immutability."""
import numpy as np
import pytest
from vision_demo.domain.bbox import BBox, CoordinateSpace
from vision_demo.kernel.read_result import ReadResult, ReadStatus
from vision_demo.kernel.media_packet import MediaPacket, InMemoryArrayRef


# ============ BBox ============

def test_bbox_basic():
    b = BBox(10, 20, 100, 50, CoordinateSpace.ORIGINAL_FRAME)
    assert b.x == 10
    assert b.x2 == 110
    assert b.y2 == 70
    assert b.area == 5000


def test_bbox_negative_size_rejected():
    with pytest.raises(ValueError):
        BBox(0, 0, -10, 50, CoordinateSpace.ORIGINAL_FRAME)


def test_bbox_immutable():
    b = BBox(10, 20, 100, 50, CoordinateSpace.ORIGINAL_FRAME)
    with pytest.raises(Exception):  # FrozenInstanceError
        b.x = 999


def test_bbox_normalized_out_of_range_rejected():
    """ERRATA E-12 (Risk 3): NORMALIZED yêu cầu tọa độ trong [0,1]."""
    with pytest.raises(ValueError):
        BBox(100.0, 0.0, 0.5, 0.5, CoordinateSpace.NORMALIZED)
    BBox(0.1, 0.2, 0.5, 0.5, CoordinateSpace.NORMALIZED)  # hợp lệ → không raise


def test_bbox_space_is_required():
    """Coordinate space MUST be explicit — không có default."""
    with pytest.raises(TypeError):
        BBox(10, 20, 100, 50)  # missing `space`


# ============ ReadResult ============

def test_readresult_frame_has_data():
    arr = np.zeros((10, 10), dtype=np.uint8)
    r = ReadResult(status=ReadStatus.FRAME, data=arr)
    assert r.has_data
    assert r.data is arr


def test_readresult_eof_no_data():
    r = ReadResult(status=ReadStatus.EOF)
    assert not r.has_data
    assert r.data is None


def test_readresult_immutable():
    r = ReadResult(status=ReadStatus.TIMEOUT)
    with pytest.raises(Exception):
        r.status = ReadStatus.FRAME


# ============ InMemoryArrayRef ============

def test_array_ref_locks_array_readonly():
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef(arr)
    
    with pytest.raises(ValueError):
        ref.array[0, 0, 0] = 99


def test_array_ref_default_takes_ownership():
    """Default constructor: caller's array also becomes read-only."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef(arr)
    
    # Caller's reference also blocked (same underlying array).
    with pytest.raises(ValueError):
        arr[0, 0, 0] = 99


def test_array_ref_from_copy_isolates():
    """from_copy: caller can keep mutating their array."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef.from_copy(arr)
    
    # Caller mutates their copy.
    arr[0, 0, 0] = 99
    
    # Ref's snapshot intact.
    assert ref.array[0, 0, 0] == 0


def test_array_ref_rejects_non_ndarray():
    """Type safety (C): non-ndarray → TypeError rõ nghĩa, không phải AttributeError tối nghĩa."""
    with pytest.raises(TypeError):
        InMemoryArrayRef([1, 2, 3])


def test_array_ref_stays_readonly_after_pickle():
    """ERRATA E-11: pickle round-trip phải GIỮ read-only.
    numpy reset writeable=True sau unpickle + __post_init__ không chạy lại →
    __setstate__ re-lock. Quan trọng khi MediaPacket đi qua ranh giới process."""
    import pickle
    ref = InMemoryArrayRef(np.zeros((4, 4, 3), dtype=np.uint8))
    ref2 = pickle.loads(pickle.dumps(ref))
    assert not ref2.array.flags.writeable
    with pytest.raises(ValueError):
        ref2.array[0, 0, 0] = 99


# ============ MediaPacket ============

def _make_packet(meta=None, arts=None):
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    return MediaPacket(
        packet_id="p1",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=12345,
        metadata=meta or {},
        artifacts=arts or {},
    )


def test_packet_metadata_blocked():
    p = _make_packet(meta={"key": "val"})
    with pytest.raises((TypeError, AttributeError)):
        p.metadata["new"] = "x"


def test_packet_artifacts_blocked():
    p = _make_packet(arts={"key": "val"})
    with pytest.raises((TypeError, AttributeError)):
        p.artifacts["new"] = "x"


def test_packet_with_artifact_returns_new_packet():
    p1 = _make_packet()
    p2 = p1.with_artifact("detections", [1, 2, 3])
    
    assert p1 is not p2
    assert "detections" not in p1.artifacts
    assert p2.artifacts["detections"] == [1, 2, 3]


def test_packet_caller_dict_mutation_does_not_leak():
    """Mutate caller's source dict AFTER construction — packet unchanged."""
    meta = {"k": "original"}
    p = _make_packet(meta=meta)
    
    meta["k"] = "modified"
    meta["new"] = "added"
    
    assert p.metadata["k"] == "original"
    assert "new" not in p.metadata


def test_packet_with_metadata_chain():
    """Multiple CoW operations chain correctly."""
    p1 = _make_packet()
    p2 = p1.with_metadata("a", 1).with_metadata("b", 2)
    
    assert p1.metadata == {}
    assert p2.metadata["a"] == 1
    assert p2.metadata["b"] == 2


def test_packet_without_artifact():
    p1 = _make_packet(arts={"x": 1, "y": 2})
    p2 = p1.without_artifact("x")
    
    assert "x" in p1.artifacts   # unchanged
    assert "x" not in p2.artifacts
    assert p2.artifacts["y"] == 2
```

**Verify**:
```bash
pytest
```

→ Expected:
```
============================= test session starts =============================
collected 21 items   # 19 step_02 + 2 smoke

tests/test_smoke.py::test_package_importable PASSED                      [  4%]
tests/test_smoke.py::test_package_has_layers PASSED                      [  9%]
tests/test_step_02_domain.py::test_bbox_basic PASSED                     [ 14%]
... (19 tests pass) ...

============================= 21 passed in 0.5s ==============================
```

---

## Self-check

1. **`__post_init__`** trong `MediaPacket` làm gì? Tại sao dùng `object.__setattr__`?

2. **`MappingProxyType(dict(self.metadata))`** — tại sao có `dict(...)` ở giữa?

3. Nếu xoá `setflags(write=False)` trong `InMemoryArrayRef.__post_init__`, test nào fail?

4. **CoordinateSpace** không có default. Pros/cons.

5. Vẽ diagram: caller có dict `meta = {"k": 1}`. Pass vào `MediaPacket(metadata=meta, ...)`. Sau đó caller `meta["k"] = 99`. **Tại sao** packet không bị mutate?

<details>
<summary>Đáp án</summary>

1. **`__post_init__` chuyển dict thành MappingProxyType với defensive copy**. Dùng `object.__setattr__` vì `frozen=True` block normal assignment. `object.__setattr__` là escape hatch chính thức được dataclass docs encourage cho post-init transformation.

2. `dict(self.metadata)` = **defensive copy** dict caller pass vào. Không có dict copy:
   ```python
   meta = {"k": 1}
   p = MediaPacket(metadata=MappingProxyType(meta))  # ← view của meta
   meta["k"] = 99
   p.metadata["k"]  # → 99! Đã leak.
   ```
   
   Có dict copy:
   ```python
   p = MediaPacket(metadata=MappingProxyType(dict(meta)))  # ← snapshot
   meta["k"] = 99
   p.metadata["k"]  # → 1. Snapshot intact.
   ```

3. `test_array_ref_locks_array_readonly` và `test_array_ref_default_takes_ownership` sẽ fail. Cả 2 expect `ValueError` khi mutate, nhưng nếu không lock thì mutate sẽ thành công.

4. **Pros**:
   - Buộc dev nghĩ về space — bug "lệch sau resize" không lặp lại.
   - Code review dễ — đọc `BBox(...space=...)` thấy ngay context.
   - Type-safe — không default → mọi instance có space.
   
   **Cons**:
   - Verbose hơn — 5 arg thay vì 4.
   - Migration code cũ cần thêm space mọi nơi.
   - Junior dev có thể default sai (e.g. luôn `ORIGINAL_FRAME` không kiểm tra).

5. **Diagram**:
   ```
   meta dict in caller's frame:
       {"k": 1}              ← caller's reference
   
   MediaPacket(metadata=meta, ...):
       __post_init__ → MappingProxyType(dict(meta))
                              ↓
       new_dict = {"k": 1}   ← copy made here, separate object
       packet.metadata = MappingProxyType(new_dict)
                              ↓
                          read-only view of new_dict
   
   caller does meta["k"] = 99:
       caller's meta dict now {"k": 99}
       new_dict (inside packet) still {"k": 1}
   
   packet.metadata["k"] → reads from new_dict → 1
   ```

</details>

---

## Liên kết

- **Module 02 file 05** (immutability + CoW) — pattern chính.
- **Production**: `Vision_platform_architecture_design/03-data-contracts/06-mediapacket-frozen-dto-voi-true-immutability-cow.md` — bản full với typed ArtifactKey, sum type media_ref, trace_context.

---

## Tóm tắt 1 câu

> **3 file cốt lõi: BBox với CoordinateSpace tag (no default), ReadResult với 6 status explicit, MediaPacket với MappingProxyType + setflags + CoW. Defensive copy ở `__post_init__` ngăn caller's mutation leak.**

➡️ Tiếp theo: [`step-03-first-port.md`](step-03-first-port.md)
