# Requirements Document

## Introduction

Tính năng này đóng hai lỗ hổng đã xác định bằng đọc code + journal (A2: `no-backpressure-cross-process` — mất frame im lặng; A3: `no-HWM` — ZMQ không set high-water-mark tường minh) trong hệ `vision-platform` (Python, kiến trúc hexagonal 6 layer, ép bằng import-linter).

Bằng chứng vấn đề (đã đọc code):
- `profiles/vision_fullstack_profile.py::camera_worker` gọi `ZmqInferenceClient.infer()` **đồng bộ, blocking** trong vòng lặp capture. Khi inference chậm hơn capture, camera bị chặn → nguồn frame (RTSP thực tế) rớt frame ở buffer OS **âm thầm, không đếm được**.
- `adapters/zmq_inference_client.py`: `self._outbound = queue.Queue()` **không giới hạn kích thước**; **không** set `zmq.SNDHWM`/`zmq.RCVHWM` → khi dùng HWM mặc định (1000) bị tràn thì ZMQ drop/block **không báo lên tầng ứng dụng**.
- `kernel/backpressure.py::BoundedQueue`: có 4 policy nhưng **thread-safe, KHÔNG process-safe** (ghi nhận K-016) → không dùng trực tiếp để điều tiết cross-process.
- Harness hiện dùng `NoiseFrameSource` pull-based đồng bộ → nhịp nguồn tự khớp nhịp tiêu thụ nên **không tái hiện được** tình trạng quá tải.

Mục tiêu: chuyển submit sang mô hình **bất đồng bộ có cửa sổ in-flight giới hạn** để camera không bị chặn và **chủ động bỏ frame có đếm** khi trễ; áp policy mặc định `DROP_OLDEST`; **cấm** cấu hình `BLOCK` cho nguồn RTSP; phát ra bộ đếm quan sát được; set ZMQ HWM tường minh; và kiểm chứng bằng test **xác định, không cần GPU**.

**Mô hình đã chốt — backpressure BOUND TRƯỚC KHI GỬI (bound-before-send):** vì `InferenceServer` (ROUTER single-thread) **không hủy được request đã nhận** (request đã gửi qua ZMQ chắc chắn bị xử lý), nếu chỉ bound *in-flight đã gửi* thì "bỏ frame" chỉ ngừng theo dõi mà server VẪN tốn sức inference frame cũ — không giảm tải, không đóng gốc A2. Do đó backpressure phải xảy ra **trước khi gửi**: hệ chỉ gửi request mới khi số request chưa-được-trả-lời (`In_Flight_Count`) nhỏ hơn `window_size` (flow-control); các frame vượt cửa sổ nằm ở **hàng đợi outbound có giới hạn** và bị `Backpressure_Policy` xử lý (DROP_OLDEST bỏ frame chờ-gửi cũ nhất) **trước khi chạm socket** → frame bị bỏ không tới server (giảm tải thật) và được đếm đầy đủ.

Phạm vi tôn trọng ràng buộc kiến trúc hiện có: kernel không import `zmq`/`torch`; adapters là leaf; thay đổi mang tính **cộng thêm (additive)**, không phá baseline 436 passed / 1 skipped, lint 5/0.

### Goals
- Camera không bị chặn bởi inference chậm.
- Mọi frame nguồn được hạch toán đầy đủ: hoặc được submit, hoặc được đếm là bị bỏ.
- HWM của ZMQ được set tường minh (đóng A3).
- Có bộ test xác định tái hiện quá tải mà không cần GPU/torch.

### Non-goals
- Không hỗ trợ multi-camera N-pool trong phiên này (giữ bất biến 1-writer/ring).
- Không thay `NoiseFrameSource`/`FakeDetector` bằng nguồn RTSP thật hay YOLO thật.
- Không đưa `zmq`/`torch` vào layer kernel.

## Glossary

