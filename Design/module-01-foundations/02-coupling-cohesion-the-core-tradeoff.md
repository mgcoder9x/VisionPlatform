# 02 — Coupling và Cohesion — đại lượng cốt lõi nhất

## TL;DR (30 giây)

> **Coupling** = mức độ A phụ thuộc vào B. Càng cao → đổi B kéo theo phải đổi A.
>
> **Cohesion** = mức độ các phần BÊN TRONG 1 module gắn với nhau theo cùng 1 mục đích. Càng cao → module dễ hiểu, dễ maintain.
>
> **Mục tiêu kiến trúc**: **Low coupling + high cohesion**. Hai đại lượng này quyết định 80% chất lượng kiến trúc bạn.

---

## Mental hook

Tưởng tượng bạn maintain dự án HeadDetect. Sếp yêu cầu: "Đổi camera RTSP sang dùng webcam USB cho demo nội bộ."

Bạn mở code. Đếm số file phải sửa:

**Trường hợp A** (coupling cao):
- `main.py` — đoạn import `cv2.VideoCapture` ngay vào main
- `camera_loop.py` — hàm `read_rtsp_frame` hard-coded URL
- `inference_thread.py` — gọi `read_rtsp_frame` trực tiếp
- `ui_window.py` — gọi `read_rtsp_frame` để show preview

→ Đổi sang webcam = sửa 4 file. Risk: quên 1 file → demo crash.

**Trường hợp B** (coupling thấp):
- `domain/data_source_port.py` — interface `IDataSource`
- `adapters/rtsp_source.py` — implement bằng cv2 RTSP
- `adapters/webcam_source.py` — implement bằng cv2 USB
- `composition_root.py` — chọn instance nào tuỳ profile

→ Đổi sang webcam = sửa 1 dòng config. Risk: không.

Hai trường hợp khác nhau **không phải vì code khó hơn**. Khác nhau vì **coupling level**. Học cách đo nó là cốt lõi của kiến trúc.

---

## Câu chuyện: từ tủ quần áo (lại) đến code thực

### Tủ quần áo

Tiếp nối ví dụ ở file 01:

**Coupling thấp giữa các ngăn**:
- Bạn lấy 1 cái áo sơ mi → không đụng vào quần.
- Đổi mùa thì lôi cả ngăn vớ ra giặt → quần không bị động.

**Cohesion cao TRONG mỗi ngăn**:
- Ngăn áo sơ mi: chỉ áo sơ mi. Không có vớ lẫn vào.
- Ngăn quần: chỉ quần. Không có cà vạt.

Nếu bạn bỏ vớ vào ngăn áo "vì còn chỗ trống" → cohesion ngăn áo giảm. Lần sau tìm áo phải tìm cả vớ. Nhỏ thôi nhưng tích luỹ.

### Code thực — module camera của HeadDetect

**Coupling cao + cohesion thấp** (BAD):

```python
# camera_module.py
import cv2
import sqlite3
from PIL import Image
import psycopg2
import requests

def process_camera(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    frame = cap.read()
    
    # Detect
    img = Image.fromarray(frame)
    # ... chạy YOLO inline ...
    
    # Lưu DB ngay trong cùng function
    conn = psycopg2.connect("postgresql://...")
    conn.execute("INSERT INTO detections...")
    
    # Gửi event qua HTTP ngay đây
    requests.post("http://api.com/events", json=...)
    
    # Hiển thị preview
    cv2.imshow("preview", frame)
```

Vấn đề:
- **Coupling**: function này phụ thuộc cv2, PIL, psycopg2, requests, network. Thay 1 cái → nhớ thay tất cả các chỗ dùng. Đổi DB từ Postgres → SQLite = sửa giữa hàm.
- **Cohesion**: 1 function làm 5 việc khác nhau (capture, detect, persist, notify, display). Cohesion thấp = "kitchen sink".

**Coupling thấp + cohesion cao** (GOOD):

