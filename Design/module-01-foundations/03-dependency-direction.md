# 03 — Chiều phụ thuộc (Dependency Direction)

## TL;DR (30 giây)

> **Quy tắc vàng**: Code "ổn định" KHÔNG được phụ thuộc code "biến động". Phụ thuộc đi NGƯỢC chiều — code biến động phụ thuộc code ổn định, không bao giờ ngược lại.
>
> Trong Vision Platform: **Domain ổn định nhất → Adapter biến động nhất**. Phụ thuộc đi từ Adapter → Application → Runtime → Kernel → Domain. KHÔNG có mũi tên đi ngược.

---

## Mental hook

Bạn vừa đọc file 02 — biết rồi: low coupling = "đổi B không kéo A đổi". Nhưng có vấn đề tinh tế hơn: **không phải mọi B "không nên đổi"**.

Cụ thể: bạn có 2 module:
- `BBox` (value object hình học) — định nghĩa 5 năm rồi, hiếm khi đổi.
- `YOLOv5Adapter` — wrapper cho thư viện YOLOv5. Năm sau đổi YOLOv8. Năm sau nữa đổi RTMDet.

Câu hỏi: ai phụ thuộc ai?

**Trường hợp 1**: `BBox` import `YOLOv5Adapter` để biết format detection.

→ Khi đổi YOLOv5 → YOLOv8, BBox phải đổi theo. Mọi code khắp dự án dùng BBox phải đổi. **Cascading nightmare**.

**Trường hợp 2**: `YOLOv5Adapter` import `BBox` để chuyển format YOLO ra `BBox`.

→ Khi đổi YOLOv5 → YOLOv8, chỉ adapter mới đổi. BBox không động. Mọi code dùng BBox không động.

→ Quyết định **chiều mũi tên** này quan trọng hơn nhiều người nghĩ. Đây là quyết định **kiến trúc cốt lõi**.

---

## Câu chuyện: tại sao USB ngược?

Bạn cắm USB. 50% xác suất sai chiều. Lật lại. Giờ đúng. Tại sao thiết kế khó chịu vậy?

Trả lời: USB-A có 1 chiều cứng cố định **vì giao tiếp định nghĩa từ phía host**. PC host định nghĩa pin layout. USB device phải "tuân theo" host.

Pin "host" không bao giờ đổi (USB-A spec từ 1996). Pin "device" có hàng tỉ thiết bị (chuột, bàn phím, ổ cứng, camera...) — **biến động vô tận**. Spec USB-A đặt **cấu trúc cố định ở phía host**, **biến động ở phía device** — và chiều phụ thuộc đi từ device → host.

Áp dụng cho code: **đặt cấu trúc cố định ở "domain core"**, **biến động ở "adapter"**. Mũi tên phụ thuộc đi từ adapter → core, không bao giờ ngược.

---

## Định nghĩa: Stable Dependencies Principle

Robert C. Martin (Uncle Bob) phát biểu trong "Clean Architecture":

> **Stable Dependencies Principle**: Phụ thuộc đi theo hướng tăng dần độ stability. Module ổn định không được phụ thuộc module ít ổn định.

**Stability** đo bằng:

```
Stability = số module phụ thuộc bạn / (số module phụ thuộc bạn + số bạn phụ thuộc)

Range: 0 (most unstable) → 1 (most stable)
```

- Stability = 1: **Mọi người đều dùng nó, nó dùng 0 thứ**. Ví dụ: `BBox`. Đổi nó = đau cả hệ thống.
- Stability = 0: **Không ai dùng nó, nó dùng nhiều thứ**. Ví dụ: `__main__.py`. Đổi nó = không ai biết.

**Quy tắc**: Module stability cao **được** import bởi module stability thấp, không bao giờ ngược lại.

---

## Vấn đề "Stable Dependencies bị đảo chiều"

Đây là bug kiến trúc số 1 mà junior dev mắc. Ví dụ:

### Anti-pattern: Domain phụ thuộc Adapter

```python
# domain/bbox.py — ĐÁNG LẼ STABLE, không phụ thuộc gì
from yolov5.detect import YOLODetection   # ← SAI

class BBox:
    @classmethod
    def from_yolo(cls, det: YOLODetection) -> "BBox":
        ...
```

**Vấn đề**:
- `BBox` (stable) phụ thuộc `yolov5` library (unstable — version đổi liên tục).
- Đổi YOLO version → BBox phải đổi → mọi code dùng BBox phải đổi.
- Test BBox cần install YOLO. CI chậm.
- **Vi phạm Stable Dependencies Principle**.

### Pattern đúng: Dependency Inversion

```python
# domain/bbox.py — STABLE
from dataclasses import dataclass

@dataclass(frozen=True)
class BBox:
    x: float; y: float; w: float; h: float
    # KHÔNG biết YOLO là gì.


# adapters/yolov5_adapter.py — UNSTABLE
from yolov5.detect import YOLODetection
from domain.bbox import BBox

def yolo_to_bbox(det: YOLODetection) -> BBox:
    return BBox(x=det.x, y=det.y, w=det.w, h=det.h)
```

→ Mũi tên: `yolov5_adapter` → `BBox`. Đúng chiều.

→ Đây gọi là **Dependency Inversion Principle** (chữ **D** trong SOLID).

---

## 4 Layer của Vision Platform — chiều phụ thuộc

Lý do thiết kế 4 layer như trong `Vision_platform_architecture_design/02-architecture/01-4-layer-package-tree.md`:

```
                      STABILITY
                         ▲
                         │ cao
                ┌────────┴────────┐
                │     Domain      │  ← BBox, CoordinateSpace, DetectionEvent
                │  (pure logic)   │     hầu như không bao giờ đổi
                └────────┬────────┘
                         │ phụ thuộc xuống
                ┌────────┴────────┐
                │     Kernel      │  ← MediaPacket, Ports, StageResult
                │  (DTOs, ports)  │     đôi khi đổi (thêm artifact key)
                └────────┬────────┘
                         │
                ┌────────┴────────┐
                │     Runtime     │  ← Executors, Batchers, Services
                │  (machinery)    │     đổi khi performance tune
                └────────┬────────┘
                         │
                ┌────────┴────────┐
                │   Application   │  ← Use cases, Orchestrators
                │ (orchestration) │     đổi theo nhu cầu nghiệp vụ
                └────────┬────────┘
                         │
                ┌────────┴────────┐
                │    Adapters     │  ← cv2, ZMQ, Postgres, Qt, OpenAI...
                │  (3rd-party)    │     đổi theo version thư viện
                └─────────────────┘
                         ▼
                       STABILITY
                         thấp
```

**Quy tắc**: mũi tên import CHỈ đi xuống (top → bottom), không bao giờ đi lên.

- Domain `import` 0 thứ ngoài Python stdlib + numpy (numpy là math infrastructure, không phải framework).
- Kernel `import` Domain.
- Runtime `import` Kernel + Domain qua port.
- Application `import` mọi thứ qua port.
- Adapters `import` Kernel/Domain để implement port.

**Application và Adapter cùng level** (có thể nói là "không phụ thuộc lẫn nhau"). Application **chọn** adapter ở composition root.

---

## Mental model: cây + lá

Tưởng tượng cấu trúc cây:

```
              [Domain] (rễ — sống lâu, bất biến)
                 │
              [Kernel] (thân — dày, ít đổi)
                 │
              [Runtime] (cành lớn)
                 │
            [Application] (cành nhỏ)
                 │
              [Adapters] (lá — rụng theo mùa)
```

- **Lá rụng** (đổi version YOLO, ZMQ, cv2) → cành không động. Thân không động. Rễ không động.
- **Rễ đổi** (đổi BBox semantics) → toàn bộ cây phải uốn lại. Cẩn thận.

