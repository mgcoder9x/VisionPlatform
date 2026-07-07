# Step 05 — SHM frame bus + multi-process bulkhead

## Mục tiêu (3h)

Bạn sẽ build:

1. `kernel/shm_frame_ref.py` — `ShmFrameRefData` (DTO thuần, mô tả 1 frame trong SHM; **không** import `multiprocessing`).
2. `runtime/ipc/shm_frame_ring.py` — `ShmRingBuffer`, `ShmFrameWriter`, `ShmFrameReader`, `SlotState` với per-slot lock + generation ABA prevention (transport — có `multiprocessing`/`shared_memory`).
3. **13 test** bao gồm cross-process subprocess test thật.

Đến cuối step, bạn có **multi-process frame transport** chạy được — frame ndarray pass qua process boundary với latency ~5µs/copy.

> **Đã verify**: 13 test pass, 1.63s runtime. Cross-process test (writer trong subprocess, reader trong parent) **chạy thật** với `multiprocessing.Process` + cleanup.

> **Layer boundary (đặt đúng ngay từ đầu):** transport SHM là **I/O concern** → đặt ở `runtime/ipc/shm_frame_ring.py`. DTO mô tả frame (`ShmFrameRefData`) là **dữ liệu thuần** → ở `kernel/shm_frame_ref.py`. Tách như vậy thì contract import-linter "Kernel chỉ phụ thuộc domain" (cấm `multiprocessing` trong kernel — xem Step 01) vẫn **KEPT**. Đây là điểm khác biệt quan trọng so với các bản nháp cũ từng đặt nhầm cả transport vào `kernel/`.

> ⚠️ **Step rủi ro nhất + lưu ý đa nền tảng (ĐỌC TRƯỚC KHI GÕ):**
> - **Windows vs Linux/macOS**: `multiprocessing.shared_memory` hành xử khác nhau. Trên
>   Windows, segment SHM được **giải phóng khi process tạo ra nó thoát** (gắn vào lifetime
>   của handle); trên Linux/macOS segment tồn tại tới khi `unlink()`. Hệ quả: **creator
>   (parent) phải còn sống** trong suốt thời gian child đọc/ghi. Test mẫu spawn writer ở
>   subprocess + đọc ở parent → parent là creator nên OK; nhưng nếu bạn đảo lại (creator là
>   child rồi child thoát) thì trên Windows segment biến mất → reader lỗi.
> - **`resource_tracker` warning**: CPython hay in cảnh báo `leaked shared_memory objects to
>   clean up at shutdown` (cả Linux lẫn Windows) — đây là [vấn đề đã biết của CPython], thường
>   **vô hại** nếu `cleanup_all()` đã `close()`+`unlink()` đúng. Đừng hoảng; xác minh segment
>   đã được unlink là đủ.
> - **Verify trên MÁY BẠN**: con số "13 test pass, 1.63s" là kỳ vọng (đo trên môi trường tác
>   giả). Tự chạy `pytest tests/test_step_05_shm.py -v` và **đọc kết quả thật** — không tin số
>   có sẵn (đặc biệt vì máy bạn có thể là Windows + Python khác bản).

---

## Recap Module 02

- **File 03 (Bulkhead)**: mỗi camera = 1 process. Crash isolation. Cost spawn ~100ms, IPC qua SHM/ZMQ.
- **File 05 (Immutability)**: frame ndarray cross-process cần `setflags(write=False)` + ABA prevention via generation counter.

---

## Phần 1 — Kiến trúc SHM (15 phút)

### Vì sao SHM thay vì ZMQ cho frame?

| Mechanism | Cost cho 1 frame 1080p (~6MB) | Khi nào dùng |
|-----------|-------------------------------|--------------|
| **`pickle` qua `multiprocessing.Queue`** | ~10ms | Tránh — quá chậm |
| **ZMQ msgpack** | ~10ms | Tránh cho frame; OK cho metadata |
| **`shared_memory`** | ~5µs (memcpy) | **Frame bus** |

