# 99 — Self-check Module 02

> Pass mới qua Module 03. Trả lời ra giấy/file TRƯỚC khi xem đáp án.

## Hướng dẫn

- 20 câu, chia 4 phần: Recall (5) + Apply (5) + Build (5) + Synthesize (5).
- **Pass criteria**: ≥4/5 mỗi phần.
- Không pass phần nào → đọc lại file tương ứng (cột bên phải).

---

## Phần 1: Recall

### Câu 1
Hexagonal có 3 vòng đồng tâm — list ra. Mũi tên phụ thuộc đi chiều nào?

→ File 01.

### Câu 2
Driving port khác driven port thế nào? Cho 1 ví dụ Vision Platform mỗi loại.

→ File 01.

### Câu 3
Bulkhead trong Vision Platform = process boundary. Tại sao **process** thay vì thread?

→ File 03.

### Câu 4
List 6 backpressure policy. Chỉ ra cái nào **forbidden cho RTSP**, giải thích lý do bằng 1 câu.

→ File 04.

### Câu 5
`@dataclass(frozen=True)` đảm bảo gì? KHÔNG đảm bảo gì? Cho 1 example.

→ File 05.

<details>
<summary>Đáp án Phần 1</summary>

1. **3 vòng**: Domain (trong) — Application (giữa) — Adapters (rìa). Ports nằm ở rìa Application. Mũi tên đi từ ngoài (Adapters) **vào trong** (Domain).

2. **Driving** = "outside calls in to me". Adapter = HTTP server, CLI, message consumer. **Driven** = "I call out". Adapter = DB, API client.
   
   Vision Platform:
   - Driving: SupervisorApp lifecycle (signal handler), Qt event loop (M3), HTTP handler (M4).
   - Driven: `IDataSource` (frame), `IDetector` (inference), `IEventSink` (output).

3. **Process vì**:
   - GIL — Python thread không scale CPU-bound (numpy, image ops).
   - Crash isolation: process die kill chỉ memory đó. Thread die có thể kéo cả process.
   - Resource isolation: 1 process OOM không kéo các process khác.

4. **6 policy**: DROP_OLDEST, DROP_NEWEST, BLOCK, SAMPLE, DEGRADE_QUALITY, REJECT.
   
   **Forbidden**: BLOCK cho RTSP. Lý do: TCP Zero Window cascade — block producer → camera disconnect/drop server-side → reconnect storm cho 16 camera đồng thời.

5. **Đảm bảo**: attribute reassignment fails (`obj.field = ...` raise FrozenInstanceError).
   
   **KHÔNG đảm bảo**: mutate **content** của field nếu field là dict/list/ndarray.
   
   Example:
   ```python
   @dataclass(frozen=True)
   class A:
       items: list
   
   a = A([1,2,3])
   a.items.append(4)   # OK — list mutate được, frozen không chặn
   ```

</details>

---

## Phần 2: Apply

### Câu 6 — Identify pattern violation

Đoạn code sau vi phạm pattern nào? Sửa.

```python
# vision_demo/application/process_stream.py
from cv2 import VideoCapture          # ← (a)
from vision_demo.adapters.kafka_sink import KafkaSink   # ← (b)


class ProcessStreamUseCase:
    def __init__(self):
        self._cap = VideoCapture("rtsp://...")           # ← (c)
        self._sink = KafkaSink(brokers=["localhost"])    # ← (d)
    
    def execute(self):
        ret, frame = self._cap.read()                    # ← (e)
        if not ret:
            return None
        self._sink.emit({"frame_id": ...})
```

→ File 01-02.

### Câu 7 — Pick policy

Bạn build app:
- **Source**: file video MP4 (1080p, 30 FPS, 1 hour).
- **Pipeline**: detection + tracking + lưu DB.
- **Constraint**: lossless (mọi frame phải process). Thời gian không quan trọng.

Pick backpressure policy. Explain.

→ File 04.

### Câu 8 — Bulkhead vs thread

Bạn có pipeline 4 stage:
1. Read RTSP
2. Preprocess (resize)
3. GPU detect
4. Lưu DB

Đặt mỗi stage 1 process? 4 process? 2 process? Lý do.

→ File 03.

### Câu 9 — Spot the immutability bug

