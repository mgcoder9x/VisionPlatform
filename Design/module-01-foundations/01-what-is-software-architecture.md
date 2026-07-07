# 01 — Kiến trúc phần mềm là gì (theo cách dùng được)

## TL;DR (30 giây)

> **Kiến trúc phần mềm = tập hợp các quyết định khó đảo ngược, định hình ranh giới giữa các phần và cách chúng giao tiếp.**

"Khó đảo ngược" là từ khoá. Đổi tên biến là code design. Chuyển từ monolith sang microservices là kiến trúc — vì 6 tháng sau muốn quay lại cũng không kịp.

---

## Mental hook

Hãy tưởng tượng bạn vừa code xong tính năng "phát hiện mũ bảo hiểm" cho dự án HeadDetect. Sếp đến nói:

> "Sau 6 tháng nữa chúng ta cần chạy hệ thống này trên 50 camera ở 5 toà nhà. Phải scale ra. Đổi nhanh nhỉ?"

Bạn nhìn vào code. Code hiện tại:
- 1 file `main.py` 800 dòng.
- Camera đọc xong gọi thẳng OpenCV detector trong cùng process.
- Detector trả kết quả gọi thẳng SQL writer.
- UI Qt embed trong main thread.

**Câu hỏi**: bao nhiêu phần code phải viết lại để scale lên 50 camera?

Câu trả lời thực tế: 70-90%. Vì các quyết định ban đầu — gọi thẳng, cùng process, sync — là các **quyết định kiến trúc** đã được "đóng băng" trong cấu trúc code. Đảo ngược = viết lại.

→ Đó là lý do bạn cần học kiến trúc TRƯỚC khi viết dự án lớn.

---

## Câu chuyện: từ tủ quần áo của bạn đến Linux kernel

### Tủ quần áo

Bạn có tủ quần áo. Sắp xếp 1 lần — dùng 5 năm.

Cách 1 — "ném vào":
- Tất cả áo / quần / vớ / đồ lót đổ chung 1 ngăn.
- Lúc cần áo trắng họp gấp: tìm 5 phút.
- Thêm áo mới: ném vào, không nghĩ.
- 5 năm sau: hỗn loạn.

Cách 2 — "phân ngăn":
- Ngăn 1: áo sơ mi (treo).
- Ngăn 2: quần.
- Ngăn 3: đồ lót (folded).
- Ngăn 4: phụ kiện.
- Lúc cần: 10 giây.
- Thêm áo mới: biết ngay đặt đâu.
- Đổi mùa: lôi ra, sắp xếp lại trong cùng nguyên tắc.

**Cách 2 là kiến trúc.** Bạn quyết định **ranh giới** (chiếc ngăn) và **luật giao tiếp** (đồ giặt → ngăn áo, không phải ngăn quần). Quyết định 1 lần. Dùng dài.

### Linux kernel

Linus Torvalds quyết định 1992: kernel chia thành layer:
- **Hardware abstraction** (drivers)
- **Process management** (scheduler)
- **Memory management** (paging, swap)
- **Filesystems**
- **Networking**
- **System call interface** (cách user app gọi vào)

30+ năm sau, vẫn cấu trúc đó. **Tại sao không cần đổi?** Vì các ranh giới được chọn ĐÚNG — chúng phản ánh cấu trúc tự nhiên của vấn đề. CPU đời mới → driver thay, scheduler không động. Filesystem mới (Btrfs, ZFS) → filesystem layer thay, networking không động.

**Bài học**: Kiến trúc tốt = ranh giới chia theo **trục thay đổi tự nhiên**, không phải chia theo "đẹp mắt".

---

## Định nghĩa dùng được

Có 100+ định nghĩa "software architecture" trong sách. Tôi cho bạn cái dùng được nhất trong thực tế:

> **Kiến trúc của 1 hệ thống = (1) các thành phần chính, (2) ranh giới giữa chúng, (3) luật giao tiếp giữa chúng. Khó đổi 3 thứ này = "kiến trúc". Dễ đổi = "code design".**

3 thành phần chính:

### (1) Components — các thành phần chính

Trong Vision Platform của bạn, các "thành phần chính" là:
- **Camera process** (đọc RTSP)
- **Inference Service** (chạy GPU detector)
- **Pipeline executor** (orchestration)
- **Event Sink** (ghi DB, gửi MQTT...)
- **UI** (Qt / web / CLI)
- **Supervisor** (quản lý lifecycle, shutdown)