→ SHM là **mandatory** cho real-time multi-camera. ZMQ chỉ cho **request/response correlation** (Step 06).

### Slot lifecycle

Ring buffer với N slot. Mỗi slot có 5 state:

```
        ┌────────────────────────────────┐
        │           Lifecycle            │
        ├────────────────────────────────┤
        │  FREE → WRITING → READY        │
        │            ↓        ↓          │
        │       (writer)  (read pinned)  │
        │            ↓        ↓          │
        │       (commit)   READING       │
        │            ↓        ↓          │
        │         READY ←─ DONE          │
        │   (next reader   (recyclable   │
        │    or recycle)   for writer)   │
        └────────────────────────────────┘
```

- **FREE**: chưa được dùng. Writer có thể write.
- **WRITING**: writer đang ghi data (data SHM segment).
- **READY**: data sẵn sàng đọc.
- **READING**: reader đang copy data ra.
- **DONE**: read xong. Slot có thể recycle (writer reuse).

### Generation counter — ABA prevention

Slot 0 reuse nhiều lần:
- t=0: write → slot 0 gen=1
- t=1: reader đọc gen=1 → DONE
- t=2: writer reuse → slot 0 gen=2 (data khác)
- t=3: reader CŨ vẫn cầm `(slot=0, gen=1)` → đọc → ABA bug

→ Generation counter monotonic increase. Reader check `actual_gen == expected_gen` trước khi trust data.

### Per-slot lock — thread/process safe

`multiprocessing.Lock` mỗi slot. Header struct `<IQQ` (state + gen + pid) read/write under lock atomic.

Lưu ý: **Vision Platform production** dùng `SlotState.QUARANTINED` cross-process sentinel + lock-free header peek (R5-CRITICAL-01) cho mutex poisoning. **vision_demo simplified** — không có quarantine, lock acquire có timeout 2s rồi return None nếu poisoned.

---

## Phần 2 — Build `ShmRingBuffer` (45 phút)

Tạo `src/vision_demo/runtime/ipc/shm_frame_ring.py`:

```python
"""SHM frame ring buffer cho multi-process frame transport.

Layer: runtime/ipc — đây là TRANSPORT (I/O concern), không phải DTO. Vì vậy
nó nằm ở runtime/, KHÔNG ở kernel/ (kernel cấm import multiprocessing).
DTO mô tả frame (`ShmFrameRefData`) ở kernel/shm_frame_ref.py và được import
vào đây.

Model:
- N slots, mỗi slot có metadata (state, generation) + data buffer.
- Writer (camera process) write frame vào slot FREE/DONE.
- Reader (inference/consumer process) read frame qua expected_gen check.
- Per-slot multiprocessing.Lock cho serialization.

Simplified vs production (Vision_platform_architecture_design):
- Không có lease deadlines (writer/reader timeout).
- Không có QUARANTINED state (R5-CRITICAL-01).
- Không có reader_count multi-reader pinning.
- Đủ để học pattern. Vị trí layer (runtime/ipc) thì GIỐNG production.
"""
from __future__ import annotations
import multiprocessing as mp
import struct
from enum import IntEnum
from multiprocessing import shared_memory
from typing import Optional
import numpy as np

from vision_demo.kernel.shm_frame_ref import ShmFrameRefData


class SlotState(IntEnum):
    FREE = 0       # Available for write
    WRITING = 1    # Writer holding, in-progress
    READY = 2      # Ready to read
    READING = 3    # Reader holding, in-progress
    DONE = 4       # Read complete, recyclable


# Header: <I (state) Q (generation) Q (writer_pid)
HEADER_FMT = "<IQQ"
HEADER_PACK_SIZE = struct.calcsize(HEADER_FMT)
SLOT_HEADER_BYTES = 32   # padded for cache-line alignment
```

**Decisions giải thích**:

