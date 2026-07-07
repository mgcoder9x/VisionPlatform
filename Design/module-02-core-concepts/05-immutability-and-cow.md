# 05 — Immutability + Copy-on-Write trong Python (cách làm ĐÚNG)

## TL;DR (30 giây)

> **Immutable** = object không thể mutate sau khi tạo. **Copy-on-Write (CoW)** = thay vì mutate, return object MỚI với thay đổi.
>
> Python `dataclass(frozen=True)` **chỉ chặn attribute reassignment**. KHÔNG chặn mutate `dict`, `list`, `np.ndarray` BÊN TRONG. Đây là **trap** mà nhiều dev không biết.
>
> Vision Platform `MediaPacket` = frozen + nested fields wrap với `MappingProxyType` / `tuple` / `setflags(write=False)` → **true** immutable. Mutate → return new MediaPacket via `with_artifact(...)`.

---

## Mental hook

Bạn vừa code 1 stage Vision Platform:

```python
@dataclass(frozen=True)
class MediaPacket:
    packet_id: str
    metadata: dict[str, str]
    artifacts: dict[str, Any]


def detection_stage(packet: MediaPacket) -> MediaPacket:
    """Detect, write into artifacts, return packet."""
    detections = run_yolo(packet)
    packet.artifacts["detections"] = detections   # ← mutate dict
    return packet
```

Test pass. Code review pass. Deploy production.

**1 tuần sau**: bug ngẫu nhiên — đôi khi camera 1 detection xuất hiện trong event của camera 2.

Bạn debug 3 ngày. Cuối cùng tìm ra:

```python
# Trong code khác:
shared_packet = create_packet()

# Camera 1 stage:
detection_stage(shared_packet)   # mutate artifacts!

# Camera 2 stage cùng lúc (concurrent):
detection_stage(shared_packet)   # đọc artifacts của Camera 1!
```

→ `frozen=True` **không** ngăn mutate dict bên trong. Bạn nghĩ packet immutable, nó không.

→ Đây chính xác là pattern bug **MediaPacket trong R1 review** đã catch. **CR-DC-01** = `ReadResult.metadata: dict` mutable trong frozen dataclass.

---

## Câu chuyện: Python `frozen=True` chỉ là **shallow freeze**

```python
from dataclasses import dataclass, field, FrozenInstanceError

@dataclass(frozen=True)
class Person:
    name: str
    hobbies: list[str] = field(default_factory=list)


p = Person("Alice", ["reading"])

# Test 1: reassignment chặn?
try:
    p.name = "Bob"
except FrozenInstanceError:
    print("✓ name reassignment blocked")

# Test 2: mutate field bên trong?
p.hobbies.append("coding")   # ← KHÔNG raise!
print(p.hobbies)
# ['reading', 'coding']  ← Đã mutate!
```

→ `frozen=True` chỉ làm `__setattr__` raise `FrozenInstanceError`. List bên trong vẫn mutate được vì list KHÔNG frozen.

**Tại sao Python design vậy?**

Python triết lý: **immutable theo từng level**. Bạn muốn deep immutable = tự enforce.

→ Đây là sự khác biệt lớn với Rust (move semantics enforce ownership), Clojure (persistent data structures), Haskell (mặc định pure).

→ Vision Platform phải **tự build** true immutability.

---

## Vấn đề thực tế: 4 cách shallow-frozen gây bug

### Bug 1: Concurrent mutation (race condition)

```python
@dataclass(frozen=True)
class CameraConfig:
    name: str
    enabled_features: list[str]  # ← mutable!

config = CameraConfig("cam1", ["motion", "face"])

# Thread A:
config.enabled_features.remove("motion")   # mutate!

# Thread B (concurrent):
if "motion" in config.enabled_features:    # đọc trong race
    do_motion_detection()
```

→ Race condition. Đôi khi B thấy "motion", đôi khi không. Bug ngẫu nhiên.

### Bug 2: Defensive copy fail

