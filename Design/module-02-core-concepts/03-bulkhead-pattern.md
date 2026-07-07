# 03 — Bulkhead Pattern: tại sao 1 camera fail KHÔNG được kéo cả hệ thống

## TL;DR (30 giây)

> **Bulkhead = chia hệ thống thành các khoang cách ly**, mỗi khoang chứa "lửa" của riêng mình. 1 khoang cháy không lan sang khoang khác.
>
> Trong Vision Platform: **mỗi camera là 1 OS process riêng**. Camera 1 hang/crash/disconnect → 15 camera khác **không động**.
>
> Cost: spawn process tốn ~50-200ms, IPC qua SHM/ZMQ thay vì function call. Đổi lại: **isolation gốc**.

---

## Mental hook

Dự án HeadDetect, 8 camera. Architecture hiện tại: **1 process** chạy tất cả.

```python
# main.py — single process
threads = []
for cam_url in camera_urls:
    t = threading.Thread(target=process_camera, args=(cam_url,))
    t.start()
    threads.append(t)
```

Buổi tối: camera 3 (RTSP) bị disconnect đột ngột. Thread đang block trong `cap.read()` → mãi mãi không return (vì cv2 internal buffer + TCP timeout 60s).

Hệ quả:
- Thread 3 stuck.
- Python GIL: thread khác không bị block "code" nhưng **shared resource** (e.g. Postgres connection pool) bị thread 3 chiếm.
- Detection latency của camera 1, 2, 4-8 tăng.
- Sau 5 phút: thread 3 thả GIL nhưng `cap` vẫn corrupt → error log spam → log writer overflow → file descriptor cạn.
- 10 phút sau: process crash. **Tất cả 8 camera dừng**.

Câu hỏi của khách: "Tại sao camera 5 mất frame? Nó đâu liên quan camera 3?"

→ Đó là vì **không có bulkhead**.

---

## Câu chuyện: tàu Titanic

Tàu thường thiết kế **bulkhead** = các khoang kín nước, ngăn cách bằng tường thép. Nếu thân tàu bị thủng:

- **Có bulkhead**: nước chỉ tràn vào 1 khoang. Tàu vẫn nổi.
- **Không bulkhead**: nước tràn toàn tàu. Chìm.

Titanic CÓ bulkhead. Nhưng tường ngăn không cao hết — nước tràn từ khoang này sang khoang khác qua đỉnh. **Bulkhead bị bypass**. 1500+ người chết.

**Bài học cho code**:
1. **Thiết kế bulkhead** là tốt.
2. Nhưng **cách hiện thực** quan trọng. Bulkhead bị bypass = vô dụng.

→ Trong Vision Platform: bulkhead = process boundary. **Bypass** = shared mutable state qua disk file, network, signal handler...

---

## Vấn đề thực tế: 5 cách 1 camera lỗi kéo theo cả hệ thống

### Cách 1: Blocking I/O không có timeout

```python
def read_camera(cam_url):
    cap = cv2.VideoCapture(cam_url)
    while True:
        frame = cap.read()   # ← block vô tận nếu camera disconnect
        process(frame)
```

→ Thread stuck. Trong cùng process, GIL release khi block I/O nên thread khác chạy được. **Nhưng**: cv2 internal mutex có thể giữ → các camera khác vẫn ảnh hưởng.

### Cách 2: Memory leak từ 1 stream

```python
def read_camera(cam_url):
    frames = []   # ← buffer tăng dần
    while True:
        frames.append(cv2.VideoCapture(cam_url).read())
```

→ Camera 3 leak → process memory grow → OS kill toàn bộ process → 8 camera die.

### Cách 3: Exception trong thread không có handler

```python
def read_camera(cam_url):
    cap = cv2.VideoCapture(cam_url)
    while True:
        frame = cap.read()
        # 1 trong N lần raise
        process(frame)   # ← raise ZeroDivisionError vì frame format edge case
```

→ Thread chết im (Python thread exception không default propagate). Camera đó dừng. Main thread không biết. Nếu các camera **share** state qua dict global → state corrupt.

### Cách 4: Shared mutable state corruption

```python
# global
detection_buffer = {}

def process_camera(cam_id):
    while True:
        frame = read_frame(cam_id)
        dets = detect(frame)
        detection_buffer[cam_id] = dets   # ← race condition + 1 thread crash = state lost
```