- **`IntEnum` thay `Enum`**: state value pack vào struct → cần int. `IntEnum` cho phép vừa enum vừa int.
- **`HEADER_FMT = "<IQQ"`**: little-endian, unsigned int (4 bytes) + 2 unsigned long long (8 bytes each) = 20 bytes. Pad to 32 cho cache-line align (avoid false sharing with adjacent slots).
- **`SLOT_HEADER_BYTES = 32` riêng** vs `HEADER_PACK_SIZE`: nếu thêm field tương lai, không cần realloc.

Tiếp theo, tạo **DTO ở kernel** — `src/vision_demo/kernel/shm_frame_ref.py`:

```python
"""ShmFrameRefData — DTO mô tả 1 frame nằm trong SHM ring.

Layer: kernel — đây là DỮ LIỆU THUẦN (không import multiprocessing/shared_memory).
Transport thật (ShmRingBuffer/Writer/Reader) ở runtime/ipc/shm_frame_ring.py.

Reader dùng (slot, generation) để lookup + verify slot chưa bị ghi đè.
DTO này có thể đi qua wire (ZMQ msgpack) hoặc gắn vào MediaPacket.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ShmFrameRefData:
    """Pure data carried by MediaPacket pointing to SHM slot."""
    ring_name: str        # ShmRingBuffer.name
    slot: int             # slot index
    generation: int       # ABA-prevention counter
    height: int
    width: int
    channels: int
```

→ Đây là **dữ liệu** describing 1 frame trong SHM. Pass qua wire (ZMQ msgpack) hoặc qua MediaPacket. Vì không import `multiprocessing`, nó hợp lệ ở `kernel/` (import-linter contract KEPT). `runtime/ipc/shm_frame_ring.py` import DTO này.

Class `ShmRingBuffer`:

```python
class ShmRingBuffer:
    """Per-slot lock variant SHM ring buffer.
    
    Architecture:
        Each slot = (meta SHM, data SHM) pair + 1 multiprocessing.Lock.
        Locks are passed cross-process via Process(args=...).
    
    Lifecycle:
        - Parent (creator) calls __init__(create=True).
        - Child processes call __init__(create=False, slot_locks=parent.slot_locks_for_children).
        - cleanup_all() unlinks all SHM segments. Parent only.
    """
    
    def __init__(
        self,
        name: str,
        n_slots: int,
        height: int,
        width: int,
        channels: int = 3,
        *,
        create: bool,
        slot_locks: Optional[list[mp.synchronize.Lock]] = None,
    ):
        self.name = name
        self.n_slots = n_slots
        self.height = height
        self.width = width
        self.channels = channels
        self._frame_bytes = height * width * channels  # uint8
        self._meta_shms: list[shared_memory.SharedMemory] = []
        self._data_shms: list[shared_memory.SharedMemory] = []
        
        # Locks: parent creates, children receive via args.
        if slot_locks is not None:
            if len(slot_locks) != n_slots:
                raise ValueError(
                    f"slot_locks length {len(slot_locks)} != n_slots {n_slots}"
                )
            self._slot_locks = slot_locks
        elif create:
            self._slot_locks = [mp.Lock() for _ in range(n_slots)]
        else:
            raise RuntimeError(
                "create=False requires slot_locks from parent process."
            )
        
        # Allocate (or attach to) SHM segments.
        for i in range(n_slots):
            meta_name = f"{name}_meta_{i}"
            data_name = f"{name}_data_{i}"
            if create:
                meta = shared_memory.SharedMemory(
                    name=meta_name, create=True, size=SLOT_HEADER_BYTES,
                )
                data = shared_memory.SharedMemory(
                    name=data_name, create=True, size=self._frame_bytes,
                )
                # Initialize header to FREE state, gen=0.
                struct.pack_into(HEADER_FMT, meta.buf, 0, SlotState.FREE, 0, 0)
            else:
                meta = shared_memory.SharedMemory(name=meta_name)
                data = shared_memory.SharedMemory(name=data_name)
            self._meta_shms.append(meta)
            self._data_shms.append(data)
    
    def slot_lock(self, slot_idx: int) -> mp.synchronize.Lock:
        return self._slot_locks[slot_idx]
    
    @property
    def slot_locks_for_children(self) -> list[mp.synchronize.Lock]:
        return self._slot_locks
    
    def cleanup_all(self) -> None:
        """Close + unlink all SHM segments. Call from creator process only."""
        for shm in self._meta_shms + self._data_shms:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self._meta_shms.clear()
        self._data_shms.clear()
```