- **Vision_Platform**: Toàn hệ thống xử lý vision real-time đa camera trong repo.
- **Camera_Worker**: Tiến trình camera trong `profiles/vision_fullstack_profile.py` thực hiện capture → ghi SHM → submit inference.
- **Inference_Client**: Thành phần `adapters/zmq_inference_client.py` gửi yêu cầu inference qua ZMQ DEALER và nhận phản hồi.
- **Submission_Window**: Cơ chế điều tiết submit theo Mô hình A gồm hai phần phối hợp: (a) **flow-control in-flight** — chỉ GỬI request mới tới server khi `In_Flight_Count` nhỏ hơn `window_size`; và (b) **hàng đợi outbound có giới hạn** giữ các frame chờ-gửi (chưa chạm socket) và áp `Backpressure_Policy` khi đầy. `window_size` là số request chưa-được-trả-lời tối đa cho phép gửi tới server tại một thời điểm.
- **In_Flight_Count**: Số yêu cầu inference **đã gửi tới server** nhưng chưa nhận được kết quả (thành công/lỗi/timeout). Hệ chỉ gửi request mới khi `In_Flight_Count` nhỏ hơn `window_size` (flow-control).
- **Backpressure_Policy**: Chính sách xử lý khi `Submission_Window` đầy; giá trị hợp lệ: `DROP_OLDEST`, `DROP_NEWEST`, `BLOCK`, `REJECT` (định nghĩa trong `kernel/backpressure.py::BackpressurePolicy`).
- **Frame_Source**: Nguồn cung cấp frame cho `Camera_Worker`.
- **Push_Frame_Source**: Nguồn mô phỏng dạng đẩy (push) phát ra frame theo **nhịp cố định** không phụ thuộc nhịp tiêu thụ, dùng để tái hiện quá tải một cách xác định.
- **Fake_Detector**: Detector giả lập có độ trễ cấu hình được (`FakeDetector` trong `adapters/`), dùng tạo tải chậm mà không cần GPU.
- **HWM**: High-Water-Mark của ZMQ — giới hạn số message đệm trên một socket (`zmq.SNDHWM` phía gửi, `zmq.RCVHWM` phía nhận).
- **Backpressure_Metrics**: Tập bộ đếm quan sát được gồm `frames_captured`, `frames_submitted`, `frames_dropped_backpressure`, `infer_ok`, `infer_err`, `infer_timeout`.
- **Frame_Conservation_Invariant**: Bất biến `frames_submitted + frames_dropped_backpressure == frames_captured`.
- **Metric_DTO**: Cấu trúc dữ liệu thuần chứa `Backpressure_Metrics`, đặt ở layer kernel (không phụ thuộc zmq/torch) nếu cần chia sẻ định nghĩa.

## Requirements

### Requirement 1: Submit inference bất đồng bộ có cửa sổ in-flight

**User Story:** Là kỹ sư vận hành hệ vision, tôi muốn camera submit yêu cầu inference bất đồng bộ với cửa sổ in-flight giới hạn, để camera không bị chặn khi inference chậm hơn tốc độ capture.

#### Acceptance Criteria

1. THE Camera_Worker SHALL submit yêu cầu inference qua cơ chế Submission_Window có kích thước tối đa `window_size` cấu hình được với giá trị mặc định lớn hơn hoặc bằng 1.
2. WHEN một frame mới đến, THE Camera_Worker SHALL đưa frame vào hàng đợi outbound có giới hạn theo cách **không chặn (non-blocking)** — nếu hàng đợi chưa đầy thì nhận frame mà không chờ phản hồi của các yêu cầu trước đó, nếu đầy thì áp `Backpressure_Policy` (Requirement 2) — để camera không bao giờ bị chặn bởi inference chậm.
3. WHILE In_Flight_Count nhỏ hơn `window_size`, THE Inference_Client SHALL gửi (send) frame chờ-gửi tiếp theo trong hàng đợi outbound tới server; WHILE In_Flight_Count bằng `window_size`, THE Inference_Client SHALL KHÔNG gửi thêm request nào tới server (flow-control) cho tới khi có phản hồi.
4. WHEN một phản hồi inference (thành công, lỗi, hoặc timeout) được nhận, THE Camera_Worker SHALL giảm In_Flight_Count đi đúng 1.
5. THE Inference_Client SHALL cung cấp giao diện submit không chặn (non-blocking) tách biệt với việc nhận phản hồi, để In_Flight_Count phản ánh số yêu cầu đã-gửi-đang-chờ tại mọi thời điểm.

### Requirement 2: Chủ động bỏ frame theo backpressure policy khi cửa sổ đầy

**User Story:** Là kỹ sư vận hành, tôi muốn hệ chủ động bỏ frame theo một policy xác định khi cửa sổ in-flight đầy, để tránh mất frame âm thầm và giữ độ trễ trong tầm kiểm soát.

