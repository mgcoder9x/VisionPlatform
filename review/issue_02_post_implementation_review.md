# Đánh giá Sau Triển khai Vấn đề #02 (Domain BBox + Kernel ReadResult + MediaPacket)

Báo cáo này đánh giá chi tiết chất lượng mã nguồn, mức độ tuân thủ thiết kế, và tính hiệu quả của các giải pháp vá lỗi an toàn đa tiến trình vừa được triển khai cho **Vấn đề #02 (step-02)**.

---

## 1. Đánh giá Mức độ Tuân thủ Thiết kế và Kiến trúc (DoD)

### Sự khớp nối Layer & Ranh giới Import
* **Domain Layer (`domain/bbox.py`):** Chỉ chứa Python thuần và Enum của thư viện tiêu chuẩn. Hoàn toàn sạch bóng các import liên quan đến I/O hoặc các thư viện ngoài phức tạp (như `cv2` hay `torch`).
* **Kernel Layer (`kernel/read_result.py` & `kernel/media_packet.py`):** Chỉ phụ thuộc vào Domain Layer và các thư viện hỗ trợ cấu trúc dữ liệu (`numpy`, `types`, `typing`).
* **Kiểm chứng Import Linter:** Kết quả `lint-imports` đạt **5 kept, 0 broken** đối với 18 files và 9 dependencies. Điều này khẳng định 100% ranh giới 4-layer Hexagonal không bị vi phạm.

### Chuẩn hóa Namespace
* Tất cả import trong mã nguồn dự án và file test đã được chuyển đổi thành công từ namespace giả định `vision_demo` sang package thực tế `vision_platform`. 

---

## 2. Phân tích Sâu sắc Giải pháp Vá lỗi An toàn (Multiprocessing & Type Safety)

Trong quá trình triển khai, hai lỗi thiết kế tiềm ẩn (được phân loại dưới mã lỗi **E-11** trong hệ thống Errata) đã được vá và kiểm chứng thành công:

### A. Vá lỗi mất tính Bất biến qua ranh giới Process (Pickle Deserialization)
* **Bản chất lỗi:** NumPy mặc định không bảo toàn thuộc tính `writeable = False` khi đi qua quá trình serialize/deserialize bằng `pickle`. Khi unpickle, mảng khôi phục có `writeable = True`, đồng thời `pickle.loads` bypass hàm `__post_init__` của dataclass, tạo kẽ hở lớn cho các thay đổi ngầm gây race-condition.
* **Giải pháp đã áp dụng:** Định nghĩa phương thức `__setstate__(self, state)` tùy chỉnh cho `InMemoryArrayRef` để chủ động khóa cứng mảng NumPy (`setflags(write=False)`) ngay khi unpickle được kích hoạt:
  ```python
  def __setstate__(self, state):
      object.__setattr__(self, "array", state["array"])
      if self.array.flags.writeable:
          self.array.setflags(write=False)
  ```
* **Bằng chứng test case:** Test case `test_array_ref_stays_readonly_after_pickle` đã kiểm chứng round-trip unpickle và khẳng định mảng phục hồi vẫn bị khóa cứng, ném `ValueError` nếu cố tình mutate.

### B. Cải thiện An toàn Kiểu dữ liệu lúc Runtime (Runtime Type Safety)
* **Bản chất lỗi:** Nếu dev truyền sai kiểu dữ liệu (như Python `list` hay PIL Image) vào `InMemoryArrayRef`, Python sẽ quăng lỗi `AttributeError` khó hiểu khi cố đọc thuộc tính `.flags`.
* **Giải pháp đã áp dụng:** Bổ sung check loại dữ liệu tường minh trong `__post_init__`:
  ```python
  if not isinstance(self.array, np.ndarray):
      raise TypeError(
          f"array phải là numpy.ndarray, nhận {type(self.array).__name__}"
      )
  ```
* **Bằng chứng test case:** Test case `test_array_ref_rejects_non_ndarray` xác thực hàm ném chính xác ngoại lệ `TypeError` như mong đợi.

---

## 3. Bằng chứng Kiểm chứng Runtime (Test Suite)

Kết quả chạy thực tế của toàn bộ test suite dự án đạt trạng thái **xanh tuyệt đối**:

* **Lệnh chạy:** `pytest`
* **Kết quả:** **20 passed** (bao gồm 2 smoke test của step-01 và 18 test case của step-02).
* **Chi tiết kiểm thử:**
  * 4 test case cho `BBox` (khởi tạo, validate giá trị âm, frozen, bắt buộc truyền space).
  * 3 test case cho `ReadResult` (has_data, EOF, tính frozen).
  * 5 test case cho `InMemoryArrayRef` (chặn ghi, zero-copy ownership, defensive copy isolation, typecheck, và pickle re-lock).
  * 6 test case cho `MediaPacket` (chặn mutate trực tiếp metadata/artifacts, CoW chains, và Mapping isolation).

