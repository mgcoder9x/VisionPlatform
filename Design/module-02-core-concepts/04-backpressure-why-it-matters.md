# 04 — Backpressure: tại sao Producer-Consumer mismatch là **rule, không phải exception**

## TL;DR (30 giây)

> **Backpressure** = mechanism để producer biết khi consumer quá tải, **chậm lại** hoặc **drop có policy**.
>
> Không có backpressure → buffer infinite → memory grow → OOM crash. **100% các real-time stream system gặp vấn đề này** không sớm thì muộn.
>
> Vision Platform có **6 policy**: DROP_OLDEST, DROP_NEWEST, BLOCK, SAMPLE, DEGRADE_QUALITY, REJECT. **BLOCK forbidden cho RTSP** — sẽ giải thích vì sao.

---

## Mental hook

Giáo sư Walt Disney từng nói:

> "Sự khác biệt giữa thành công và thất bại = ai sẽ giải quyết vấn đề khi nó vỡ."

Trong real-time system: vấn đề **luôn** vỡ tại 1 thời điểm. Không phải "có thể". Là **chắc chắn**. Câu hỏi chỉ là: bạn đã chuẩn bị chưa?

**Tình huống thực tế** với HeadDetect 8 camera:

- **Bình thường**: GPU detect ~8ms/frame. 30 FPS × 8 camera = 240 fps. GPU xử lý kịp.
- **Bất thường**: GPU thermal throttle (đêm nóng) → ~16ms/frame. Pipeline có thể xử lý chỉ ~62 fps.
- **Producer ép vào**: 240 fps. **Consumer chỉ 62 fps**. Khoảng cách: **178 fps đẩy vào queue**.

Câu hỏi: **đẩy vào đâu**?

Cách 1 — vào dict / list trong RAM:
```python
queue.put(frame)   # frame ~6MB
```
→ 178 frame/s × 6MB = 1GB/s tăng memory. **OOM trong vài giây**.

Cách 2 — vào file disk:
```python
with open("buffer.bin", "ab") as f:
    f.write(frame.tobytes())
```
→ Disk fill nhanh. Sau khi GPU phục hồi, queue vẫn còn 1GB backlog → latency tăng vọt.

Cách 3 — **drop có ý thức**:
```python
if queue.qsize() > MAX:
    queue.popleft()   # drop frame cũ nhất
queue.put(frame)
```
→ Memory bound. Latency bound. **Mất 1 số frame nhưng app sống sót**.

Cách 3 = **backpressure**. Nếu không thiết kế từ đầu = bạn sẽ học bài học khó.

---

## Câu chuyện: TCP sliding window — mọi network protocol có backpressure

Bạn nghĩ HTTP "đơn giản"? Sai. **TCP underneath có backpressure built-in**.

TCP sender không gửi vô tận. Receiver có **receive window** (RWND) — buffer size. Sender gửi tối đa RWND bytes "in flight". Khi receiver process chậm:

```
Receiver: window=1500 bytes  ← receiver buffer còn 1500B
Sender: gửi 1000B (in flight)
Receiver: ack 500B, advertise window=1000   ← receiver xử lý được 500B
Sender: chỉ gửi thêm 500B (window full)
Receiver: chậm → window=0
Sender: STOP. Đợi receiver advertise window > 0.
```

**TCP Zero Window**: receiver advertise window=0 → sender block hoàn toàn. Sender không "tự đoán cố gắng gửi" — chờ tín hiệu.

→ Đây là **backpressure ở protocol level**. Built-in 50 năm rồi (TCP 1974).

**Bài học cho code**:
- Nếu TCP cần backpressure ở mạng, **app layer cũng cần**. 
- Producer phải có tín hiệu "consumer slow". Không có = buffer infinite.
- **Drop có thể là OK** (UDP) hoặc **block là OK** (TCP). Nhưng phải **chọn explicit**, không silent buffer.

---

## Vấn đề thực tế: 5 cách thiếu backpressure giết hệ thống

### Case 1: OOM crash từ buffer

```python
# Producer (camera reading)
for frame in camera:
    queue.put_nowait(frame)   # không block, không drop

# Consumer (inference, slow)
while True:
    frame = queue.get()
    detect(frame)   # 8ms → 16ms (thermal)
```

→ Producer đẩy 30 fps, consumer 60 fps capable nhưng giờ chỉ 30 → khớp. **Một ngày** consumer 16ms thay 8ms → consumer tụt → queue grow → OOM.

