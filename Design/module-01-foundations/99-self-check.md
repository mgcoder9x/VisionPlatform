# 99 — Self-check Module 01

> Pass mới qua Module 02. **Quy tắc: trả lời ra giấy/file TRƯỚC khi xem đáp án. Đọc đáp án xong vẫn không hiểu → quay lại đọc file đó.**

## Hướng dẫn

- 15 câu, chia 3 mức: Recall (5) → Apply (5) → Analyze (5).
- **Pass criteria**: ≥4/5 Recall + ≥3/5 Apply + ≥2/5 Analyze.
- Không pass — đọc lại file tương ứng (cột bên phải).
- Pass — qua Module 02.

---

## Phần 1: Recall (nhớ được)

### Câu 1
Định nghĩa "kiến trúc phần mềm" theo cách dùng được trong thực tế.

→ File [`01-what-is-software-architecture.md`](01-what-is-software-architecture.md)

### Câu 2
Khác biệt giữa Architecture decision và Design decision? Cho 2 ví dụ mỗi loại.

→ File 01.

### Câu 3
"Coupling" là gì? "Cohesion" là gì? Mục tiêu kiến trúc với 2 đại lượng này?

→ File [`02-coupling-cohesion-the-core-tradeoff.md`](02-coupling-cohesion-the-core-tradeoff.md).

### Câu 4
"Stable Dependencies Principle" — phát biểu? Tại sao Domain phải stable nhất?

→ File [`03-dependency-direction.md`](03-dependency-direction.md).

### Câu 5
4 layer của Vision Platform? Chiều phụ thuộc?

→ File 03.

<details>
<summary>Đáp án Phần 1</summary>

1. **Kiến trúc = tập hợp các quyết định khó đảo ngược về components, boundaries, contracts.** Cost đảo ngược = tuần/tháng. Khác với code design (cost = phút/giờ).

2. **Architecture**: tách camera process khỏi UI process; chọn ZMQ làm IPC; centralized inference service. **Design**: đổi tên hàm; refactor 1 function; đổi enum value name.

3. **Coupling** = mức độ A phụ thuộc B; càng cao → đổi B kéo A đổi. **Cohesion** = mức độ các phần TRONG 1 module gắn theo cùng 1 mục đích. Mục tiêu: **low coupling + high cohesion**.

4. **Stable Dependencies Principle**: Phụ thuộc đi theo chiều tăng stability. Module ổn định không được phụ thuộc module ít ổn định. **Domain stable nhất** vì:
   - Định nghĩa core concept (BBox, CoordinateSpace) — đời đời không đổi.
   - Nếu Domain phụ thuộc thứ unstable → đổi thứ unstable kéo Domain → kéo cả hệ thống.
   - Domain là **center of gravity** của kiến trúc.

5. **Domain → Kernel → Runtime → Application**, với **Adapters** là leaf. Mũi tên import luôn đi từ ngoài (adapter) vào trong (domain). Adapter implement port của Kernel/Domain.

</details>

---

## Phần 2: Apply (áp dụng)

### Câu 6

Đoạn code sau:

```python
class CameraReader:
    def __init__(self, rtsp_url):
        import cv2
        self._cap = cv2.VideoCapture(rtsp_url)
        
        import psycopg2
        self._db = psycopg2.connect("host=localhost user=...")
    
    def read_and_save(self):
        ret, frame = self._cap.read()
        self._db.execute("INSERT INTO frames ...")
```

Đánh giá: Coupling level? Cohesion level? Đề xuất refactor.

### Câu 7

File `vision/domain/bbox.py`:

```python
import cv2
import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class BBox:
    x: float; y: float; w: float; h: float
    
    def draw_on(self, frame: np.ndarray) -> np.ndarray:
        return cv2.rectangle(frame, ...)
```

Vi phạm gì? Sửa thế nào để giữ chức năng "vẽ bbox lên frame" mà không vi phạm dependency direction?

### Câu 8

Bạn được giao dự án mới: hệ thống nhận video upload từ user, chạy phát hiện vật thể, trả kết quả qua API. Spec:

- Web app, user upload video file.
- 100 user/ngày, mỗi video <100MB.
- Chạy trên 1 server có 1 GPU.
- Team: 1 dev (bạn).