**Decisions cốt lõi**:

### Lock-passing across process

```python
# Parent process:
ring = ShmRingBuffer(name="cam1", n_slots=4, ..., create=True)
# ring._slot_locks = [mp.Lock(), mp.Lock(), ...]

# Spawn child:
proc = mp.Process(
    target=worker,
    args=(ring.name, 4, ..., ring.slot_locks_for_children),  # ← pass locks
)

# Child process (in worker):
ring_attach = ShmRingBuffer(
    name="cam1", n_slots=4, ..., create=False,
    slot_locks=parent_locks,   # ← receive
)
```

→ `multiprocessing.Lock` được **pickle-able** when used in `args=...`. Python ducks this magic via `multiprocessing.synchronize` shared OS semaphore.

→ KHÔNG được làm `child._slot_locks = [mp.Lock() for _ in range(n)]` — sẽ tạo lock LOCAL in child process, không share với parent. **Race condition nguy hiểm**.

### `create=True` vs `create=False`

- **Parent**: `create=True` → calls `shared_memory.SharedMemory(create=True)` → allocate OS segment.
- **Child**: `create=False` → `shared_memory.SharedMemory(name=...)` (không có create) → **attach** existing segment by name.

Gọi `create=False` mà không pass `slot_locks` → raise — vì child không có cách tự tạo lock share với parent.

---

## Phần 3 — Build `ShmFrameWriter` + `ShmFrameReader` (60 phút)

```python
class ShmFrameWriter:
    """Camera-side SHM writer.
    
    Strategy: round-robin slot scan, write to first FREE/DONE slot.
    NEVER overwrites READY (would silently drop).
    """
    
    _LOCK_TIMEOUT_S = 2.0
    
    def __init__(self, ring: ShmRingBuffer):
        self._ring = ring
        self._next_slot = 0
        self._next_generation = 1
        self._pid = mp.current_process().pid or 0
    
    def write(self, frame: np.ndarray) -> Optional[ShmFrameRefData]:
        """Write frame to next available slot.
        
        Returns ShmFrameRefData on success, None if all slots busy.
        """
        if frame.shape != (self._ring.height, self._ring.width, self._ring.channels):
            raise ValueError(
                f"Frame shape mismatch: got {frame.shape}, "
                f"expected ({self._ring.height}, {self._ring.width}, {self._ring.channels})"
            )
        
        for attempt in range(self._ring.n_slots):
            slot_idx = (self._next_slot + attempt) % self._ring.n_slots
            lock = self._ring.slot_lock(slot_idx)
            
            if not lock.acquire(timeout=self._LOCK_TIMEOUT_S):
                continue   # poisoned lock — skip slot
            
            try:
                state, gen, _pid = struct.unpack_from(
                    HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
                )
                
                # Available: FREE or DONE. NOT READY (would drop).
                if state not in (SlotState.FREE, SlotState.DONE):
                    continue
                
                # Mark WRITING.
                new_gen = self._next_generation
                self._next_generation += 1
                struct.pack_into(
                    HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
                    SlotState.WRITING, new_gen, self._pid,
                )
            finally:
                lock.release()
            
            # Write data outside lock — slot is in WRITING, no one else touches.
            arr = np.ndarray(
                (self._ring.height, self._ring.width, self._ring.channels),
                dtype=np.uint8,
                buffer=self._ring._data_shms[slot_idx].buf,
            )
            np.copyto(arr, frame)
            
            # Commit READY.
            if not lock.acquire(timeout=self._LOCK_TIMEOUT_S):
                return None
            try:
                struct.pack_into(
                    HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
                    SlotState.READY, new_gen, self._pid,
                )
            finally:
                lock.release()
            
            self._next_slot = (slot_idx + 1) % self._ring.n_slots
            return ShmFrameRefData(
                ring_name=self._ring.name,
                slot=slot_idx,
                generation=new_gen,
                height=self._ring.height,
                width=self._ring.width,
                channels=self._ring.channels,
            )
        
        return None  # all slots busy → caller backpressures
```