### Case 2: Latency cascade

Nếu queue đầy buffer 1000 frame:
```
frame N được capture lúc T=0
queue.put_nowait(frame N)
... 1000 frame trước đó vẫn ở queue ...
consumer xử lý frame N lúc T = 1000 / 30fps = 33 giây sau
```

→ **Detection trễ 33 giây**. Phát hiện "có người vào" sau khi người đã đi 33s. Vô dụng.

→ Buffer lớn = latency tăng. **Drop frame cũ tốt hơn process frame cũ**.

### Case 3: Camera-side back-effect (TCP Zero Window)

RTSP camera → ZMQ pipeline. ZMQ có internal buffer (HWM). Khi consumer chậm + HWM đầy:

- ZMQ default behavior: **block** producer (`socket.send()` block).
- Producer = camera process. Block = không đọc frame mới từ RTSP.
- RTSP stream có TCP socket. Producer không đọc → TCP RX buffer đầy → TCP ACK với window=0.
- **Camera firmware** thấy Zero Window → có 2 phản ứng:
  - **Drop frame** server-side (camera buffer overflow) — frame loss permanent.
  - **Drop I-frame** (keyframe) → next frame là P-frame → decode lỗi → cascade frame error.
- Some camera: **disconnect TCP** sau timeout → reconnect storm.
- 16 camera đồng thời disconnect → **thundering herd** restart → server overload.

→ Đây là R1 review CR-RT-03 — chính xác lý do **BLOCK forbidden cho RTSP**.

### Case 4: Resource exhaustion qua bias

Producer fast, consumer slow. Consumer được nhiều CPU vì code chạy "trong suốt". Producer block trên `queue.put` không tốn CPU nhưng chiếm thread. Pool thread của asyncio cạn → các task khác đói.

### Case 5: Silent data loss

```python
queue = asyncio.Queue(maxsize=100)
await queue.put(frame)
```

`Queue` đầy → `put` block. Caller không biết → vẻ ngoài bình thường. **Latency cao một cách bí ẩn**. Debugging khó.

→ Backpressure phải **explicit và visible** — emit metric "drops/s", log structured warning.

---

## 6 backpressure policy + khi nào dùng cái nào

Vision Platform định nghĩa 6 policy. **Mỗi source type có whitelist policy phù hợp.**

### 1. `DROP_OLDEST`

Khi queue đầy → drop **frame cũ nhất**, push frame mới.

**Use case**: real-time view. Frame mới quan trọng hơn frame cũ.

```python
if queue.full():
    queue.popleft()   # drop oldest
queue.append(new_frame)
```

**Vision Platform dùng**: RTSP camera default. "Tôi muốn xem hiện tại, không phải 5s trước."

### 2. `DROP_NEWEST`

Khi queue đầy → **giữ frame cũ**, drop frame mới.

**Use case**: precise time-series, mất 1 frame OK nhưng giữ continuous từ T=0.

```python
if queue.full():
    return  # drop new
queue.append(new_frame)
```

**Vision Platform dùng**: ít dùng cho RTSP. Có thể dùng cho file batch khi cần "first N frames".

### 3. `BLOCK`

Khi queue đầy → **block producer**, đợi consumer.

**Use case**: file batch, no time pressure. Đảm bảo lossless.

```python
queue.put(new_frame)  # block until space
```

**Vision Platform — FORBIDDEN cho RTSP**. Lý do: TCP Zero Window cascade (Case 3 ở trên). Thiết kế enforce ở config-time qua `ProfileValidator`.

→ **Đây là decision quan trọng**: Vision Platform whitelist policy theo source type, không cho user pick BLOCK cho RTSP.

### 4. `SAMPLE`

Process every Nth frame, ignore rest. **Decision lúc capture**, không lúc queue.

**Use case**: high-FPS camera (60 FPS) + budget thấp (15 FPS) → process 1/4.

```python
if frame_count % 4 != 0:
    return  # skip
process(frame)
frame_count += 1
```

**Vision Platform dùng**: nhiều camera FPS cao + budget hạn chế.

### 5. `DEGRADE_QUALITY`

Khi overload → resize/recompress frame nhỏ hơn → giảm cost.

**Use case**: detection có thể work với 720p thay vì 1080p. Có lợi vs drop hoàn toàn.

```python
if overloaded:
    frame = cv2.resize(frame, (640, 480))   # 1080p → VGA
process(frame)
```

**Vision Platform dùng**: combined với inference health signal.