Chọn kiến trúc nào? Tại sao? Dùng Vision Platform có over-engineer không?

### Câu 9

Sếp: "Em hãy thêm support cho camera ONVIF (giao thức khác RTSP) vào HeadDetect."

Code hiện tại: `main_app/thread/thread_capture.py` hard-code OpenCV RTSP loop. Đề xuất plan refactor (3-5 bước).

### Câu 10

Bạn đọc 1 PR review: "Code này coupling thấp vì có 5 file abstraction layer."

Phản biện hoặc đồng ý?

<details>
<summary>Đáp án Phần 2</summary>

6. **Coupling level**: cao (Stamp + External — phụ thuộc cv2 và psycopg2 cụ thể, hardcoded). **Cohesion level**: thấp (procedural — class làm 2 việc: capture frame VÀ persist DB).
   
   **Refactor**:
   ```python
   # ports
   class IFrameSource(Protocol):
       def read(self) -> Optional[Frame]: ...
   
   class IFrameSink(Protocol):
       def save(self, frame: Frame) -> None: ...
   
   # adapters
   class CV2RTSPSource: ...   # implements IFrameSource
   class PostgresSink: ...     # implements IFrameSink
   
   # use case
   class CameraReadAndSaveUseCase:
       def __init__(self, source: IFrameSource, sink: IFrameSink):
           self._source = source
           self._sink = sink
       
       def run_one(self):
           frame = self._source.read()
           if frame: self._sink.save(frame)
   ```
   
   Coupling: thấp. Cohesion: cao (use case = 1 trách nhiệm).

7. **Vi phạm**: Domain (`BBox`) đang phụ thuộc cv2 (adapter layer). Vi phạm Stable Dependencies Principle.

   **Sửa**:
   ```python
   # domain/bbox.py — không cv2
   @dataclass(frozen=True)
   class BBox:
       x: float; y: float; w: float; h: float
   
   # adapters/visualization/cv2_drawer.py
   import cv2
   from vision.domain.bbox import BBox
   
   def draw_bbox(frame: np.ndarray, bbox: BBox) -> np.ndarray:
       return cv2.rectangle(frame, (int(bbox.x), int(bbox.y)),
                            (int(bbox.x + bbox.w), int(bbox.y + bbox.h)), ...)
   ```
   
   Mũi tên: `cv2_drawer` → `BBox` (đúng chiều). BBox không biết cv2.

8. **Context**: 1 dev, 100 user/ngày, batch processing (không real-time multi-camera).
   
   → **Kiến trúc đơn giản**: Flask/FastAPI + Celery worker + 1 detector process. **KHÔNG cần** Vision Platform full (bulkhead per camera, ZMQ inference service, SHM, backpressure cascading). 
   
   Vision Platform được thiết kế cho real-time multi-camera (M1 mode). Context của bạn là batch processing (M2 mode) — Vision Platform M2 SIMPLER hơn nhiều. Chỉ cần: source (file) → detector → sink (HTTP/DB). 
   
   Over-engineer nếu áp full M1.

9. **Plan**:
   1. **Tạo port** `IDataSource` ở kernel layer (chưa có thì thêm).
   2. **Refactor RTSP code** thành `RTSPSource` adapter implement `IDataSource`.
   3. **Tạo `ONVIFSource`** adapter mới implement cùng port.
   4. **Update composition root** (main.py hoặc factory) để chọn adapter theo config.
   5. **Test**: viết contract test chung cho `IDataSource` — cả 2 adapter pass.
   
   Sau plan này: thêm IP camera khác giao thức (Hikvision SDK, Axis VAPIX...) chỉ tạo 1 adapter mới — KHÔNG động vào logic chính.

10. **Phản biện** (5 file abstraction ≠ low coupling).
    
    Coupling đo bằng "đổi B kéo theo bao nhiêu A?" KHÔNG đo bằng "có bao nhiêu file". 5 file abstraction có thể:
    - Nếu mỗi abstraction dùng 1 lần → over-engineering. Tăng coupling vì 5 file đều phụ thuộc lẫn nhau.
    - Nếu mỗi abstraction có ≥2 implementation → có thể OK.
    
    Hỏi lại: "Mỗi abstraction này có ít nhất 2 implementation thật không, hay bạn thêm vì 'có thể cần sau'?"