→ Camera 3 thread crash giữa write → `detection_buffer[3]` corrupt → camera 5 đọc cùng dict → race → bug ngẫu nhiên.

### Cách 5: Resource pool exhaustion

1 process có:
- Postgres connection pool: 20 connection.
- File descriptor limit: 1024.
- GPU memory: 8GB.

Camera 3 crash → connection không release → pool exhaustion → camera 1-8 không insert được DB.

→ **1 camera fail = tất cả fail**. Đó là **anti-bulkhead**.

---

## Cách giải: Process bulkhead

**Pattern**: mỗi camera = 1 OS process **riêng biệt**.

```
                    ┌─────────────────────┐
                    │   Supervisor        │
                    │   (parent process)  │
                    └──┬──┬──┬──┬─────────┘
                       │  │  │  │ spawn
              ┌────────┘  │  │  └────────┐
              ▼           ▼  ▼           ▼
        ┌─────────┐  ┌────────┐  ┌─────────┐
        │ Camera 1│  │Camera 2│  │ Camera N│
        │ process │  │ process│  │ process │
        │         │  │        │  │         │
        │ - cv2   │  │ - cv2  │  │ - cv2   │
        │ - SHM   │  │ - SHM  │  │ - SHM   │
        │ writer  │  │ writer │  │ writer  │
        └────┬────┘  └───┬────┘  └────┬────┘
             │ frames    │frames      │ frames
             ▼           ▼            ▼
        ┌──────────────────────────────────┐
        │  Inference Service (1 process)   │
        │  - GPU detector                  │
        │  - SHM reader                    │
        │  - ZMQ ROUTER                    │
        └──────────────────────────────────┘
```

**Lợi ích bulkhead**:
- Camera 1 crash → OS kill process 1 → process 2-N **không ảnh hưởng**.
- Memory leak ở camera 1 → process 1 OOM → kill chỉ process 1.
- Exception camera 1 → process 1 die im, supervisor restart → 2-N không biết.
- Camera 1 share state với camera 2? **Không thể** (separate address space).

**Cost**:
- Spawn process ~50-200ms (vs thread ~0.1ms).
- IPC qua SHM/ZMQ thay function call.
- Không thể share Python object trực tiếp — phải serialize.

→ **Trade off này đáng** với multi-camera real-time.

---

## Process vs Thread: phân biệt cốt lõi

Đây là lúc bạn cần hiểu chi tiết.

| | Process | Thread |
|---|---------|--------|
| **Address space** | Riêng biệt | Share với thread khác cùng process |
| **GIL (Python)** | Mỗi process GIL riêng → true parallelism | Share GIL → CPU-bound không parallel |
| **Crash isolation** | 1 process die, others OK | 1 thread die có thể kéo cả process |
| **Cost spawn** | ~50-200ms | ~0.1ms |
| **Memory** | ~30-50MB/process (Python) | ~1MB/thread |
| **Communication** | IPC (SHM, pipe, socket) | Direct memory access |
| **Synchronization** | OS-level (signal, file lock) | In-process (Lock, Event, Queue) |

### GIL là yếu tố quyết định

Python GIL = chỉ 1 thread chạy bytecode tại 1 thời điểm. Hệ quả:

- **CPU-bound** (NumPy ops, image processing): thread không scale. **Process** scale linearly.
- **I/O-bound** (network, file): thread OK vì I/O release GIL.

Vision Platform có **cả hai**:
- Camera reading: I/O-bound (network/USB) — thread đủ.
- Detection: CPU-bound (numpy, GPU ops) — cần process.

→ **Architecture mix**: mỗi camera (I/O) là 1 process (cũng để bulkhead), inference (CPU+GPU) là 1 process riêng.

### Khi nào dùng thread thay process?

- **Trong cùng 1 component** đã là 1 process: thread OK cho concurrency I/O.
- **Cùng share state mạnh** + **không cần isolation**: thread.
- **Latency-sensitive spawn**: thread spawn nhanh hơn 1000×.

Vision Platform dùng thread bên trong inference service (cho ZMQ receive loop + GPU compute) — **bên trong** 1 process duy nhất.

---

## Build bulkhead from scratch — minimal demo

