# K-012 — Phân tích thiết kế: cấp phát khoá slot cross-process cho ring mới (chặn Task 6)

> **Trạng thái:** DESIGN-FIRST · CHƯA code · chờ user VALID + chốt hướng.
> **Ngày:** 2026-07-03 · **Nguồn grounded:** đọc code thật (không đoán) — trích dưới.
> Mọi khẳng định chưa chạy đều gắn **[chưa kiểm]**; đã đọc code gắn **(verify)**.

## 1. Vấn đề (bản chất, không phải ngọn)

**Hiện trạng (verify — đọc code):**
- `ShmRingBuffer.__init__` (đọc L240-284): `create=False` **bắt buộc** nhận `slot_locks` từ parent; không có → `RuntimeError` (`test_attach_without_locks_raises` verify). Child **không tự tạo lock local** (sẽ là lock KHÁC → không loại trừ lẫn nhau cross-process).
- Cấp lock cross-process hiện tại (verify — `test_step_05_shm.py` L200-204, `test_hardening_kill_recovery.py` L46-48): `mp.Process(args=(..., ring.slot_locks_for_children, ...))` → `mp.Lock` **thừa kế qua spawn**. Điều kiện: **ring tạo TRƯỚC khi spawn worker**.

**Mâu thuẫn với switchover:** ring epoch N+1 sinh ra **trong lúc** writer/reader đã chạy (switchover runtime). `mp.Lock` **không truyền được** vào process đang chạy (thừa kế chỉ lúc spawn; `mp.Lock` **không mở được theo tên**). ⇒ worker không thể khoá slot của ring mới ⇒ recovery/quarantine/single-writer trên ring mới **không hoạt động cross-process**.

> Task 4.2/4.3/5 hiện ĐÚNG cho **in-process** (ring_opener trả ring có sẵn lock). Cross-process THẬT (Task 6 T-B) chặn ở đây.

## 2. Ba hướng (Forces + cái giá + khi nào KHÔNG dùng)