### 6. `REJECT`

Khi queue đầy → reject với error response.

**Use case**: HTTP upload (M4 web). Client biết retry sau.

```python
if queue.full():
    return Response(503, "Service busy, retry later")
queue.append(frame)
```

**Vision Platform dùng**: M4 web mode.

### Quick reference

| Policy | RTSP | File | Webcam | HTTP upload | Image folder |
|--------|------|------|--------|-------------|--------------|
| DROP_OLDEST | ✅ default | ✅ | ✅ default | ❌ | ❌ |
| DROP_NEWEST | ✅ | ✅ | ✅ | ❌ | ❌ |
| BLOCK | ❌ FORBIDDEN | ✅ default | ❌ | ✅ | ✅ default |
| SAMPLE | ✅ | ✅ | ✅ | ❌ | ❌ |
| DEGRADE_QUALITY | ✅ | ❌ | ❌ | ❌ | ❌ |
| REJECT | ❌ | ❌ | ❌ | ✅ default | ✅ |

→ Chính xác bảng này có trong `Vision_platform_architecture_design/06-resilience-and-shutdown/01-backpressurepolicy-per-source-enforcement.md`.

---

## Build backpressure from scratch (45 phút)

Build mini producer-consumer với 4 policy, observe behavior.

```python
# bp_demo/bounded_queue.py
"""Custom bounded queue với explicit policy."""
import time
from collections import deque
from enum import Enum
from threading import Lock
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class BackpressurePolicy(Enum):
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"
    REJECT = "reject"


class BoundedQueue(Generic[T]):
    """Thread-safe bounded queue với configurable backpressure policy."""

    def __init__(self, maxsize: int, policy: BackpressurePolicy):
        self._buf: deque[T] = deque()
        self._maxsize = maxsize
        self._policy = policy
        self._lock = Lock()
        self._not_empty = self._lock_cond_var()
        self._not_full = self._lock_cond_var()
        # Metrics
        self.drops = 0
        self.rejects = 0
        self.blocks_total_s = 0.0

    def _lock_cond_var(self):
        from threading import Condition
        return Condition(self._lock)

    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """Try to put. Return True nếu thành công, False nếu drop/reject.
        
        BLOCK policy: block until success OR timeout.
        Other: return False on full.
        """
        with self._lock:
            if len(self._buf) < self._maxsize:
                self._buf.append(item)
                self._not_empty.notify()
                return True
            
            # Queue full — apply policy
            match self._policy:
                case BackpressurePolicy.DROP_OLDEST:
                    self._buf.popleft()
                    self._buf.append(item)
                    self.drops += 1
                    return True   # caller insert OK, but oldest dropped
                
                case BackpressurePolicy.DROP_NEWEST:
                    self.drops += 1
                    return False  # caller insert dropped
                
                case BackpressurePolicy.REJECT:
                    self.rejects += 1
                    return False
                
                case BackpressurePolicy.BLOCK:
                    block_start = time.monotonic()
                    while len(self._buf) >= self._maxsize:
                        if not self._not_full.wait(timeout=timeout):
                            self.blocks_total_s += time.monotonic() - block_start
                            return False  # timeout
                    self.blocks_total_s += time.monotonic() - block_start
                    self._buf.append(item)
                    self._not_empty.notify()
                    return True

    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        with self._lock:
            while not self._buf:
                if not self._not_empty.wait(timeout=timeout):
                    return None
            item = self._buf.popleft()
            self._not_full.notify()
            return item

    def qsize(self) -> int:
        with self._lock:
            return len(self._buf)
```