```python
# bulkhead_demo/worker.py
"""Code chạy trong worker process."""
import os
import time
import sys
import random


def worker_main(worker_id: int, output_path: str):
    """Worker process: ghi heartbeat ra file."""
    print(f"[Worker {worker_id}] PID={os.getpid()} start", file=sys.stderr)
    
    # Giả lập: worker 2 sẽ crash ngẫu nhiên ở giây thứ 3.
    crash_at = 3 if worker_id == 2 else None
    
    start = time.time()
    while True:
        elapsed = time.time() - start
        
        if crash_at is not None and elapsed > crash_at:
            print(f"[Worker {worker_id}] CRASH simulated", file=sys.stderr)
            sys.exit(1)
        
        with open(output_path, "a") as f:
            f.write(f"worker_{worker_id} alive at {elapsed:.1f}s\n")
        
        time.sleep(0.5)


if __name__ == "__main__":
    worker_main(int(sys.argv[1]), sys.argv[2])
```

```python
# bulkhead_demo/supervisor.py
"""Supervisor: spawn 4 worker processes, monitor, restart nếu crash."""
import multiprocessing as mp
import time
import os
from pathlib import Path
from bulkhead_demo.worker import worker_main


def supervise(n_workers: int, run_seconds: float):
    log_dir = Path("bulkhead_logs")
    log_dir.mkdir(exist_ok=True)
    
    procs: dict[int, mp.Process] = {}
    
    def spawn_worker(wid: int) -> mp.Process:
        log_path = log_dir / f"worker_{wid}.log"
        p = mp.Process(
            target=worker_main,
            args=(wid, str(log_path)),
            name=f"worker-{wid}",
            daemon=True,  # supervisor exit → worker die theo
        )
        p.start()
        return p
    
    # Spawn ban đầu
    for wid in range(1, n_workers + 1):
        procs[wid] = spawn_worker(wid)
    
    print(f"[Supervisor] PID={os.getpid()} spawned {n_workers} workers")
    
    # Monitor + restart loop
    start = time.time()
    while time.time() - start < run_seconds:
        for wid, p in list(procs.items()):
            if not p.is_alive():
                exit_code = p.exitcode
                print(
                    f"[Supervisor] worker {wid} died exit={exit_code}, restart"
                )
                p.join()  # cleanup zombie
                # Restart!
                procs[wid] = spawn_worker(wid)
        time.sleep(0.5)
    
    print("[Supervisor] shutdown")
    for wid, p in procs.items():
        p.terminate()
        p.join(timeout=2)
        if p.is_alive():
            p.kill()


if __name__ == "__main__":
    supervise(n_workers=4, run_seconds=10)
```

Run:

```bash
mkdir bulkhead_demo
cd bulkhead_demo
# tạo file ở trên
py -m bulkhead_demo.supervisor
```

Quan sát:
- 4 worker spawn.
- ~3s sau, worker 2 crash.
- Supervisor detect → spawn worker 2 mới.
- Worker 1, 3, 4 **liên tục** ghi log không gián đoạn.

```bash
cat bulkhead_logs/worker_1.log
# worker_1 alive at 0.0s
# worker_1 alive at 0.5s
# worker_1 alive at 1.0s
# ... liên tục, không gián đoạn ...

cat bulkhead_logs/worker_2.log
# worker_2 alive at 0.0s
# ... 3.0s
# CRASH
# worker_2 alive at 0.0s   ← restart, đếm lại từ 0
```

→ **Đây là bulkhead working**. Worker 2 crash, worker 1/3/4 không động.

---

## Áp dụng vào Vision Platform

Vision Platform có 3 tầng bulkhead:

### Tầng 1: Camera process bulkhead (M1 mode)

```
Supervisor process
├── Camera 1 process (cv2 RTSP, SHM writer)
├── Camera 2 process (cv2 RTSP, SHM writer)
├── ... 
├── Camera N process
├── Inference Service process (1)
└── Event Dispatcher process (1)
```

→ N+2 process. Camera die → restart. Inference die → camera tạm pause backpressure → restart.

### Tầng 2: Subprocess bulkhead (M3 desktop)

```
Qt UI process (main thread Qt event loop)
└── Pipeline subprocess (multiprocessing.Process)
    ├── Camera read thread
    ├── Inference thread
    └── Sink thread
```