</details>

---

## Phần 3: Analyze (phân tích sâu)

### Câu 11

Bạn được giới thiệu 1 codebase mới (HeadDetect/main_app/ chẳng hạn). Bạn có **30 phút** để đánh giá kiến trúc. List 5 thứ bạn check, theo thứ tự ưu tiên.

### Câu 12

Đọc đoạn code này từ Vision_platform_architecture_design/03-data-contracts/:

```python
@dataclass(frozen=True)
class StageResult:
    status: StageStatus
    packet: Optional["MediaPacket"] = None
    error: Optional[Exception] = None        # ← R5-CRITICAL-02 cảnh báo
    error_summary: Optional[ErrorSummary] = None
    ...
```

Tại sao có CẢ `error` và `error_summary`? Phân tích trade-off (coupling, cohesion, technical debt).

### Câu 13

Trong 4-layer: Domain / Kernel / Runtime / Application. Có 1 chuyên gia tư vấn nói: "Bỏ Kernel đi, gộp vào Domain. 4 layer thừa, 3 đủ rồi." Phản biện hoặc đồng ý — phân tích pros/cons.

### Câu 14

Bạn được phép **chỉ chọn 2** trong 5 nguyên tắc kiến trúc (low coupling, high cohesion, stable dependencies, dependency inversion, single responsibility) áp dụng cho dự án nhỏ (5-10 file). 2 cái nào? Tại sao?

### Câu 15

"Composition root" pattern — chỉ 1 chỗ biết cụ thể implementation. Tại sao **không** áp dụng nguyên tắc tương tự cho test code? (Test thường có nhiều `Mock(...)` rải rác.)

<details>
<summary>Đáp án Phần 3</summary>

11. **5 thứ check, ưu tiên giảm dần**:
    1. **`README.md` / docs** — có không, có document context không (scale, target user)?
    2. **Tree cấu trúc folder** — có layer rõ ràng (domain / adapter / use case)? Có "kitchen sink" folder (`utils/`, `helpers/`) lớn?
    3. **Dependency direction** — `import` của file domain/core có thuần không? `from cv2` xuất hiện trong `domain/`?
    4. **Test coverage** — có test riêng cho domain (không cần mock thế giới)? Hay phải spin up everything?
    5. **Composition root** — có chỗ tập trung wire dependencies, hay rải rác `new XXX()` khắp nơi?

12. **Tại sao có cả `error` và `error_summary`**:
    - `error_summary` (lightweight, no traceback) = **path mới**, dùng cho non-fatal errors (DLQ, retry buffer). Mục đích: KHÔNG retain MediaPacket via traceback frame locals (R5-CRITICAL-02 fix).
    - `error: Exception` = **path legacy**, chỉ dùng khi `fatal=True` cho executor's `raise result.error` propagation. Cần exception thật để re-raise + supervisor inspect.
    
    **Trade-off**:
    - **Coupling**: tăng nhẹ (2 field thay vì 1). Acceptable vì semantics khác nhau.
    - **Cohesion**: vẫn cao (cùng `StageResult`, cùng concern: stage outcome).
    - **Technical debt**: deprecating `error` từ từ — tài liệu hoá rõ.
    
    Đây là **migration pattern thực tế**. Không thể đổi tất cả call site cùng lúc → giữ both, ép convention "non-fatal dùng `error_summary`, fatal dùng `error`".

13. **Phản biện** (giữ Kernel tách Domain).
    
    **Pros của ý kiến** ("bỏ Kernel"):
    - Đơn giản hơn — 3 layer ít cognitive load hơn 4.
    - Domain có thể chứa cả ports và DTOs — như Clean Architecture của Bob Martin.
    
    **Cons**:
    - **Domain pure rule** vi phạm: Domain không được biết về `MediaPacket` (vì `MediaPacket` chứa `media_ref: ShmFrameRef` — kernel concept). Nếu gộp, `BBox` (pure domain) cùng package với `ShmFrameRef` (infrastructure) — coupling sai.
    - **`numpy`** được phép trong Domain (math), nhưng `multiprocessing.shared_memory` thì KHÔNG. Cần boundary tách 2 thứ này.
    - Vision Platform có **1 lớp giữa**: technical primitive (Port, MediaPacket, IPC contract) — không thuần business logic, không thuần adapter. Đây là Kernel.
    
    → **Phản biện**: 4 layer phù hợp cho hệ thống có **technical primitive layer** (kernel). Hệ thống business-heavy (banking, ERP) có thể 3 layer đủ. **Context-specific.**