```python
@dataclass(frozen=True)
class Snapshot:
    timestamp: float
    data: dict


snapshot = take_snapshot()
historical = []
historical.append(snapshot)   # lưu snapshot

# 1 phút sau, code khác mutate snapshot.data
snapshot.data["new_key"] = "value"

# Bây giờ historical[0].data có new_key — snapshot bị "rewrite history"
```

→ Snapshot không phải snapshot. **Định nghĩa "snapshot"** đã bị vi phạm.

### Bug 3: Cache poisoning

```python
@cache
def expensive_compute(packet: MediaPacket) -> Result:
    ...

p1 = MediaPacket("id1", artifacts={})
result = expensive_compute(p1)   # cached

p1.artifacts["key"] = "value"    # mutate
result2 = expensive_compute(p1)  # ← cache hit, return cũ. KHÔNG re-compute.
```

→ Cache key (object identity) = same. Cache trả result cũ. Caller nghĩ packet đã đổi.

→ **Mutable object là cache KEY = bug rủi ro**.

### Bug 4: Logging frozen lúc read

```python
@dataclass(frozen=True)
class Order:
    items: list[OrderItem]


order = Order([item_a, item_b])
logger.info("order created", order=order)   # ← log "snapshot" lúc này

# Logger là async, queue → format str sau:
# Trong thời gian đó:
order.items.append(item_c)   # mutate

# Logger format str: "items=[item_a, item_b, item_c]"  ← sai!
```

→ Log nhìn như **lúc log gửi đi** chứ không phải lúc emit.

---

## Định nghĩa chính xác

### Immutable — 3 levels

| Level | Đảm bảo | Python achieve |
|-------|---------|----------------|
| **Reference immutable** | Không reassign attribute | `frozen=True` ✓ |
| **Shallow immutable** | Không mutate top-level field | `__setattr__` block + tự kiểm |
| **Deep immutable** | Không mutate nested gì | `MappingProxyType`, `tuple`, `ndarray.setflags(write=False)` |

Vision Platform target **deep immutable** cho `MediaPacket` — đây là yêu cầu thật.

### Copy-on-Write (CoW)

Khi cần "mutate" → **return new object**, giữ old:

```python
# Mutate (anti-pattern in immutable world)
obj.field = new_value

# CoW
new_obj = obj.with_field(new_value)
```

Lợi ích:
- Old object vẫn valid → caller giữ reference an toàn.
- Concurrent: mỗi thread giữ snapshot riêng, không race.
- Cache key stable.
- Reasoning về flow dễ — **không có "spooky action at distance"**.

Cost:
- Allocation — tạo object mới mỗi lần.
- GC pressure — Python ref-count + cyclic GC.
- Phải design API mới (`with_xxx`, `replace_xxx`).

### Trade-off

Immutability đẹp nhưng cost cao. Vision Platform pick chỗ:
- **MediaPacket** = deep immutable (frame xử lý cross-thread, cross-process).
- **Stage internal state** = mutable (1 thread, 1 stage instance).

→ **Áp dụng có chọn lọc**. Không phải mọi class đều immutable.

---

## Cách làm ĐÚNG trong Python — 5 kỹ thuật

### Kỹ thuật 1: `dataclass(frozen=True)` cho top-level

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Coord:
    x: float
    y: float

c = Coord(1.0, 2.0)
c.x = 3.0   # FrozenInstanceError
```

→ Đủ cho **value object đơn giản** (chỉ scalar field).

### Kỹ thuật 2: `tuple` cho list immutable

```python
@dataclass(frozen=True)
class Polygon:
    points: tuple[Coord, ...]   # tuple thay vì list

p = Polygon((Coord(0,0), Coord(1,0), Coord(1,1)))
p.points.append(...)   # AttributeError - tuple không có append
```

→ `tuple` là immutable built-in. Lúc construct: `tuple(my_list)`.

### Kỹ thuật 3: `MappingProxyType` cho dict immutable view

```python
from types import MappingProxyType

@dataclass(frozen=True)
class Config:
    options: MappingProxyType   # read-only view

# Lúc construct:
def make_config(options_dict):
    return Config(MappingProxyType(dict(options_dict)))

