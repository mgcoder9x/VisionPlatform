# Requirements Document

## Introduction

Feature `multicamera-fleet-profile` giải quyết **Finding F7.2** trong `.kiro/specs/architecture-review/design.md`:
"Hai topology không hợp nhất (điểm gãy production chính)" — repo hiện có hai profile rời rạc, mỗi cái chỉ có
một nửa nhu cầu sản phẩm 24/7:

1. `vision_platform/profiles/vision_web_app.py` — single-view web app: webcam → detect → MJPEG stream + overlay
   JSON, chạy **in-process** (không SHM/ZMQ), có web UI live nhưng **chỉ 1 camera**.
2. `vision_platform/profiles/vision_fullstack_profile.py` — multi-process: capture → SHM ring buffer → ZMQ
   inference service → Supervisor (bulkhead per-process, chịu lỗi), nhưng **không có web UI** và v1 chỉ 1
   camera + 1 pool.

Feature này là một **composition-root profile mới** wire cả hai ưu điểm: N camera, mỗi camera cô lập bulkhead
(1 camera chết không kéo sập cái khác — nguyên tắc K-045), đi qua tầng inference multi-process (tái dùng
ZMQ/SHM), tổng hợp về một web gateway phục vụ overlay + stream **live** cho từng camera, có Supervisor giám sát.

Phạm vi feature là **wiring / composition** các thành phần đã tồn tại; feature này KHÔNG phát minh cơ chế IPC,
SHM, hay detector mới.

### Thành phần code đã tồn tại được tái dùng (đã verify tồn tại trong repo)

- `ShmRingBuffer` — `runtime/ipc/shm_frame_ring.py`
- `RingPool` — `runtime/ipc/ring_pool.py`
- `ReaderEpochCoordinator` — `application/reader_epoch_coordinator.py`
- `InferenceServer` — `application/inference_server.py`; `ZmqInferenceClient` — `adapters/zmq_inference_client.py`
- `Supervisor` — `application/supervisor.py` (heartbeat + backoff)
- `OverlayStateStore` — `runtime/overlay_state_store.py` (atomic epoch/lease overlay)
- `DetectorPipeline` — `adapters/detector_pipeline.py`
- 5 port trong `kernel/ports/`: `IDetector`, `IFrameSource`, `IInferenceClient`, `ISink`, `ITracker`
  (`ITracker` camera-affinity, K-042: 1 instance / 1 luồng)

### Giả định tường minh (ASSUMPTION — chưa phải fact đã chốt)

- **[ASSUMPTION A1] GPU target = x86-64 + NVIDIA rời** (máy dev thật x86 + RTX 2060). Nếu triển khai trên
  Jetson/ARM thì kích hoạt nợ K-001 (atomicity SHM chưa verify trên phần cứng ARM) — nằm ngoài phạm vi v1.
- **[ASSUMPTION A2] Quy mô = fleet nhỏ–vừa** (hàng chục camera, ít viewer đồng thời). Số camera N và số slot
  ring được tham số hoá qua config, không hard-code.
- **[ASSUMPTION A3] Web transport = MJPEG** (đã có trong `vision_web_app.py`). WebRTC là follow-on (F4.1) khi
  cần phục vụ nhiều viewer đồng thời — nằm ngoài phạm vi v1.

### Ràng buộc kiến trúc bắt buộc (repo rule — phải phản ánh trong acceptance criteria)

- Hexagonal 6 tầng, cưỡng chế bằng import-linter: `domain ← kernel ← runtime ← application`; `adapters` và
  `profiles` là rim. `domain` thuần (numpy, không cv2/torch/ZMQ); `kernel` chỉ ports + DTO.
