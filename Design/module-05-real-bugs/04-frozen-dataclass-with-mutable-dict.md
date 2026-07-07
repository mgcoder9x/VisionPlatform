## CR-DC-01 — Frozen Dataclass with Mutable Dict (Shallow Immutability Trap)

**Severity**: MEDIUM. Race condition + cross-camera leak.

---

## Setup (3 phút) — Reproducer

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ReadResult:
    status: str
    data: object = None
    metadata: dict = None  # ← shallow frozen — content mutable!


# Bug: caller mutates metadata after construction.
result = ReadResult(status="frame", data=None, metadata={"camera_id": "cam_1"})
print(result.metadata)  # {"camera_id": "cam_1"}

# Some downstream code mutates:
result.metadata["camera_id"] = "cam_2"
result.metadata["leaked"] = "secret"

print(result.metadata)  # {"camera_id": "cam_2", "leaked": "secret"} — BUG!
```

→ `frozen=True` chỉ chặn `result.metadata = new_dict`. NOT chặn `result.metadata["x"] = y`.

---

## Bug story

**Production scenario**: Vision Platform 16 cameras processing frames concurrently. Sporadic detection mix-ups.

- **Symptom 1**: Camera 1 detection events occasionally tagged with camera_id="cam_2".
- **Symptom 2**: Tracker IDs cross-contaminating between cameras.
- **Symptom 3**: Privacy filter sometimes applied to wrong frames.
- **Frequency**: ~1 in 10000 frames. Hard to reproduce.

### Investigation

- Race condition heavy logging on `ReadResult.metadata` modifications.
- Trace shows: 2 threads holding refs to same `metadata` dict.
- Modify happens between consumers → state torn.

### Reviewer R1 finding

```python
@dataclass(frozen=True)
class ReadResult:
    metadata: dict = None
```

→ Reviewer noted: "`frozen=True` is **shallow**. `metadata` field is plain `dict` → mutable."

→ Verified by writing failing test (was passing before):

```python
def test_metadata_is_immutable():
    r = ReadResult(metadata={"a": 1})
    r.metadata["b"] = 2  # MUST raise
```

Original passed (no raise). Bug confirmed.

---

## Why it happened (root cause)

### Mental model sai

Dev assumed:
```
"@dataclass(frozen=True) → entire object immutable, including nested fields."
```

**Reality**: Python `frozen=True` only blocks `obj.field = value`. Does NOT recurse into mutable containers (dict, list, set, ndarray, ...).

### Why Python doesn't deep-freeze

Python philosophy:
- Immutability is a property of the **type**, not enforceable per-object.
- `dict`, `list`, `set` are inherently mutable types.
- To freeze, **wrap** in immutable type (`frozenset` for set, `tuple` for list, `MappingProxyType` for dict, `setflags(write=False)` for ndarray).

→ Dev must enforce manually.

### Race condition pattern

```
Thread A: result = read()  # metadata = {"camera_id": "cam_1"}
Thread A: process(result)
Thread B: result = read()  # different ReadResult, different metadata
Thread B: process(result)

# Some shared cache:
Thread A: cache.put("key", result)  # holds metadata
Thread B: cache.put("key", result)  # overwrites
Thread A: cache.get("key").metadata["camera_id"]  # → "cam_2"! Stale.
```

If `metadata` is **shared** between caches/buffers, mutation propagates.

---

## Fix (CR-DC-01 implemented)

### MappingProxyType wrap in __post_init__

```python
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

@dataclass(frozen=True)
class ReadResult:
    status: str
    data: object = None
    metadata: Mapping[str, object] = None  # ← Mapping, not dict
    
    def __post_init__(self):
        if self.metadata is not None and not isinstance(self.metadata, MappingProxyType):
            # `object.__setattr__` bypass frozen=True for post-init transformation.
            # Đây là escape hatch chính thống — Python design intentionally để dataclass
            # `__post_init__` có thể normalize/wrap field. Xem Module 02 file 05 (kỹ thuật 3).
            object.__setattr__(
                self, "metadata",
                MappingProxyType(dict(self.metadata)),  # defensive copy + read-only view
            )
```

### Critical: defensive copy `dict(self.metadata)`

```python
# Without defensive copy:
metadata = {"a": 1}
r = ReadResult(metadata=MappingProxyType(metadata))
metadata["b"] = 2  # ← CALLER mutates source dict
r.metadata["b"]    # → 2! Leaked.
```

```python
# With defensive copy:
r = ReadResult(metadata=MappingProxyType(dict(metadata)))
metadata["b"] = 2  # caller mutates own dict
r.metadata["b"]    # → KeyError. Snapshot intact.
```

### Test verifies fix

```python
def test_metadata_is_truly_immutable():
    r = ReadResult(metadata={"a": 1})
    
    # 1. Direct attribute reassignment blocked.
    with pytest.raises(FrozenInstanceError):
        r.metadata = {}
    
    # 2. Mutation of nested dict blocked.
    with pytest.raises((TypeError, AttributeError)):
        r.metadata["b"] = 2
    
    # 3. Caller's source dict mutation does not leak.
    src = {"k": "v"}
    r2 = ReadResult(metadata=src)
    src["leaked"] = True
    assert "leaked" not in r2.metadata  # snapshot intact
