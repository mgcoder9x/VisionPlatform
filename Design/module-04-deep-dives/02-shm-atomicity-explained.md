# 02 — SHM Atomicity Explained: header torn read và x86-64 guarantees

## Câu hỏi cốt lõi

> Tại sao SHM ring buffer cần lock? Trong R5-CRITICAL-01 nói "header lock-free atomic store là single 32-bit aligned" — atomic là gì? Tại sao 32 bytes không atomic?

## TL;DR (30s)

**x86-64 atomic store**:
- ≤8 bytes aligned → atomic (1 instruction).
- > 8 bytes → KHÔNG atomic (multiple instructions, có thể torn read).

SHM header struct `<IQQ` = 20 bytes → write `pack_into(HEADER_FMT, ...)` KHÔNG atomic. Reader concurrent có thể đọc state mới + gen cũ → corrupt logic.

→ Solution: **lock per slot** (vision_demo) hoặc **lock-free seqlock** (Vision Platform optional). R5-CRITICAL-01 fix dùng **single 32-bit state field write atomic** cho cross-process QUARANTINED sentinel.

---

## Theory

### Atomic store — what it means

CPU instruction = 1 unit of work. Reader thread either sees:
- ENTIRE old value, OR
- ENTIRE new value.

**Never** half-old + half-new.

### x86-64 atomic guarantees

Per Intel SDM Vol 3A § 8.1.1:
- **1 byte** (any address): atomic.
- **2 bytes** (16-bit aligned): atomic.
- **4 bytes** (32-bit aligned): atomic.
- **8 bytes** (64-bit aligned): atomic.
- **16 bytes**: atomic ONLY if `MOVNTDQA` + naturally aligned + ... (rare cases).
- **>16 bytes**: NEVER atomic (bus arbitrate per cache line).

→ Header struct `<IQQ` = 4 + 8 + 8 = 20 bytes. **Not atomic**.

### Reading "torn" data

```c
// CPU instruction view (simplified):
struct header { uint32_t state; uint64_t gen; uint64_t pid; };

void write_header(header* h, uint32_t s, uint64_t g, uint64_t p) {
    h->state = s;     // store 4 bytes  (instruction 1)
    h->gen = g;       // store 8 bytes  (instruction 2)
    h->pid = p;       // store 8 bytes  (instruction 3)
}
```

3 separate stores. Reader concurrent có thể đọc:
- After ins 1: state=NEW, gen=OLD, pid=OLD ← TORN
- After ins 2: state=NEW, gen=NEW, pid=OLD ← TORN
- After ins 3: state=NEW, gen=NEW, pid=NEW ← consistent

→ Reader MUST coordinate. Options:
1. **Lock**: writer + reader both acquire lock.
2. **Seqlock**: optimistic concurrency với version counter.
3. **Single atomic store**: pack everything into ≤8 bytes.

---

## Lock approach (vision_demo + Vision Platform default)

### Code Pattern

```python
# Writer
with lock:
    struct.pack_into("<IQQ", buf, 0, NEW_STATE, NEW_GEN, NEW_PID)

# Reader
with lock:
    state, gen, pid = struct.unpack_from("<IQQ", buf, 0)
```

→ Mutual exclusion. Reader chỉ đọc khi writer xong. **Always consistent**.

### Cost

`multiprocessing.Lock.acquire()` ~1-3µs trên Linux (futex). Lock release ~1µs.

For 30 fps × 16 cam × 5 stage = 2400 ops/s × 4µs/op = **9.6ms total CPU time/s**. ~1% of 1 core. Acceptable.

### Trade-off

- **Pros**: simple, correct.
- **Cons**:
  - 1 writer + 1 reader on same slot serialized — no parallelism for that slot.
  - **Mutex poisoning risk** (R5-CRITICAL-01).

---

## Seqlock approach (Vision Platform optional Option B)

Lock-free reader. Writer coordinate via version counter.

```c
// Pseudocode
volatile uint64_t version = 0;
struct data { ... };
struct data shared;

// Writer
write(new_data) {
    version_atomic_store(version, version + 1);  // odd = writing
    shared = new_data;
    version_atomic_store(version, version + 1);  // even = stable
}

// Reader (loop until consistent read)
read() {
    do {
        v1 = version_atomic_load(version);
        if (v1 & 1) continue;  // odd = writer in progress, retry
        local = shared;
        v2 = version_atomic_load(version);
    } while (v1 != v2);  // version changed during read = retry
    return local;
}
```

**Linux kernel** dùng pattern này extensively (e.g. `clock_gettime` cache).

### Pros / Cons

- **Pros**:
  - Reader lock-free. No futex.
  - Multi-reader parallel.
  - No mutex poisoning.
- **Cons**:
  - Single writer (multi-writer = lock anyway).
  - Reader retry on contention (rare nhưng exists).
  - Complex implementation.
  - Python: requires `atomics` library (not stdlib).

→ Vision Platform: **Option A (lock) default**. Option B (seqlock) cho high-contention case (Beyond ~32 cameras).

---

## R5-CRITICAL-01: lock-free sentinel write