```python
# domain/ports.py
class IDataSource(Protocol):
    def read(self) -> Frame: ...

class IDetector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]: ...

class IEventSink(Protocol):
    def emit(self, event: DetectionEvent) -> None: ...


# adapters/cv2_rtsp_source.py
class CV2RTSPSource:
    def __init__(self, url): ...
    def read(self) -> Frame: ...   # implement IDataSource


# application/process_stream_use_case.py
class ProcessStreamUseCase:
    """Cohesion cao: 1 trách nhiệm — orchestrate 1 stream."""
    def __init__(
        self,
        source: IDataSource,
        detector: IDetector,
        sink: IEventSink,
    ):
        self._source = source
        self._detector = detector
        self._sink = sink

    def run_one_iteration(self):
        frame = self._source.read()
        dets = self._detector.detect(frame)
        for d in dets:
            self._sink.emit(DetectionEvent.from_detection(d))
```

Bây giờ:
- **Coupling thấp**: `ProcessStreamUseCase` không biết cv2, không biết Postgres, không biết HTTP. Chỉ biết 3 interface.
- **Cohesion cao**: 1 class = 1 trách nhiệm = "chạy 1 vòng lặp xử lý stream".
- **Đổi adapter**: thay 1 dòng `source = WebcamSource(...)` thay vì `RTSPSource(...)`. Không động vào logic chính.

---

## Định nghĩa chính xác

### Coupling

> **Coupling = mức độ phụ thuộc** giữa 2 module. Đo bằng "nếu tôi đổi B, có bao nhiêu phần của A phải đổi theo?"

Có 7 cấp coupling, từ tệ nhất đến tốt nhất (theo Page-Jones):

| # | Loại | Mô tả | Ví dụ |
|---|------|-------|-------|
| 1 | **Content** (worst) | A đọc/sửa biến nội bộ của B. | Truy cập `b._private_field` từ A. |
| 2 | **Common** | A và B share global state. | Cả 2 cùng đọc/ghi `GLOBAL_CONFIG`. |
| 3 | **External** | A và B share external format/protocol. | A và B đều đọc cùng file CSV format. |
| 4 | **Control** | A truyền flag điều khiển B's behavior. | `b.process(mode="fast", debug=True, ...)` |
| 5 | **Stamp** | A truyền cả struct, B chỉ dùng 1 phần. | `b.process(packet)` nhưng b chỉ dùng `packet.id`. |
| 6 | **Data** | A truyền chính xác data cần. | `b.process(packet_id)`. |
| 7 | **Message** (best) | A gửi message qua interface, B tự diễn dịch. | `bus.publish(IdReceived(packet_id))`. |

**Trong thực tế**, bạn nhắm tới **Data hoặc Message coupling** ở các ranh giới quan trọng (giữa layer, giữa process). **Stamp coupling chấp nhận được** trong cùng module.

### Cohesion

> **Cohesion = mức độ các phần TRONG 1 module gắn với nhau theo cùng 1 mục đích.** Đo bằng "nếu tôi xé module này làm 2, có dễ không?"

7 cấp cohesion, từ tệ đến tốt nhất:

| # | Loại | Mô tả | Ví dụ |
|---|------|-------|-------|
| 1 | **Coincidental** (worst) | Các phần ngẫu nhiên ở chung. | `helpers.py` chứa 50 hàm random. |
| 2 | **Logical** | Cùng category nhưng làm việc khác nhau. | `io.py` chứa cả file I/O và network I/O. |
| 3 | **Temporal** | Cùng được gọi cùng lúc. | `setup.py` init DB + load config + start log. |
| 4 | **Procedural** | Cùng workflow. | `process_user_signup` gọi 5 hàm theo thứ tự. |
| 5 | **Communicational** | Cùng dữ liệu. | Class `Order` có `total()`, `discount()`, `tax()`. |
| 6 | **Sequential** | Output của hàm này = input của hàm kia. | Pipeline `read → parse → validate`. |
| 7 | **Functional** (best) | 1 mục đích duy nhất. | `parse_rtsp_url(s) -> URL`. |

**Trong thực tế**: nhắm functional/sequential cho hàm và class, communicational cho module.

---

## Cách ĐO trong code thật

Đo coupling và cohesion không cần tool đặc biệt. Bạn dùng 3 câu hỏi:

### Câu hỏi 1: "Khi tôi đổi X, bao nhiêu file khác phải đổi?"

→ Đếm file. Càng nhiều = coupling càng cao.

```bash
# Trong git, dùng pickaxe
git log --follow --all -- "tests/test_xxx.py" | wc -l
git log -p --all -S "WeirdSpecificFunction" | wc -l
```

### Câu hỏi 2: "Mở 1 file ra, đọc 30 giây, có giải thích được trách nhiệm chính không?"