```

---

## Alternative fixes (rejected)

### Reject 1: Make all fields explicit immutable

```python
@dataclass(frozen=True)
class ReadResult:
    status: str
    data: object = None
    metadata_keys: tuple = ()
    metadata_values: tuple = ()
```

Pros: pure tuple, immutable.
Cons:
- Lookup O(n).
- Caller writes `dict(zip(r.metadata_keys, r.metadata_values))`.
- Awkward.

→ **Rejected**.

### Reject 2: Document "don't mutate" + trust

```python
@dataclass(frozen=True)
class ReadResult:
    metadata: dict = None
    """WARNING: do NOT mutate metadata."""
```

Pros: zero overhead.
Cons:
- Trust documentation in 50-person team = bug eventually.
- Race condition isn't documented away.
- "Don't break things" is policy, not enforcement.

→ **Rejected**. Defense in depth.

### Reject 3: Deep freeze recursively

```python
def deep_freeze(obj):
    if isinstance(obj, dict):
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(deep_freeze(x) for x in obj)
    if isinstance(obj, np.ndarray):
        obj.setflags(write=False)
        return obj
    return obj
```

Pros: fully recursive.
Cons:
- Slow for deep structures (recursive traversal).
- Doesn't catch user types (custom objects with mutable internal state).
- Over-engineering for current need.

→ **Rejected as default**. MappingProxyType + tuple at known boundary fields is sufficient.

---

## Prevention

### Test pattern

```python
def test_frozen_field_x_is_truly_immutable():
    """Regression test for shallow-frozen bug."""
    obj = MyDataclass(field_x={"k": "v"})
    
    # Reassignment blocked.
    with pytest.raises(FrozenInstanceError):
        obj.field_x = {}
    
    # Mutation of nested.
    with pytest.raises((TypeError, AttributeError)):
        obj.field_x["k"] = "modified"
    
    # Caller's dict mutation doesn't leak.
    src = {"k": "v"}
    obj2 = MyDataclass(field_x=src)
    src["leaked"] = True
    assert "leaked" not in obj2.field_x
```

→ Add for every frozen dataclass with dict/list field.

### Code review checklist

- [ ] `@dataclass(frozen=True)` + dict field → MappingProxyType wrap in __post_init__.
- [ ] List field → tuple.
- [ ] Set field → frozenset.
- [ ] ndarray field → setflags(write=False) + ownership doc.
- [ ] __post_init__ defensive copy from caller's input.

### Type hint enforcement

```python
metadata: Mapping[str, object] = None  # ← Mapping, not dict
```

→ Mypy catches `result.metadata["x"] = y` as type error (Mapping has no `__setitem__`).

### Lint rule (custom)

```python
# AST visitor detect:
# 1. @dataclass(frozen=True) with field type dict/list/set/np.ndarray.
# 2. Without __post_init__ wrap.
# Flag for review.
```

(Vision Platform doesn't have this lint yet — manual review.)

---

## Liên kết production

- `Vision_platform_architecture_design/03-data-contracts/02-idatasource-t-readresult.md` — `ReadResult` with MappingProxyType.
- `Vision_platform_architecture_design/03-data-contracts/06-mediapacket-frozen-dto-voi-true-immutability-cow.md` — `MediaPacket` similar pattern.
- Module 02 file 05 — immutability + CoW.
- Module 03 step 02 — code MediaPacket implementation.

---

## Tóm tắt

> **`@dataclass(frozen=True)` chỉ shallow — chặn `obj.field = ...`, KHÔNG chặn `obj.field[k] = ...`. Fix: `__post_init__` wrap dict trong `MappingProxyType(dict(self.metadata))` (defensive copy + read-only view). Test mọi frozen dataclass có dict/list/ndarray field.**

✅ Module 05 — 4 case studies hoàn thành.

---

## Tiếp tục đọc

Các bug khác (HI-IPC-04, CR-INF-02, CR-SEC-01, CR-PRV-01, ...) follow pattern tương tự. Đọc trực tiếp `Vision_platform_architecture_design/00-README.md` Round 1-5 fix tables — bạn đã có pattern recognition để hiểu mỗi bug nhanh.

➡️ Tiếp theo: [`../module-06-implementation/`](../module-06-implementation/)
