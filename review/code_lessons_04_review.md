# Đánh giá & Rà soát Kiến trúc Cực sâu (Bài #04 - Pipeline)

Báo cáo này đánh giá chi tiết cấu trúc, nội dung, tính sư phạm của các tài liệu giải thích mã nguồn trong thư mục `code-lessons/04-pipeline/`, đồng thời vạch ra các rủi ro thiết kế ngầm ẩn, lỗ hổng quản lý tài nguyên, và các điểm mâu thuẫn sư phạm trong codebase.

---

## 1. Đánh giá Tổng quan Chất lượng Sư phạm

* **Ưu điểm nổi bật:**
  * **Giải thích xuất sắc lỗi Traceback Retention (Mẩu 01):** Bài giảng giải thích cực kỳ trực quan và sâu sắc về cơ chế Python giữ lại stack frame (kèm theo các biến local là mảng ảnh lớn) khi Exception bị lưu giữ trong hàng đợi, từ đó gây ra rò rỉ RAM âm thầm. Đây là bài học chất lượng cao về quản lý bộ nhớ Python cấp thấp.
  * **Áp dụng mẫu thiết kế chuẩn chỉ (Mẩu 04 & 07):** Giới thiệu mượt mà mẫu thiết kế **Template Method** kết hợp với **ABC** trong `BaseStage` để chuẩn hóa khâu bắt lỗi, và sử dụng **Protocol** trong `IStage` để đạt sự linh hoạt khi cắm ghép các stage.
  * **Hướng dẫn tư duy phân tách rạch ròi (Mẩu 02):** Giải thích rõ lý do thay thế trả về `Optional[MediaPacket]` bằng đối tượng kết quả `ExecutionResult` để tránh việc nuốt lỗi (silent error swallowing) và phân biệt rõ rệt giữa việc filter chủ ý (SKIPPED) với lỗi runtime (ERROR).

---

## 2. Phân tích Các Rủi ro Kiến trúc Chí tử trong Thiết kế Pipeline (Chỉ đánh giá)

Qua việc đối chiếu kỹ lưỡng mã nguồn của Bài #04 (`stage_contract.py`, `base_stage.py`, `sync_linear_executor.py`, `demo_pipeline.py`), chúng tôi phát hiện ra **6 rủi ro thiết kế và cạm bẫy tiềm ẩn**:

### 🚨 Rủi ro 1: Mất Stack Trace khi xử lý Exception (Traceback Loss vs. Memory Leak)
* **Vấn đề (Độ nghiêm trọng: Cao):**
  Để giải quyết triệt để lỗi rò rỉ bộ nhớ **E-14/R5 (Traceback Memory Retention)**, `StageResult.error` được thiết kế chỉ trích xuất `error_type` (str) và `error_message` (str) từ Exception, hoàn toàn vứt bỏ Exception object cùng traceback của nó:
  ```python
  @classmethod
  def error(cls, error: Exception, stage: str = "") -> "StageResult":
      return cls(
          status=StageStatus.ERROR,
          error_type=type(error).__qualname__,
          error_message=str(error),
          stage=stage,
      )
  ```
  Việc này giúp bảo vệ RAM nhưng lại **tước đi khả năng debug** của lập trình viên. Khi xảy ra lỗi phức tạp trong model AI hoặc logic xử lý ảnh lồng sâu, người vận hành hệ thống chỉ nhận được thông báo lỗi chung chung (ví dụ: `IndexError: index out of bounds`) mà không có bất kỳ thông tin nào về dòng code bị lỗi (no stack trace).
* **Đề xuất cải tiến thiết kế:**
  Sử dụng mô hình **Cân bằng Trade-off**: Tại thời điểm bắt Exception trong `BaseStage.process`, ta có thể sử dụng thư viện `traceback` để định dạng toàn bộ call stack thành một chuỗi ký tự thô (`str`) bằng `traceback.format_exc()`. Chuỗi ký tự thô này hoàn toàn không giữ tham chiếu đến stack frame hay biến local (không gây rò rỉ RAM) nhưng vẫn lưu giữ trọn vẹn thông tin debug quý giá cho lập trình viên.

---

### 🚨 Rủi ro 2: Mâu thuẫn Sư phạm & Lỗi Rò rỉ Tài nguyên trong Demo Pipeline
* **Vấn đề (Độ nghiêm trọng: Cao):**
  Bài giảng mẩu 08 nhấn mạnh việc đưa `setup_all`/`teardown_all` vào context manager (`__enter__`/`__exit__`) của `SyncLinearExecutor` để tự động hóa việc dọn dẹp, tránh cạm bẫy quên đóng stage nếu có exception nổ ra giữa chừng (lỗi **E-14**).
  Tuy nhiên, trong file composition root chạy thật của bài học là `demo_pipeline.py`, lập trình viên **hoàn toàn không sử dụng** cú pháp `with executor:`! Thay vào đó, họ vẫn gọi thủ công:
  ```python
  source.setup()
  executor.setup_all()
  try:
      # run loop
  finally:
      executor.teardown_all()
      source.teardown()
  ```
  Sự không nhất quán này phá vỡ tính sư phạm (pedagogical consistency), khiến người học bối rối về cách sử dụng đúng.