→ Đây là why "domain stable, adapter volatile". Đặt biến động ở **lá**, không phải ở **rễ**.

---

## Cách CHECK chiều phụ thuộc đã đúng chưa

### Cách 1: visual — vẽ graph

Dùng `pydeps` hoặc `import-linter` để vẽ graph dependency:

```bash
pip install pydeps
pydeps your_package --max-bacon=2
```

Nếu thấy **mũi tên đi từ domain → adapter** → SAI.
Nếu thấy **cycle** (A → B → A) → SAI cực nặng.

### Cách 2: code — `import-linter`

Vision Platform dùng `import-linter` để CI-enforce. Ví dụ rule:

```toml
# pyproject.toml
[tool.importlinter]
root_package = "vision"

[[tool.importlinter.contracts]]
name = "Domain is pure"
type = "forbidden"
source_modules = ["vision.domain"]
forbidden_modules = [
    "vision.kernel",
    "vision.runtime",
    "vision.application",
    "vision.adapters",
    "PyQt6", "fastapi", "cv2",   # framework
]
```

→ Nếu domain accidentally `import cv2` → CI fail. **Bug kiến trúc bắt ở compile time.**

### Cách 3: thủ công — đọc imports

Mở 1 file domain. Đọc các dòng `import`. Nếu thấy:
- ✅ `from typing`, `from dataclasses`, `import numpy as np` → OK
- ❌ `import cv2` / `from PyQt6 import` / `from fastapi import` → vi phạm

Mở 1 file adapter. Đọc imports:
- ✅ `from vision.domain import BBox`, `from vision.kernel import MediaPacket` → OK
- ❌ `from vision.application import SomeUseCase` → SAI (adapter đang phụ thuộc application?!)

---

## Tinh tế: Dependency Inversion Principle (DIP)

DIP là **kỹ thuật** để ép mũi tên đi đúng chiều khi tự nhiên nó muốn đi sai chiều.

### Trường hợp tự nhiên muốn đi sai chiều

Use case `ProcessStreamUseCase` cần đọc frame từ source. "Tự nhiên" là:

```python
# application/process_stream.py
from adapters.cv2_rtsp_source import CV2RTSPSource   # ← application → adapter

class ProcessStreamUseCase:
    def __init__(self):
        self._source = CV2RTSPSource("rtsp://...")    # tự tạo
```

→ Application phụ thuộc Adapter. **SAI** theo Stable Dependencies Principle (adapter unstable hơn).

### Cách invert chiều: định nghĩa interface ở phía stable

```python
# kernel/ports/data_source_port.py — STABLE
from typing import Protocol

class IDataSource(Protocol):
    def read(self) -> Frame: ...


# application/process_stream.py
from kernel.ports.data_source_port import IDataSource    # ← application → kernel (stable)

class ProcessStreamUseCase:
    def __init__(self, source: IDataSource):    # nhận từ ngoài
        self._source = source


# adapters/cv2_rtsp_source.py — UNSTABLE
from kernel.ports.data_source_port import IDataSource    # ← adapter → kernel (stable)

class CV2RTSPSource:
    """Implements IDataSource."""
    def read(self) -> Frame: ...
```

Bây giờ:
- Application → Kernel ✓
- Adapter → Kernel ✓
- **Application không phụ thuộc Adapter** ✓
- **Adapter "thực hiện" interface mà Application yêu cầu** — chiều phụ thuộc đảo ngược.

Composition root (file `__main__.py`) là chỗ duy nhất "biết" cụ thể adapter nào, "wire" lại:

```python
# main.py — composition root
def main():
    source = CV2RTSPSource(...)            # adapter cụ thể
    use_case = ProcessStreamUseCase(source)   # inject vào application
    use_case.run()
```