- Overlay hiển thị KHÔNG import analytics (contract #6).
- Bulkhead isolation per-camera (K-045).
- Fail-fast, quan-sát-được (observability đã có: `LoggingObserver` / `MetricsObserver` / endpoint `/metrics`).

## Glossary

- **Fleet_Profile**: Composition-root profile mới (feature này), khởi tạo và wire toàn hệ N-camera multi-process
  + web gateway + supervision. Sống ở tầng `profiles`.
- **Camera_Lane**: Một luồng xử lý end-to-end cô lập cho MỘT camera (capture → SHM ring → inference → overlay).
  Đơn vị bulkhead. N camera = N Camera_Lane.
- **Web_Gateway**: Thành phần phục vụ HTTP: MJPEG stream + overlay JSON per-camera + trang chỉ mục fleet + các
  endpoint quan-sát (`/metrics`, health). Đọc kết quả từ các Camera_Lane, KHÔNG chạy inference.
- **Fleet_Supervisor**: Instance `Supervisor` (đã có) giám sát toàn bộ process con của fleet qua heartbeat +
  backoff restart.
- **Fleet_Config**: File cấu hình TOML khai báo danh sách camera và tham số fleet.
- **Camera_Id**: Định danh duy nhất, ổn định của một camera trong `Fleet_Config`.
- **Bulkhead**: Ranh giới cô lập lỗi — hỏng trong một Camera_Lane không lan sang Camera_Lane khác (K-045).
- **Overlay_Store**: Instance `OverlayStateStore` per-camera, giữ kết quả overlay mới nhất theo epoch/lease.
- **MJPEG**: Motion JPEG — transport stream ảnh đã có trong `vision_web_app.py` (ASSUMPTION A3).

---

## Requirements

### Requirement 1: Đa-camera capture + cấu hình khai báo TOML

**User Story:** Là người vận hành fleet, tôi muốn khai báo N camera trong một file TOML, để hệ thống khởi tạo
đúng số Camera_Lane mà không cần sửa code.

#### Acceptance Criteria

1. WHEN Fleet_Profile khởi động, THE Fleet_Profile SHALL đọc Fleet_Config từ một file TOML được chỉ định qua
   tham số dòng lệnh hoặc biến môi trường.
2. WHEN Fleet_Config chứa danh sách N camera hợp lệ, THE Fleet_Profile SHALL tạo đúng N Camera_Lane, mỗi
   Camera_Lane gắn với đúng một Camera_Id.
3. THE Fleet_Config SHALL cho phép khai báo cho mỗi camera tối thiểu: Camera_Id, nguồn frame (frame source),
   độ phân giải khung (chiều cao, chiều rộng, số kênh), và số slot ring buffer.
4. IF hai mục camera trong Fleet_Config có cùng Camera_Id, THEN THE Fleet_Profile SHALL từ chối khởi động và
   ghi một thông báo lỗi nêu rõ Camera_Id bị trùng (fail-fast).
5. IF Fleet_Config thiếu một trường bắt buộc hoặc chứa giá trị sai kiểu, THEN THE Fleet_Profile SHALL từ chối
   khởi động và ghi một thông báo lỗi nêu rõ trường và camera vi phạm (fail-fast).
6. WHERE Fleet_Config không chỉ định số slot ring buffer cho một camera, THE Fleet_Profile SHALL áp dụng một giá
   trị mặc định được định nghĩa ở cấp fleet.
7. THE Fleet_Config SHALL cho phép khai báo số camera N là tham số (ASSUMPTION A2: tham số hoá, không hard-code).

### Requirement 2: Bulkhead isolation per-camera

**User Story:** Là người vận hành fleet, tôi muốn mỗi camera được cô lập, để một camera lỗi (mất tín hiệu, sập
process) không làm gián đoạn các camera khác.

#### Acceptance Criteria

1. THE Fleet_Profile SHALL cấp cho mỗi Camera_Lane tài nguyên IPC riêng (SHM ring buffer riêng, không chia sẻ
   slot giữa các Camera_Id khác nhau).
2. IF một Camera_Lane gặp lỗi không phục hồi được (process con thoát bất thường), THEN THE Fleet_Profile SHALL
   giữ các Camera_Lane còn lại tiếp tục hoạt động bình thường (K-045).
3. WHILE một Camera_Lane đang ở trạng thái lỗi, THE Web_Gateway SHALL tiếp tục phục vụ stream và overlay của các
   Camera_Lane đang khỏe mạnh.
4. IF nguồn frame của một camera không cung cấp frame trong một khoảng thời gian ngưỡng cấu hình được, THEN THE
   Fleet_Profile SHALL đánh dấu Camera_Lane đó là không khỏe mạnh mà không dừng các Camera_Lane khác.
5. THE Fleet_Profile SHALL bảo đảm không có Camera_Lane nào giữ khóa (lock) hoặc tài nguyên dùng chung mà việc
   giải phóng phụ thuộc vào một Camera_Lane khác còn sống.

### Requirement 3: Tầng inference multi-process (tái dùng ZMQ/SHM)

**User Story:** Là kỹ sư nền tảng, tôi muốn inference chạy ở process riêng qua ZMQ/SHM đã có, để tách CPU/GPU
khỏi capture và tái dùng hạ tầng đã được kiểm chứng thay vì viết lại.

#### Acceptance Criteria

1. THE Fleet_Profile SHALL truyền frame từ mỗi Camera_Lane tới tầng inference qua `ShmRingBuffer` (không copy
   frame qua socket).
2. THE Fleet_Profile SHALL dùng `ZmqInferenceClient` và `InferenceServer` đã có để gửi/nhận yêu cầu inference
   cross-process.
3. WHEN một Camera_Lane gửi một InferenceRequest, THE tầng inference SHALL trả về InferenceResponse có cùng
   request_id (echo, đúng hợp đồng `IInferenceClient` đã có).
4. THE Fleet_Profile SHALL gán mỗi frame kết quả về đúng Camera_Id gốc (không lẫn kết quả giữa các camera).
5. WHERE nhiều Camera_Lane cùng chia sẻ một tiến trình inference, THE Fleet_Profile SHALL bảo toàn tính cô lập
   kết quả per-camera (Requirement 2) ngay cả khi dùng chung tài nguyên GPU.
6. WHILE một `ITracker` đang chạy cho một Camera_Lane, THE Fleet_Profile SHALL dùng đúng một instance `ITracker`
   cho mỗi luồng camera (K-042 camera-affinity).

### Requirement 4: Web gateway live overlay per-camera

**User Story:** Là người xem, tôi muốn xem stream live kèm overlay của từng camera qua trình duyệt, để giám sát
toàn fleet ở một nơi.

#### Acceptance Criteria

1. THE Web_Gateway SHALL cung cấp một endpoint MJPEG stream riêng cho mỗi Camera_Id (ASSUMPTION A3).
2. THE Web_Gateway SHALL cung cấp một endpoint overlay JSON riêng cho mỗi Camera_Id, trả về kết quả detection
   mới nhất của camera đó.
3. THE Web_Gateway SHALL đọc kết quả overlay của mỗi camera từ `OverlayStateStore` per-camera (một Overlay_Store
   trên một Camera_Id).
4. WHEN kết quả overlay mới của một camera sẵn sàng, THE Web_Gateway SHALL phục vụ phiên bản mới nhất theo
   epoch/lease của `OverlayStateStore` (không phục vụ kết quả cũ hơn epoch đã commit).
5. THE Web_Gateway SHALL cung cấp một trang chỉ mục liệt kê tất cả Camera_Id đang cấu hình cùng trạng thái
   khỏe/lỗi của mỗi camera.
6. IF một client yêu cầu stream hoặc overlay cho một Camera_Id không tồn tại trong Fleet_Config, THEN THE
   Web_Gateway SHALL trả về mã lỗi HTTP 404.
7. THE Web_Gateway SHALL NOT thực thi inference; Web_Gateway chỉ đọc và phục vụ kết quả đã được các Camera_Lane
   tạo ra. (Ngoại lệ negative statement: ràng buộc phân tách trách nhiệm.)

### Requirement 5: Supervision và tự phục hồi lỗi

**User Story:** Là người vận hành fleet, tôi muốn hệ thống tự giám sát và phục hồi process con, để fleet chạy
liên tục 24/7 mà không cần can thiệp tay khi có sự cố tạm thời.

#### Acceptance Criteria

1. THE Fleet_Profile SHALL đăng ký mọi process con (camera worker, inference server) với `Fleet_Supervisor`.
2. WHILE fleet đang chạy, THE Fleet_Supervisor SHALL theo dõi heartbeat của từng process con đã đăng ký.
3. IF một process con ngừng gửi heartbeat quá ngưỡng cấu hình được, THEN THE Fleet_Supervisor SHALL khởi động
   lại process đó theo chính sách backoff đã có.
4. WHEN Fleet_Supervisor khởi động lại một process của một Camera_Lane, THE Fleet_Profile SHALL giữ các
   Camera_Lane khác không bị gián đoạn (nhất quán với Requirement 2).
5. WHEN Fleet_Profile nhận tín hiệu tắt (shutdown), THE Fleet_Profile SHALL dừng tất cả process con một cách có
   trật tự và giải phóng tài nguyên SHM/ZMQ đã cấp.
6. THE Fleet_Profile SHALL bật heartbeat và backoff một cách tường minh trong cấu hình fleet (đối chiếu F5.2:
   heartbeat/backoff mặc định tắt — fleet production phải bật).

### Requirement 6: Observability per-camera

**User Story:** Là người vận hành fleet, tôi muốn số liệu và log gắn theo từng camera, để chẩn đoán nhanh camera
nào đang gặp vấn đề.

#### Acceptance Criteria

1. THE Fleet_Profile SHALL gắn `LoggingObserver` và `MetricsObserver` đã có vào mỗi Camera_Lane.
2. THE Web_Gateway SHALL phơi bày một endpoint `/metrics` tổng hợp số liệu của toàn fleet.
3. THE Fleet_Profile SHALL gán nhãn (label) mỗi số liệu và mỗi bản ghi log theo Camera_Id tương ứng.
4. THE Fleet_Profile SHALL phơi bày cho mỗi Camera_Lane tối thiểu: số frame đã xử lý, số frame bị rớt
   (frames dropped), và trạng thái khỏe/lỗi hiện tại.
5. WHEN một Camera_Lane chuyển trạng thái khỏe ↔ lỗi, THE Fleet_Profile SHALL ghi một bản ghi log kèm Camera_Id
   và trạng thái mới.
6. THE Fleet_Profile SHALL phơi bày số liệu số lần restart do Fleet_Supervisor thực hiện, gắn nhãn theo process
   con (nhất quán với Requirement 5).

### Requirement 7: Ràng buộc layering (hexagonal 6 tầng)

**User Story:** Là người bảo trì kiến trúc, tôi muốn Fleet_Profile tuân thủ luật hexagonal 6 tầng, để ranh giới
phụ thuộc được cưỡng chế bằng máy và không phát sinh nợ kiến trúc.

#### Acceptance Criteria

1. THE Fleet_Profile SHALL nằm ở tầng `profiles` (composition root) và là nơi duy nhất được phép wire các
   thành phần cụ thể của tất cả các tầng.
2. THE Fleet_Profile SHALL chỉ giao tiếp với domain/runtime/application qua các port trong `kernel/ports`
   (`IDetector`, `IFrameSource`, `IInferenceClient`, `ISink`, `ITracker`).
3. THE thành phần overlay hiển thị SHALL NOT import bất kỳ module analytics nào (contract #6). (Ngoại lệ
   negative statement: ràng buộc phân tách phụ thuộc bắt buộc.)
4. THE mã tầng `domain` được feature này chạm tới SHALL chỉ phụ thuộc numpy và không import cv2, torch, hoặc ZMQ.
5. THE mã tầng `kernel` được feature này chạm tới SHALL chỉ chứa ports và DTO, không chứa adapter cụ thể.
6. WHEN bộ kiểm import-linter chạy trên codebase sau khi thêm Fleet_Profile, THE codebase SHALL vượt qua mọi
   contract ranh giới tầng mà không có vi phạm mới.