* **Nguyên nhân sâu xa:**
  `IFrameSource` (cổng camera ở Bài #03) và các Adapter của nó (`FakeFrameSource`, `NoiseFrameSource`) **không hề được thiết kế để hỗ trợ Context Manager**! Chúng chỉ có các hàm mở/đóng thủ công `setup()` / `teardown()`. Vì vậy, dev không thể dùng cú pháp `with source, executor:` một cách đồng bộ.
* **Đề xuất cải tiến thiết kế:**
  Cần bổ sung các phương thức đặc biệt `__enter__` và `__exit__` cho `IFrameSource` (Protocol) tương tự như `SyncLinearExecutor` để đồng bộ hóa giao thức quản lý vòng đời tài nguyên trên toàn hệ thống.

---

### 🚨 Rủi ro 3: Trạng thái Khởi tạo mập mờ khi Teardown Thất bại nửa chừng
* **Vấn đề (Độ nghiêm trọng: Trung bình):**
  Trong `SyncLinearExecutor.teardown_all()`:
  ```python
  def teardown_all(self) -> None:
      for s in reversed(self._stages):
          try:
              s.teardown()
          except Exception:
              pass
  ```
  Nếu quá trình `executor.setup_all()` bị crash ở giữa chuỗi (ví dụ: stage thứ 3 lỗi driver camera/model AI), khối lệnh `finally` sẽ kích hoạt `teardown_all()`.
  Lúc này, `teardown_all()` sẽ cố gắng gọi `teardown()` trên **tất cả** các stage (bao gồm cả các stage chưa từng được khởi tạo thành công). Nếu hàm `teardown()` của các stage đó giả định tài nguyên đã tồn tại, nó sẽ ném ra lỗi `AttributeError` (lỗi này tuy bị nuốt bởi `except Exception: pass` nhưng lại che giấu trạng thái thực của hệ thống).
* **Đề xuất cải tiến thiết kế:**
  Executor nên duy trì một danh sách các stage đã được `setup()` thành công, và khi giải phóng chỉ thực hiện `teardown()` ngược lại trên danh sách đó để tránh gọi vào các stage chưa được khởi tạo.

---

### 🚨 Rủi ro 4: Im lặng Nuốt Lỗi trong Teardown (Silent Resource Leaks)
* **Vấn đề (Độ nghiêm trọng: Trung bình):**
  Hàm `teardown_all()` sử dụng `except Exception: pass` để đảm bảo nếu một stage dọn dẹp lỗi thì các stage tiếp theo vẫn được gọi dọn dẹp. Đây là ý đồ thiết kế tốt. Tuy nhiên, việc **im lặng bỏ qua hoàn toàn lỗi** mà không ghi lại bất kỳ thông tin cảnh báo nào (no logging/warning) sẽ làm ẩn giấu lỗi rò rỉ file descriptors, socket kẹt hoặc CUDA memory leak trong môi trường production chạy dài ngày.
* **Đề xuất cải tiến thiết kế:**
  Thay vì nuốt lỗi âm thầm, cần ghi nhận lỗi ra `sys.stderr`, dùng module `logging`, hoặc gom các exception lại bằng `ExceptionGroup` (Python 3.11+) để ném ra sau khi tất cả các stage đã được dọn dẹp xong.

---

### 🚨 Rủi ro 5: Stage State Leakage & Thread-Safety (Không an toàn đa luồng)
* **Vấn đề (Độ nghiêm trọng: Cao):**
  Thiết kế `IStage` và `BaseStage` cho phép các stage instance giữ trạng thái nội bộ. Nếu hệ thống sau này nâng cấp chạy đa luồng song song (ví dụ: dùng chung một danh sách các stage để xử lý frame từ nhiều camera đồng thời), các biến trạng thái nội bộ, bộ đệm hoặc model AI dùng chung trong các stage sẽ bị ghi đè chéo (data corruption / race conditions).
* **Đề xuất cải tiến thiết kế:**
  Hợp đồng `IStage` cần quy định rõ: các stage instance phải stateless đối với dữ liệu xử lý, hoặc nếu có state thì phải dùng cơ chế thread-local, hoặc mỗi luồng/camera pipeline phải tự sở hữu các stage instance độc lập hoàn toàn.

---

### 🚨 Rủi ro 6: Thiếu cơ chế Validate kiểu dữ liệu trả về của Stage (Type-Safety Bypass)
* **Vấn đề (Độ nghiêm trọng: Thấp):**
  Trong `BaseStage.process()`:
  ```python
  result_packet = self._do_process(packet)
  return StageResult.success(result_packet, stage=self._name)
  ```
  Phương thức `_do_process(packet)` của lớp con được mong đợi trả về một `MediaPacket`. Tuy nhiên, nếu lập trình viên viết sai logic trả về `None`, trả về mảng numpy thô, hoặc trả về một kiểu dữ liệu khác, `BaseStage` không hề thực hiện bất kỳ kiểm tra kiểu dữ liệu nào (type validation). Lỗi này sẽ lọt xuống các stage downstream và gây crash hệ thống ở một vị trí rất xa, gây khó khăn cho việc tìm nguyên nhân.
* **Đề xuất cải tiến thiết kế:**
  Bổ sung `assert isinstance(result_packet, MediaPacket)` ngay sau khi gọi `_do_process` để phát hiện lỗi lập trình sớm nhất có thể.

---

## 3. Nhật ký các thay đổi trong phiên hiện tại

| Đường dẫn File | Loại thay đổi | Lý do thực hiện |
| :--- | :--- | :--- |
| `review/code_lessons_04_review.md` | **New** (File này) | Bản đánh giá chất lượng sư phạm và rà soát kiến trúc cực sâu cho bài học #04 (Pipeline). |

---
*Báo cáo được lập bởi Antigravity vào lúc 2026-06-21. Toàn bộ các rủi ro kiến trúc đã được đối chiếu kỹ lưỡng với mã nguồn thật.*