#### Acceptance Criteria

1. THE Camera_Worker SHALL sử dụng Backpressure_Policy với giá trị mặc định `DROP_OLDEST`.
2. WHILE hàng đợi outbound đã đầy AND Backpressure_Policy là `DROP_OLDEST`, WHEN một frame mới đến, THE Camera_Worker SHALL loại bỏ **frame chờ-gửi cũ nhất (chưa được gửi tới server)** trong hàng đợi outbound, đưa frame mới vào hàng đợi, và tăng `frames_dropped_backpressure` đi đúng 1; frame bị loại SHALL KHÔNG được gửi tới server.
3. WHILE hàng đợi outbound đã đầy AND Backpressure_Policy là `DROP_NEWEST`, WHEN một frame mới đến, THE Camera_Worker SHALL bỏ frame mới (không đưa vào hàng đợi, không gửi) và tăng `frames_dropped_backpressure` đi đúng 1.
4. WHILE hàng đợi outbound đã đầy AND Backpressure_Policy là `REJECT`, WHEN một frame mới đến, THE Camera_Worker SHALL bỏ frame mới (không đưa vào hàng đợi, không gửi) và tăng `frames_dropped_backpressure` đi đúng 1.
5. WHILE hàng đợi outbound đã đầy AND Backpressure_Policy là `BLOCK`, WHEN một frame mới đến, THE Camera_Worker SHALL chờ tới khi có chỗ trống trong hàng đợi outbound rồi đưa frame đó vào mà không tăng `frames_dropped_backpressure`.

### Requirement 3: Cấm policy BLOCK cho nguồn RTSP

**User Story:** Là kỹ sư vận hành, tôi muốn hệ từ chối cấu hình `BLOCK` cho nguồn RTSP, để tránh gây TCP Zero Window làm nghẽn luồng và mất kết nối im lặng.

#### Acceptance Criteria

1. IF Frame_Source là nguồn RTSP AND Backpressure_Policy được cấu hình là `BLOCK`, THEN THE Vision_Platform SHALL từ chối cấu hình bằng cách phát ra lỗi cấu hình có thông điệp mô tả rõ nguyên nhân.
2. THE Vision_Platform SHALL thực thi ràng buộc cấm `BLOCK` cho RTSP tại tầng cấu hình per-source, không tại `kernel/backpressure.py::BoundedQueue` (giữ BoundedQueue policy-agnostic).

### Requirement 4: Hạch toán frame đầy đủ (bất biến bảo toàn)

**User Story:** Là kỹ sư vận hành, tôi muốn mọi frame nguồn được hạch toán đầy đủ, để biết chính xác bao nhiêu frame được xử lý và bao nhiêu bị bỏ thay vì mất im lặng.

#### Acceptance Criteria

1. WHEN Camera_Worker nhận một frame từ Frame_Source, THE Camera_Worker SHALL tăng `frames_captured` đi đúng 1.
2. WHEN Camera_Worker submit thành công một frame vào Submission_Window, THE Camera_Worker SHALL tăng `frames_submitted` đi đúng 1.
3. THE Camera_Worker SHALL duy trì Frame_Conservation_Invariant `frames_submitted + frames_dropped_backpressure == frames_captured` tại mọi thời điểm quan sát sau khi vòng lặp xử lý kết thúc.

### Requirement 5: Bộ đếm quan sát được (Backpressure_Metrics)

**User Story:** Là kỹ sư quan sát hệ thống, tôi muốn truy xuất bộ đếm backpressure và inference, để giám sát tình trạng quá tải và tỷ lệ bỏ frame.

#### Acceptance Criteria

1. THE Camera_Worker SHALL phát ra Backpressure_Metrics gồm `frames_captured`, `frames_submitted`, `frames_dropped_backpressure`, `infer_ok`, `infer_err`, và `infer_timeout`.
2. WHEN một yêu cầu inference nhận phản hồi thành công, THE Camera_Worker SHALL tăng `infer_ok` đi đúng 1.
3. IF một yêu cầu inference nhận phản hồi lỗi không phải timeout, THEN THE Camera_Worker SHALL tăng `infer_err` đi đúng 1.
4. IF một yêu cầu inference không nhận phản hồi trong thời hạn timeout cấu hình, THEN THE Camera_Worker SHALL tăng `infer_timeout` đi đúng 1.
5. WHERE cần chia sẻ định nghĩa Backpressure_Metrics giữa các layer, THE Vision_Platform SHALL định nghĩa Metric_DTO tại layer kernel không phụ thuộc `zmq` hoặc `torch`.

