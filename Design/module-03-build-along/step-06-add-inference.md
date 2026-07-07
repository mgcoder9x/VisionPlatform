# Step 06 — Inference protocol + Detector port + Inline client

> **ERRATA (2026-07-04) — điều chỉnh khi triển khai thật trên `vision_platform`** (Design này viết TRƯỚC #05 nên lệch 2 chỗ; đã valid + duyệt, xem `implement/06-inference-inline/00-brief.md` + journal D-023/C-007):
> - **E-06-1 (kiến trúc):** `InlineInferenceClient` KHÔNG đặt ở `adapters/` mà ở **`application/`**. Lý do: contract import-linter "Adapters la leaf" CẤM `adapters→runtime`, nhưng client phải import `runtime.ipc.ShmFrameReader`. Bản chất: client là service điều phối (runtime reader + `IDetector` port DI), không phải leaf-adapter. `FakeDetector` vẫn ở `adapters/` (leaf hợp lệ).
> - **E-06-2 (tích hợp switchover #05):** `InferenceRequest` KHÔNG dùng field rời `shm_ring_name/shm_slot/shm_generation`, mà **nhúng thẳng `frame_ref: ShmFrameRefData`** (gồm `ring_epoch`). Client gọi `reader.read_ref(frame_ref)` → hưởng stale-check P0-3 (ref epoch cũ sau switchover → trả None, không đọc nhầm frame). Design gốc thiếu `ring_epoch` vì viết trước khi #05 thêm epoch.
> - Bằng chứng: `pytest tests/test_step_06_inference.py` = 9 passed; full 261 passed/1 skipped; `lint-imports` 5 kept/0 broken.

## Mục tiêu (3h)

Build inference layer:

1. `kernel/inference_protocol.py` — DTOs cho request/response.
2. `kernel/ports/detector.py` — `IDetector` Protocol.
3. `adapters/fake_detector.py` — Detector giả implements port.
4. `adapters/inline_inference_client.py` — In-process inference (no IPC).

**Đã verify**: 9 test pass.

> **Lưu ý**: vision_demo dùng "inline" client (single-process). Vision Platform production dùng ZMQ ROUTER/DEALER cross-process. Inline đủ để học **request_id correlation pattern** mà không phải debug ZMQ.

---

## Phần 1 — Inference DTOs (30 phút)

```python
# src/vision_demo/kernel/inference_protocol.py
"""Inference request/response protocol — DTOs cho IPC.

Wire format: msgpack (handled by ZMQ adapter).
Domain DTO ở đây — không tham chiếu zmq.

Detection mang BBox (domain value object) có CoordinateSpace tag — KHÔNG dùng
raw x/y/w/h. Đây là invariant từ Step 02: mọi toạ độ phải gắn space để tránh
bug resize/letterbox. inference_protocol ở kernel/ được phép import domain/.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from vision_demo.domain.bbox import BBox


@dataclass(frozen=True)
class InferenceRequest:
    """Request gửi từ camera process → inference service."""
    request_id: str          # UUID — correlation key
    source_id: str           # camera_id
    shm_ring_name: str
    shm_slot: int
    shm_generation: int
    height: int
    width: int
    channels: int


@dataclass(frozen=True)
class InferenceError:
    error_type: str
    error_message: str
    retryable: bool


@dataclass(frozen=True)
class Detection:
    """Pure detection result. Không phụ thuộc model.

    `box` là BBox có CoordinateSpace tag — detector PHẢI khai báo toạ độ của
    nó ở space nào (thường MODEL_INPUT khi vừa ra khỏi model). Downstream
    muốn vẽ lên frame gốc phải transform về ORIGINAL_FRAME trước.
    """
    label: str
    confidence: float
    box: BBox


@dataclass(frozen=True)
class InferenceResponse:
    request_id: str          # echo to correlate
    detections: tuple[Detection, ...] = field(default_factory=tuple)
    error: Optional[InferenceError] = None
    
    @property
    def is_success(self) -> bool:
        return self.error is None
```

**Decisions**:

### `request_id` correlation

Đây là **kỹ thuật critical** trong async IPC:

- Camera 1 send req `id="r1"`, camera 2 send `id="r2"`.
- Inference service xử lý batch — có thể trả `r2` trước `r1` (depends on schedule).
- Mỗi camera nhận response → match `request_id` để biết của mình.

**Không có request_id** = camera 1 nhận response của r2 → tracking lệch khắp nơi.

→ Vision Platform full ZMQ implementation: server-side dedup, client-side correlation map (`request_id → asyncio.Future`).

### `Detection` không phụ thuộc model, nhưng toạ độ luôn có space

Detection là **domain DTO**. Adapter (YOLO/RTMDet/...) trả raw output → convert thành Detection.

→ Đổi YOLO sang RTMDet: chỉ adapter đổi. Detection class không động.

**Quan trọng (invariant từ Step 02):** `Detection.box` là `BBox` có `CoordinateSpace` tag, KHÔNG phải 4 số `x/y/w/h` trần. Lý do: model nhận frame đã resize/letterbox (ví dụ 640×640 = `MODEL_INPUT`), nhưng UI vẽ trên frame gốc (`ORIGINAL_FRAME`). Nếu Detection chỉ mang số trần, downstream không biết toạ độ thuộc space nào → vẽ lệch. Bắt buộc `space` ép mọi consumer phải transform trước khi dùng — chính là bug kinh điển mà Step 02 dạy cách chặn. Đặt raw float vào Detection = bypass pattern vừa học.

### `InferenceError` có `retryable` field

Production: phân biệt error retryable (timeout, transient) vs non-retryable (CUDA OOM, bad input). Camera-side circuit breaker dùng để decide.

vision_demo: simplified — luôn `retryable=False`.

---

## Phần 2 — IDetector port (15 phút)

```python
# src/vision_demo/kernel/ports/detector.py
"""IDetector — driven port cho object detection."""
from typing import Protocol
import numpy as np
from vision_demo.kernel.inference_protocol import Detection


class IDetector(Protocol):
    """Detector interface. Implementation có thể là YOLO, RTMDet, fake..."""
    def detect(self, frame: np.ndarray) -> list[Detection]: ...
    
    def setup(self) -> None: ...
    
    def teardown(self) -> None: ...
```

→ Same pattern như `IFrameSource` Step 03.

---

## Phần 3 — FakeDetector adapter (30 phút)

```python
# src/vision_demo/adapters/fake_detector.py
"""Fake detector adapter: trả detection giả deterministic theo frame."""
import numpy as np
from vision_demo.domain.bbox import BBox, CoordinateSpace
from vision_demo.kernel.inference_protocol import Detection


class FakeDetector:
    """Detector giả — confidence dựa trên brightness frame.
    
    Logic giả: 1 detection cho mỗi frame, label = 'object',
    confidence = brightness / 255. Box ở MODEL_INPUT space (toạ độ trên
    frame mà detector nhận vào).
    """
    
    def __init__(self):
        self._is_setup = False
    
    def setup(self) -> None:
        self._is_setup = True
    
    def teardown(self) -> None:
        self._is_setup = False
    
    def detect(self, frame: np.ndarray) -> list[Detection]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before detect()")
        
        h, w = frame.shape[:2]
        brightness = float(frame.mean())
        
        return [
            Detection(
                label="object",
                confidence=brightness / 255.0,
                box=BBox(
                    x=w * 0.25,
                    y=h * 0.25,
                    w=w * 0.5,
                    h=h * 0.5,
                    space=CoordinateSpace.MODEL_INPUT,
                ),
            )
        ]
```

**Decisions**:

- **Deterministic detection** từ brightness — test verify được.
- **Setup required** check — fail-fast nếu quên init model.
- 1 fake bbox tâm frame, 50% size — non-trivial enough cho test pipeline downstream.

---

## Phần 4 — InlineInferenceClient (45 phút)

```python
# src/vision_demo/adapters/inline_inference_client.py
"""Inline inference client — chạy detector cùng process (no IPC).

Tested cho dev/test. Production dùng ZMQ client (Vision Platform).
"""
from typing import Optional
from vision_demo.kernel.inference_protocol import (
    InferenceRequest, InferenceResponse, InferenceError, Detection,
)
from vision_demo.kernel.ports.detector import IDetector
from vision_demo.runtime.ipc.shm_frame_ring import ShmFrameReader, ShmRingBuffer


class InlineInferenceClient:
    """Single-process inference: read frame from SHM, detect, return response."""
    
    def __init__(self, ring: ShmRingBuffer, detector: IDetector):
        self._ring = ring
        self._reader = ShmFrameReader(ring)
        self._detector = detector
    
    def setup(self) -> None:
        self._detector.setup()
    
    def teardown(self) -> None:
        self._detector.teardown()
    
    def infer(self, request: InferenceRequest) -> InferenceResponse:
        # 1. Read frame from SHM.
        frame = self._reader.read(request.shm_slot, request.shm_generation)
        
        if frame is None:
            return InferenceResponse(
                request_id=request.request_id,
                error=InferenceError(
                    error_type="ShmReadFailed",
                    error_message=(
                        f"Slot {request.shm_slot} gen {request.shm_generation} "
                        "not readable (overwritten or in wrong state)"
                    ),
                    retryable=False,
                ),
            )
        
        # 2. Detect.
        try:
            dets = self._detector.detect(frame)
            return InferenceResponse(
                request_id=request.request_id,
                detections=tuple(dets),  # freeze list → tuple at DTO boundary
            )
        except Exception as e:
            return InferenceResponse(
                request_id=request.request_id,
                error=InferenceError(
                    error_type=type(e).__qualname__,
                    error_message=str(e),
                    retryable=False,
                ),
            )
```

**Decisions**:

### Why "Inline"?

vision_demo demo client trong **cùng process** với caller. Không IPC.

- **Pros**: easier test, không cần spawn process.
- **Cons**: không bulkhead — detector crash kéo cả app.

→ Production Vision Platform có `AsyncInferenceClient` qua ZMQ. Pattern same: `request_id` correlation, `InferenceResponse` echo back. Chỉ khác: ZMQ DEALER socket + async receive task + future map.

### Error handling — không retain Exception

```python
except Exception as e:
    return InferenceResponse(
        ...
        error=InferenceError(
            error_type=type(e).__qualname__,   # ← string only
            error_message=str(e),               # ← string only
            retryable=False,
        ),
    )
```

→ R5-CRITICAL-02 pattern again. `InferenceError` chỉ giữ string. Không reference `e` Exception trực tiếp.

---

## Phần 5 — Tests (30 phút)

Test file `tests/test_step_06_inference.py` có **9 test**:

1. **Detector** (3): returns 1 detection, requires setup, confidence scales với brightness.
2. **DTO** (3): is_success, immutable, error case.
3. **Inline client** (3): end-to-end, stale generation, request_id correlation.

Test correlation quan trọng:

```python
def test_inline_client_correlates_request_id(ring):
    """Multiple requests, response.request_id must match request.request_id."""
    detector = FakeDetector()
    client = InlineInferenceClient(ring, detector)
    client.setup()
    
    writer = ShmFrameWriter(ring)
    refs = []
    for i in range(3):
        f = np.full((20, 20, 3), 50 + i, dtype=np.uint8)
        refs.append(writer.write(f))
    
    for i, ref in enumerate(refs):
        req = InferenceRequest(
            request_id=f"req_{i}",
            source_id="cam1",
            shm_ring_name=ring.name,
            shm_slot=ref.slot,
            shm_generation=ref.generation,
            height=ref.height, width=ref.width, channels=ref.channels,
        )
        resp = client.infer(req)
        assert resp.request_id == f"req_{i}"   # correlation guaranteed
    
    client.teardown()
```

→ Chứng minh **mọi request có response correlation đúng**. Trong production async ZMQ, đây là invariant phải maintain.

**Run**:
```bash
pytest tests/test_step_06_inference.py -v
```

Expected: **9 passed in ~0.3s**.

---

## Self-check

1. **Tại sao request_id phải có** trong async IPC? Cho 1 scenario bug nếu không có.

2. **InlineInferenceClient** tại sao không thực sự "Inline" trong production? Sao không dùng?

3. **`InferenceError.retryable`** — khi nào set True, khi nào False? Cho 3 ví dụ mỗi loại.

4. **Detection class không phụ thuộc YOLO** — pros/cons khi đổi sang model khác?

5. **Reader trong InlineInferenceClient** dùng `ShmFrameReader` từ Step 05. Sao không cách nào để inline detector "skip" SHM (vì cùng process)?

<details>
<summary>Đáp án</summary>

1. **Bug scenario**:
   - Camera 1 send detect req at t=0.
   - Camera 2 send detect req at t=1.
   - GPU batches → process cam2 first (smaller frame), cam1 second.
   - Response order: cam2 then cam1.
   - **Without request_id**: client cam1 nhận response cam2 → wrong detection cho cam1.
   - **With request_id**: client correlate qua map `request_id → Future`. Mỗi camera lấy đúng response của mình.

2. **InlineClient không Inline production vì**:
   - Detector + camera cùng process → 1 GPU CUDA crash kéo cả camera. Không bulkhead.
   - Detector cần GPU access → all camera processes cần CUDA driver. OOM 1 camera = OOM all.
   - Centralized inference (1 detector serve N camera) cần process boundary để batch + share GPU.
   - Vision Platform `AsyncInferenceClient` → ZMQ ROUTER/DEALER → camera process light-weight, inference process heavy.

3. **`retryable=True`**:
   - Network timeout (ZMQ deadline).
   - Inference queue full (transient backpressure).
   - GPU thermal throttle (will recover).
   
   **`retryable=False`**:
   - CUDA out-of-memory (re-try sẽ OOM lại).
   - Bad input shape (deterministic).
   - Model not loaded (config issue).

4. **Detection independent**:
   - **Pros**: đổi YOLO → RTMDet → DINO → chỉ adapter `YoloAdapter`/`RtmdetAdapter`/`DinoAdapter` đổi. Use case + tracker + sink không động.
   - **Cons**: thông tin model-specific (e.g. mask cho instance segmentation, keypoints) không có trong Detection. Cần extend (e.g. `DetectionWithMask` subclass).
   - Trade-off: **simple core + extensibility** vs full feature.
   - **Lưu ý invariant**: `Detection.box` là `BBox` có `CoordinateSpace` (Step 02), không phải float trần. Adapter chịu trách nhiệm khai báo đúng space (thường `MODEL_INPUT`); downstream transform về `ORIGINAL_FRAME`/`DISPLAY` khi cần vẽ. Đây là chỗ pattern coordinate-space được áp dụng xuyên suốt, không bị bypass ở boundary inference.

5. **Why not skip SHM trong inline?**:
   - Skip SHM = pass `np.ndarray` trực tiếp qua method call → ~0.1µs (pointer copy). Vs SHM ~5µs.
   - **Trade-off**:
     - Pros: faster.
     - Cons: KHÁC API với production (ZMQ + SHM). Test inline không catch SHM bug. Refactor sau khó.
   - vision_demo decision: **same API as production** để học pattern, accept ~5µs cost.
   - Production option: `inline` mode for development, `centralized_zmq` for production. Same `IInferenceClient` interface.

</details>

---

## Liên kết

- **Module 02 file 02** — port + adapter pattern.
- **Production**: `Vision_platform_architecture_design/05-inference-and-ipc/05-inference-protocol.md`, `08-inference-client.md`.

---

➡️ Tiếp theo: [`step-07-add-backpressure.md`](step-07-add-backpressure.md)