```python
@dataclass(frozen=True)
class Snapshot:
    timestamp: float
    metrics: dict[str, float]


def take_snapshots(n):
    snapshots = []
    metrics_pool = {}
    for i in range(n):
        metrics_pool["count"] = i
        snapshots.append(Snapshot(timestamp=time.time(), metrics=metrics_pool))
    return snapshots


s = take_snapshots(5)
print(s[0].metrics)
print(s[4].metrics)
# Bug: cùng giá trị?
```

→ File 05.

### Câu 10 — Read source design

Mở `Vision_platform_architecture_design/03-data-contracts/02-idatasource-t-readresult.md`. Đếm số `ReadStatus` value. Mỗi status có **1 caller behavior** khác. Liệt.

→ File 02.

<details>
<summary>Đáp án Phần 2</summary>

6. **Vi phạm**:
   - (a) Application layer import cv2 (Adapter dependency).
   - (b) Application import KafkaSink (specific adapter).
   - (c) Tự khởi tạo cv2 VideoCapture (không DI).
   - (d) Tự khởi tạo Kafka (không DI).
   - (e) Use case biết frame là tuple (ret, frame) — leak cv2 detail.
   
   **Sửa**:
   ```python
   from vision_demo.kernel.ports.frame_source import IFrameSource
   from vision_demo.kernel.ports.event_sink import IEventSink
   
   class ProcessStreamUseCase:
       def __init__(self, source: IFrameSource, sink: IEventSink):
           self._source = source
           self._sink = sink
       
       def execute(self):
           result = self._source.read()
           if result.status == ReadStatus.FRAME:
               self._sink.emit({"frame_id": ...})
   
   # Composition root: chọn cụ thể
   source = CV2RTSPSource(url=...)
   sink = KafkaSink(brokers=...)
   use_case = ProcessStreamUseCase(source, sink)
   ```

7. **BLOCK** (file batch, lossless required, time không matter). Hoặc DROP_NEWEST nếu đôi khi accept loss để giữ continuity.
   
   File source là **finite** — EOF báo "done" rõ ràng. Không có TCP Zero Window vấn đề. BLOCK an toàn.

8. **2 process**: 1 cho camera reading + preprocess (I/O + light CPU), 1 cho GPU detect. DB save có thể là thread trong process 2.
   
   **Lý do**:
   - Camera reading + preprocess thường thuộc cùng pipeline locality. Tách 4 process = nhiều IPC overhead.
   - GPU detect cần process riêng vì:
     - GPU resource contention.
     - Centralized inference cho multi-camera (1 process serve all).
     - Crash isolation — model crash không kéo camera reading.
   - DB save = I/O bound, có thể thread trong process detect (hoặc tách 3rd process Event Dispatcher như Vision Platform M1).
   
   **Anti-pattern**: 4 process cho 4 stage = unnecessary IPC. Stage là **logical boundary**, không cần process boundary.

9. **Bug**: `metrics_pool` là **cùng dict** được pass vào 5 Snapshot. `Snapshot(metrics=metrics_pool)` không copy. 5 snapshot chia sẻ dict. Mutate `metrics_pool["count"] = i` cuối cùng → tất cả snapshot có `count=4`.
   
   **Sửa**: 
   - Defensive copy lúc construct: `Snapshot(metrics=dict(metrics_pool))`.
   - HOẶC enforce trong `__post_init__` với `MappingProxyType(dict(self.metrics))`.

10. **6 ReadStatus**:
    - `FRAME`: process data.
    - `EOF`: stop loop (file mode) hoặc bug (stream mode).
    - `TIMEOUT`: continue loop, đếm metric.
    - `RECONNECTING`: sleep `retry_after_ms`, retry.
    - `DROPPED`: continue, đếm metric.
    - `ERROR`: log + check fatal, decide stop or continue.
    
    Mỗi status có behavior khác → caller MUST handle explicit.

</details>

---

## Phần 3: Build (code-along ngắn)

### Câu 11 — Build a port + 2 adapters

Trong `_my_workspace/`, build:
- Port `IGreeter` với method `greet(name: str) -> str`.
- Adapter 1: `EnglishGreeter` returns `f"Hello, {name}!"`.
- Adapter 2: `VietnameseGreeter` returns `f"Xin chào, {name}!"`.
- 1 contract test pass cả 2 adapter.

(Không cần submit, chỉ build và verify pass.)