---

## 4. Các Rủi ro Kiến trúc Sâu sắc Vẫn Tồn tại (Cực kỳ Quan trọng)

Dù mã nguồn đã vượt qua toàn bộ 20 test cases và tuân thủ tuyệt đối các ràng buộc của tài liệu thiết kế, chúng tôi phát hiện ra **3 rủi ro tiềm ẩn** về mặt kiến trúc mà thiết kế gốc của Step 02 chưa thể giải quyết triệt để:

### Rủi ro 1: Rò rỉ tính Bất biến Nông (Shallow Immutability Leak) trong Metadata/Artifacts
* **Chi tiết:** `MappingProxyType` và hàm tạo bản sao `dict(self.metadata)` trong `MediaPacket.__post_init__` chỉ bảo vệ và sao chép ở mức **nông (shallow)**. 
* **Hiện tượng:** Nếu `metadata` hoặc `artifacts` chứa các đối tượng thay đổi được ở mức lồng sâu hơn (như Python `list` chứa các nhãn, hoặc một `dict` con), các stage hạ nguồn hoàn toàn có thể chỉnh sửa chúng:
  ```python
  # mutate phần tử con của MappingProxyType thành công mà không gây lỗi:
  packet.metadata["nested_list"].append("new_value")
  ```
  Thử nghiệm thực tế của chúng tôi đã xác nhận hành vi rò rỉ này.
* **Cách khắc phục triệt để:** Cần thực hiện defensive copy sâu (`copy.deepcopy`) khi khởi tạo hoặc sử dụng các cấu trúc bất biến chuyên biệt (như `frozendict` hoặc Pyrsistent) cho metadata/artifacts nếu chúng chứa dữ liệu phức tạp.

### Rủi ro 2: Lỗi ghi đè vùng nhớ do Tái sử dụng Buffer (Buffer Reuse Tearing) của Camera Adapter
* **Chi tiết:** Trong các SDK camera hiệu năng cao (như OpenCV đọc từ USB, hoặc GStreamer, RTSP), adapter thường sử dụng cơ chế ghi đè tuần hoàn lên một NumPy array cố định để tránh cấp phát bộ nhớ liên tục.
* **Hiện tượng:** Mặc dù `InMemoryArrayRef` khóa mảng bằng `write=False` để ngăn downstream stages chỉnh sửa mảng, nó **không thể ngăn** camera adapter ghi đè dữ liệu frame mới lên chính buffer đó khi camera nhận frame tiếp theo. Điều này sẽ làm biến đổi ngầm dữ liệu của `MediaPacket` cũ mà các stage hạ nguồn đang xử lý, dẫn đến rách hình (tearing) hoặc race-condition nghiêm trọng.
* **Cách khắc phục triệt để:** Phải đảm bảo Camera Adapter thực hiện copy dữ liệu khi đóng gói vào `InMemoryArrayRef` (bằng `from_copy` thay vì `from_owned_array`), hoặc sử dụng hệ thống quản lý vòng đời buffer chặt chẽ (như ShmFrameBus ở Step 05).

### Rủi ro 3: Thiếu ràng buộc chặt chẽ trong không gian chuẩn hóa (Normalized Space Validation)
* **Chi tiết:** Khi BBox được gắn nhãn `CoordinateSpace.NORMALIZED`, các giá trị tọa độ `x, y, w, h` bắt buộc phải nằm trong khoảng `[0.0, 1.0]`. Tuy nhiên, `BBox` hiện tại chỉ kiểm tra `w >= 0` và `h >= 0`. Dev vẫn có thể vô tình khởi tạo một bbox có tọa độ 100.0 trong normalized space mà không bị báo lỗi.

---

## 5. Đánh giá Mức độ Kỷ luật Quy trình (AGENTS.md)

* **Luật per-turn (§2.5):** Hoàn toàn tuân thủ. Con trỏ hiện tại trong `memory-bank/activeContext.md` và `implement/00-IMPLEMENTATION-TRACKER.md` đã được đồng bộ với mốc ngày `2026-06-20`.
* **Nhật ký AI-IMPLEMENTATION-LOG.md:** Đã được append một cách có kỷ luật (Entry #43).
* **Quản lý file rác:** Toàn bộ file tạm trong thư mục `scratch/` đã được dọn sạch trước khi kết thúc phase.
* **Trạng thái Git:** Sẵn sàng commit.

---
*Báo cáo được tạo bởi Antigravity vào lúc 2026-06-20. Thiết kế của Vấn đề #02 đã được kiểm chứng thành công.*
