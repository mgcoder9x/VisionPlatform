# 01 — GIL Truth: tại sao Python multi-thread vô dụng cho CPU-bound

## Câu hỏi cốt lõi

> Tại sao Vision Platform mỗi camera 1 process thay vì 1 thread? Tại sao thread vẫn dùng được trong inference service?

## TL;DR (30s)

**Python GIL** = chỉ 1 thread chạy bytecode tại 1 thời điểm trong 1 process. Hệ quả:
- **CPU-bound**: thread KHÔNG scale. Tệ hơn serial vì context-switch overhead.
- **I/O-bound**: thread VẪN scale vì I/O syscall **release GIL**.
- **C extension** (NumPy, OpenCV, PyTorch): **release GIL** trong C code → thread scale **một phần**.

→ Vision Platform: process cho bulkhead + bypass GIL. Thread bên trong mỗi process cho I/O concurrency (ZMQ recv loop).

---

## Theory

### GIL là gì

Python (CPython) interpreter có **1 global lock** (Global Interpreter Lock). Mỗi thread phải **acquire GIL** trước khi chạy bytecode.

```
Thread A: acquire GIL → run 100 bytecodes → release GIL
Thread B: acquire GIL → run 100 bytecodes → release GIL
Thread A: acquire GIL → ...
```

→ 2 thread Python KHÔNG bao giờ chạy bytecode cùng lúc trong 1 process.

### Tại sao GIL tồn tại?

Reference counting + simplicity. Mỗi Python object có ref count. Mọi `obj.field = ...` cũng tăng/giảm ref count. Without GIL → race condition trên ref count → memory corruption.

→ GIL = "dirty hack" cho thread safety. Tồn tại 30 năm vì removing nó = rewrite CPython memory model (PEP 703 đang work nhưng chưa stable, dự kiến Python 3.13+ optional, 3.14 stable).

### Khi nào GIL release?

3 cases:
1. **I/O syscall**: `socket.recv`, `time.sleep`, `open(...)`. → release GIL while waiting kernel.
2. **C extension call**: numpy `arr.mean()`, OpenCV `cv2.resize`, PyTorch `tensor.cuda()` — implementations marked `Py_BEGIN_ALLOW_THREADS`. → release GIL while in C code.
3. **Periodic** (every ~5ms by default): voluntary release để fairness giữa threads.

→ I/O-bound + numpy-heavy code **scale** với thread vì >90% time GIL released.
→ Pure Python loop **không scale** vì 0% time release.

---

## Experiment thật

Tạo file `experiments/bench_gil.py` trong `vision_demo_workspace/`:

```python
def cpu_work(n_iters: int) -> int:
    """CPU-bound: pure Python loop."""
    s = 0
    for i in range(n_iters):
        s += i * i
    return s


def io_work(n_sleeps: int) -> int:
    """I/O-bound (giả lập): sleep N times."""
    for _ in range(n_sleeps):
        time.sleep(0.01)
    return n_sleeps
```

Chạy:

```bash
cd vision_demo_workspace
.venv\Scripts\python.exe experiments\bench_gil.py
```

### Real numbers (Python 3.11.9, 4 tasks, Windows)

> **Platform note**: Số liệu dưới đo trên **Windows** (`spawn` mode cho `multiprocessing`). Trên **Linux/macOS** dùng `fork` mode mặc định, **process spawn cost thấp hơn đáng kể** (~10-20ms vs ~50-100ms Windows). Hệ quả:
> - Trên Linux, `process: 0.89s` (CPU-bound) có thể giảm xuống ~0.80s — gần serial.
> - Trên Linux với task **lớn** (>5s/task), process scale tốt hơn Windows do spawn cost amortize.
> - Pattern **kết luận chính** vẫn đúng: thread không scale CPU-bound, scale I/O-bound; chỉ con số tuyệt đối khác giữa platforms.
>
> Verify trên máy bạn: tạo/chạy `experiments/bench_gil.py` trong `vision_demo_workspace/`. Số liệu sẽ phản ánh OS + CPU + Python version của bạn.