→ Pipeline crash không kéo Qt UI. Qt vẫn hiển thị "pipeline disconnected, click reconnect".

### Tầng 3: Per-tenant bulkhead (M4 web, future)

```
FastAPI process
└── Per-tenant worker pool (subprocess per tenant)
    ├── Tenant A pipeline subprocess
    └── Tenant B pipeline subprocess
```

→ Tenant A crash không kéo Tenant B. Multi-tenant isolation.

→ Tham khảo `Vision_platform_architecture_design/13-adr/06-multi-process-bulkhead-*.md`.

---

## Communication giữa các bulkhead — không leak isolation

### Nguyên tắc: communication qua **giao thức** không qua **shared object**

**Sai**:
```python
# Cùng dict trong shared memory
shared_dict["camera_1_status"] = "ok"   # ← nếu corrupt struct, all readers crash
```

**Đúng**:
```python
# Mỗi camera ghi message qua SHM/ZMQ với envelope rõ ràng
zmq_pub.send_multipart([b"cam.1.status", msgpack.packb({"status": "ok"})])
```

→ Subscribers parse message. Nếu 1 message corrupt → reject 1 message thôi, không crash subscriber.

### 3 IPC mechanism Vision Platform dùng

| Mechanism | Use case | Cost | Visibility |
|-----------|----------|------|------------|
| **SHM (shared memory)** | Frame data (large bytes) | ~5µs/copy | Fast, low overhead |
| **ZMQ ROUTER/DEALER** | Inference request/response | ~1ms/round | Async, correlation, retry |
| **ZMQ PUB/SUB** | Health signal, config update | ~0.5ms | Broadcast, fire-and-forget |

→ Frame ndarray TOO BIG cho ZMQ (msgpack serialization 6MB ảnh = ~10ms). **SHM cho frame, ZMQ cho metadata.**

### Failure mode: process die holding lock?

Đây là **R5-CRITICAL-01** từ review.

`multiprocessing.Lock` là futex (POSIX) — non-robust. Process die holding lock → futex stay locked. Reader khác wait forever.

→ Vision Platform đã fix bằng:
1. **Bounded `lock.acquire(timeout=...)`** — không block forever.
2. **Sentinel state `QUARANTINED`** trong header — cross-process visible.
3. **Supervisor recovery sweep** — quarantine slot khi owner pid die.

→ Đây là **bulkhead còn cần thêm safety**. Naive bulkhead = chưa đủ. Cần OS-level safety + cleanup.

Tham khảo: `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-*.md`.

---

## Mental model: container ship

Tàu container có hàng nghìn container. Mỗi container = 1 bulkhead:
- Nước vào container 1 → container 1 chìm trong tàu.
- Container 2-1000 vẫn khô.
- Tàu vẫn nổi (đa số bulkhead còn nguyên).

Nhưng:
- Nếu container 1 cháy → cháy có thể lan qua khe hở.
- Nếu container 1 đặc biệt nặng + lệch → tàu lệch trọng tâm → mất ổn định.

→ **Bulkhead không phải bullet-proof**. Cần thêm:
- **Fire suppression** (process resource limits — cgroup).
- **Load balancing** (mỗi process ~đều load — không 1 process ăn 80% CPU).
- **Health monitoring** (supervisor detect anomaly).

Vision Platform có cả 3.

---

## Code-along: bulkhead minimal cho Vision (30 phút)

Build mini "vision bulkhead":
- 3 camera process (giả lập).
- 1 supervisor.
- Camera 2 crash sau 5s, supervisor restart.

```python
# vision_bulkhead_demo/camera_proc.py
"""Camera worker — giả lập đọc frame, ghi vào file giả lập SHM."""
import os
import sys
import time
import json
import random


def camera_main(cam_id: int, frame_log_path: str):
    print(f"[Cam {cam_id}] PID={os.getpid()} start", file=sys.stderr)
    
    # Camera 2 sẽ crash random.
    crash_after = 5.0 if cam_id == 2 else None
    
    start = time.time()
    frame_n = 0
    while True:
        elapsed = time.time() - start
        
        if crash_after is not None and elapsed > crash_after:
            print(f"[Cam {cam_id}] disconnect simulated", file=sys.stderr)
            # Giả lập như cv2 hang trên RTSP disconnect.
            sys.exit(1)
        
        # "Read frame" + ghi log
        with open(frame_log_path, "a") as f:
            f.write(json.dumps({
                "cam_id": cam_id,
                "frame_n": frame_n,
                "ts": elapsed,
            }) + "\n")
        
        frame_n += 1
        time.sleep(0.1)  # ~10 FPS giả lập


if __name__ == "__main__":
    camera_main(int(sys.argv[1]), sys.argv[2])
```

