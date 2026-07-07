# Danh Sách Rủi Ro Kỹ Thuật Sâu Sắc: SHM Frame Bus Production Hardening

> **Mã thiết kế:** `shm-production-hardening`  
> **Tài liệu gốc:** [.kiro/specs/shm-production-hardening/design.md](file:///E:/VisionPlatform/.kiro/specs/shm-production-hardening/design.md)  
> **Trạng thái review:** 🔴 CHỈ TRÌNH BÀY RỦI RO & EDGE CASES (Không đề xuất giải pháp theo yêu cầu)  
> **Người thực hiện:** Antigravity (Gemini 3.5 Flash)

---

## 1. Rủi Ro Về Đồng Bộ Hóa Hệ Điều Hành (OS Locks & Poisoning)

### 1.1. Lock Hệ Điều Hành Bị Kẹt Vĩnh Viễn (Deadlock Thật Sự)
* **Chi tiết:** Thiết kế sử dụng cơ chế ghi đè `SlotState.QUARANTINED` vào shared memory khi phát hiện tiến trình giữ lock đã chết. Tuy nhiên, việc thay đổi trạng thái trong SHM **không giải phóng được Lock vật lý của hệ điều hành** (semaphores/mutexes được bọc bởi `multiprocessing.Lock`).
* **Hệ quả:** Lock đó vẫn bị kẹt ở mức nhân hệ điều hành. Khi một tiến trình mới (writer hoặc reader) cố gắng truy cập slot này sau khi nó được reclaim về `FREE`, tiến trình đó vẫn phải thực hiện acquire cái lock vật lý bị kẹt này và sẽ bị timeout vĩnh viễn. Slot này coi như bị cô lập vĩnh viễn khỏi hệ thống cho đến khi reboot.

### 1.2. Mâu Thuẫn Trạng Thái Trả Về Của Lock trên Windows (Abandoned Mutex)
* **Chi tiết:** Trên Windows, nếu một tiến trình giữ mutex bị crash, OS sẽ đánh dấu mutex là *abandoned* (`WAIT_ABANDONED`). Mặc dù Windows API cho phép phát hiện điều này để khôi phục, nhưng thư viện chuẩn Python `multiprocessing` không bộc lộ trực tiếp cơ chế xử lý này một cách nhất quán, dễ dẫn đến ném ngoại lệ không mong muốn (`RuntimeError` hoặc treo) khi tiến trình khác cố acquire lock.

---

## 2. Rủi Ro Trong Môi Trường Đa Reader (Multi-Reader Edge Cases)

### 2.1. Kẹt Reader Vĩnh Viễn Khi Một Reader Bị Crash (Reader Leak)
* **Chi tiết:** Khi một slot ở trạng thái `READING` được dùng chung bởi nhiều reader, trường `owner_pid` trong thiết kế chỉ lưu được 1 PID duy nhất (của writer hoặc của reader cuối cùng).
* **Hệ quả:** Nếu có 3 reader đang đọc song song và 1 reader bị crash đột ngột trước khi kịp gọi `unpin`, `reader_count` sẽ bị kẹt ở mức `> 0` vĩnh viễn. Slot đó mãi mãi ở trạng thái `READING`, không bao giờ chuyển sang `DONE`. Do writer không có cách nào biết PID của reader đã chết để dọn dẹp, slot này bị kẹt vĩnh viễn.

### 2.2. Race Condition Giữa Ghi Và Đọc Khi Quarantine Gây Corrupt Dữ Liệu
* **Chi tiết:** Nếu một reader chạy quá chậm và vượt quá `lease_deadline` nhưng tiến trình của nó vẫn đang sống. 
* **Hệ quả:** Nếu writer scan và phát hiện một reader khác đã chết trên slot đó và kích hoạt quarantine slot, hành động này có thể ngắt quãng reader đang sống và chạy chậm kia, dẫn đến việc đọc dữ liệu dở dang hoặc corrupt dữ liệu đầu ra của reader đó.

---

## 3. Rủi Ro Khác Biệt Nền Tảng & Môi Trường Chạy (Platform & Env Risks)

### 3.1. Rủi Ro Trùng/Tái Sử Dụng PID của Hệ Điều Hành (PID Reuse)
* **Chi tiết:** Các hệ điều hành tái sử dụng PID tuần hoàn hoặc ngẫu nhiên.
* **Hệ quả:** Nếu một tiến trình writer/reader chết đột ngột và ngay lập tức OS cấp PID đó cho một tiến trình hệ thống hoặc ứng dụng khác (ví dụ: Chrome). Khi kiểm tra `pid_is_alive(owner_pid)`, hàm sẽ trả về `True` (vì tiến trình mới trùng PID đang sống). Hệ thống sẽ không kích hoạt recovery cho slot bị kẹt, làm mất đi khả năng tự phục hồi.

### 3.2. Lỗi Phân Quyền Truy Cập Tiến Trình Trên Windows (Access Denied)
* **Chi tiết:** Khi dùng ctypes `OpenProcess` để kiểm tra trạng thái sống của PID, hàm yêu cầu quyền truy cập cụ thể vào tiến trình đó.
* **Hệ quả:** Nếu Writer chạy dưới một ngữ cảnh bảo mật cao hơn Reader (ví dụ: Administrator/SYSTEM service vs Standard User), Reader gọi `OpenProcess` sẽ bị lỗi `ERROR_ACCESS_DENIED` (5), khiến hàm `pid_is_alive` trả về `False` sai lệch và tự động quarantine nhầm một Writer vẫn đang hoạt động tốt.

### 3.3. Trạng Thái STILL_ACTIVE Trùng Mã Thoát Thực Tế của Tiến Trình
* **Chi tiết:** Hàm `pid_is_alive` trên Windows dựa trên việc so sánh exit code với `STILL_ACTIVE (259)`.
* **Hệ quả:** Nếu một tiến trình thực sự đã kết thúc nhưng trả về exit code là `259`, hàm sẽ xác định sai rằng tiến trình vẫn đang chạy.

---

## 4. Rủi Ro Về Hiệu Năng & Phần Cứng (Hardware & Performance)

### 4.1. Torn Read/Write và Memory Consistency trên ARM (Weak Memory Model)
* **Chi tiết:** Giả định ghi 32-bit aligned là atomic chỉ đúng tuyệt đối trên x86-64 (Intel/AMD). Trên kiến trúc ARM64 (như NVIDIA Jetson Orin/Nano, Apple Silicon), mô hình bộ nhớ là Weakly-Ordered.
* **Hệ quả:** Nếu thực hiện ghi lock-free `QUARANTINED` hoặc peek lock-free trạng thái slot mà không sử dụng các rào cản bộ nhớ (Memory Barriers / Fences) ở mức phần cứng, các core CPU khác có thể đọc thấy dữ liệu cũ hoặc không đồng bộ kịp thời, dẫn đến race condition trầm trọng trên các thiết bị Edge AI.

### 4.2. Tranh Chấp Lock (Lock Contention) Dưới Tải Cao
* **Chi tiết:** Việc sử dụng lock vật lý trên từng slot bắt buộc các tiến trình phải tuần tự hóa (serialize) các thao tác đọc ghi.
* **Hệ quả:** Khi hệ thống chạy với camera FPS cao (>60 FPS) hoặc nhiều camera truyền vào cùng một Ring, việc tranh chấp lock liên tục sẽ kéo tụt throughput truyền dữ liệu và tạo ra độ trễ không đồng đều (latency jitter).

---

## 5. Rủi Ro Khi Khởi Động Lại Hệ Thống (Cold Start & Sanitation)

### 5.1. Dữ Liệu Rác Và Lock Poison Sót Lại Từ Phiên Chạy Trước
* **Chi tiết:** Nếu hệ thống bị crash toàn bộ đột ngột (mất điện, tắt cưỡng bức), shared memory segment và semaphores của OS vẫn tồn tại trong RAM.
* **Hệ quả:** Khi hệ thống được bật lại, Writer/Reader khởi tạo mới và đính kèm (attach) vào vùng SHM cũ. Nếu không có cơ chế dọn dẹp sạch sẽ (sanitation/cold start wipe) toàn bộ metadata và trạng thái lock từ đầu, tiến trình mới sẽ đọc phải trạng thái rác hoặc bị kẹt ngay lập tức khi cố gắng acquire các lock bị poison từ phiên chạy trước.