### Quan sát quan trọng

**Write data OUTSIDE lock**:
```python
# Lock acquire → check state → mark WRITING → release lock
# Write 6MB data outside lock (no other writer can touch — slot WRITING)
# Lock acquire → mark READY → release lock
```

→ Lock chỉ cần protect **state transitions**, không protect data write. Data write 6MB ~5µs — quá lâu để giữ lock. Tách 2 critical sections + outside-lock data write = **giảm contention**.

→ Trade-off: nếu writer crash giữa "data write" và "commit READY", slot stuck WRITING. Reader gen check → mismatch → return None (graceful skip). Vision Platform có **lease timeout** detect crashed writer; vision_demo skip cho gọn.

**`for attempt in range(n_slots)`**:

Round-robin scan. Nếu slot 0 READY (chưa đọc), thử slot 1, 2, 3. Đảm bảo **không evict** READY frame.

Reader code:

```python
class ShmFrameReader:
    """Reader side: pin slot, copy frame, mark DONE."""
    
    _LOCK_TIMEOUT_S = 2.0
    
    def __init__(self, ring: ShmRingBuffer):
        self._ring = ring
    
    def read(self, slot_idx: int, expected_gen: int) -> Optional[np.ndarray]:
        """Read slot if (state==READY and generation==expected_gen).
        
        Returns frame copy. Returns None if generation mismatched (slot
        overwritten) or slot not in READY state.
        """
        lock = self._ring.slot_lock(slot_idx)
        
        # Pin: verify generation, mark READING.
        if not lock.acquire(timeout=self._LOCK_TIMEOUT_S):
            return None
        try:
            state, gen, _pid = struct.unpack_from(
                HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
            )
            if gen != expected_gen or state != SlotState.READY:
                return None
            struct.pack_into(
                HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
                SlotState.READING, gen, _pid,
            )
        finally:
            lock.release()
        
        # Copy out.
        arr = np.ndarray(
            (self._ring.height, self._ring.width, self._ring.channels),
            dtype=np.uint8,
            buffer=self._ring._data_shms[slot_idx].buf,
        )
        frame_copy = arr.copy()
        
        # Release: mark DONE if generation still matches.
        if not lock.acquire(timeout=self._LOCK_TIMEOUT_S):
            return frame_copy
        try:
            state, gen, _pid = struct.unpack_from(
                HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
            )
            if gen == expected_gen:
                struct.pack_into(
                    HEADER_FMT, self._ring._meta_shms[slot_idx].buf, 0,
                    SlotState.DONE, gen, _pid,
                )
        finally:
            lock.release()
        
        return frame_copy
```

### Frame copy out OUTSIDE lock

Same idea as writer. State transition → state set READING → copy 6MB outside lock → state DONE.

### `arr.copy()` — defensive

Pattern critical: copy frame to caller's process memory **trước khi** mark DONE. Nếu không copy:
- Mark DONE → writer reuse slot ngay → caller's `arr` view → corrupted data.

→ Copy-then-release. Cost ~5µs/copy. Đáng.

---

## Phần 4 — Tests (60 phút)

Tạo `tests/test_step_05_shm.py` với **13 test** bao gồm:

1. **Basic ring lifecycle** (3): N segments allocated, FREE state initial, cleanup idempotent.
2. **Writer** (4): writes to first FREE, round-robin, returns None when all busy, rejects wrong shape.
3. **Reader** (3): reads after write, None for wrong gen, None for FREE slot.
4. **Recycle + ABA** (2): writer recycles DONE, ABA prevention test.
5. **Multi-process integration** (1): writer in subprocess, reader in parent.

Code mẫu đầy đủ của 13 test in ngay trong step này — gõ theo và verify **cá nhân** từng test (đặt vào `tests/test_step_05_shm.py` trong workspace của bạn).