### Requirement 6: Set ZMQ HWM tường minh (đóng A3)

**User Story:** Là kỹ sư vận hành, tôi muốn ZMQ HWM được set tường minh, để hành vi đệm/đẩy-lùi trên socket là xác định và không phụ thuộc mặc định ẩn.

#### Acceptance Criteria

1. WHEN Inference_Client khởi tạo socket ZMQ, THE Inference_Client SHALL set `zmq.SNDHWM` với giá trị cấu hình được lớn hơn hoặc bằng 1.
2. WHEN Inference_Client khởi tạo socket ZMQ, THE Inference_Client SHALL set `zmq.RCVHWM` với giá trị cấu hình được lớn hơn hoặc bằng 1.
3. THE Inference_Client SHALL set giá trị SNDHWM và RCVHWM trước khi thực hiện `connect` tới endpoint.

### Requirement 7: Nguồn push mô phỏng để tái hiện quá tải xác định

**User Story:** Là kỹ sư kiểm thử, tôi muốn một nguồn frame dạng push phát nhịp cố định, để tái hiện tình trạng quá tải một cách xác định mà không cần GPU.

#### Acceptance Criteria

1. THE Push_Frame_Source SHALL phát ra đúng `M` frame với `M` cấu hình được.
2. THE Push_Frame_Source SHALL phát frame theo nhịp cố định độc lập với tốc độ tiêu thụ của Camera_Worker.
3. WHERE test cần tạo tải inference chậm, THE Fake_Detector SHALL áp một độ trễ xử lý cấu hình được cho mỗi yêu cầu mà không yêu cầu `torch` hoặc GPU.

### Requirement 8: Test acceptance xác định (không GPU)

**User Story:** Là kỹ sư kiểm thử, tôi muốn bộ test xác định kiểm chứng hành vi backpressure, để bảo đảm hệ đúng mà không cần phần cứng GPU.

#### Acceptance Criteria

1. WHEN Push_Frame_Source phát `M` frame vào hệ có Fake_Detector độ trễ gây quá tải, THE Vision_Platform SHALL thỏa mãn Frame_Conservation_Invariant `frames_submitted + frames_dropped_backpressure == frames_captured`.
2. WHEN hệ bị quá tải với Backpressure_Policy `DROP_OLDEST`, THE Vision_Platform SHALL báo `frames_dropped_backpressure` lớn hơn 0 với số đếm khớp số frame thực tế bị bỏ.
3. WHILE Backpressure_Policy là `BLOCK` trên nguồn non-RTSP trong test, WHEN hệ bị quá tải, THE Vision_Platform SHALL báo `frames_dropped_backpressure` bằng 0.
4. WHEN hệ quá tải với Backpressure_Policy `DROP_OLDEST`, THE Vision_Platform SHALL ưu tiên giữ các yêu cầu inference của frame mới hơn so với frame cũ nhất bị loại.
5. THE Vision_Platform SHALL mở rộng `tests/test_zmq_inference_cross_process.py` với ca kiểm thử cross-process (spawn) kiểm chứng backpressure end-to-end.

### Requirement 9: Bảo toàn ràng buộc kiến trúc và baseline

**User Story:** Là người bảo trì kiến trúc, tôi muốn thay đổi tuân thủ ranh giới 6 layer và không phá baseline, để giữ tính toàn vẹn của hệ.

#### Acceptance Criteria

1. THE Vision_Platform SHALL giữ layer kernel không import `zmq`, `torch`, `cv2`, `multiprocessing`, hoặc `shared_memory` (theo contract import-linter hiện hành).
2. THE Vision_Platform SHALL giữ các adapter là leaf, chỉ phụ thuộc layer kernel.
3. WHEN chạy toàn bộ suite kiểm thử sau khi thêm tính năng, THE Vision_Platform SHALL giữ toàn bộ số test của baseline (436 passed, 1 skipped) ở trạng thái đậu và không giảm.
4. WHEN chạy kiểm tra lint, THE Vision_Platform SHALL giữ kết quả lint ở mức baseline 5 passed / 0 failed.
