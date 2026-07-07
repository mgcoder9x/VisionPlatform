# Đánh giá Sau Triển khai Vấn đề #04 (StageContract + SyncLinearExecutor + Demo Pipeline)

Báo cáo này đánh giá chất lượng triển khai, các test cases, và phân tích sâu sắc các rủi ro kiến trúc dài hạn cho sản phẩm thương mại liên quan đến **Vấn đề #04 (step-04)**.

---

## 1. Đánh giá Mức độ Tuân thủ Thiết kế và Kiến trúc (DoD)

### Sự khớp nối Layer & Composition Root
* **Stage Contract (`kernel/stage_contract.py`):** Triển khai chính xác các thực thể dữ liệu bất biến (`StageResult`, `ExecutionResult`) bằng `@dataclass(frozen=True)` và định nghĩa hợp đồng hành vi (`IStage`) bằng `typing.Protocol`.
* **Base Stage (`runtime/base_stage.py`):** Đóng vai trò là scaffold trung gian rất tốt để chuẩn hóa việc xử lý ngoại lệ, tự động dịch các tín hiệu skip (`SkipFrameSignal`) và lỗi thành các kết quả có cấu trúc.
* **Composition Root (`profiles/demo_pipeline.py`):** Thể hiện đúng tư duy Clean Architecture khi đây là nơi duy nhất import trực tiếp các adapters cụ thể (`FakeFrameSource`, `NoiseFrameSource`), khởi tạo các stages, và liên kết chúng thông qua executor.

---

## ## 2. Bằng chứng Kiểm chứng Runtime (Test Suite & Demo End-to-End)

Tôi đã tự chạy kiểm thử trên môi trường ảo `.venv` và ghi nhận kết quả:
* **pytest:** **63 passed, 1 skipped** (tổng số 64 test cases). 
  * Đã chạy thành công 12 test case mới của Step 04 kiểm tra các hành vi của Executor, BaseStage, BrightnessStage, và DarkFilterStage.
* **lint-imports:** **5 kept, 0 broken** (33 files, 48 dependencies). Cấu trúc layer được bảo toàn tuyệt đối.
* **Demo End-to-End chạy thật:** Với cấu hình nguồn giả lập (`fake`), 5 frames, threshold 100:
  * Kết quả: `Processed: 0`, `Skipped (filter): 5`, `EOF: 1`. Kết quả này chính xác 100% so với thiết kế vì độ sáng của 5 frame đầu (từ 0 đến 4) đều nhỏ hơn threshold 100 nên bị lọc bỏ hoàn toàn.

---

## 3. Các Rủi ro Kiến trúc Sâu sắc Vẫn Tồn tại (Cực kỳ Quan trọng cho Sản phẩm Thương mại)

Dù mã nguồn hiện tại đã vượt qua toàn bộ test suite, dưới lăng kính phát triển hệ thống chạy 24/7 quy mô thương mại, chúng tôi phát hiện ra **4 rủi ro lớn** sau đây:

### Rủi ro 1: Rò rỉ tài nguyên âm thầm do Nuốt lỗi Teardown (Silent Teardown Failure)
* **Chi tiết:** Phương thức `teardown_all` của `SyncLinearExecutor` sử dụng khối lệnh:
  ```python
  def teardown_all(self) -> None:
      for s in self._stages:
          try:
              s.teardown()
          except Exception:
              pass
  ```
* **Hiện tượng:** 
  1. Việc dọn dẹp được thực hiện theo **thứ tự xuôi** thay vì **thứ tự ngược** (`reversed(self._stages)`). Nếu Stage B phụ thuộc vào tài nguyên của Stage A, việc đóng Stage A trước sẽ khiến Stage B lỗi khi cố dọn dẹp.
  2. Khối `except Exception: pass` nuốt toàn bộ lỗi một cách im lặng. Nếu một stage gặp lỗi khi giải phóng bộ nhớ, kẹt socket, hoặc không thể giải phóng camera bus, lỗi này sẽ bị bỏ qua và không bao giờ được ghi nhận vào hệ thống giám sát. Sau nhiều ngày chạy liên tục, tài nguyên rò rỉ sẽ làm treo toàn bộ hệ điều hành (Resource Exhaustion).