### Câu 12 — Detect bulkhead leak

Đoạn code này **claim** là bulkhead nhưng có leak:

```python
import multiprocessing as mp
import os

LOG_PATH = "/var/log/vision.log"  # shared

def camera_proc(cam_id):
    while True:
        with open(LOG_PATH, "a") as f:
            f.write(f"cam {cam_id} alive\n")

if __name__ == "__main__":
    for cam_id in range(4):
        p = mp.Process(target=camera_proc, args=(cam_id,))
        p.start()
```

Tìm 2 leak. Sửa.

### Câu 13 — Implement adaptive backpressure

Wrap cùng cấu trúc như demo file 04. Thêm logic:
- Bình thường policy = DROP_OLDEST.
- Khi consumer rate < 50% producer rate (phát hiện qua queue depth >80% liên tục 5s) → switch SAMPLE rate=2.
- Khi recovered → switch lại DROP_OLDEST.

Sketch class `AdaptiveBackpressure` với method `set_health(queue_depth, capacity, t)`.

### Câu 14 — True immutable LinkedList

Build `ImmutableList[T]` với:
- `__init__(self, items: Iterable[T])`.
- `append(self, item) -> ImmutableList[T]` — return new list.
- `extend(self, items) -> ImmutableList[T]`.
- `__getitem__`, `__len__`, `__iter__`.
- Immutable: mutate fails.

Tip: store internal as tuple.

### Câu 15 — Hexagonal review

Mở `Vision_platform_architecture_design/02-architecture/01-4-layer-package-tree.md`. Đếm số folder ở mỗi layer. Cho 1 ví dụ file ở mỗi layer.

<details>
<summary>Đáp án Phần 3</summary>

11. **Code**:
    ```python
    # ports/greeter.py
    from typing import Protocol
    
    class IGreeter(Protocol):
        def greet(self, name: str) -> str: ...
    
    # adapters/english_greeter.py
    class EnglishGreeter:
        def greet(self, name: str) -> str:
            return f"Hello, {name}!"
    
    # adapters/vietnamese_greeter.py
    class VietnameseGreeter:
        def greet(self, name: str) -> str:
            return f"Xin chào, {name}!"
    
    # tests/test_greeter_contract.py
    import pytest
    
    @pytest.fixture(params=[EnglishGreeter, VietnameseGreeter])
    def greeter(request):
        return request.param()
    
    def test_greet_returns_str(greeter):
        result = greeter.greet("World")
        assert isinstance(result, str)
        assert "World" in result
    
    def test_greet_handles_empty_name(greeter):
        result = greeter.greet("")
        assert isinstance(result, str)
    ```

12. **Leak 1**: cùng file `LOG_PATH`. 4 process append cùng file. Linux append > 4096B = race. Vision Platform fix với `concurrent_log_handler.ConcurrentRotatingFileHandler` (multi-process safe).
    
    **Leak 2**: không catch exception. Camera process crash → `multiprocessing` không restart. Cần supervisor pattern.
    
    **Sửa**:
    ```python
    LOG_DIR = "/var/log/vision"
    
    def camera_proc(cam_id):
        log_path = f"{LOG_DIR}/cam_{cam_id}.log"   # per-process file
        try:
            while True:
                with open(log_path, "a") as f:
                    f.write(f"cam {cam_id} alive\n")
        except Exception as e:
            print(f"cam {cam_id} died: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Supervisor pattern (file 03):
    while not stop:
        for cid, p in list(procs.items()):
            if not p.is_alive():
                procs[cid] = spawn(cid)   # restart
        time.sleep(0.5)
    ```

13. **Sketch**:
    ```python
    class AdaptiveBackpressure:
        def __init__(self):
            self._policy = BackpressurePolicy.DROP_OLDEST
            self._overload_history: list[tuple[float, bool]] = []  # (timestamp, is_overloaded)
        
        def set_health(self, queue_depth: int, capacity: int, t: float):
            is_overloaded = queue_depth / capacity > 0.8
            self._overload_history.append((t, is_overloaded))
            # Keep only last 5s
            self._overload_history = [
                (ts, ov) for ts, ov in self._overload_history if t - ts < 5.0
            ]
            
            if all(ov for ts, ov in self._overload_history) and len(self._overload_history) > 10:
                self._policy = BackpressurePolicy.SAMPLE
            elif not any(ov for ts, ov in self._overload_history):
                self._policy = BackpressurePolicy.DROP_OLDEST
        
        @property
        def policy(self):
            return self._policy
    ```