### H1 — Named OS primitive (khoá mở-theo-tên)
- **Ý tưởng:** thay `mp.Lock` bằng khoá có TÊN mở được ở mọi process: Windows named mutex (`CreateMutexW`/`OpenMutexW` qua `ctypes`), POSIX `posix_ipc.Semaphore` (thư viện ngoài) / `sysv_ipc`.
- **Được:** ring mới sinh runtime → mọi worker `OpenMutex(name)` theo tên → khoá thật. Số ring phân biệt **không giới hạn**. Đúng bản chất "khoá cross-process động".
- **Giá:** (a) code **phụ thuộc nền tảng** (ctypes Windows + thư viện ngoài POSIX — **dependency mới**, chưa có trong `pyproject`). (b) Vòng đời khoá có tên: phải create/open/close/**unlink** — thêm bài toán rò rỉ named object (POSIX persist tới unlink — cùng loại K-003). (c) Sửa **mọi điểm** acquire/release + thay đổi lớn ở `ShmRingBuffer`. (d) Rủi ro hồi quy cao trên 216 test hiện có.
- **[chưa kiểm]:** khả dụng thực tế của named mutex qua ctypes trên máy này + `posix_ipc` cài được; ngữ nghĩa timeout acquire khớp `mp.Lock`.
- **KHÔNG dùng khi:** không cần vô số ring phân biệt đồng thời (đúng ca của ta — rebuild là hiếm, chỉ cần vài ring sống chồng lúc migrate).

### H2 — Ring pool cấp sẵn, tái dùng vòng (KHUYẾN NGHỊ)
- **Ý tưởng:** tạo TRƯỚC một pool cố định K ring lúc startup; truyền **toàn bộ** `slot_locks` của K ring cho mọi worker qua spawn (thừa kế — CƠ CHẾ ĐÃ VERIFY). Switchover epoch N → dùng `pool[N % K]`: **bump `ring_epoch`** trong ctrl của ring đó + reset slot về FREE + `register_writer` + `publish(N, name_pool[N%K])`. Không cấp SHM/lock mới runtime.
- **Được:** (a) **KHÔNG đổi cơ chế khoá** — dùng lại `mp.Lock` thừa kế + toàn bộ recovery/quarantine/single-writer đã verify. (b) **Không cấp phát runtime** → hợp real-time (không jitter do alloc giữa luồng). (c) Bộ nhớ **bị chặn, đoán trước** = K × ring. (d) Rủi ro thấp: switchover chỉ còn "reset + bump epoch + publish" trên ring có sẵn. (e) `ring_epoch` đơn điệu vẫn phân biệt thế hệ dù TÊN lặp lại (stale-check theo epoch — đã verify sẵn ở `read`).
- **Giá:** (a) số ring sống CHỒNG cùng lúc ≤ K → cần ring cũ **drain xong** (reader rời) trước khi vòng lại tái dùng slot pool (với K≥2–3 và migrate nhanh/best-effort-drop thì đủ). (b) Luôn giữ K× bộ nhớ dù chỉ dùng 1. (c) Cần cơ chế reset-state-on-reuse an toàn (chỉ creator reset khi chắc không còn reader — dùng reader registry đã có).
- **[chưa kiểm]:** hành vi reset ctrl `ring_epoch` + clear slot khi tái dùng chưa code/chưa test; ngưỡng K tối thiểu thực tế.
- **KHÔNG dùng khi:** cần vô số ring kích thước KHÁC nhau đồng thời / không biết trước K (không phải ca của ta).

### H3 — Slot protocol lock-free (bỏ per-slot mp.Lock)
- **Ý tưởng:** bỏ khoá, chỉ dùng ghi state atomic 4B + kỷ luật CAS/generation.
- **Được:** hết hẳn bài toán cấp khoá cross-process; nhẹ nhất runtime.
- **Giá:** thiết kế lại lõi writer/reader; phải **chứng minh** atomicity/visibility đa-process — **dính K-001 (ARM chưa test HW)**; rủi ro rất cao; mâu thuẫn quyết định #05 (đã chọn khoá + QUARANTINED terminal vì `mp.Lock` không robust khi chết). Không hợp "từng bước chắc chắn".
- **KHÔNG dùng khi:** chưa có ngân sách kiểm chứng atomicity sâu trên mọi HW đích (đúng hiện tại).

## 3. Khuyến nghị (để user valid)

**Chọn H2 (ring pool, tái dùng vòng)** cho giai đoạn thương mại near-term:
- Giải K-012 bằng cách **né cấp-phát-động** (khoá tạo 1 lần lúc startup, mọi worker thừa kế) — tái dùng **toàn bộ máy móc đã verify**, rủi ro thấp nhất.
- Hợp **real-time** (không alloc giữa luồng) + bộ nhớ **đoán trước** (tiêu chí sản phẩm 24/7).
- H1 để dành nếu sau này CẦN vô số ring động (chưa cần). H3 là hướng nghiên cứu dài hạn, gắn với giải quyết K-001 (ARM).

## 4. Nếu chốt H2 — các điểm PHẢI thiết kế tiếp (trước khi code Task 6)
1. K tối thiểu (đề xuất K=2 hoặc 3) + lập luận drain-before-reuse.
2. Ai reset ring khi tái dùng (supervisor, chỉ khi reader_count==0 toàn ring) + emit observability.
3. `RingSupervisor.switchover()` đổi từ "tạo ring mới" → "chọn pool[N%K] + bump epoch + reset + publish" (đụng D-002 — sẽ ghi C-mới + đảo một phần).
4. Coordinator `ring_opener` map tên→ring pool có sẵn (đã hợp với thiết kế hiện tại).
5. T-B: spawn writer+reader với TOÀN BỘ locks pool; kill → threshold → switchover sang pool ring khác → assert reader ref epoch cũ=None, bắt epoch mới; đo frame-drop (điền Q2).

## 5. Trạng thái
- CHƯA code gì cho K-012/Task 6. Đây là artifact **design-first** chờ user VALID + chốt H1/H2/H3.
- 216 passed/1 skipped hiện tại KHÔNG đụng (phân tích thuần tài liệu).

## 6. Cập nhật sau VALID SÂU (2026-07-03) — đính chính + phát hiện (verify từ code)

> Bổ sung append-only. Lượt phân tích đầu (§1-5) có 1 chỗ NHẸ TAY về teardown — sửa ở đây (không giấu).

### 6.1 (verify) `ring_epoch` đọc LIVE cross-process → H2 khả thi về epoch
- `ShmRingBuffer.ring_epoch` là **@property đọc thẳng ctrl segment mỗi lần** (đọc L335-337):
  `return struct.unpack_from(U64_FMT, self._ctrl_shm.buf, OFFSET_RING_EPOCH)[0]`.
- `test_hardening_ring_epoch.py` L67-70 (verify): ghi thẳng `struct.pack_into(..., ctrl.buf, OFFSET_RING_EPOCH, 3)` → `ring.ring_epoch==3` + `reader.read_ref(ref_epoch2)` → None.
- ⇒ Với H2, supervisor **bump `ring_epoch` trong ctrl** khi tái dùng pool ring → mọi process đang attach ring đó **thấy epoch mới LIVE** → stale-check phân biệt thế hệ đúng dù TÊN ring lặp lại. **H2 chạy được về mặt epoch (bằng chứng: test poke ctrl trực tiếp đã pass).**
- Lưu ý (verify): `ShmFrameWriter._ring_epoch` **cache lúc __init__** → coordinator PHẢI dựng writer mới khi switch (đã làm ở D-008). Reader dùng `self._ring.ring_epoch` LIVE (không cache) → luôn đúng.

### 6.2 (ĐÍNH CHÍNH) H2 SỬA mô hình teardown — không "tương thích sẵn" như nói ở §3
- Pool cố định K ring ⇒ ring **KHÔNG free khi migrate**; giữ + reset + tái dùng vòng. Hệ quả:
  - **Supervisor phải GIỮ cả K ring suốt phiên** (pool owner) → **mâu thuẫn D-010** ("supervisor close ring cũ sau publish") và **quyết định B** ("OS free ở handle cuối khi migrate"). Dưới H2, không free giữa phiên; chỉ free lúc shutdown (`cleanup_all` cả pool).
  - Coordinator `old.close()` (D-008/D-009) vẫn OK (worker rời handle của nó) NHƯNG segment KHÔNG biến mất vì supervisor còn giữ → đúng ý "ring tái dùng được".
- **Mặt TỐT (không phải nợ):** H2 **MOOT K-003** (teardown Linux `resource_tracker` giữa vận hành) vì không free/unlink giữa phiên; alloc/free chỉ ở startup/shutdown → hợp real-time + đơn giản hơn về teardown.
- **Việc phải làm nếu chốt H2:** đảo D-002 (switchover: chọn pool[N%K] + reset + bump epoch, KHÔNG tạo tên mới) + đảo D-010 (supervisor GIỮ pool, không close-per-migrate) + điều chỉnh Task 5 (teardown = shutdown-only). Ghi C-mới + K-mới khi triển khai.

### 6.3 So sánh lại (đã đủ thông tin)
- **H2**: locking rủi ro THẤP (dùng lại lock thừa kế verified) + real-time + moot K-003; **giá = sửa mô hình teardown (D-002/D-010/B) + giữ K× RAM + drain-before-reuse**.
- **H1**: GIỮ mô hình create-new/free-old (Task 1-5 gần như nguyên) nhưng thêm named-lock (dependency + code theo nền tảng) + GIỮ K-003 + rủi ro hồi quy cao.
- **Khuyến nghị GIỮ NGUYÊN = H2**, nhưng nay nêu RÕ: chọn H2 = chấp nhận đảo D-002/D-010 (teardown thành pool-shutdown-only). Đây là đánh đổi có LỢI cho sản phẩm 24/7 (bộ nhớ đoán trước, không jitter, teardown đơn giản), miễn chấp nhận RAM K× + drain-before-reuse.

### 6.4 CHƯA verify (chờ khi code, nếu chốt H2)
- [chưa kiểm] cơ chế reset ring an toàn khi tái dùng (chỉ creator, khi reader_count==0 toàn ring + writer rời) — chưa có `reset_for_reuse()`.
- [chưa kiểm] K tối thiểu thực tế (đề xuất 2-3) + hành vi khi rebuild dồn dập (ring kế chưa drain).
- [chưa kiểm] đo frame-drop lúc switchover (Q2) — Task 6.