c = make_config({"a": 1, "b": 2})
c.options["c"] = 3   # TypeError - read-only
```

**Lưu ý**: `MappingProxyType` là **view**, không copy. Nếu underlying dict thay đổi, view phản ánh:

```python
underlying = {"a": 1}
view = MappingProxyType(underlying)
underlying["b"] = 2   # mutate underlying
print(view)   # {"a": 1, "b": 2} — view see changes
```

→ **Phải copy dict TRƯỚC khi wrap**: `MappingProxyType(dict(original))` (copy underlying).

Vision Platform `ReadResult` dùng `__post_init__` enforce:

```python
@dataclass(frozen=True)
class ReadResult:
    metadata: Optional[Mapping[str, object]] = None

    def __post_init__(self):
        if self.metadata is not None and not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(
                self, "metadata", MappingProxyType(dict(self.metadata)),
            )
```

**Notes**:
- `object.__setattr__` bypass `frozen=True` block — chỉ làm trong `__post_init__`.
- `dict(self.metadata)` defensive copy.
- Sau `__post_init__`, attribute is `MappingProxyType` → mọi mutate fail.

### Kỹ thuật 4: `np.ndarray.setflags(write=False)`

```python
import numpy as np

arr = np.zeros((100, 100, 3), dtype=np.uint8)
arr.setflags(write=False)   # read-only