14. **Code**:
    ```python
    from typing import Generic, TypeVar, Iterable, Iterator
    
    T = TypeVar("T")
    
    class ImmutableList(Generic[T]):
        __slots__ = ("_items",)
        
        def __init__(self, items: Iterable[T] = ()):
            object.__setattr__(self, "_items", tuple(items))
        
        def __setattr__(self, key, value):
            raise AttributeError(f"ImmutableList is immutable")
        
        def append(self, item: T) -> "ImmutableList[T]":
            return ImmutableList(self._items + (item,))
        
        def extend(self, items: Iterable[T]) -> "ImmutableList[T]":
            return ImmutableList(self._items + tuple(items))
        
        def __getitem__(self, idx: int) -> T:
            return self._items[idx]
        
        def __len__(self) -> int:
            return len(self._items)
        
        def __iter__(self) -> Iterator[T]:
            return iter(self._items)
        
        def __repr__(self) -> str:
            return f"ImmutableList({list(self._items)!r})"
    
    # Test
    a = ImmutableList([1, 2, 3])
    b = a.append(4)
    assert list(a) == [1, 2, 3]   # a unchanged
    assert list(b) == [1, 2, 3, 4]
    
    try:
        a._items = (99,)   # should fail
    except AttributeError:
        pass
    ```

15. **4 layer trong package tree** (xem file `02-architecture/01-...md` để chi tiết):
    - `vision/domain/` — pure logic. Files: `bbox.py`, `coordinate_space.py`, `detection_event.py`.
    - `vision/kernel/` — DTO + ports. Files: `media_packet.py`, `read_result.py`, `ports/data_source_port.py`.
    - `vision/runtime/` — executors, batchers. Files: `executors/sync_linear_executor.py`, `batcher_adaptive.py`.
    - `vision/application/` — use cases. Files: `orchestrators/supervisor_app.py`, `use_cases/process_stream_use_case.py`.
    - `vision/adapters/` — leaf, framework-specific. Files: `sources/ffmpeg_rtsp_source.py`, `inference_runtime/zmq_router_async.py`.
    - `vision/profiles/` — composition roots. Files: `realtime_multicam_profile.py`.

</details>

---

## Phần 4: Synthesize (kết hợp pattern)

### Câu 16 — Pattern composition

Vision Platform M1 (real-time multi-camera) dùng đồng thời:
- Hexagonal (4 layer).
- Bulkhead (mỗi camera 1 process).
- Backpressure (DROP_OLDEST default cho RTSP).
- Immutability (MediaPacket frozen).

Giải thích **dòng dữ liệu** từ "RTSP frame arrived" đến "event written to Kafka":
- Pattern nào hoạt động ở step nào?
- Boundary nào trong dòng?
- Failure point khả năng cao nhất ở đâu?

### Câu 17 — Anti-pattern detection

Bạn review PR đồng nghiệp. Code sau:

```python
# vision_demo/runtime/inference_service.py
from vision_demo.adapters.cv2_rtsp_source import CV2RTSPSource
from vision_demo.adapters.kafka_sink import KafkaSink

class InferenceService:
    def __init__(self):
        self._source = CV2RTSPSource("rtsp://...")
        self._sink = KafkaSink()
        self._buffer = []   # chứa frame nếu inference chậm
    
    def run(self):
        while True:
            frame = self._source.read()
            self._buffer.append(frame)
            
            # Inference
            for f in self._buffer:
                detections = detect(f)
                self._sink.emit(detections)
            
            self._buffer.clear()
```

List **5 vấn đề** với code này theo Module 02 patterns.

### Câu 18 — Trade-off analysis

Sếp: "Em nói pattern Hexagonal tốt. Nhưng dự án mới chỉ 100 dòng code, 1 dev, deploy 1 lần. Tôi không thấy giá trị."

Bạn trả lời thế nào? Nếu đồng ý không cần Hexagonal, đề xuất khi nào nên adopt.

### Câu 19 — Pick architecture for new project

Spec:
- Cảm biến IoT 50 thiết bị, mỗi cảm biến gửi data 10Hz qua MQTT.
- Cần aggregate, detect anomaly, lưu DB.
- 24/7 uptime, on-premise.
- Team 2 dev.