```python
# bp_demo/demo.py
"""Producer fast, consumer slow — observe each policy."""
import threading
import time
from bp_demo.bounded_queue import BoundedQueue, BackpressurePolicy


def producer(q: BoundedQueue[int], n: int, rate_fps: float, stop_event):
    """Push n items at rate_fps. Stop when stop_event set."""
    interval = 1.0 / rate_fps
    for i in range(n):
        if stop_event.is_set():
            break
        q.put(i)
        time.sleep(interval)


def consumer(q: BoundedQueue[int], rate_fps: float, stop_event):
    """Consume at rate_fps. Stop when stop_event set."""
    interval = 1.0 / rate_fps
    consumed = 0
    while not stop_event.is_set():
        item = q.get(timeout=0.5)
        if item is None:
            continue
        consumed += 1
        time.sleep(interval)
    return consumed


def run_test(policy: BackpressurePolicy, duration_s: float):
    """Producer 30fps, consumer 10fps, queue size 5. Run duration_s seconds."""
    q = BoundedQueue[int](maxsize=5, policy=policy)
    stop = threading.Event()
    
    # Producer 30 fps, consumer 10 fps — producer 3× faster.
    # Queue size 5 → backlog ~5 items, then policy kicks in.
    p = threading.Thread(
        target=producer, args=(q, 10000, 30.0, stop),
    )
    c = threading.Thread(
        target=consumer, args=(q, 10.0, stop),
    )
    
    start = time.monotonic()
    p.start()
    c.start()
    
    time.sleep(duration_s)
    stop.set()
    
    p.join(timeout=2)
    c.join(timeout=2)
    
    elapsed = time.monotonic() - start
    print(f"\n=== Policy: {policy.value} ===")
    print(f"Duration: {elapsed:.2f}s")
    print(f"Final queue size: {q.qsize()}")
    print(f"Drops: {q.drops}")
    print(f"Rejects: {q.rejects}")
    print(f"Total block time: {q.blocks_total_s:.2f}s")


if __name__ == "__main__":
    for policy in [
        BackpressurePolicy.DROP_OLDEST,
        BackpressurePolicy.DROP_NEWEST,
        BackpressurePolicy.BLOCK,
        BackpressurePolicy.REJECT,
    ]:
        run_test(policy, duration_s=3.0)
```

Run:

```bash
mkdir bp_demo
# tạo 2 file
py -m bp_demo.demo
```

Expected output (xấp xỉ):

```
=== Policy: drop_oldest ===
Duration: 3.00s
Final queue size: 5
Drops: 60
Rejects: 0
Total block time: 0.00s

=== Policy: drop_newest ===
Duration: 3.00s
Final queue size: 5
Drops: 60
Rejects: 0
Total block time: 0.00s

=== Policy: block ===
Duration: 3.00s
Final queue size: 5
Drops: 0
Rejects: 0
Total block time: 2.00s   ← producer block 2/3 thời gian!

=== Policy: reject ===
Duration: 3.00s
Final queue size: 5
Drops: 0
Rejects: 60
Total block time: 0.00s
```

**Phân tích**:
- DROP_OLDEST/NEWEST: drop 60 item, queue ổn định ở size 5.
- BLOCK: producer block 2s/3s (= 67% time waste). Memory bounded NHƯNG **producer paralyzed**.
- REJECT: producer fast nhưng phải handle 60 rejects.

→ Mỗi policy có hành vi quan sát được khác nhau. **Chọn theo use case**.

### Bài tập mở rộng

**Bài 1: Add SAMPLE policy**

Sample mỗi Nth frame:
```python
class SamplingProducer:
    def __init__(self, q, sample_rate: int):
        self._q = q
        self._sample_rate = sample_rate  # process 1/N
        self._counter = 0
    
    def maybe_put(self, item):
        self._counter += 1
        if self._counter % self._sample_rate == 0:
            self._q.put(item)
```

→ Sample rate 3 → 30 fps producer → 10 fps "real" → consumer 10 fps khớp. Không drop, không block.

**Bài 2: DEGRADE_QUALITY**

Wrap producer logic:
```python
def degrading_producer(q, frames, overloaded_signal):
    for frame in frames:
        if overloaded_signal.is_set():
            frame = downsize(frame)   # 1080p → 480p
        q.put(frame)
```

→ Cần `overloaded_signal` từ consumer side. Đây là **feedback loop**, không chỉ buffer.

**Bài 3: Observability**

Add metric: `q.drops_per_sec`, `q.depth_p50/p99`. Print mỗi 1s. Dùng để alert.

---

## Áp dụng vào Vision Platform

### Producer side

```python
# vision_demo/adapters/ffmpeg_rtsp_source.py — sketch
class FFmpegRTSPSource:
    def __init__(self, url, backpressure_policy):
        self._policy = backpressure_policy
        # ProfileValidator đã refuse nếu policy=BLOCK + source=rtsp
    
    def read(self) -> ReadResult:
        raw = self._ffmpeg_proc.stdout.read(self._frame_size)
        frame = decode(raw)
        
        # Try put vào SHM
        slot_info = self._shm.write(frame, self._fmt)
        if slot_info is None:
            # SHM full
            match self._policy:
                case BackpressurePolicy.DROP_OLDEST:
                    return self._shm.force_write(frame, self._fmt)
                case BackpressurePolicy.DROP_NEWEST:
                    self._dropped_count += 1
                    return ReadResult(status=ReadStatus.DROPPED)
                case BackpressurePolicy.SAMPLE:
                    return ReadResult(status=ReadStatus.DROPPED)
                case BackpressurePolicy.DEGRADE_QUALITY:
                    if self._is_overloaded():
                        target = self._bp.degrade_target_resolution
                        small = cv2.resize(frame, target)
                        return self._shm.force_write(small, fmt_with_size(target))
                    return ReadResult(status=ReadStatus.DROPPED)
        
        return ReadResult(status=ReadStatus.FRAME, data=frame, slot=slot_info)
```