Mỗi component = 1 process hoặc 1 module với trách nhiệm RÕ RỆT.

### (2) Boundaries — ranh giới

Ranh giới = **đường biên qua đó dữ liệu/lệnh phải dịch chuyển** với cost xác định.

Ví dụ ranh giới:
- **Process boundary**: dữ liệu phải qua IPC (SHM/ZMQ) — cost ~50µs-1ms.
- **Module boundary**: dữ liệu pass qua function call — cost ~1ns.
- **Network boundary**: phải qua HTTP/gRPC — cost ~1-10ms.

Ranh giới quan trọng vì 2 lý do:
1. **Cost qua ranh giới** = bottleneck tiềm năng.
2. **Ranh giới = đơn vị thay thế**. Đổi adapter A↔B trong cùng module = dễ. Đổi xuyên process = khó hơn.

### (3) Contracts — luật giao tiếp

Contract = "khi đi qua ranh giới, dữ liệu phải có hình dạng X, theo protocol Y".

Ví dụ trong Vision Platform:
- Camera process → Inference Service: phải qua wire DTO `InferenceRequestWire` (msgpack-serializable, có request_id để correlation).
- Pipeline → Event Sink: phải qua `EventEnvelope` với `idempotency_key`.
- Domain DTO ↔ Wire DTO: phải qua converter ở boundary.

Contract càng **explicit** (rõ ràng) → càng dễ test, càng dễ thay implementation.

---

## Phân biệt: Architecture vs. Design

Đây là chỗ nhiều dev nhầm. Phân biệt như sau:

| | Architecture | Design |
|---|---|---|
| **Phạm vi** | Toàn hệ thống / nhiều module | 1 class / 1 function |
| **Ví dụ** | "Camera process tách riêng inference" | "Hàm parse_rtsp_url trả về Optional[URL]" |
| **Cost đảo ngược** | Tuần / tháng | Phút / giờ |
| **Quyết định khi nào** | Đầu dự án (hoặc sau khi pain xuất hiện) | Mỗi sprint, mỗi PR |
| **Người làm** | Tech lead / architect | Mọi developer |
| **Sai thì** | Toàn dự án trễ. Refactor đau đớn. | 1 PR sửa được. |

**Tóm gọn**: Architecture quyết định *các thành phần lớn*, Design quyết định *bên trong từng thành phần*.

---

## Tại sao kiến trúc QUAN TRỌNG cho Vision Platform multi-camera?

Đây là phần liên hệ trực tiếp với Vision Platform:

### Áp lực 1: GPU là tài nguyên chia sẻ

Bạn có **1 GPU**, **16 camera**. Nếu mỗi camera spawn 1 detector instance → 16× VRAM, OOM ngay.

→ Quyết định kiến trúc: **centralized inference service**. 1 detector instance, các camera gửi request qua.

→ Hệ quả: cần **request/response correlation** (frame nào của camera nào), cần **batching**, cần **circuit breaker** khi service chết.

→ Bạn vừa khoá vào 5+ quyết định khác chỉ vì 1 quyết định ban đầu.

Đó là **tính cascading** của quyết định kiến trúc — và là lý do nó "khó đảo ngược".

### Áp lực 2: 1 camera chết không được kéo theo 15 camera khác

Camera RTSP hay disconnect (network blip, camera reboot). Nếu camera 1 hang trong `socket.read()` → toàn bộ pipeline dừng → 15 camera kia mất frame.

→ Quyết định kiến trúc: **bulkhead pattern** — mỗi camera là 1 OS process riêng.

→ Hệ quả: cần IPC (SHM hoặc ZMQ), cần shutdown protocol cascade, cần observability cross-process.

### Áp lực 3: GPU thermal throttle → chậm 50%

Đêm GPU nóng, batch latency tăng từ 8ms → 16ms. Nếu camera vẫn capture 30 FPS → queue đầy → memory bloat → OOM crash.

→ Quyết định kiến trúc: **backpressure first-class**. Camera đọc xong, nếu queue đầy → drop frame có policy (DROP_OLDEST, SAMPLE, DEGRADE_QUALITY).

→ Hệ quả: cần health signal feedback từ inference service về camera, cần metrics.

### Liên hệ

3 áp lực trên **không phải lý thuyết**. Chúng là 3 production incident có thật mà thiết kế trong `Vision_platform_architecture_design/` đã phải trả lời. Mỗi quyết định kiến trúc trong design đều có 1 áp lực thực tế phía sau.