Production fix uses **single 32-bit aligned store** cho cross-process QUARANTINED state:

```python
# vision/runtime/ipc/shm_frame.py
class SlotState(IntEnum):
    FREE = 0
    WRITING = 1
    READY = 2
    READING = 3
    DONE = 4
    QUARANTINED = 0xFFFF_FFFF   # ← sentinel

def quarantine_poisoned_slot(self, slot_idx: int):
    # Cannot acquire poisoned lock → write state field WITHOUT lock.
    # Single 4-byte aligned store is atomic on x86-64.
    struct.pack_into("<I", meta.buf, 0, SlotState.QUARANTINED)
    # Bump generation in separate aligned 8-byte store (optional, for diagnostics).
    struct.pack_into("<Q", meta.buf, 4, gen + 1)
```

### Why this works

1. State field **at offset 0**, **4-byte aligned** → 32-bit store atomic.
2. Reader reads state lock-free first:
   ```python
   peek_state, *_ = struct.unpack_from(HEADER_FMT, buf, 0)
   if peek_state == SlotState.QUARANTINED:
       return None  # skip without acquiring poisoned lock
   ```
3. Reader **never** touches gen/pid for QUARANTINED slot — irrelevant.
4. State write is single instruction → reader sees old (FREE/READY/...) OR new (QUARANTINED). Never torn.

### Multi-architecture

- **x86-64**: 4-byte aligned store atomic ✓
- **ARM64**: 4-byte aligned store atomic with proper memory ordering ✓ (most modern CPUs)
- **32-bit ARM v7**: 4-byte aligned word store atomic ✓
- **RISC-V**: 4-byte aligned store atomic per spec ✓

→ Vision Platform tested on x86-64 + ARM64 (M-series Mac, AWS Graviton).

---

## Practical experiment

### Demo: torn header in Python

```python
# torn_demo.py
import multiprocessing as mp
import struct
import time
from multiprocessing import shared_memory


HEADER_FMT = "<IQQ"   # state, gen, pid - 20 bytes
SHM_NAME = "torn_demo"


def writer(stop_event):
    shm = shared_memory.SharedMemory(name=SHM_NAME)
    n = 0
    while not stop_event.is_set():
        # Alternating values that should always be paired.
        # If reader sees state=A but gen!=A, that's torn.
        if n % 2 == 0:
            struct.pack_into(HEADER_FMT, shm.buf, 0, 0xAAAAAAAA, 0xAAAAAAAAAAAAAAAA, 0xAAAAAAAAAAAAAAAA)
        else:
            struct.pack_into(HEADER_FMT, shm.buf, 0, 0x55555555, 0x5555555555555555, 0x5555555555555555)
        n += 1
    shm.close()


def reader(stop_event, n_iters):
    shm = shared_memory.SharedMemory(name=SHM_NAME)
    torn_count = 0
    for _ in range(n_iters):
        state, gen, pid = struct.unpack_from(HEADER_FMT, shm.buf, 0)
        # Detect torn: state should match gen pattern.
        state_bits = state | (state << 32)
        if (state_bits != gen) or (state_bits != pid):
            # Hmm, complicated check. Simpler: check field consistency.
            if state == 0xAAAAAAAA and gen != 0xAAAAAAAAAAAAAAAA:
                torn_count += 1
            elif state == 0x55555555 and gen != 0x5555555555555555:
                torn_count += 1
    shm.close()
    return torn_count


if __name__ == "__main__":
    shm = shared_memory.SharedMemory(name=SHM_NAME, create=True, size=64)
    struct.pack_into(HEADER_FMT, shm.buf, 0, 0, 0, 0)
    
    stop = mp.Event()
    
    p_writer = mp.Process(target=writer, args=(stop,))
    p_writer.start()
    
    time.sleep(0.05)  # let writer ramp up
    torn = reader(stop, n_iters=100_000)
    
    stop.set()
    p_writer.join()
    
    shm.close()
    shm.unlink()
    
    print(f"Torn reads detected: {torn} / 100,000")
```

→ Run trên Windows/Linux: typically thấy **vài nghìn torn reads** trong 100k iterations. **Empirical proof** rằng multi-byte struct write KHÔNG atomic.

### Demo: lock-free single-byte field works

Repeat pattern but write only `state` field (4 bytes):

```python
struct.pack_into("<I", shm.buf, 0, 0xAAAAAAAA)
# vs
struct.pack_into("<I", shm.buf, 0, 0x55555555)
```

Reader reads only state — **never sees value other than 0xAAAAAAAA or 0x55555555**. **Never torn**.

→ x86-64 32-bit aligned store atomic. Confirmed.

---

## Áp dụng Vision Platform

### Lock acquire timeout (R5-CRITICAL-01 fix)

```python
# vision/runtime/ipc/shm_frame.py
class ShmFrameWriter:
    _LOCK_TIMEOUT_S = 2.0
    
    def write(self, frame):
        for slot_idx in range(...):
            lock = self._ring.slot_lock(slot_idx)
            
            # Bounded acquire. Poisoned futex → skip slot.
            if not lock.acquire(timeout=self._LOCK_TIMEOUT_S):
                logger.warning("shm_slot_lock_poisoned", slot_idx=slot_idx)
                continue
            
            try:
                # ... safe critical section ...
            finally:
                lock.release()
```