arr[0, 0, 0] = 255   # ValueError - assignment destination is read-only
```

→ Numpy có flag riêng. **In-place** — không copy, chỉ flip flag.

**Caveat**: `setflags(write=False)` **mutate** ndarray (đổi flag). Khác với truly immutable.

Vision Platform `InMemoryArrayRef`:

```python
@dataclass(frozen=True)
class InMemoryArrayRef:
    """Frame data is np.ndarray in this process's memory.

    Ownership contract:
      - Constructor takes ownership of `array` and locks it read-only.
      - The CALLER must NOT continue to write through their reference
        after constructing this ref.
    """
    array: np.ndarray

    def __post_init__(self):
        if self.array.flags.writeable:
            self.array.setflags(write=False)
    
    @classmethod
    def from_copy(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Take a defensive copy and lock the COPY read-only."""
        snapshot = np.ascontiguousarray(array.copy())
        return cls(array=snapshot)
```

→ 2 mode:
- Default: **transfer ownership** (caller hứa không mutate sau khi tạo ref). Zero copy.
- `from_copy`: **defensive copy** (caller giữ reference + mutate). Cost = extra alloc.

### Kỹ thuật 5: `with_*` methods cho CoW

```python
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class MediaPacket:
    packet_id: str
    artifacts: MappingProxyType  # frozen dict-like

    def with_artifact(self, key: str, value: Any) -> "MediaPacket":
        """Return new packet with artifact added/replaced."""
        new_artifacts = dict(self.artifacts)  # defensive copy
        new_artifacts[key] = value
        return replace(self, artifacts=MappingProxyType(new_artifacts))


p1 = MediaPacket("id1", MappingProxyType({}))
p2 = p1.with_artifact("detections", [...])

# p1 unchanged
print(p1.artifacts)  # {}
print(p2.artifacts)  # {"detections": [...]}
```

→ **`dataclasses.replace()`** built-in tạo new dataclass với field thay đổi. Khớp tốt với `frozen=True`.

→ Convention: method `with_xxx(...)` return new instance.

---

## Build true immutable MediaPacket from scratch (45 phút)

```python
# packet_demo/media_packet.py
"""True immutable MediaPacket."""
from dataclasses import dataclass, field, replace
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
import numpy as np


@dataclass(frozen=True)
class InMemoryArrayRef:
    """Frame data, read-only by contract.
    
    Ownership transfer pattern: constructor locks array read-only.
    """
    array: np.ndarray

    def __post_init__(self):
        if self.array.flags.writeable:
            self.array.setflags(write=False)

    @classmethod
    def from_copy(cls, array: np.ndarray) -> "InMemoryArrayRef":
        snapshot = np.ascontiguousarray(array.copy())
        return cls(array=snapshot)


@dataclass(frozen=True)
class MediaPacket:
    """Immutable MediaPacket with CoW semantics.
    
    Use `with_artifact(key, value)` to add artifact — returns NEW instance.
    Original is unchanged.
    """
    packet_id: str
    source_id: str
    media_ref: InMemoryArrayRef
    capture_time_ns: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Wrap dict-like fields in MappingProxyType.
        # Defensive copy to detach from caller's reference.
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

    # CoW operations
    def with_artifact(self, key: str, value: Any) -> "MediaPacket":
        """Return new packet with artifact added/replaced."""
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

```python
# packet_demo/test_immutable.py
"""Verify true immutability."""
import numpy as np
import pytest
from packet_demo.media_packet import MediaPacket, InMemoryArrayRef


def make_packet():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    return MediaPacket(
        packet_id="p1",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=12345,
        metadata={"key1": "val1"},
        artifacts={},
    )


def test_attribute_reassignment_blocked():
    p = make_packet()
    with pytest.raises(Exception):
        p.packet_id = "p2"


def test_artifacts_mutation_blocked():
    p = make_packet()
    with pytest.raises((TypeError, AttributeError)):
        p.artifacts["new"] = "value"


def test_metadata_mutation_blocked():
    p = make_packet()
    with pytest.raises((TypeError, AttributeError)):
        p.metadata["new"] = "value"


def test_frame_mutation_blocked():
    p = make_packet()
    with pytest.raises(ValueError):
        p.media_ref.array[0, 0, 0] = 255   # writeable=False


def test_with_artifact_creates_new_packet():
    p1 = make_packet()
    p2 = p1.with_artifact("detections", [1, 2, 3])
    
    # p1 unchanged
    assert "detections" not in p1.artifacts
    
    # p2 has it
    assert p2.artifacts["detections"] == [1, 2, 3]
    
    # Different objects
    assert p1 is not p2


def test_caller_dict_mutation_doesnt_leak():
    """Caller mutate dict source AFTER construction → packet không bị ảnh hưởng."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    metadata = {"key": "original"}
    p = MediaPacket(
        packet_id="p1",
        source_id="cam1",
        media_ref=InMemoryArrayRef(arr),
        capture_time_ns=0,
        metadata=metadata,
    )
    
    # Caller mutates source dict.
    metadata["key"] = "modified"
    metadata["new_key"] = "new_value"
    
    # Packet UNCHANGED.
    assert p.metadata["key"] == "original"
    assert "new_key" not in p.metadata


def test_caller_array_mutation_doesnt_leak_with_from_copy():
    """If using from_copy, caller mutation won't leak."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef.from_copy(arr)
    
    arr[0, 0, 0] = 99   # caller mutates after construction
    
    assert ref.array[0, 0, 0] == 0   # snapshot intact


def test_caller_array_mutation_LEAKS_with_default_constructor():
    """Default constructor takes OWNERSHIP — caller MUST NOT mutate after."""
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ref = InMemoryArrayRef(arr)
    
    # arr.setflags(write=False) đã set → caller mutate sẽ raise
    with pytest.raises(ValueError):
        arr[0, 0, 0] = 99
```

Run:

```bash
mkdir packet_demo
# tạo 2 file
pip install pytest numpy
py -m pytest packet_demo/test_immutable.py -v
```

Expected: cả 8 test pass.

---

## Áp dụng vào Vision Platform

`Vision_platform_architecture_design/03-data-contracts/06-mediapacket-frozen-dto-voi-true-immutability-cow.md` chứa MediaPacket production version. Khác bản trên ở:

- Thêm `trace_context` cho distributed tracing.
- `artifacts` dùng `ArtifactKey[T]` typed namespaced thay vì `str`.
- `media_ref` là sum type (InMemoryArrayRef | ShmFrameRef | BytesRef | FileRef).
- `with_artifact(key, value, producer_stage)` track stage tạo artifact.

→ **Cùng pattern**, scale up.

### CoW chain trong pipeline

```python
def detection_stage(packet: MediaPacket) -> MediaPacket:
    detections = run_yolo(packet)
    return packet.with_artifact(DETECTIONS_RAW, detections, producer_stage="detect")


def tracking_stage(packet: MediaPacket) -> MediaPacket:
    detections = packet.artifacts.get(DETECTIONS_RAW) or []
    tracks = tracker.update(detections)
    return packet.with_artifact(TRACKS, tracks, producer_stage="track")


# Pipeline
p0 = source.read()
p1 = detection_stage(p0)   # p0 unchanged
p2 = tracking_stage(p1)    # p1 unchanged
sink.emit(p2)
```

→ Mỗi stage **immutable transform**. Pipeline = **chain of CoW**. Easy debug, no race.

---

## Checkpoint

1. **Shallow vs deep immutability** — phân biệt với code example.

2. **`MappingProxyType` trap**: Cho 1 đoạn code dùng `MappingProxyType` SAI. Sửa.

3. **`setflags(write=False)`**: cost là gì? In-place hay copy? Khi nào caller cần `from_copy`?

4. **CoW chain**: Pipeline 5 stage, mỗi stage `with_artifact`. Allocation cost? Nó có vấn đề?

5. **Concurrent**: 2 thread cùng đọc `packet.artifacts["detections"]`. Có race không nếu packet `frozen=True` + `MappingProxyType`?

<details>
<summary>Đáp án</summary>

1. **Shallow** = top-level reassignment blocked. **Deep** = mutate nested cũng blocked.
   ```python
   @dataclass(frozen=True)
   class A:
       items: list   # ← shallow only
   
   a = A([1,2,3])
   # a.items = [4]    → blocked (shallow)
   a.items.append(4)  # OK — list bên trong vẫn mutate được
   ```
   
   Deep version:
   ```python
   @dataclass(frozen=True)
   class A:
       items: tuple   # tuple = immutable
   ```

2. **Sai**:
   ```python
   data = {"a": 1}
   view = MappingProxyType(data)
   ```
   → `data` vẫn mutable bên ngoài. `view` chỉ "block" mutate qua view, không block qua `data`.
   
   **Đúng**:
   ```python
   data = {"a": 1}
   view = MappingProxyType(dict(data))   # copy first
   ```
   → Sau này `data["b"] = 2` không ảnh hưởng `view`.

3. **`setflags(write=False)`**: in-place, **không copy**. Cost ~ns. Chỉ flip 1 flag.
   
   **Khi cần `from_copy`**:
   - Caller muốn giữ reference array gốc và **mutate tiếp** (e.g. UI redraw on same buffer).
   - Caller pass array shared với code khác.
   
   Default constructor = **transfer ownership** = caller không mutate sau. Zero alloc cost. Hot path Vision Platform dùng default.

4. **5 stage allocation**: mỗi stage → 1 MediaPacket mới + 1 dict copy cho artifacts. Cost mỗi stage:
   - Dataclass new instance: ~100ns.
   - dict copy: ~O(n) where n = số artifact.
   - MappingProxyType wrap: ~ns.
   
   **Vấn đề**: nếu artifacts dict to (100+ items), dict copy cost lên ~µs. 5 stage × frame × 30 fps = ~150µs/s = 0.015% CPU. **Negligible** ở scale Vision Platform.
   
   Chỉ vấn đề ở scale extreme (10000 artifact/packet). Vision Platform có 5-20 artifact/packet thường thấy.

5. **Không race** với 2 reader concurrent:
   - `frozen=True` block reassign packet.
   - `MappingProxyType` chỉ cung cấp **read** API.
   - 2 reader cùng `packet.artifacts.get("key")` = 2 dict lookup parallel — không race vì không write.
   - **Nếu** có thread thứ 3 mutate underlying dict (vi phạm contract!) → race possible. Nhưng `from_copy` defensive đã ngăn.
   
   → Đây chính là **lý do** immutability mạnh. Concurrent read **safe by design**.

</details>

---

## Trade-offs

### "Allocation overhead?"

CoW = mỗi mutate tạo new instance + dict copy. Cost ~µs/op.

→ **Negligible** với rate vừa. Nhưng hot loop millions/s = vấn đề. Vision Platform ~30 fps × 16 cam × 5 stage = 2400 op/s. **Hoàn toàn OK**.

→ Nếu hot path thật sự cần mutable (game engine, signal processing): chấp nhận mutable, cẩn thận race.

### "Mọi class phải immutable?"

KHÔNG. Quy tắc:

- **DTO cross-thread/process**: immutable. (`MediaPacket`, `ReadResult`)
- **Stage internal state**: mutable OK. (1 thread, 1 instance)
- **Service singleton**: mutable OK. (singleton pattern)
- **Builder, factory**: mutable trong build phase, freeze final.

→ Vision Platform mix.

### "Python không native immutable — cost cao?"

**Cost**: ~30% slower so với Java/Rust native immutable. Nhưng Vision Platform hot path là numpy/cv2/GPU — Python overhead < 5%. **Acceptable**.

---

## Pitfalls

### Pitfall 1: `frozen=True` self-confidence

Bug từ R1: `ReadResult.metadata: dict` mutable trong frozen dataclass. Test pass vì test không mutate metadata. Production crash khi 1 caller mutate.

**Sửa**: enforce `MappingProxyType` trong `__post_init__` với defensive copy.

### Pitfall 2: Forget defensive copy

```python
# Sai
def make_packet(metadata):
    return MediaPacket(metadata=MappingProxyType(metadata))   # ← view của caller's dict

# Đúng
def make_packet(metadata):
    return MediaPacket(metadata=MappingProxyType(dict(metadata)))   # copy first
```

→ Caller mutate `metadata` AFTER construction = packet "follows" — bug.

### Pitfall 3: Performance regression do over-CoW

```python
# Loop có CoW
for i in range(1000):
    packet = packet.with_artifact(f"item_{i}", i)   # 1000 × CoW
```

→ 1000 dict copies. O(n²) tổng cost.

**Sửa**: build dict trong 1 dict, sau đó freeze 1 lần:
```python
mutable_dict = dict(packet.artifacts)
for i in range(1000):
    mutable_dict[f"item_{i}"] = i
packet = replace(packet, artifacts=MappingProxyType(mutable_dict))
```

→ Vision Platform tránh batch operation kiểu này. Nếu có loop → batch và freeze 1 lần cuối.

### Pitfall 4: Exception traceback giữ packet sống

R5-CRITICAL-02: `Exception.__traceback__` giữ stack frame → frame's `f_locals` → MediaPacket → ndarray 6MB. DLQ buffer chứa 1000 exception = 6GB RAM lock down.

→ Vision Platform fix bằng `ErrorSummary` + `traceback.clear_frames()`. Đọc Module 04 file 06.

### Pitfall 5: Cycle reference với `replace()`

```python
@dataclass(frozen=True)
class Node:
    value: int
    parent: Optional["Node"] = None

n1 = Node(1)
n2 = Node(2, parent=n1)
n3 = Node(3, parent=n2)

# Mutate n1's "next"? Không thể — frozen.
# Phải rebuild cả chain.
```

→ Linked structure với immutable: rebuild hoặc dùng persistent data structure (immutables.org).

→ Vision Platform tránh cycle. Pipeline = linear chain.

---

## Liên kết

- File [`99-self-check.md`](99-self-check.md) — tổng hợp Module 02.
- Production: `Vision_platform_architecture_design/03-data-contracts/06-mediapacket-*.md`.
- Module 04 file 06 (`06-traceback-memory-retention.md`) — deep dive R5-CRITICAL-02 traceback bug.
- Module 05 file 02 (`02-traceback-retention-r5.md`) — case study bug R5-CRITICAL-02.
- Module 05 file 04 (`04-frozen-dataclass-with-mutable-dict.md`) — case study bug CR-DC-01.

---

## Tóm tắt 1 câu

> **Python `frozen=True` chỉ shallow — cần `MappingProxyType` (dict), `tuple` (list), `setflags(write=False)` (ndarray) để deep immutable. CoW = `with_xxx()` return new instance. Defensive copy KHI construct, không lưu reference của caller.**

➡️ Tiếp theo: [`99-self-check.md`](99-self-check.md)