Nếu có (ví dụ: "file này lo việc đọc RTSP frame") → cohesion tốt.
Nếu không (ví dụ: "ờ... nó làm vài việc") → cohesion thấp.

### Câu hỏi 3: "Số import vào module này là bao nhiêu?"

```bash
# Tìm tất cả file import module foo
rg "from foo import|import foo" --type py
```

- Module được import bởi 1 file → **độc lập**, có thể coupling thấp.
- Module được import bởi 50 file → **central** — coupling cao theo bản chất, phải GIỮ ổn định (interface stable).

→ Đây là lý do **port** (interface) ổn định + **adapter** (implementation) thay đổi: port được import nhiều, không thể đổi liên tục; adapter được import ít, đổi tự do.

---

## Mental model: hệ trục Coupling × Cohesion

```
                     COHESION CAO (tốt)
                           ▲
                           │
       Module            ┌─┼─┐         Module
       cohesive          │ │ │         cohesive
       nhưng quá       │ │ │       INDEPENDENT
       coupled         │ │ │       (mục tiêu)
                       └─┼─┘
                         │
COUPLING ◄───────────────┼───────────────► COUPLING
CAO                      │                 THẤP
(xấu)                    │                  (tốt)
                       ┌─┼─┐
       Hỗn loạn        │ │ │       Module rời rạc
       toàn diện       │ │ │       không liên kết
       (worst)         │ │ │       (vô dụng)
                       └─┼─┘
                         │
                         ▼
                     COHESION THẤP (xấu)
```

4 góc:

- **Góc trên-phải** (low coupling + high cohesion): mục tiêu.
- **Góc dưới-trái** (high coupling + low cohesion): worst case. Spaghetti code.
- **Góc trên-trái** (high coupling + high cohesion): module nội bộ tốt nhưng "knot" với nhau quá nhiều — thường là mới refactor 1/2 đường.
- **Góc dưới-phải** (low coupling + low cohesion): module rời rạc, mỗi module ngẫu nhiên — thường là util folder lộn xộn.

---

## Áp dụng vào Vision Platform

Đây là cách kiến trúc 4 layer (xem `Vision_platform_architecture_design/02-architecture/`) tối ưu coupling/cohesion:

```
┌─────────────────────────────────────────────┐
│ Application (use cases, orchestrators)      │  
│ - ProcessStreamUseCase                      │  ← cohesion cao
│ - QtDesktopApp, SupervisorApp               │     (1 use case = 1 trách nhiệm)
└──┬──────────────────────────────────────────┘
   │ phụ thuộc qua port (low coupling)
   ▼
┌─────────────────────────────────────────────┐
│ Runtime (executors, batchers, services)     │  ← cohesion theo concern:
│ - SyncLinearExecutor                        │     batcher / dedup / shutdown
│ - AdaptiveDeadlineBatcher                   │     mỗi cái = 1 file
│ - InferenceService                          │
└──┬──────────────────────────────────────────┘
   │ phụ thuộc qua port
   ▼
┌─────────────────────────────────────────────┐
│ Kernel (DTOs, ports, contracts)             │  ← cohesion = "tất cả đều
│ - MediaPacket (frozen DTO)                  │     là contract giữa layer"
│ - IDataSource, IDetector ports              │
│ - StageResult, ErrorSummary                 │
└──┬──────────────────────────────────────────┘
   │ phụ thuộc qua port
   ▼
┌─────────────────────────────────────────────┐
│ Domain (pure logic — no I/O)                │  ← cohesion cực cao,
│ - BBox, CoordinateSpace                     │     coupling = ZERO với
│ - DetectionEvent value objects              │     I/O / framework
└─────────────────────────────────────────────┘
```

**Coupling rules**:
- Domain phụ thuộc 0 thứ ngoài Python stdlib + numpy.
- Kernel phụ thuộc Domain.
- Runtime phụ thuộc Kernel + Domain qua port.
- Application phụ thuộc tất cả qua port.
- **Adapter** (implementations) sống ở 1 folder riêng, được Application "wire" lại tại composition root.

→ Coupling thấp ở các ranh giới quan trọng (vì qua port = Message/Data coupling).
→ Cohesion cao trong từng layer (mỗi layer = 1 concern level).

---

## Code-along (20 phút)

Mở terminal. Tạo `_coupling_demo/` folder:

```bash
mkdir _coupling_demo
cd _coupling_demo
```