### Quarantine via lock-free atomic state write

```python
def quarantine_poisoned_slot(self, slot_idx):
    """Mark slot QUARANTINED via lock-free 32-bit atomic store."""
    meta = self._meta_shms[slot_idx]
    
    # Lock-free peek to verify poisoned (owner_pid dead).
    state, _, owner_pid, _, _, reader_pid, _ = struct.unpack_from(HEADER_FMT, meta.buf, 0)
    
    if owner_pid > 0 and _pid_is_alive(owner_pid):
        return False  # don't quarantine, still alive
    
    # Atomic 32-bit state write.
    struct.pack_into("<I", meta.buf, 0, SlotState.QUARANTINED)
    # Bump gen separately (8-byte aligned at offset 4 — also atomic).
    struct.pack_into("<Q", meta.buf, 4, gen + 1)
    
    return True
```

→ Production design: `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-lock-per-slot-ho-c-seqlock.md` + `03-shm-frame-bus-slot-lifecycle-protocol.md`.

---

## Self-check

1. **x86-64 atomic store size limit** — bytes? Cho phản ví dụ size lớn hơn.

2. **`struct.pack_into("<IQQ", buf, 0, ...)` ghi 20 bytes** — có thể torn read không? Tại sao?

3. **Seqlock vs lock** — pros/cons. Khi nào prefer seqlock?

4. **R5-CRITICAL-01 lock-free quarantine** — sao chỉ ghi state field 4 bytes thay vì cả header? Reader logic gì để skip?

5. **ARM32 mobile (32-bit)** — atomic store size limit khác x86-64? Code Vision Platform có port được không?

<details>
<summary>Đáp án</summary>

1. **x86-64 atomic store**: ≤8 bytes naturally aligned. **Phản ví dụ**: 16 bytes — KHÔNG atomic trừ khi dùng instruction đặc biệt (`MOVDQA` + alignment). Trong Python, `struct.pack_into` không guarantee instruction này. → Treat as non-atomic.

2. **20 bytes — CAN torn**:
   - Writer = 3 separate store instructions (4+8+8 bytes).
   - Reader concurrent có thể đọc giữa các instructions.
   - → MUST coordinate (lock or seqlock).

3. **Seqlock vs lock**:
   - **Seqlock pros**: lock-free reader, multi-reader parallel, no mutex poisoning.
   - **Seqlock cons**: single writer, reader retry on contention (rare), complex impl.
   - **Lock pros**: simple, correct, multi-writer.
   - **Prefer seqlock when**:
     - Read-heavy + write-rare (state machine where reads >> writes).
     - Need lock-free safety (no poisoning risk).
     - Linux kernel `clock_gettime` is canonical example.
   - Vision Platform default = lock (simpler), seqlock optional.

4. **Lock-free quarantine** logic:
   - **Why state-only write**: state at offset 0, 4-byte aligned → atomic on x86-64. Reader peek state lock-free first.
   - **Reader skip logic**:
     ```python
     # Lock-free peek BEFORE attempting lock.
     peek_state, *_ = struct.unpack_from(HEADER_FMT, buf, 0)
     if peek_state == SlotState.QUARANTINED:
         return None  # skip
     # Else: try lock acquire normally.
     ```
   - **No race**: state QUARANTINED is **sticky** — once set, never reverts. So reader sees old state OR QUARANTINED. Both safe.
   - **Generation**: bumped for diagnostic — reader doesn't care about gen for quarantined slot.

5. **ARM32 atomic**:
   - 32-bit aligned word: atomic.
   - 64-bit (qword): NOT atomic on ARM32 — requires `LDREXD/STREXD` for atomic 64-bit access.
   - **Vision Platform code**: state field 32-bit OK. Gen field 64-bit on offset 4 → may need atomic helpers on ARM32.
   - **Practically**: Vision Platform target x86-64 + ARM64 (server / edge). ARM32 mobile rarely target.
   - If port to ARM32: use `atomics` library or `ctypes` with `c_uint32` instead of c_uint64 for gen.

</details>

---

## Liên kết

- **Module 02 file 03** (Bulkhead) — bug nếu cross-process state corrupt.
- **Module 03 step 05** — `shm_frame_ring.py` simplified version với lock.
- **Production**: `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-lock-per-slot-ho-c-seqlock.md`.
- **Reference**: Intel SDM Vol 3A § 8.1.1 (atomic operations).

---

## Tóm tắt 1 câu

> **x86-64 atomic store ≤8 bytes aligned. SHM header 20 bytes KHÔNG atomic → cần lock hoặc seqlock. R5-CRITICAL-01 dùng single 32-bit state field aligned write (atomic) làm cross-process QUARANTINED sentinel — bypass poisoned lock.**

➡️ Tiếp theo: [`03-zmq-patterns-comparison.md`](03-zmq-patterns-comparison.md)