```
=== CPU-bound work (5M iter loop) × 4 tasks ===
  serial:   0.77s
  thread:   0.81s   (speedup vs serial: 0.94x)
  process:  0.89s   (speedup vs serial: 0.86x)

=== I/O-bound work (50 × 10ms sleep) × 4 tasks ===
  serial:   2.06s
  thread:   0.52s   (speedup vs serial: 4.01x)
  process:  1.02s   (speedup vs serial: 2.03x)
```

### Phân tích

#### CPU-bound: thread = serial (slightly slower)

`thread: 0.81s` vs `serial: 0.77s` — thread chậm hơn 5%.
- 4 thread chia GIL → mỗi thread effectively chạy 1/4 time.
- Total CPU time same = 4 × 0.77/4 = 0.77s.
- + Context-switch overhead (~5ms × N switches) = thêm ~0.04s.
- → 0.81s tổng. **Speedup 0.94x = thua serial**.

`process: 0.89s` chậm vì spawn cost (~50-100ms × 4) overshadow benefit cho task ngắn.

→ **Bài học**: với CPU-bound task **lớn** (>5s), process scale linearly. Task **nhỏ**, spawn cost > work cost → thread/process worthless.

#### I/O-bound: thread scale 4x

`serial: 2.06s` (4 × 50 × 10ms = 2s + overhead).
`thread: 0.52s` (4 thread parallel, each does 0.5s wait → max 0.5s).
- **Speedup ~4x** vì thread chạy **đồng thời** trong `time.sleep` (sleep release GIL).

`process: 1.02s` slower than thread vì process spawn overhead.

→ **Bài học**: I/O-bound thread **đỉnh**. Không spawn cost. Bypass GIL không cần process.

### Hệ quả thực tế cho Vision Platform

**Camera process** (mỗi camera 1 process):
- I/O-bound chính (RTSP read network, SHM write).
- + CPU-bound nhẹ (decode frame, color convert).
- Decode dùng FFmpeg/OpenCV C extension → **GIL released trong decode**.
- → Multi-process bulkhead chính thay vì performance.

**Inference service** (1 process):
- CPU-bound heavy (preprocess, postprocess Python).
- GPU compute (CUDA → C extension, GIL released).
- → 1 process. Multi-thread bên trong process cho ZMQ recv (I/O-bound).

**Sai lầm phổ biến**:
```python
# Tưởng tăng tốc detection bằng thread:
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(detect, frames))

# → KHÔNG nhanh hơn vì detect dùng GIL phần lớn time.
# → Process pool KHÔNG được vì share GPU + spawn cost.
# → Đúng: batch detection trong 1 thread (GPU làm parallel), batch frame queue.
```

---

## Khi nào thread vẫn tốt cho CPU-bound Python?

3 case:

### 1. NumPy/OpenCV-heavy code

```python
def preprocess(frame):
    return cv2.resize(frame, (640, 640))   # ← C code, GIL released

with ThreadPoolExecutor(max_workers=4) as ex:
    results = ex.map(preprocess, frames)  # ← scale ~3-4x
```

→ resize chạy trong C, release GIL. 4 thread = 4 cv2 thread parallel. **Đo cụ thể** dự án bạn — ratio C / Python varies.

### 2. PyTorch/CUDA on different streams

```python
def gpu_work(tensor):
    with torch.cuda.stream(...):
        return model(tensor)
```

→ GPU compute là async, GIL released. Multiple streams parallel.

### 3. Free-threaded Python (3.13+)

PEP 703 — Python 3.13 có **experimental no-GIL build**. 3.14+ planned default. Khi mature, thread sẽ scale như C++/Rust.

→ Vision Platform 2025 vẫn dùng GIL Python 3.11. Khi 3.14 stable + production-ready, có thể migrate.

---

## Áp dụng Vision Platform

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| Camera process | 1 OS process per camera | Bulkhead + GIL bypass |
| Inference service | 1 process, threads inside | GPU shared, ZMQ recv I/O |
| Event sink | Thread inside camera process | I/O-bound (network) |
| UI (Qt) | Main thread + worker thread for compute | Qt event loop blocking |