* **Khắc phục:** Cần đảo ngược thứ tự teardown và **ghi log cảnh báo rõ ràng** (thay vì nuốt lỗi) khi một stage giải phóng tài nguyên thất bại.

### Rủi ro 2: Kẹt luồng chính do Xử lý Đồng bộ (Single-threaded Blocking Bottlenecks)
* **Chi tiết:** `SyncLinearExecutor` chạy toàn bộ pipeline (Đọc frame -> Xử lý Stage 1 -> Xử lý Stage 2 -> ...) trên một luồng duy nhất.
* **Rủi ro thật:** Nếu bất kỳ stage nào ở hạ nguồn bị block (ví dụ: Deep Learning inference mất 100ms, hoặc gửi dữ liệu qua API bị lag mạng), toàn bộ luồng chính sẽ bị dừng lại. Điều này khiến việc đọc frame từ camera (`source.read()`) bị chậm theo. Đối với các dòng camera IP (RTSP), việc không đọc buffer liên tục sẽ lập tức gây ra hiện tượng tràn buffer driver, tăng độ trễ hình (latency buildup) hoặc mất kết nối camera.
* **Khắc phục:** Đây chỉ là sync executor demo. Với sản phẩm thương mại, bắt buộc phải dùng các Executor bất đồng bộ (Async/Multi-threading/Multi-processing) với các hàng đợi đệm (bounded queue) giữa các stage.

### Rủi ro 3: Phụ thuộc ngầm về Dữ liệu giữa các Stage (Temporal Coupling)
* **Chi tiết:** `DarkFilterStage` yêu cầu phải có thuộc tính `brightness` trong `packet.artifacts` (do `BrightnessStage` tạo ra trước đó).
* **Rủi ro thật:** Sự phụ thuộc này hoàn toàn nằm ngoài tầm kiểm soát của static type checkers (như mypy). Nếu dev cấu hình sai thứ tự trong composition root (đặt Filter trước Brightness), lỗi chỉ xuất hiện tại runtime khi frame đầu tiên đi qua. Khi hệ thống mở rộng lên hàng chục stage, mạng lưới phụ thuộc ngầm này sẽ cực kỳ khó kiểm soát.
* **Khắc phục:** Cần xây dựng cơ chế tự xác thực cấu hình pipeline (Pipeline Configuration Validation) lúc khởi động. Executor phải quét qua các stage để so khớp "Output Schema" của stage trước với "Input Schema" của stage sau trước khi cho phép chạy loop.

### Rủi ro 4: Thiếu cơ chế Quản lý Vòng đời tự động (No Context Manager)
* **Chi tiết:** Executor và Source yêu cầu phải gọi `setup_all()`/`setup()` ở đầu và bắt buộc phải gọi `teardown_all()`/`teardown()` trong khối `finally` ở cuối.
* **Rủi ro thật:** Nếu dev sử dụng executor ở nhiều nơi và quên bọc nó trong `try-finally`, hoặc khi executor bị hủy/lỗi giữa chừng mà supervisor không gọi teardown, tài nguyên sẽ bị rò rỉ lập tức.
* **Khắc phục:** Nên triển khai giao thức Context Manager của Python (`__enter__` và `__exit__`) cho cả `SyncLinearExecutor` và `IFrameSource` để đảm bảo việc thu hồi tài nguyên luôn được thực hiện tự động bằng cú pháp `with`.

---

## 4. Đánh giá Mức độ Kỷ luật Quy trình (AGENTS.md)

* **Luật per-turn (§2.5):** Hoàn toàn tuân thủ. Con trỏ hiện tại trong `memory-bank/activeContext.md` và `implement/00-IMPLEMENTATION-TRACKER.md` đã được đồng bộ với mốc ngày `2026-06-20`.
* **Nhật ký AI-IMPLEMENTATION-LOG.md:** Đã được append một cách có kỷ luật (Entry #47).
* **Quản lý file rác:** Toàn bộ file tạm (`_t.txt`, `_l.txt`, `_demo.txt`) đã được dọn sạch trước khi kết thúc phase.

---
*Báo cáo được tạo bởi Antigravity vào lúc 2026-06-20. Thiết kế của Vấn đề #04 đã được kiểm chứng thành công.*
