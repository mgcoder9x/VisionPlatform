# Đánh giá Thiết kế Vấn đề #02 (Domain BBox + Kernel ReadResult + MediaPacket)

Tài liệu này đánh giá chi tiết các vấn đề kỹ thuật, rủi ro kiến trúc và đề xuất cải tiến liên quan đến **Vấn đề #02 (step-02)** của Module 03, đồng thời ghi nhận chính xác các thay đổi đã thực hiện trong phiên hiện tại.

---

## 1. Các vấn đề kỹ thuật phát hiện liên quan đến Vấn đề #02

### Vấn đề A: Lệch pha Namespace giữa Thiết kế và Thực tế
* **Hiện tượng:** Tài liệu thiết kế gốc `step-02-first-mediapacket.md` sử dụng package name `vision_demo` (ví dụ: `from vision_demo.domain.bbox ...`). Tuy nhiên, ở Vấn đề #01, package thực tế đã được thống nhất đặt tên là `vision_platform`.
* **Ảnh hưởng:** Nếu copy-paste code thiết kế trực tiếp sẽ gây lỗi import lập tức.
* **Giải pháp:** Sẽ tự động chuẩn hóa toàn bộ import sang `vision_platform` khi viết code nguồn và test.

### Vấn đề B: Rò rỉ tính Bất biến (Immutability) khi qua Ranh giới Tiến trình (Pickle/Multiprocessing)
Đây là lỗi thiết kế tinh vi và nguy hiểm nhất khi chạy đa tiến trình trong Python:
* **Cơ chế lỗi:** 
  1. Trong thiết kế, `InMemoryArrayRef` khóa mảng NumPy bằng cách đặt cờ `array.setflags(write=False)` trong `__post_init__`.
  2. Khi truyền `MediaPacket` qua các process khác nhau (sử dụng multiprocessing Queue), Python sử dụng thư viện `pickle` để tuần tự hóa (serialize) dữ liệu.
  3. Thử nghiệm thực tế của tôi chứng minh rằng: **Khi `pickle` khôi phục (deserialize) một mảng NumPy, nó luôn đặt cờ `writeable = True`** ở process nhận.
  4. Đồng thời, `pickle.loads` dựng lại dataclass bằng cách cập nhật trực tiếp `__dict__` mà **KHÔNG chạy lại `__post_init__`**.
* **Hậu quả:** Ở process nhận, mảng NumPy bên trong `InMemoryArrayRef` sẽ hoàn toàn writable. Mọi luồng/tiến trình ở tầng sau có thể vô tình mutate dữ liệu gốc mà không gặp bất kỳ lỗi hay cảnh báo nào, phá vỡ hợp đồng bất biến của MediaPacket.
* **Giải pháp khắc phục:** Bổ sung phương thức `__setstate__(self, state)` tùy chỉnh cho `InMemoryArrayRef`. Khi unpickle, Python sẽ gọi phương thức này để khôi phục trạng thái, cho phép chúng ta chủ động gọi lại `setflags(write=False)` để khóa cứng mảng NumPy ở process nhận:
  ```python
  def __setstate__(self, state):
      object.__setattr__(self, 'array', state['array'])
      if self.array.flags.writeable:
          self.array.setflags(write=False)
  ```

### Vấn đề C: Rủi ro thiếu Kiểm tra Kiểu dữ liệu (Type Safety) lúc Runtime
* **Hiện tượng:** `InMemoryArrayRef` khai báo thuộc tính `array: np.ndarray`. Nhưng do Python là dynamic typing, nếu caller truyền vào một kiểu khác (ví dụ: `list` hoặc `PIL.Image`), chương trình sẽ không báo lỗi lúc compile mà chỉ quăng lỗi `AttributeError: 'list' object has no attribute 'flags'` lúc runtime khi chạy `__post_init__`.
* **Giải pháp:** Nên bổ sung kiểm tra tường minh `isinstance(self.array, np.ndarray)` trong `__post_init__` để ném lỗi có nghĩa rõ ràng:
  ```python
  if not isinstance(self.array, np.ndarray):
      raise TypeError(f"array must be a numpy.ndarray, got {type(self.array)}")
  ```

### Vấn đề D: Thiếu phương thức CoW `without_metadata`
* **Hiện tượng:** Thiết kế định nghĩa `with_artifact`, `with_metadata`, và `without_artifact` nhưng thiếu `without_metadata`.
* **Đánh giá:** Trong các luồng camera, siêu dữ liệu gốc (metadata như camera_id, timestamp) là bất biến và không bao giờ được xóa. Do đó, việc thiếu `without_metadata` là hoàn toàn hợp lý về mặt nghiệp vụ để tránh làm mất thông tin nguồn gốc của frame.

---

## 2. Nhật ký chi tiết các thay đổi trong phiên hiện tại

Để đảm bảo tính minh bạch và kỷ luật cao nhất của dự án, dưới đây là chi tiết những gì tôi đã sửa đổi và lý do thực hiện:

| Đường dẫn File | Loại thay đổi | Lý do thực hiện |
| :--- | :--- | :--- |
| `memory-bank/activeContext.md` | **Modify** | Cập nhật con trỏ hiện tại sang Vấn đề #02 và cập nhật timestamp sang ngày 2026-06-20 (Tuân thủ Quy tắc cập nhật bộ nhớ per-turn §2.5 của `AGENTS.md`). |
| `implement/00-IMPLEMENTATION-TRACKER.md` | **Modify** | Đánh dấu Vấn đề #02 là đang thực hiện (`🔵`) để đồng bộ tiến độ. |
| `review/issue_02_design_review.md` | **New** (File này) | Viết báo cáo đánh giá sâu thiết kế và ghi nhận thay đổi theo yêu cầu trực tiếp từ người dùng. |
| *Thư mục Scratch (ngoài repo)* | **New** | Tạo các file thử nghiệm độc lập (`test_numpy_flags.py`, `test_dataclass_replace.py`, `test_numpy_pickle.py`, `test_numpy_pickle_setstate.py`) để chạy thật lấy bằng chứng kỹ thuật trước khi đưa ra nhận định. |

> [!IMPORTANT]
> **Cam kết:** Tôi **chưa sửa đổi hoặc tạo mới bất kỳ dòng code nguồn nào** thuộc package `vision_platform` (`src/vision_platform/`) hay các file kiểm thử chính thức của dự án (`tests/`). Trạng thái code nguồn vẫn giữ nguyên 100% so với thời điểm kết thúc Vấn đề #01.

---
*Tài liệu được biên soạn bởi Antigravity vào lúc 2026-06-20.*