→ Khi đọc design, **luôn hỏi**: "Áp lực thực tế nào tạo ra quyết định này?". Nếu không tìm ra → có thể là over-engineering.

---

## Mental model: thành phố và đường giao thông

Tưởng tượng kiến trúc phần mềm = quy hoạch thành phố:

- **Components** = các khu (khu dân cư, khu công nghiệp, khu thương mại).
- **Boundaries** = đường biên các khu.
- **Contracts** = luật giao thông giữa các khu (xe tải vào khu công nghiệp được; vào khu dân cư cấm ban đêm).

Các nguyên tắc bạn sẽ thấy:

1. **Đặt khu công nghiệp gần đường cao tốc** = đặt component tốn I/O ở chỗ có băng thông (camera process gần SHM, không gần UI).
2. **Đường nội bộ khu vs đường liên khu** = function call vs IPC. Cost khác nhau.
3. **Đổi luật giao thông trong khu = dễ. Đổi luật cao tốc = phải họp hội đồng.** = đổi code trong module dễ, đổi contract giữa process khó.

Nếu bạn quy hoạch sai từ đầu (đặt nhà máy cạnh trường học) → 20 năm sau muốn sửa = phá dỡ. Code cũng vậy.

---

## Code-along (15 phút)

Mở terminal. Tạo file `_arch_check.py` ở đâu đó:

```python
# _arch_check.py
"""Bài tập: phân biệt Architecture vs. Design quyết định trong code thực."""

# Đoạn 1
def parse_rtsp_url(s: str) -> str:
    """Strip credentials from RTSP URL for logging."""
    if "@" in s:
        scheme, rest = s.split("://", 1)
        creds, host = rest.split("@", 1)
        return f"{scheme}://***@{host}"
    return s


# Đoạn 2
class CameraReader:
    """Đọc frame từ RTSP, ghi vào shared memory để inference service đọc."""
    def __init__(self, rtsp_url, shm_writer, inference_client):
        self._url = rtsp_url
        self._shm = shm_writer
        self._infer = inference_client    # ← inject từ ngoài

    def read_loop(self):
        while True:
            frame = self._read_one()
            slot, gen = self._shm.write(frame)
            self._infer.send_request(slot, gen)


# Đoạn 3
class CameraReaderV2:
    """Phiên bản khác."""
    def __init__(self, rtsp_url):
        self._url = rtsp_url
        # Tự tạo SHM + inference client BÊN TRONG
        self._shm = ShmRingBuffer(name="cam_shm")
        self._infer = ZMQInferenceClient(endpoint="tcp://localhost:5555")


print("Đoạn nào là Architecture decision, đoạn nào là Design decision?")
```

**Bài tập**:
1. Đoạn 1 (`parse_rtsp_url`) — Architecture hay Design?
2. Đoạn 2 (`CameraReader` với DI) — Architecture hay Design?
3. Đoạn 3 (`CameraReaderV2` self-create) — Architecture hay Design? Tại sao có sự khác biệt với đoạn 2?

→ Trả lời TRƯỚC khi xem đáp án dưới.

<details>
<summary>Đáp án (click sau khi đã trả lời)</summary>

1. **Đoạn 1 = Design**. Logic format string. Đổi tên function, sửa regex — không ảnh hưởng kiến trúc. 1 PR sửa được.

2. **Đoạn 2 = Architecture**. Quyết định "CameraReader phụ thuộc qua interface inject từ ngoài" → dễ test (mock inference_client), dễ đổi adapter (`ZMQClient` ↔ `InProcessClient`), dễ thay SHM impl. Bạn vừa **chọn dependency direction**.

3. **Đoạn 3 = ANTI-architecture**. CameraReader **TỰ TẠO** dependency cụ thể bên trong → coupling cao với `ShmRingBuffer` và `ZMQInferenceClient`. Muốn test? Phải mock global. Muốn đổi từ ZMQ sang HTTP? Phải sửa code CameraReader. **Đoạn 2 và 3 chỉ khác cách inject dependency, nhưng cost đảo ngược chênh nhau 1000 lần.**

**Đây là chỗ tinh tế nhất**: 2 phiên bản nhìn giống nhau (đều có `_shm` và `_infer`), nhưng 1 cái là **kiến trúc tốt** và 1 cái là **kiến trúc sai**. Khác biệt = WHO creates the dependency.

</details>