Test ABA quan trọng:

```python
def test_aba_prevention_old_ref_cannot_read_new_data(ring):
    """Slot recycled. Old ref must NOT read new data."""
    writer = ShmFrameWriter(ring)
    reader = ShmFrameReader(ring)
    
    f1 = np.full((10, 10, 3), 11, dtype=np.uint8)
    ref_old = writer.write(f1)   # gen=1
    
    # Reader with ref_old reads + marks DONE.
    out_old = reader.read(ref_old.slot, ref_old.generation)
    assert np.array_equal(out_old, f1)
    
    # Fill rest of slots first to force reuse of slot 0.
    for v in [2, 3, 4]:
        writer.write(np.full((10, 10, 3), v, dtype=np.uint8))
    f_new = np.full((10, 10, 3), 99, dtype=np.uint8)
    ref_new = writer.write(f_new)
    
    # Both refs may point to same slot.
    assert ref_new.slot == ref_old.slot
    assert ref_new.generation > ref_old.generation
    
    # Old ref reads → None (generation mismatch — ABA prevented).
    out_stale = reader.read(ref_old.slot, ref_old.generation)
    assert out_stale is None
    
    # New ref reads → new data.
    out_new = reader.read(ref_new.slot, ref_new.generation)
    assert np.array_equal(out_new, f_new)
```

Cross-process test:

```python
def _camera_worker_with_queue(ring_name, n_slots, height, width, channels,
                              slot_locks, n_frames, sentinel_value, queue):
    """Worker process: writes N frames with sentinel values."""
    # Re-attach to ring (don't create).
    ring = ShmRingBuffer(
        name=ring_name, n_slots=n_slots, height=height, width=width,
        channels=channels, create=False, slot_locks=slot_locks,
    )
    writer = ShmFrameWriter(ring)
    refs = []
    for i in range(n_frames):
        frame = np.full((height, width, channels), i + sentinel_value, dtype=np.uint8)
        ref = writer.write(frame)
        if ref is None:
            break
        refs.append((ref.slot, ref.generation))
    queue.put(refs)


def test_writer_in_subprocess_reader_in_parent():
    """Validate cross-process SHM."""
    name = f"test_xproc_{mp.current_process().pid}"
    ring = ShmRingBuffer(
        name=name, n_slots=4, height=8, width=8, channels=3, create=True,
    )
    
    queue: mp.Queue = mp.Queue()
    
    proc = mp.Process(
        target=_camera_worker_with_queue,
        args=(name, 4, 8, 8, 3, ring.slot_locks_for_children, 4, 100, queue),
    )
    proc.start()
    proc.join(timeout=5)
    assert proc.exitcode == 0
    
    refs = queue.get(timeout=2)
    assert len(refs) == 4
    
    # Read in parent process.
    reader = ShmFrameReader(ring)
    for i, (slot, gen) in enumerate(refs):
        frame = reader.read(slot, gen)
        assert frame is not None, f"Frame {i} not readable"
        assert frame[0, 0, 0] == i + 100
    
    ring.cleanup_all()
```

→ **Đây là test thực sự**: spawn subprocess, share lock, write trong subprocess, read trong parent. **Chứng minh** SHM cross-process work.

**Run**:
```bash
pytest tests/test_step_05_shm.py -v
```

Expected: **13 passed in ~1.6s**.

---

## Self-check

1. **Tại sao ngôn ngữ "ABA prevention"** — list 1 scenario lỗi nếu không có generation counter.

2. **`mp.Lock()` được pickle khi pass vào `Process(args=...)`** — cơ chế gì làm nó share giữa process?

3. **Test cross-process pass slot_locks vào worker** — nếu pass `slot_locks=None` thay vì truyền parent locks, **bug gì xảy ra**?

4. **Writer write data ngoài lock**: làm gì khi 2 writer cùng đụng vào slot 0 (race)?

5. **`SlotState.READY` vs `READING` vs `DONE`** — sao cần 3 state? Có thể gộp `DONE = FREE` được không?

<details>
<summary>Đáp án</summary>