Áp dụng Module 01-02 — vẽ kiến trúc đề xuất. Pattern nào? Tại sao?

### Câu 20 — Module 02 → Module 03 readiness

Bạn cần build `vision_demo_workspace/` ở Module 03 từ con số 0 (workspace folder chứa Python package `vision_demo`). Module 03 yêu cầu bạn vững Module 01-02. Self-assess:

- 1-5 (1 = chỉ vừa nghe, 5 = code thuần thục), bạn thực sự ở mức nào với MỖI pattern?
- Pattern nào weak nhất? Quay lại file đó đọc trước Module 03.

<details>
<summary>Đáp án Phần 4</summary>

16. **Dòng dữ liệu**:
    ```
    [Camera firmware] 
        ↓ RTSP TCP stream
    [Camera process] (Bulkhead — process riêng per camera)
        ├─ Adapter: FFmpegRTSPSource (Hexagonal driven adapter)
        │   └─ Backpressure: DROP_OLDEST nếu SHM slot đầy
        ├─ MediaPacket immutable từ frame ndarray
        ↓ SHM frame bus (Bulkhead boundary 1: process → process)
    [Inference Service process] (Bulkhead — process riêng)
        ├─ Adapter: ShmFrameReader, AsyncInferenceClient
        ├─ Use case: detect batch
        ├─ MediaPacket.with_artifact(DETECTIONS) — CoW
        ↓ ZMQ ROUTER/DEALER (Bulkhead boundary 2)
    [Camera process again] (response routes back)
        ├─ Pipeline stages: tracking, filter, etc.
        ├─ Each stage: with_artifact → new MediaPacket
        ↓ Event sink chain
    [Event Dispatcher process] (Bulkhead — process riêng)
        ├─ Decorator chain: PrivacyFiltered → DLQ → BufferedRetrying → KafkaSink
        ↓ Kafka producer
    [Kafka cluster]
    ```
    
    **Pattern hoạt động**:
    - Hexagonal: ports tách logic và adapter ở mọi boundary.
    - Bulkhead: 3 process boundaries — camera, inference, dispatcher.
    - Backpressure: source → SHM (DROP_OLDEST), inference → ZMQ (HWM), event → buffer (file DLQ overflow).
    - Immutability: MediaPacket immutable cross-thread/process; clone qua wire DTO ở process boundary.
    
    **Failure point khả năng cao nhất**: 
    - **Camera RTSP disconnect** (network, camera reboot) — recovery qua FFmpegRTSPSource reconnect.
    - **Inference Service crash** (CUDA OOM, model corrupt) — circuit breaker on camera side.
    - **Kafka unreachable** — DLQ retry, eventually disk fill.

17. **5 vấn đề**:
    - **Vi phạm dependency direction**: Runtime layer (`inference_service.py`) import Adapter (`cv2_rtsp_source`, `kafka_sink`). Runtime chỉ được biết Port, không Adapter.
    - **Tự khởi tạo dependency**: `self._source = CV2RTSPSource("rtsp://...")` — hardcode URL, không thể test/swap. Phải DI.
    - **`self._buffer = []` unbounded**: vi phạm backpressure. Producer fast → buffer grow → OOM.
    - **Iterate buffer trong loop và clear**: nếu inference chậm, frame mới push vào buffer trong khi đang iterate (nếu concurrent). Race condition + frame loss.
    - **Không phân tách concern**: 1 class làm 4 việc (read source, buffer, inference, sink). Cohesion thấp. Không testable.
    
    **Sửa**: tách thành multiple class với Hexagonal pattern, DI source/sink/detector, dùng SHM thay buffer Python list, có policy backpressure rõ ràng.

18. **Trả lời**:
    "Đồng ý — với 100 LOC, 1 dev, deploy 1 lần, Hexagonal là **over-engineering**. YAGNI áp dụng. Code đơn giản hơn = dễ maintain hơn cho team nhỏ.
    
    **Nhưng** đặt câu hỏi: 
    - Code này **thật sự** sẽ stay 100 LOC? Hay sẽ grow?
    - 1 dev mãi? Hay đội lớn lên?
    - Deploy 1 lần? Hay sẽ có v2, v3?
    
    Nếu trả lời tất cả 'không' → adopt Hexagonal khi:
    - Code vượt ~500 LOC.
    - Có ≥2 dev.
    - Test bắt đầu khó (cần spin up infra).
    - Có yêu cầu chạy 2+ environment (dev/prod, CLI/web).
    
    **Tới điểm nào** là điểm 'pivot' — không phải bắt đầu áp Hexagonal Day 1, cũng không đợi đến khi có 1000 LOC + 5 dev. Quan sát pain points."