---

## Checkpoint (5 phút)

Trả lời ra giấy hoặc file `_my_answers.md`:

1. Đưa ra 1 ví dụ trong dự án bạn đang làm (HeadDetect hoặc khác): 1 quyết định Architecture và 1 quyết định Design.

2. Trong Vision Platform, "centralized inference service" là Architecture hay Design? Giải thích.

3. "Đổi tên file `helpers.py` → `utils.py`" — Architecture hay Design? Cost đảo ngược?

4. Tại sao "khó đảo ngược" lại là tiêu chí phân biệt tốt? Cho 1 phản ví dụ — quyết định khó đảo ngược NHƯNG không phải Architecture.

<details>
<summary>Đáp án gợi ý</summary>

1. *(Câu cá nhân — bạn tự đánh giá)*. Ví dụ với HeadDetect: Architecture = "tách camera process khỏi UI process". Design = "biến `frame_count` đổi tên thành `n_frames`".

2. **Architecture**. Đảo ngược = viết lại 30-50% code (mỗi camera tự host detector). Cost: tuần. Quyết định 1 lần ảnh hưởng nhiều quyết định khác (cần ZMQ, cần correlation, cần circuit breaker).

3. **Design**. Cost đảo ngược: 5 phút (rename + update import). Không ảnh hưởng kiến trúc.

4. Phản ví dụ: "Chọn ngôn ngữ Python thay vì Rust" — khó đảo ngược (viết lại 100% codebase) NHƯNG không hẳn là Architecture (là **technology choice**, một category riêng). Đây là biên giới mờ — sách Fundamentals of Software Architecture (Mark Richards) gọi technology choice là một sub-class của architecture decision.

Tiêu chí "khó đảo ngược" tốt nhưng không hoàn hảo. Bổ sung: Architecture **xác định ranh giới**. Tech choice xác định **vật liệu xây dựng**.

</details>

---

## Trade-offs

### Khi nào KHÔNG cần nghĩ về kiến trúc?

- **Prototype throw-away**: code 1 tuần show demo, vứt sau đó. Đừng over-engineer.
- **Script tự động hoá**: 100 dòng, 1 người dùng. Đừng layer.
- **MVP cực sớm**: chưa biết product có ai dùng → đừng paint Bikeshed.

### Dấu hiệu bạn over-engineer kiến trúc

- Code 200 dòng nhưng có 8 file abstraction layer.
- Mỗi class implement 1 interface với 1 implementation duy nhất.
- README giải thích "Hexagonal" trước khi giải thích "tính năng X".

→ **Quy tắc YAGNI** ("You Ain't Gonna Need It"): chỉ thêm abstraction khi có **lý do cụ thể tồn tại HÔM NAY**, không phải "có thể cần sau".

### Dấu hiệu bạn under-engineer

- 1 file 1000+ dòng làm nhiều việc.
- Đổi feature A → ngỏ tay sửa 5 file random.
- Test khó viết vì cần mock toàn bộ thế giới.
- Sếp hỏi "scale ra 50 camera" → bạn estimate 3 tháng.

→ Đây là lúc cần **invest** vào kiến trúc.

---

## Liên kết

- **Pattern này gặp lại ở**: file `02-coupling-cohesion-the-core-tradeoff.md` — đo "quyết định khó đảo ngược" = đo coupling.
- **Production design liên quan**: `Vision_platform_architecture_design/02-architecture/` — concrete 4 layer của Vision Platform.
- **Đọc thêm (optional)**: 
  - "Fundamentals of Software Architecture" — Mark Richards & Neal Ford. Chương 1-3.
  - "A Philosophy of Software Design" — John Ousterhout. Chương 1-2 về complexity.

---

## Tóm tắt

| Khái niệm | Một câu nhớ |
|-----------|-------------|
| Kiến trúc = | Tập hợp các quyết định khó đảo ngược về components, boundaries, contracts. |
| Architecture vs Design | Architecture: tuần/tháng để đảo. Design: phút/giờ. |
| Sao quan trọng cho Vision Platform | GPU sharing, bulkhead, backpressure — 3 áp lực thực tế ép kiến trúc. |
| Quy tắc thực hành | YAGNI — chỉ thêm khi có lý do hôm nay. Cũng đừng under-engineer. |

---

➡️ Tiếp theo: [`02-coupling-cohesion-the-core-tradeoff.md`](02-coupling-cohesion-the-core-tradeoff.md)