→ Toàn bộ code khác KHÔNG biết tồn tại của `CV2RTSPSource`. Đổi adapter chỉ sửa `main.py`.

---

## Code-along (15 phút)

Tạo `_dep_demo/`:

```bash
mkdir _dep_demo
cd _dep_demo
```

Tạo `_dep_demo/domain.py`:

```python
"""Domain - stable, không phụ thuộc gì ngoài stdlib."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x: float; y: float; w: float; h: float
```

Tạo `_dep_demo/ports.py`:

```python
"""Kernel ports - stable interface."""
from typing import Protocol, Iterable
from .domain import Detection


class IDetector(Protocol):
    def detect(self, frame_bytes: bytes) -> Iterable[Detection]: ...
```

Tạo `_dep_demo/use_case.py`:

```python
"""Application - phụ thuộc port, không phụ thuộc adapter cụ thể."""
from .ports import IDetector


class CountObjectsUseCase:
    def __init__(self, detector: IDetector):
        self._detector = detector

    def count_in_frame(self, frame_bytes: bytes) -> dict[str, int]:
        dets = self._detector.detect(frame_bytes)
        counts: dict[str, int] = {}
        for d in dets:
            counts[d.label] = counts.get(d.label, 0) + 1
        return counts
```

Tạo `_dep_demo/adapter_fake.py`:

```python
"""Adapter giả — implement port với fake data."""
from .ports import IDetector
from .domain import Detection


class FakeDetector:
    def detect(self, frame_bytes):
        # Trả 3 detection giả
        yield Detection("person", 0.9, 0, 0, 100, 200)
        yield Detection("person", 0.8, 50, 50, 100, 200)
        yield Detection("car",    0.7, 200, 100, 80, 60)
```

Tạo `_dep_demo/__main__.py`:

```python
from .use_case import CountObjectsUseCase
from .adapter_fake import FakeDetector


def main():
    detector = FakeDetector()
    uc = CountObjectsUseCase(detector)
    counts = uc.count_in_frame(b"...fake bytes...")
    print(counts)


if __name__ == "__main__":
    main()
```

Chạy:

```bash
py -m _dep_demo
```

Output:
```
{'person': 2, 'car': 1}
```

**Bài tập 1**: Bây giờ thêm 1 adapter mới `YoloAdapter` (không cần code thật, mock thôi). Đoán: bạn phải sửa file nào?

→ Đáp án: chỉ tạo file mới `adapter_yolo.py`, sửa 1 dòng `__main__.py`. KHÔNG đụng vào `use_case.py`, `ports.py`, `domain.py`.

**Bài tập 2**: Vẽ graph dependency:

```bash
pip install pydeps
pydeps _dep_demo --max-bacon=3 --output dep.svg
```

Mở `dep.svg`. Xác minh: tất cả mũi tên đi từ ngoài (`__main__`, `adapter_fake`) → trong (`use_case`, `ports`, `domain`). Không có mũi tên ngược.

---

## Checkpoint

Mở `_my_answers.md`, trả lời:

1. Domain layer **được phép import** những gì? Cho 3 thứ.

2. Tại sao numpy được phép trong Domain nhưng cv2 thì không? (Hint: ADR-022 trong design.)

3. Adapter `RTSPSource` có thể import `ProcessStreamUseCase` không? Tại sao?

4. Trong Vision Platform, `composition root` là file nào? Tại sao chỉ chỗ đó "biết" cụ thể adapter?

5. Bạn thấy code: `from vision.adapters.qt_window import QtWindow` xuất hiện trong `vision/runtime/inference_service.py`. Đúng hay sai? Sửa thế nào?

<details>
<summary>Đáp án gợi ý</summary>

1. Stdlib (typing, dataclasses, datetime, enum), `numpy` (math infrastructure), không gì khác. KHÔNG cv2/torch/PyQt/fastapi.