19. **Architecture đề xuất**:
    
    ```
    [50 IoT devices]
        ↓ MQTT (1 broker, e.g. Mosquitto)
    [Aggregator process] (single process - 50 device không cần bulkhead per device)
        ├─ MQTT subscriber adapter (driven)
        ├─ Per-device pipeline (in-process):
        │   ├─ DataNormalizationStage
        │   ├─ AnomalyDetectionStage (rule-based ban đầu)
        │   └─ AggregationStage (rolling window)
        ↓ (per device, async)
    [DB writer thread] (driven adapter)
        └─ Postgres time-series
    ```
    
    **Pattern adopt**:
    - **Hexagonal**: yes — ports cho MQTT subscriber, DB writer, anomaly detector. Test logic không cần MQTT/DB thật.
    - **Bulkhead**: NO multi-process. 50 device không CPU-heavy. 1 process + asyncio đủ. Crash isolation theo device không cần — 1 device data corrupt = log, không crash.
    - **Backpressure**: YES — MQTT QoS 1 + bounded queue. Producer (broker) có flow control. Internal queue → DROP_OLDEST nếu DB chậm.
    - **Immutability**: YES — sensor reading DTO immutable.
    
    **Lý do KHÔNG bulkhead**:
    - 50 device data nhỏ (kB, không MB). Không CPU-heavy.
    - 50 process Python = 1.5GB overhead — quá tốn cho IoT use case.
    - Crash isolation theo device không value cao — data có thể skip 1 batch.
    - Single process + asyncio = 50× concurrency với <50MB.
    
    **Pattern thừa khác**:
    - Distributed system, microservices: NO. 2 dev không vận hành nổi.
    - Event Sourcing: NO. Sensor reading không cần replay.

20. *(Câu cá nhân)*. **Nếu**:
    - Hexagonal weak (3-): đọc lại file 01 + 02. Build greeter exercise.
    - Bulkhead weak: file 03. Build supervisor exercise.
    - Backpressure weak: file 04. Implement adaptive policy.
    - Immutability weak: file 05. Build ImmutableList exercise.
    
    **Tip**: nếu cảm thấy ≥3 pattern weak → đừng vội Module 03. Đọc lại files đó trước. Module 03 sẽ áp dụng tất cả 5 pattern đồng thời — yếu pattern nào sẽ vỡ lúc đó.

</details>

---

## Đánh giá

- **Phần 1 (Recall) ≥4/5** + **Phần 2 (Apply) ≥4/5** + **Phần 3 (Build) ≥4/5** + **Phần 4 (Synthesize) ≥3/5** = ✅ Pass tuyệt vời. Sẵn sàng Module 03.
- **Phần 1 + 2 + 3 OK, Phần 4 < 3/5** = ⚠️ Pass yếu. Có thể bắt đầu Module 03 nhưng đọc lại Synthesize đáp án + áp dụng vào dự án thật.
- **Phần 1 + 2 OK, Phần 3 < 4/5** = ❌ Chưa làm code-along đủ. Quay lại Module 02, build các adapter exercises trước Module 03.
- **Phần 1 < 4/5** = ❌ Đọc lại Module 02 từ đầu.

---

## Trước khi sang Module 03

Setup môi trường cho `vision_demo_workspace/` (workspace folder chứa Python package `vision_demo`):

```bash
cd ~/Desktop
mkdir -p vision_demo_workspace
cd vision_demo_workspace

py -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/Mac

pip install --upgrade pip
pip install pytest opencv-python numpy structlog pydantic pyzmq filelock psutil
```

Verify:

```bash
py -c "import cv2, numpy, zmq, structlog, pydantic; print('OK')"
```

Kết quả: `OK`. Sẵn sàng.

---

✅ Hoàn thành Module 02. 

➡️ Tiếp theo: [`../module-03-build-along/00-overview.md`](../module-03-build-along/00-overview.md)