### Phiên bản A — coupling cao

Tạo `bad_camera.py`:

```python
import cv2
import sqlite3
import json

def run_camera(rtsp_url, db_path, log_path):
    """Tất cả gộp 1 chỗ — coupling cao."""
    cap = cv2.VideoCapture(rtsp_url)
    conn = sqlite3.connect(db_path)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        h, w = frame.shape[:2]
        
        # "Detect" giả lập
        center_brightness = int(frame[h//2, w//2].mean())
        
        # Lưu DB inline
        conn.execute(
            "INSERT INTO frames (brightness) VALUES (?)",
            (center_brightness,),
        )
        conn.commit()
        
        # Log inline
        with open(log_path, "a") as f:
            f.write(json.dumps({"brightness": center_brightness}) + "\n")
    
    cap.release()
    conn.close()


if __name__ == "__main__":
    run_camera("video.mp4", "data.db", "log.jsonl")
```

**Bài tập**: Đếm số dependency cứng. Yêu cầu mới — "đổi từ SQLite sang CSV file".

→ Bạn phải sửa `run_camera` function. Mọi caller cũng phải đổi (không có caller nào nhưng tưởng tượng có 5 caller). Coupling = **cao**.

### Phiên bản B — coupling thấp

Tạo `good/ports.py`:

```python
from typing import Protocol, Any


class IFrameSource(Protocol):
    def read(self) -> Any: ...   # trả về frame (np.ndarray)
    def close(self) -> None: ...


class IDetector(Protocol):
    def detect(self, frame: Any) -> int: ...   # giả lập: trả brightness


class IEventSink(Protocol):
    def emit(self, event: dict) -> None: ...
```

Tạo `good/adapters.py`:

```python
import cv2
import sqlite3
import json
from typing import Any


class CV2VideoSource:
    def __init__(self, url: str):
        self._cap = cv2.VideoCapture(url)

    def read(self) -> Any:
        ret, frame = self._cap.read()
        return frame if ret else None

    def close(self) -> None:
        self._cap.release()


class FakeDetector:
    def detect(self, frame: Any) -> int:
        h, w = frame.shape[:2]
        return int(frame[h // 2, w // 2].mean())


class SqliteSink:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path)

    def emit(self, event: dict) -> None:
        self._conn.execute(
            "INSERT INTO frames (brightness) VALUES (?)",
            (event["brightness"],),
        )
        self._conn.commit()


class JsonlSink:
    def __init__(self, path: str):
        self._path = path

    def emit(self, event: dict) -> None:
        with open(self._path, "a") as f:
            f.write(json.dumps(event) + "\n")


class CompositeSink:
    """Adapter pattern: nhiều sink hành xử như 1."""
    def __init__(self, *sinks):
        self._sinks = sinks

    def emit(self, event: dict) -> None:
        for s in self._sinks:
            s.emit(event)
```

Tạo `good/use_case.py`:

```python
from .ports import IFrameSource, IDetector, IEventSink


class ProcessStreamUseCase:
    """Cohesion cao: 1 trách nhiệm — chạy 1 stream loop.
    Coupling thấp: phụ thuộc qua interface, không biết implementation cụ thể.
    """
    def __init__(
        self,
        source: IFrameSource,
        detector: IDetector,
        sink: IEventSink,
    ):
        self._source = source
        self._detector = detector
        self._sink = sink

    def run(self) -> None:
        while True:
            frame = self._source.read()
            if frame is None:
                break
            brightness = self._detector.detect(frame)
            self._sink.emit({"brightness": brightness})
        self._source.close()
```

Tạo `good/__main__.py` — composition root:

```python
from .adapters import CV2VideoSource, FakeDetector, SqliteSink, JsonlSink, CompositeSink
from .use_case import ProcessStreamUseCase


def main():
    # ← Đây là chỗ DUY NHẤT biết về cụ thể implementation.
    source = CV2VideoSource("video.mp4")
    detector = FakeDetector()
    sink = CompositeSink(SqliteSink("data.db"), JsonlSink("log.jsonl"))

    use_case = ProcessStreamUseCase(source, detector, sink)
    use_case.run()


if __name__ == "__main__":
    main()
```

**Bài tập**: Yêu cầu cũ — "đổi từ SQLite sang CSV file".