```python
# vision_bulkhead_demo/supervisor.py
"""Supervisor: spawn N camera, restart camera die."""
import multiprocessing as mp
import time
import os
from pathlib import Path
from vision_bulkhead_demo.camera_proc import camera_main


def supervise(n_cameras: int, run_seconds: float):
    log_dir = Path("camera_frames")
    log_dir.mkdir(exist_ok=True)
    
    procs: dict[int, mp.Process] = {}
    restart_counts: dict[int, int] = {}
    
    def spawn_camera(cam_id: int) -> mp.Process:
        log_path = log_dir / f"cam_{cam_id}.jsonl"
        p = mp.Process(
            target=camera_main,
            args=(cam_id, str(log_path)),
            name=f"cam-{cam_id}",
            daemon=True,
        )
        p.start()
        return p
    
    for cid in range(1, n_cameras + 1):
        procs[cid] = spawn_camera(cid)
        restart_counts[cid] = 0
    
    print(f"[Supervisor] {n_cameras} cameras spawned")
    
    start = time.time()
    while time.time() - start < run_seconds:
        for cid, p in list(procs.items()):
            if not p.is_alive():
                exit_code = p.exitcode
                restart_counts[cid] += 1
                
                # Cap restart — không restart vô hạn (camera lỗi vĩnh viễn).
                if restart_counts[cid] > 3:
                    print(
                        f"[Supervisor] cam {cid} crashed {restart_counts[cid]}× "
                        "→ giving up, NO restart"
                    )
                    p.join()
                    del procs[cid]
                    continue
                
                print(
                    f"[Supervisor] cam {cid} died exit={exit_code} "
                    f"(restart #{restart_counts[cid]})"
                )
                p.join()
                procs[cid] = spawn_camera(cid)
        
        time.sleep(0.5)
    
    # Shutdown
    print("[Supervisor] shutdown")
    for cid, p in procs.items():
        p.terminate()
        p.join(timeout=2)
        if p.is_alive():
            p.kill()
    
    # Verify isolation
    print("\n=== Bulkhead verification ===")
    for cid in range(1, n_cameras + 1):
        log_path = log_dir / f"cam_{cid}.jsonl"
        if not log_path.exists():
            continue
        with open(log_path) as f:
            n_frames = sum(1 for _ in f)
        print(f"cam {cid}: {n_frames} frames captured (restarts: {restart_counts.get(cid, 0)})")


if __name__ == "__main__":
    supervise(n_cameras=4, run_seconds=15)
```

Run:

```bash
mkdir vision_bulkhead_demo
cd vision_bulkhead_demo
# tạo 2 file
py -m vision_bulkhead_demo.supervisor
```

Expected:
```
[Supervisor] 4 cameras spawned
[Cam 1] PID=12345 start
[Cam 2] PID=12346 start
[Cam 3] PID=12347 start
[Cam 4] PID=12348 start
[Cam 2] disconnect simulated
[Supervisor] cam 2 died exit=1 (restart #1)
[Cam 2] PID=12350 start
[Cam 2] disconnect simulated   ← lại crash sau 5s
[Supervisor] cam 2 died exit=1 (restart #2)
...

=== Bulkhead verification ===
cam 1: 150 frames captured (restarts: 0)
cam 2: ~50 frames × 3 restarts = 150 frames (restarts: 3)
cam 3: 150 frames captured (restarts: 0)
cam 4: 150 frames captured (restarts: 0)
```

→ Camera 2 crash 3 lần, **không ảnh hưởng** camera 1, 3, 4.

### Bài tập mở rộng

**Bài 1**: Add health check. Supervisor ping mỗi camera mỗi 2s, restart nếu camera **stale** (không update frame_log trong 5s) — phát hiện hang (process còn alive nhưng stuck).