1. **ABA scenario without generation**:
   - t=0: writer ghi vào slot 0, reader nhận ref `(slot=0)`.
   - t=1: reader chậm (network blip), chưa đọc.
   - t=2: writer reuse slot 0 (giả sử FREE state set lại), data MỚI khác.
   - t=3: reader đọc `slot=0` → nhận data MỚI nhưng tưởng là data CŨ (timestamp/correlation cũ).
   - **Bug**: detection được áp dụng cho frame sai. Tracking ID mix-up.
   
   Generation counter giải quyết: ref carrying gen=1, slot bây giờ gen=2 → reader detect mismatch → return None. **Frame skipped** (better than wrong frame).

2. **`multiprocessing.Lock` cross-process**:
   - Implementation Python: `multiprocessing.synchronize.Lock` wrap **POSIX semaphore** (Linux/Mac) hoặc **Windows event/mutex** (Windows).
   - OS semaphore là **kernel object**, không phải user-space struct. Có **handle** (file descriptor on Linux).
   - Khi pickle Lock → pickle handle (số int hệ kernel).
   - Khi child unpickle → re-attach handle → cùng kernel object.
   - **Lock acquire/release** là syscall vào kernel → atomic across all processes share handle.
   
   → Pickle Lock **không pickle "data"**. Pickle pointer/reference đến kernel object. Kernel object là **single source of truth** giữa processes.

3. **Bug nếu `slot_locks=None`**:
   - Child process raise `RuntimeError("create=False requires slot_locks")` — code mình defensive.
   - Nếu remove safeguard: child tự `mp.Lock()` → tạo lock LOCAL trong child.
   - Parent lock vs child lock = 2 lock khác nhau cùng vị trí.
   - 2 process write cùng lúc → **race**, header corruption, undefined behavior.

4. **2 writer race trên slot 0**:
   - Writer A acquire lock → check state FREE → set WRITING_A, gen=10 → release lock.
   - Writer B acquire lock → check state WRITING (not FREE/DONE) → continue to slot 1.
   - **Lock-free data write** an toàn vì only writer A is "owner" (state=WRITING_A).
   - Writer A finish → re-acquire lock → set READY.
   
   → 2 writer **không bao giờ write cùng data buffer** vì check state under lock first. Lock-free data write OK.

5. **Tại sao 5 state**:
   - **FREE vs DONE**: Logical phân biệt — FREE = chưa từng dùng (gen=0), DONE = từng READY (gen>0). Cleanup logic + metric khác nhau.
   - Có thể **technical** gộp DONE → FREE sau read xong (gen vẫn tăng → no ABA). Nhưng:
     - Lose information: "slot này đã bao giờ chứa frame chưa?"
     - Vision Platform `force_write` (DROP_OLDEST policy) cần phân biệt "evict from READY" vs "use FREE/DONE" — nếu gộp, evict logic phức tạp hơn.
   - **READY vs READING**: critical phân biệt. READING = reader đang copy frame. Writer KHÔNG được reuse (data corrupted nếu copy đang pending). 
   - vision_demo simplified: chỉ 1 reader → READING → DONE đơn giản. Vision Platform multi-reader: `reader_count` đếm pin.
   
   → **5 state phù hợp** với complexity. Gộp = giảm 1 case nhưng tăng coupling logic.

</details>

---

## Liên kết

- **Module 02 file 03** (Bulkhead): tại sao multi-process.
- **Module 02 file 05** (Immutability): generation counter là kỹ thuật immutability cho mutable shared memory.
- **Production**: `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-*.md`, `03-shm-frame-bus-*.md`.

---

## Tóm tắt 1 câu

> **SHM ring buffer N slot, mỗi slot có header struct (state + generation + pid) + data buffer + lock. Writer round-robin scan FREE/DONE → WRITING → READY. Reader generation match → READING → copy → DONE. ABA prevent qua gen counter. Cross-process via lock pass trong `Process(args=...)`.**

➡️ Tiếp theo: [`step-06-add-inference.md`](step-06-add-inference.md)