```python
# Thêm vào adapters.py
import csv

class CsvSink:
    def __init__(self, path: str):
        self._path = path
        # write header nếu file rỗng...

    def emit(self, event: dict) -> None:
        with open(self._path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=event.keys())
            writer.writerow(event)
```

Trong `__main__.py`, đổi đúng **1 dòng**:

```python
sink = CompositeSink(CsvSink("data.csv"), JsonlSink("log.jsonl"))
```

→ Coupling thấp = đổi 1 dòng. Use case `ProcessStreamUseCase` không biết, không động vào.

---

## Checkpoint (10 phút)

Mở `_my_answers.md`, trả lời:

1. Trong dự án HeadDetect/main_app/ hiện tại, đoán **3 chỗ** có coupling cao nhất. Mở source ra check, viết tên file + lý do.

2. Định nghĩa "low coupling" theo cách của bạn (không copy định nghĩa). Ví dụ thực tế.

3. Một function 200 dòng làm 4 việc — cohesion cấp gì? Lợi ích nếu xé thành 4 function?

4. Tại sao "đo coupling" không có công thức cố định? (Hint: phụ thuộc *direction*.)

5. Pipeline `frame → preprocess → detect → postprocess → emit` — đây là cohesion loại gì? Tại sao tốt hay xấu trong context Vision Platform?

<details>
<summary>Đáp án gợi ý</summary>

1. *(Câu cá nhân)*. Common pattern: file `main.py` import nhiều thứ là dấu hiệu. Hardcoded SQL/HTTP trong loop logic. Class self-create dependency thay vì DI.

2. Low coupling = **tôi có thể test module A mà không cần khởi động module B thật**. Hoặc: **đổi B không kéo theo đổi A**.

3. **Procedural cohesion** (cấp 4). Lợi ích xé:
   - Mỗi function tên rõ ràng → đọc dễ hơn.
   - Mỗi function test riêng được.
   - Reuse 1 phần ở chỗ khác mà không gọi cả 200 dòng.
   - Reduce cognitive load (đọc 50 dòng dễ hơn 200).

4. Coupling là **directional**: "A depend B" khác "B depend A". Đo coupling phải hỏi "theo chiều nào". Cũng phụ thuộc **stability** của module được phụ thuộc — depend on stable thing OK, depend on volatile thing không OK.

5. **Sequential cohesion** (cấp 6) — output của stage A là input của stage B. Tốt cho Vision Platform vì:
   - Mỗi stage testable riêng (đầu vào → đầu ra deterministic).
   - Pipeline có thể swap order, swap stage.
   - Frame data flow tự nhiên qua sequence.
   - Architecture "Pipes and Filters" áp dụng được.

</details>

---

## Trade-offs

### Có khi nào coupling cao là OK?

CÓ. Khi:
- 2 module thật sự **luôn cùng đổi** (cohesion logic chung). Tách ra = artificial boundary.
- **Performance critical**: thêm interface = virtual dispatch cost. Game engine, low-level driver thường tránh interface ở hot path.
- **Throw-away code**: prototype 1 tuần.

### Có khi nào cohesion thấp là OK?

CÓ. Khi:
- **Utility module**: `utils/` chấp nhận coincidental cohesion vì "tiện".
- **Adapter layer**: nhiều adapter cùng folder không thật sự liên quan logic.

### Cảnh báo: chia quá nhỏ cũng tệ

Cohesion cao không = mỗi function 5 dòng. Có **sweet spot**: 1 module có ~5-15 hàm liên quan. Nhỏ hơn nữa → cognitive overhead chuyển ngữ cảnh giữa file.

→ **Quy tắc**: nếu bạn phải mở 5 file để hiểu 1 logic → có thể chia QUÁ nhỏ.

---

## Liên kết

- File 03 (`03-dependency-direction.md`) sẽ dạy **chiều phụ thuộc** — bổ sung cho coupling.
- Production: `Vision_platform_architecture_design/03-data-contracts/01-ports-overview.md` — port là cách giảm coupling tới 0.
- Module 02 (`module-02-core-concepts/02-ports-and-adapters-build-one.md`) — concrete pattern dùng coupling thấp.

---

## Tóm tắt 1 câu

> **Mục tiêu kiến trúc: low coupling + high cohesion. Coupling đo qua "đổi B kéo theo bao nhiêu A?". Cohesion đo qua "module này nói về gì?".**

➡️ Tiếp theo: [`03-dependency-direction.md`](03-dependency-direction.md)