### Consumer signal (feedback loop)

Consumer (inference service) emit health signal:

```python
# Inference service → publish health
zmq_pub.send_multipart([
    b"inference.health",
    msgpack.packb({
        "queue_depth": current_depth,
        "queue_capacity": max_depth,
        "p99_latency_ms": p99,
        "overloaded": current_depth > max_depth * 0.8 or p99 > 50,
    }),
])

# Camera process → subscribe, set overloaded
class HealthSubscriber:
    def latest(self):
        # Returns latest health snapshot
        ...

# In camera read loop
health = health_sub.latest()
if health.overloaded:
    self._bp.policy = BackpressurePolicy.SAMPLE   # tạm chuyển policy
```

→ **Adaptive backpressure**: policy thay đổi runtime theo health signal.

### File trong Vision Platform

- `Vision_platform_architecture_design/06-resilience-and-shutdown/01-backpressurepolicy-per-source-enforcement.md` — chi tiết policy + enforcement.
- `Vision_platform_architecture_design/06-resilience-and-shutdown/02-backpressure-metrics-feedback-loop.md` — feedback loop.
- `Vision_platform_architecture_design/06-resilience-and-shutdown/05-block-policy-banned-cho-rtsp.md` — vì sao BLOCK forbidden RTSP.

---

## Checkpoint

1. **TCP Zero Window** — giải thích cơ chế. Liên hệ với "BLOCK forbidden cho RTSP" trong Vision Platform.

2. **6 policy** — list tên + 1 câu use case mỗi policy. Không tra cứu.

3. **Buffer infinite không backpressure** — 3 cách OOM xảy ra (chỉ list, không cần code).

4. Bạn build webcam app real-time. Frame rate webcam 60 fps, detection 20 fps. Chọn policy gì? Explain.

5. **Anti-pattern**: ai đó đề xuất "tăng buffer size lên 10000 thay vì backpressure". Phản biện.

<details>
<summary>Đáp án</summary>

1. **TCP Zero Window**: receiver buffer đầy → ack window=0 → sender block. Đây là **flow control** built-in TCP. 
   
   **Liên hệ**: nếu Vision Platform dùng BLOCK + RTSP → camera process block trên `queue.put()` → không đọc TCP receive buffer → kernel ack window=0 → camera firmware (RTSP server) thấy → drop frame server-side hoặc disconnect. **Hậu quả tệ hơn drop có chủ ý**: mất control, mất data, có thể disconnect storm. → Vision Platform refuse cấu hình BLOCK + RTSP ngay tại config load time.

2. - **DROP_OLDEST**: real-time view, prefer "now".
   - **DROP_NEWEST**: giữ continuous, mất 1 frame OK.
   - **BLOCK**: lossless cần thiết, file batch không deadline.
   - **SAMPLE**: high-FPS source nhiều hơn budget, lấy every Nth.
   - **DEGRADE_QUALITY**: trade resolution thay vì drop hoàn toàn.
   - **REJECT**: HTTP-style, client biết retry.

3. **3 cách OOM**:
   - Producer push nhanh hơn consumer process → buffer grow → OOM.
   - Buffer = list/dict in-memory → mỗi item Python object overhead lớn → OOM nhanh hơn ngay khi item nhỏ.
   - Buffer in-memory + frame ndarray ~6MB/frame → 1000 frame = 6GB. Chỉ vài giây drift = OOM.

4. **Webcam 60 fps, detect 20 fps**: 
   - Có **3 phương án**:
     - **SAMPLE rate=3**: process 1/3 frame. Predictable. Không drop ngẫu nhiên.
     - **DROP_OLDEST**: queue size 1, luôn lấy frame mới nhất. "Lag-free" UI.
     - **DROP_NEWEST**: drop frame mới khi backlog. Hiếm dùng cho live view.
   - **Khuyến nghị**: SAMPLE rate=3 cho deterministic, hoặc DROP_OLDEST queue=1 cho lowest latency.