→ Tham khảo `Vision_platform_architecture_design/04-pipeline-and-concurrency/04-mo-hinh-concurrency-gil-hazards-per-mode.md` cho 5 deployment modes.

---

## Self-check

1. **Tại sao GIL tồn tại** (mặc dù bị ghét)?

2. **`time.sleep(1)` block 1 thread → thread khác có chạy được không?** Tại sao?

3. **Numpy `arr.sum()` cho 1M element** — release GIL không? Test cách nào?

4. **PyTorch `model(input).backward()`** — GIL? Multi-thread benefit?

5. **GIL-free Python (3.13+) sẽ thay đổi Vision Platform thế nào?** Pros/cons.

<details>
<summary>Đáp án</summary>

1. **GIL exists vì**:
   - CPython memory model dựa trên **reference counting** (mọi object có refcount).
   - Concurrent thread + refcount = race → corruption.
   - Solution 1 (slow): atomic refcount mọi access.
   - Solution 2 (slow): lock per-object.
   - Solution 3 (used): 1 global lock = GIL.
   - Solution 1+2 perf 30-50% slower vs single-thread. GIL avoid.
   - PEP 703 finally found Solution 4: biased refcount + deferred. Production 2026+.

2. **Thread khác chạy được**: 
   - `time.sleep` release GIL while waiting OS timer.
   - Other thread acquires GIL, runs.
   - When sleep returns → re-acquire GIL.
   - Đây là pattern I/O-bound work scale với thread.

3. **Numpy release GIL**: 
   - YES. Numpy operations là C code with `Py_BEGIN_ALLOW_THREADS`.
   - Test:
     ```python
     import numpy as np, threading, time
     arr = np.zeros(10**8)
     
     def numpy_op():
         arr.sum()
     
     def python_op():
         s = 0
         for i in range(10**6):
             s += 1
     
     t1 = time.monotonic()
     t = threading.Thread(target=numpy_op)
     t.start()
     python_op()
     t.join()
     t2 = time.monotonic()
     print(f"parallel: {t2-t1:.2f}s")
     ```
   - Compare with serial — should see ~2x speedup if GIL released during sum().

4. **PyTorch GIL**:
   - Most ops release GIL (C++/CUDA).
   - But Python-side: tensor wrapping, autograd graph build — GIL held.
   - Forward pass: ~80% GIL released (CUDA compute).
   - Backward: similar.
   - **Multi-thread benefit**: limited (~1.5-2x with 4 threads). Better: **batch larger** in 1 thread.

5. **GIL-free Vision Platform**:
   - **Pros**: thread scale linearly. Mỗi camera 1 thread thay 1 process → spawn cost ~0, IPC gone.
   - **Cons**:
     - Per-object lock contention (shared MediaPacket → contention).
     - Refcount overhead +5-10% (biased refcount).
     - Some C extensions chưa GIL-free (cv2, msgpack).
     - Memory model bugs latent → exposed.
   - **Migration**: gradual. Run benchmarks, measure. Có thể hybrid (process for bulkhead + thread for performance) như đang làm.
   - **Timeline**: Python 3.13 (Oct 2024) experimental. 3.14 (Oct 2025) likely default. Production migration 2026+ realistic.

</details>

---

## Liên kết

- **Module 02 file 03** — bulkhead.
- **Production**: `Vision_platform_architecture_design/04-pipeline-and-concurrency/04-mo-hinh-concurrency-gil-hazards-per-mode.md`.
- **Reference**: PEP 703, Python `concurrent.futures` docs.

---

## Tóm tắt 1 câu

> **GIL serialize Python bytecode trong 1 process. Released khi I/O syscall + C extension. Vision Platform: process cho bulkhead + GIL bypass; thread inside cho I/O concurrency. Verified bằng `bench_gil.py`: CPU-bound thread 0.94x, I/O-bound thread 4x speedup.**

➡️ Tiếp theo: [`02-shm-atomicity-explained.md`](02-shm-atomicity-explained.md)