14. **Chọn 2**: **Low coupling** + **High cohesion**.
    
    **Lý do**:
    - Dự án 5-10 file — không cần 5 layer abstraction. Stable Dependencies Principle có giá trị khi nhiều module với life cycle khác nhau — 5 file thì life cycle gần như đồng đều.
    - Dependency Inversion là kỹ thuật phục vụ low coupling — bạn đã có low coupling rồi, không cần thêm tầng abstraction.
    - Single Responsibility là 1 form của high cohesion — có rồi.
    
    → 2 nguyên tắc bao phủ phần lớn lợi ích. 3 nguyên tắc còn lại = nice-to-have ở scale này. **YAGNI**.

15. **Test khác production**:
    - **Production**: stable, ship to user. Composition root = single source of truth → đổi adapter dễ.
    - **Test**: ephemeral, rebuild mỗi run. Mock object lifecycle = lifecycle của test → "rải rác" = OK.
    - **Test isolation**: mỗi test cần state riêng — không thể "share global mock" như composition root.
    - **Test readability**: gom mọi mock vào 1 conftest.py = giấu thông tin. Khi đọc 1 test, muốn thấy ngay "nó mock gì". Inline mock đọc dễ hơn.
    
    → **Quy tắc**: test có "spread mock" nhưng phải **tổ chức theo concern** (fixture cho common setup, parametrize cho edge cases). KHÔNG copy-paste.

</details>

---

## Đánh giá kết quả

Đếm số câu trả lời đúng:

- **Recall ≥4/5** + **Apply ≥3/5** + **Analyze ≥2/5** = ✅ Pass. Qua Module 02.
- **Recall ≥4/5** + **Apply <3/5** = ⚠️ Đọc lại file `02-coupling-cohesion` và `03-dependency-direction`, code thêm bài tập.
- **Recall <4/5** = ❌ Đọc lại Module 01 từ đầu. Đừng vội qua Module 02.

---

## Sau khi pass

Trước khi qua Module 02:

1. **Áp dụng vào dự án thật**: Mở HeadDetect/main_app/ hoặc dự án khác bạn đang code. List 3 vi phạm dependency direction. Suy nghĩ cách sửa (KHÔNG sửa, chỉ suy nghĩ).

2. **Cài tools**: 
   ```bash
   pip install pydeps import-linter
   ```
   Vẽ graph dependency cho dự án bạn. Có cycle không?

3. **Chọn ngày bắt đầu Module 02**: kế hoạch 6-8 giờ. Module 02 là 5 file pattern — không nặng nhưng cần thời gian thấm.

➡️ Khi sẵn sàng, mở [`../module-02-core-concepts/00-index.md`](../module-02-core-concepts/00-index.md).

---

## Q&A nhanh

**Q: Tôi không pass, hơi nản. Có bình thường không?**
A: Có. Tôi đã thiết kế self-check khó hơn nội dung. Mục tiêu là ép bạn nhận ra điểm yếu và đọc lại. Không có "Module 01 ngắn 1h xong". Module này là **NỀN** — yếu nền sẽ vỡ sau.

**Q: Có cần làm hết bài tập trong file 1-4 không?**
A: Code-along: BẮT BUỘC. Checkpoint từng file: nên có. Self-check: BẮT BUỘC.

**Q: Tôi muốn skip qua Module 03 (build-along) ngay, có được không?**
A: KHÔNG khuyến nghị. Module 03 sẽ build code thật áp dụng Module 02 pattern. Nếu Module 02 chưa pass thì code Module 03 sẽ đầy lỗi mà bạn không hiểu why.

**Q: Tôi đã có kinh nghiệm 5 năm, có cần Module 01 không?**
A: Tuỳ. Đọc thử file 03 (`dependency-direction`). Nếu trả lời được hết checkpoint của file đó → skip Module 01. Nếu không → đọc cả module.

---

✅ Hoàn thành Module 01.