5. **Phản biện**:
   - Buffer 10000 frame × 6MB = **60GB**. Vô lý.
   - Latency: 10000 / 20 fps = **500 giây** (8 phút) trễ. Detection vô dụng.
   - Memory cấp phát rồi không trả → OS memory pressure → OOM khác process.
   - Vẫn không giải quyết: nếu producer fast hơn consumer **trung bình**, buffer cuối cùng đầy.
   
   **Đúng**: backpressure là **rule, không phải exception**. Buffer lớn chỉ delay vấn đề, không giải quyết.

</details>

---

## Trade-offs

### "Drop frame có làm hỏng tracking?"

**Có thể**. Tracker (ByteTrack, BoT-SORT...) giả định frame liên tục. Drop 1 frame thi thoảng OK. Drop 50% = tracker mất ID.

→ Vision Platform có **tracker scope** + **circuit breaker** giúp tracker resync nhanh sau drop burst. Không hoàn hảo.

→ **Trade-off**: drop frame > buffer infinite. Drop có policy > drop ngẫu nhiên. Tracker tốt > tracker kém với cùng drop rate.

### "Backpressure phức tạp — script đơn giản có cần không?"

Tuỳ:
- **1 file đọc 10 ảnh xử lý**: KHÔNG cần. Synchronous OK.
- **Realtime stream 1+ camera**: PHẢI có.
- **Async pipeline với queue**: PHẢI có.

→ Đặt câu hỏi: "producer nhanh hơn consumer trung bình?" Nếu có → backpressure required.

### "Vì sao không dùng `asyncio.Queue(maxsize=N)` đơn giản?"

`asyncio.Queue` chỉ implement BLOCK policy (khi full, `await put()` block). Đủ cho file batch, KHÔNG đủ cho RTSP (forbidden). Không có DROP_OLDEST built-in. Không có DEGRADE.

→ Custom queue với policy cần thiết.

---

## Pitfalls

### Pitfall 1: Backpressure không observable

```python
# Không metric, không log
queue.put_nowait(frame)
```

→ Bug "latency cao" không trace được vì không thấy drops/blocks.

**Sửa**: emit metric `backpressure_drops_total{source_id, policy}`. Alert khi drops > threshold.

### Pitfall 2: Policy cố định, không adaptive

Tốc độ thực tế biến động (thermal, network, load). Policy fixed = không tối ưu.

**Sửa**: feedback loop. Health signal từ consumer → producer adapt policy.

### Pitfall 3: Backpressure quá aggressive

Drop quá nhiều → detection rate giảm xuống dưới usable. UI nhìn "lag".

**Sửa**: monitor drop rate. Alert > 5% drops trong 5 phút. Investigate consumer chậm sao (GPU thermal? config sai?).

### Pitfall 4: Drop SILENT — không phân biệt với "no event"

```python
if queue.full():
    return  # silent drop
```

→ Caller không biết. Số liệu detection thấp đi không ai biết tại sao.

**Sửa**: trả `ReadStatus.DROPPED` (như Vision Platform). Caller log + đếm.

### Pitfall 5: BLOCK trong async, deadlock

```python
async def producer():
    await queue.put(frame)   # ← block coroutine

async def consumer():
    frame = await queue.get()
```

Nếu chỉ 1 thread chạy event loop và producer + consumer cùng coroutine → deadlock có thể. Cần kiểm tra concurrency model.

→ Vision Platform xử lý cẩn thận: producer là **separate process** (camera proc), không cùng event loop với consumer (inference service).

---

## Liên kết

- File 05 (`05-immutability-and-cow.md`) — frame data trong queue cần immutable, không thì mutate giữa drop.
- Production: `Vision_platform_architecture_design/06-resilience-and-shutdown/` — chi tiết.
- Module 04 file 05 (`05-circuit-breaker-math.md`) — circuit breaker phối hợp với backpressure.

---

## Tóm tắt 1 câu

> **Backpressure = rule không phải exception. 6 policy: DROP_OLDEST/NEWEST, BLOCK, SAMPLE, DEGRADE_QUALITY, REJECT. Whitelist theo source: BLOCK forbidden cho RTSP. Adaptive với feedback loop. Observable qua metric.**

➡️ Tiếp theo: [`05-immutability-and-cow.md`](05-immutability-and-cow.md)