Hint:
```python
# Trong supervisor loop
for cid in procs:
    last_modified = os.path.getmtime(log_dir / f"cam_{cid}.jsonl")
    if time.time() - last_modified > 5:
        print(f"cam {cid} STALE, killing")
        procs[cid].kill()
        # next loop sẽ detect not alive → restart
```

**Bài 2**: Cap memory mỗi camera process với `resource.setrlimit(RLIMIT_AS, ...)`. Camera 1 cố malloc 1GB → OS kill chỉ camera 1, không kéo cả supervisor.

(Linux only — Windows không có `RLIMIT_AS`.)

**Bài 3**: Verify isolation thực sự. Trong `camera_main`, thử:
- `os.environ["MY_VAR"] = f"cam_{cam_id}"` — env per-process.
- Ghi 1 dict global trong `camera_proc.py` module.
- Verify rằng **giá trị global khác nhau** giữa các process — ngược với threading.

---

## Checkpoint

Mở `_my_answers.md`:

1. **Định nghĩa bulkhead** — 1 câu. Cho 1 ví dụ ngoài software.

2. **Process vs Thread**: list 3 khác biệt cốt lõi. Vision Platform chọn **process** vì lý do nào trong 3?

3. **Cost của bulkhead**: spawn process ~50-200ms, IPC overhead. Trong context Vision Platform 16 camera, cost này có chấp nhận được không? Tính toán cụ thể.

4. **R5-CRITICAL-01 (mutex poisoning)**: tại sao bulkhead "đơn thuần" (mỗi process riêng) chưa đủ? Cần thêm gì?

5. **Bulkhead bị bypass**: cho 3 ví dụ "tưởng là bulkhead nhưng thực ra leak isolation". Cách phát hiện.

<details>
<summary>Đáp án</summary>

1. **Bulkhead** = chia hệ thống thành các khoang isolated, 1 khoang fail không lan sang khoang khác. **Ví dụ ngoài software**: tàu thuỷ với khoang kín nước; nhà chung cư với firewall giữa căn hộ; cơ thể với hệ miễn dịch khu vực.

2. **3 khác biệt**:
   - Address space riêng vs share.
   - GIL riêng vs share (Python).
   - Crash isolation: process boundary = OS-level isolation.
   
   Vision Platform chọn process **vì 3 lý do đồng thời**: 
   - GIL cho CPU-bound (numpy, image ops) cần process scale.
   - Crash isolation: 1 camera die không kéo 15 cái.
   - Resource isolation: OOM 1 process không kéo cả app.

3. **Tính toán**:
   - Spawn cost: 16 camera × 100ms = 1.6s **một lần** lúc start. Không là vấn đề.
   - IPC cost mỗi frame: SHM ~5µs/copy. Frame size 1920×1080×3 = 6MB. 6MB / SHM bandwidth (~5GB/s) = ~1.2ms. Tốn ~3% frame budget 33ms. **OK**.
   - Memory cost: 16 process × 50MB Python overhead = 800MB. Server 16GB RAM = OK.
   - Total: bulkhead **chấp nhận được** ở scale 16 camera. Beyond ~32 camera bắt đầu marginal.

4. **R5-CRITICAL-01**: 
   - Naive bulkhead: process die → kernel cleanup memory + close fd. **Nhưng futex (multiprocessing.Lock) không tự cleanup**.
   - Process die holding lock → readers wait forever.
   - **Cần thêm**:
     - Bounded `lock.acquire(timeout=...)` — không block forever.
     - Sentinel `QUARANTINED` cross-process visible (header lock-free atomic write).
     - Supervisor sweep detect dead-pid → quarantine slot.
   
   → Bulkhead = **process boundary** + **safety mechanism** xung quanh shared resources.

5. **3 ví dụ leak**:
   - **Shared file mutate**: 2 process cùng ghi 1 log file. Process 1 lock file. Crash. File lock leaked.
   - **Shared memory không robust**: như R5-CRITICAL-01.
   - **Network port reservation**: process 1 hold port 8080. Crash đột ngột. Port không tự release ngay (TIME_WAIT 60s) → process restart không bind được port.
   
   **Cách phát hiện**:
   - Chaos engineering: kill 1 process → observe các process khác có hang không.
   - Strace/lsof xem process còn hold gì sau die.
   - Health check + heartbeat — phát hiện stale (process alive nhưng stuck).

</details>

---

## Trade-offs