2. **Numpy** là toán học cơ bản — bạn không thể biểu diễn `BBox` mà thiếu math. Numpy stable theo nghĩa "tồn tại 20 năm, API không đổi". **Cv2** là implementation cụ thể của image processing — domain không nên biết cv2 hay PIL hay scikit-image. ADR-022 quy định numpy = "stable math infrastructure".

3. KHÔNG. Vi phạm dependency direction. Adapter ở **lá**, application ở **cành** — lá không phụ thuộc cành. Adapter chỉ phụ thuộc Kernel/Domain (port + DTO).

4. Composition root = `vision/main.py` (hoặc orchestrator như `qt_desktop_app.py`, `supervisor_app.py`). Chỉ chỗ này "biết" cụ thể adapter để **wire** lại. Lý do: nếu nhiều file biết cụ thể adapter → đổi adapter phải sửa nhiều file. Composition root = single source of truth cho wiring.

5. **SAI**. Runtime đang import Adapter — vi phạm chiều phụ thuộc. Sửa: tạo port (interface) ở Kernel, ví dụ `IUIPresenter`. `inference_service` import `IUIPresenter`. `QtWindow` implement `IUIPresenter`. Composition root inject `QtWindow` vào `inference_service`.

</details>

---

## Trade-offs

### "Tôi phải tạo port cho MỌI adapter?"

KHÔNG. Quy tắc thực tế:

- **Có port nếu** sẽ có ≥ 2 implementation (test mock + real, hoặc 2 real). Hoặc nếu adapter ở phía stable (kernel/runtime).
- **KHÔNG cần port nếu** chỉ có 1 implementation đời đời và adapter ở leaf. Ví dụ: `JsonLogFormatter` chỉ format log — không có alternative cần thiết.

**YAGNI**: thêm port khi có **lý do hôm nay** (test, alternative). Không "có thể cần sau".

### "Composition root quá to thì sao?"

Composition root có thể chia thành nhiều **profile**:

```python
# profiles/realtime_multicam_profile.py
def compose(config) -> SupervisorApp: ...

# profiles/batch_processing_profile.py
def compose(config) -> BatchApp: ...
```

Mỗi profile = 1 composition cho 1 deployment mode. `main.py` chỉ dispatch:

```python
PROFILES = {
    "realtime_multicam": realtime_multicam_profile.compose,
    "batch_processing": batch_processing_profile.compose,
    "interactive_desktop": qt_desktop_profile.compose,
}

def main():
    config = load_config()
    app = PROFILES[config.profile](config)
    app.run()
```

→ Composition root vẫn "biết tất cả adapters" nhưng được tổ chức theo deployment context. Đây chính là pattern Vision Platform dùng.

### "Test code đặt ở layer nào?"

Test = **không phải production code**. Test có thể "vi phạm" dependency direction (ví dụ test domain mock các thứ kiến trúc rộng) — chấp nhận được vì test không ship.

Chỉ cấm: **production import test code**. Đó mới là sai.

---

## Liên kết

- File 04 (`04-context-matters-no-best-architecture.md`) — bao giờ chiều phụ thuộc strict cần nới lỏng.
- Production: `Vision_platform_architecture_design/02-architecture/02-dependency-direction.md` (file gốc) — concrete rules + import-linter contracts.
- Module 02 file 01 (`01-hexagonal-architecture-from-scratch.md`) — pattern này = Hexagonal Architecture.
- Sách: "Clean Architecture" — Robert C. Martin. Chương 11 (DIP), 13 (Component Cohesion), 14 (Component Coupling).

---

## Tóm tắt 1 câu

> **Mũi tên import luôn đi từ unstable → stable. Domain stable nhất. Adapter unstable nhất. Application chọn adapter cụ thể tại composition root, mọi nơi khác chỉ thấy port.**

➡️ Tiếp theo: [`04-context-matters-no-best-architecture.md`](04-context-matters-no-best-architecture.md)