### "Bulkhead đắt — tôi có thể dùng thread thay không?"

Tuỳ scenario:

- **CPU-bound + isolation cần thiết**: PHẢI dùng process. Thread không bypass GIL + thread crash kéo process.
- **I/O-bound + share state OK**: thread đủ.
- **Mixed**: process cho bulkhead level + thread bên trong process cho I/O concurrency.

Vision Platform: **mixed** — process cho camera/inference bulkhead, thread bên trong inference service cho ZMQ + GPU.

### "Cost spawn process — có cách giảm không?"

Có:
- **Pre-fork** — spawn pool process từ đầu, reuse.
- **Process pool** với `multiprocessing.Pool` — dùng existing process cho task ngắn.

Vision Platform dùng **persistent process** (camera process sống suốt). Không pre-fork vì:
- Process chỉ spawn 1 lần lúc start. 100ms spawn không matter.
- Persistent process = state rõ ràng, không lo "stale state" của pre-fork.

### "Khi nào KHÔNG dùng bulkhead?"

- **Single user CLI tool**: 1 process đủ.
- **Throughput 1-2 camera, không 24/7**: thread đủ.
- **Embedded device** memory limit cực ngặt: bulkhead overhead không kham nổi.

→ Vision Platform target 8-16 camera 24/7. Bulkhead is **necessity**.

---

## Pitfalls

### Pitfall 1: Bulkhead nhưng share file lỏng lẻo

```python
# Mỗi camera process ghi vào CÙNG 1 log file
camera_1: open("/var/log/cam.log", "a").write(...)
camera_2: open("/var/log/cam.log", "a").write(...)
```

→ Linux append guarantee atomic ≤ PIPE_BUF (typically 4096B). Lớn hơn: race, line interleave.

**Sửa**: file rotation per process (`cam_1.log`, `cam_2.log`). Hoặc dùng `concurrent_log_handler.ConcurrentRotatingFileHandler` (multi-process safe — Vision Platform dùng).

### Pitfall 2: Kill cứng không cleanup

```python
proc.kill()   # SIGKILL — không cho cleanup
```

→ SHM segment, file lock, port reservation **leaked**.

**Sửa**: SIGTERM → wait timeout → SIGKILL. Vision Platform có shutdown protocol cascade. Cleanup orphan SHM ở supervisor restart.

### Pitfall 3: Restart loop vô tận

```python
while True:
    if not proc.is_alive():
        proc = spawn(...)   # ← mỗi crash spawn lại
```

→ Camera lỗi cứng (camera offline) → restart vô tận → log spam → CPU 100%.

**Sửa**: cap restart count + exponential backoff:
```python
restart_counts[cid] += 1
if restart_counts[cid] > 5:
    give_up()
else:
    backoff_s = min(60, 2 ** restart_counts[cid])
    time.sleep(backoff_s)
    spawn()
```

Vision Platform có **circuit breaker** (xem Module 04 deep dive).

### Pitfall 4: IPC chia sẻ "small thing" mà thread vẫn dùng được

```python
# Mỗi camera process gửi mỗi config update qua ZMQ
zmq_publish_config_to_all_cameras()
```

→ Config update không cần 1ms ZMQ. Có thể dùng file watch + reload — đơn giản hơn.

→ **Nguyên tắc**: dùng IPC cho **data flow lớn** (frames). Cho **rare events** (config update, signal), file/signal đủ.

---

## Liên kết

- File 04 (`04-backpressure-why-it-matters.md`) — sao backpressure là rule trong bulkhead architecture.
- Production: `Vision_platform_architecture_design/13-adr/06-multi-process-bulkhead-*.md` — ADR.
- Production: `Vision_platform_architecture_design/05-inference-and-ipc/01-shm-atomicity-*.md` — SHM với mutex robustness.
- Module 04 file 01 (`01-gil-truth.md`) — đào sâu why process > thread cho CPU-bound Python.

---

## Tóm tắt 1 câu

> **Bulkhead = mỗi camera 1 OS process. Crash isolation gốc qua address space riêng. Cost = spawn 100ms + IPC, đáng cho multi-camera 24/7. Cẩn thận bypass: shared file lỏng lẻo, mutex non-robust, restart loop.**

➡️ Tiếp theo: [`04-backpressure-why-it-matters.md`](04-backpressure-why-it-matters.md)
