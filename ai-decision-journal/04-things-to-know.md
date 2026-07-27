# 04 — Bất kỳ điều gì bạn NÊN BIẾT (rủi ro / giả định / nợ / phần CHƯA kiểm)

> Đây là nơi giữ các món 🔴 **CHƯA verify** và giả định — để phiên sau không tưởng nhầm là "đã xong".
> Quy tắc: chỉ hạ 🔴→✅ khi có bằng chứng thật (lệnh+output/nguồn). Đóng thì cập nhật, đừng xoá.
> Trạng thái: ✅ đã đóng · 🟡 một phần · 🔴 đang mở.

---

### K-001 — 🔴 ARM atomicity/visibility CHƯA test trên phần cứng thật
Scope: #05 Task 11
Nguồn: LOG Entry #111 (`test_hardening_platform_scope` — x86-64 pass, ARM/khác → pytest.skip)
Ảnh hưởng: mọi lập luận "ghi state 4B atomic + visibility" mới chỉ đúng trên x86-64. Sản phẩm chạy ARM (vd Jetson) phải chạy `arm-atomic-sentinel-validation` trên HW thật trước khi tin.
Đóng khi: có kết quả test trên HW ARM thật.

### K-002 — ✅ (ĐÓNG 2026-07-03) Switchover CROSS-PROCESS thật — T-B pass 5/5
Scope: shm-ring-epoch-switchover / Task 6 (T-B)
Nguồn: LOG Entry #138 · `test_switchover_cross_process.py` · D-015
Ảnh hưởng (đã xử lý): T-B spawn THẬT — worker process ghi cross-process, parent switchover, worker chuyển ring đích + parent đọc frame epoch mới. 5/5 không flaky. full 232 passed/1 skipped.
Đóng: ✅ (Windows). Còn lại: race đa-process reader dày đặc + đo frame-drop Q2 (kịch bản tải riêng); POSIX ở T-C (K-003).

### K-003 — 🔴 Teardown trên Linux (resource_tracker) chưa verify — mới chỉ Windows
Scope: shm-ring-epoch-switchover / Task 7 (T-C), gắn D-004/T-002
Nguồn: LOG Entry #126 · activeContext ("POSIX MAY unlink sớm; 🔴 Linux resource_tracker verify ở T-C")
Ảnh hưởng: quyết định "OS handle ref-count" (D-004) được chứng minh bằng thực nghiệm trên **Windows**. POSIX/Linux có `resource_tracker` của `multiprocessing.shared_memory` có thể unlink sớm / cảnh báo leak — hành vi teardown có thể KHÁC.
Đóng khi: chạy T-C (leak/teardown) trên Linux thật.

### K-004 — 🔴 REBUILD_THRESHOLD chưa tuning theo SLA thật
Scope: #05 Task 10.2
Nguồn: LOG Entry #111 · T-006
Ảnh hưởng: default `ceil(n/2)` là phỏng đoán thận trọng, chưa có số đo. Có thể trigger rebuild sai nhịp trong tải thật.
Đóng khi: có benchmark SLA + chọn ngưỡng theo số đo.

### K-005 — 🔴 AccessDenied cross-privilege trên Windows còn dùng FAKE
Scope: #05 Task 1 (process identity/liveness)
Nguồn: LOG Entry #100, #111
Ảnh hưởng: nhánh psutil `AccessDenied` (khi query process khác quyền) test bằng monkeypatch, CHƯA dựng process khác privilege thật. Suy luận: AccessDenied ⇒ coi như ALIVE (an toàn), nhưng chưa chứng minh cross-privilege thật.
Đóng khi: test với process chạy quyền khác thật trên Windows.

### K-006 — ✅ (ĐÓNG 2026-07-03, Windows) Đa-process reader stress cross-process
Scope: #05 multi-reader / cross-process
Nguồn: LOG Entry #154 · `tests/test_multi_reader_cross_process.py`
Đã xử lý: N reader PROCESS riêng (lock thừa kế qua Process args) đọc đồng thời (barrier): (a) mỗi reader 1 slot riêng → tất cả đọc ĐÚNG data (không torn); (b) N reader cùng 1 slot → mỗi reader OK(đúng)/None, KHÔNG BAO GIỜ TORN/ERROR. **2 test, chạy 5/5 không flaky**, full 250 passed/1 skipped. Guard win32; POSIX chưa verify.
Đóng: ✅ Windows. (🔴 POSIX spawn để dành cùng K-003.)

### K-007 — 🔴 Push BỊ CHẶN QUYỀN (403) — ~38 commit develop chưa backup được (2026-07-03)
Scope: git / toàn repo
Nguồn: `git push -u origin develop` → **403 Permission denied**. Chẩn đoán read-only 2026-07-03: remote=`https://github.com/mgcoder9x/VisionPlatform.git` (URL sạch, không token); **AUTH push = tài khoản `toannmWeb`** (credential HTTPS đang lưu) thiếu write vào repo của `mgcoder9x`; commit-identity=`toannm7691@gmail.com` (không liên quan quyền); ahead 42 commit.
NGUYÊN NHÂN GỐC: credential push SAI TÀI KHOẢN (`toannmWeb` ≠ chủ repo `mgcoder9x`). 3 hướng sửa (USER làm, AI không đụng credential): A. nếu là mgcoder9x → sửa Windows Credential Manager (`git:https://github.com`) đăng nhập lại bằng mgcoder9x/PAT; B. chủ repo add `toannmWeb` làm collaborator (Write); C. đổi remote sang fork bạn sở hữu rồi push. Sau khi user sửa → AI push giúp (FF, không force). Rủi ro backup thật (mọi công sức chỉ ở máy local).
Ảnh hưởng: công việc switchover + dọn rác chưa lên remote → rủi ro mất nếu máy hỏng; người/AI khác clone origin sẽ KHÔNG thấy. Theo git-safety (§8 AGENTS): chỉ push khi được cho phép rõ.
Đóng khi: người dùng cho phép push (nên push nhánh, không đụng main).

### K-008 — 🟡 Có HAI bản memory-bank — dễ đọc nhầm bản template
Scope: hạ tầng bộ nhớ
Nguồn: file_search 2 kết quả `memory-bank/activeContext.md`
Ảnh hưởng: bản THẬT (đang chạy) = `memory-bank/` ở GỐC repo (activeContext cập nhật 2026-07-02, chi tiết #05/switchover). Bản trong `ai-learning-os-kit/memory-bank/` còn placeholder `{{...}}` — là TEMPLATE tái dùng, KHÔNG phải trạng thái thật. Đọc nhầm bản kit → tưởng dự án trống.
Đóng khi: (không cần đóng) — ghi nhớ luôn đọc bản gốc-repo; kit chỉ để copy sang dự án mới.

### K-009 — ℹ️ Log gốc chạy tới Entry #127, KHỚP git — không lệch pha (đã kiểm)
Scope: kiểm chứng đầu phiên
Nguồn: grep `Entry #12[0-9]` → tồn tại #120..#127; `git log` `b812071` = nội dung Entry #127 (`close()`)
Ảnh hưởng: xác nhận `AI-IMPLEMENTATION-LOG.md` đồng bộ với commit mới nhất — bước kế có thể tin log. (Lần đọc file đầu bị prune hiển thị tới #122; đừng nhầm là log dừng ở đó.)
Đóng: đã đóng (ℹ️ thông tin).

### K-011 — ✅ (ĐÃ ĐÓNG 2026-07-03) `tasks.md` 4.1/4.2/4.3 còn tàn dư API đã bỏ (detach/attach_register)
Scope: shm-ring-epoch-switchover / tasks.md, Wave 3
Nguồn: đọc `tasks.md` vs `ring_control_plane.py` + LOG Entry #126, #129
Ảnh hưởng (đã xử lý): đã sửa text 4.1/4.2/4.3 → dùng `ring.close()` (teardown B), bỏ `detach`/`attach_register`. Code coordinator (D-008) dùng close(), verify 206 passed/1 skipped.
Đóng: đã đóng (sửa spec khớp quyết định B, LOG #129).

### K-012 — 🔴 Cấp phát slot_locks (mp.Lock) cho ring mới ở process writer đang chạy — CHƯA giải
Scope: shm-ring-epoch-switchover / Task 4.2 (bản chất), Task 6 (T-B)
Nguồn: LOG Entry #129 · `ShmRingBuffer.__init__` (create=False YÊU CẦU slot_locks từ parent) · `WriterEpochCoordinator` docstring
Ảnh hưởng: `WriterEpochCoordinator` (D-008) VÀ `ReaderEpochCoordinator` (D-009) đều đúng cho IN-PROCESS (ring_opener trả ring có sẵn lock). Cross-process THẬT: ring mới do supervisor tạo ở process khác; writer/reader đang chạy KHÔNG thể nhận mp.Lock của ring đó (mp.Lock không attach theo tên). Đây là vấn đề GỐC của switchover cross-process, chưa có lời giải trong code hiện tại (chung cho cả writer + reader).
Đóng khi: Task 6 (T-B) chọn cơ chế lock cross-process + chứng minh spawn thật.
Trạng thái: 🔴 (phát hiện 2026-07-03) · **ĐÃ CÓ phân tích thiết kế:** `.kiro/specs/shm-ring-epoch-switchover/K-012-lock-provisioning-analysis.md` (H1 named-primitive / H2 ring-pool / H3 lock-free) + §6 valid sâu. **Khuyến nghị H2**.
**Valid sâu (verify từ code):** (a) `ring_epoch` là @property đọc LIVE ctrl segment (không cache) — `test_hardening_ring_epoch.py` poke ctrl trực tiếp đã pass ⇒ H2 bump-epoch nhìn thấy cross-process, khả thi. (b) **ĐÍNH CHÍNH:** H2 **SỬA mô hình teardown** — pool giữ K ring suốt phiên, reset+tái dùng, KHÔNG free giữa phiên ⇒ **sẽ đảo D-002 (tạo ring mới→chọn pool[N%K]+reset) + D-010 (supervisor close→GIỮ pool)**; mặt tốt: MOOT K-003 (teardown Linux giữa vận hành). Giá: K× RAM + drain-before-reuse.
**[2026-07-03] ĐÃ CHỐT H2** (user ủy quyền "theo khuyến nghị", D-011/C-006). Tiến độ đóng K-012:
- ✅ (1a) `reset_for_reuse` (D-011, 5 test) · ✅ (1b) `RingPool` + `make_pool_opener` (D-012, 9 test) → 230 passed/1 skipped.
- ✅ (2) `RingSupervisor` H2 dùng `pool.activate` (D-013, đảo D-002/D-010) — 4 test (3 fake + 1 pool thật), 229 passed/1 skipped.
- ✅ (3) coordinator + pool tích hợp in-proc (D-014, 2 test, 231 passed/1 skipped) — vòng switchover đầy đủ + cyclic reuse epoch 1→4 với SHM thật + single-writer giữ.
- ✅ (4) **T-B spawn cross-process THẬT** (D-015, 5/5 không flaky, 232 passed/1 skipped) — chứng minh lock THỪA KẾ phủ ring đích switchover → **K-012 GIẢI XONG cross-process (Windows)**.
K đề xuất 2-3 (chính xác cần đo SLA, như K-004).
**SUB-SPEC SWITCHOVER: Task 1-9 ✅ TRÊN WINDOWS (2026-07-03).** ✅ Task 8 (PBT, D-016) · ✅ Task 9 (observability, D-017) · ✅ Task 7 (T-C no-leak, D-018). Còn treo (đã ghi rõ, KHÔNG claim xong tuyệt đối): 🔴 K-003 (POSIX teardown) · 🔴 K-014 (Q2 số-đo-tải) · 🔴 K-001 (ARM). → Quay lại phần DẠY HỌC: Feynman #05 + viết bài switchover.

### K-014 — ✅ Q2 frame-drop: BOUND ≤ n_slots + drop@fps thật ĐÃ ĐO (perf-harness)
Scope: shm-ring-epoch-switchover / Q2
Nguồn: LOG Entry #155 · #453 · `tests/test_switchover_q2_bound.py` · `benchmarks/measure_ring_drop.py` · design.md §Q2
CẬP NHẬT 2026-07-03 (D-022): **bound ≤ n_slots đã chứng minh THỰC NGHIỆM** — worst-case (ring đầy frame chưa đọc) drop = 4 = n_slots; đối chứng drain trước switchover → drop = 0. 2 test deterministic pass.
CẬP NHẬT 2026-07-19 (D-149, ĐÓNG ✅): drop DƯỚI TẢI fps thật ĐÃ đo bằng `measure_ring_drop.py` (in-process keep-latest, 30fps producer, 480×640, 3 vòng variance≈0): consume 33ms→drop **0.0%**·cons_fps 30.0 · 50ms→**34.0%**·19.8 · 100ms(YOLO-CPU)→**66.2%**·10.0. Quan hệ **drop% ≈ 1 − consumer_rate/producer_rate**; **consumer_fps = 1000/consume_ms** bất kể producer → keep-latest **latency-bounded** (consumer không backlog, drop = frame cũ bỏ, không tích luỹ trễ) = hành vi ĐÚNG real-time, số này là SLA nguồn KHÔNG phải lỗi. Ghép #452 (detector-throughput GPU/CPU) → SLA đầu-cuối định lượng.
CÒN (ngoài scope đóng): đa-reader fan-out >1 consumer cùng ring (topology khác, ngoài đường web/inference 1-consumer/stream hiện tại) — chưa đo, KHÔNG bịa.

### K-013 — 🔴 Môi trường venv đổi phiên bản (dựng lại bằng Python máy hiện tại)
Scope: môi trường build/test
Nguồn: LOG Entry #129 · T-007
Ảnh hưởng: `.venv` cũ (snapshot) trỏ interpreter user khác → hỏng; dựng lại bằng Python 3.13 (scoop). Env MỚI: py3.13.12·numpy2.5.0·import-linter2.13 (cũ Entry #121: py3.11·numpy2.4.6·il2.12). Baseline vẫn 200/1 + lint 5/0 → tương thích, nhưng số phiên bản khác ⇒ nếu sau có lệch hành vi, đây là nghi phạm đầu tiên.
Đóng khi: (không cần đóng) — ghi để truy vết; cân nhắc pin phiên bản trong pyproject nếu cần tái lập chính xác.

### K-015 — 🔴 (PHÁT HIỆN doubt-driven 2026-07-03) `reset_for_reuse` BỎ QUA reader protection → torn frame nếu reset lúc reader đang copy
Scope: shm-ring-epoch-switchover / reset_for_reuse + reader read path
Nguồn: đọc `shm_frame_ring.py` — `ShmFrameReader.read` COPY ngoài lock dựa bất biến "writer không tái dùng slot khi reader_count>0" (comment L672); `reset_for_reuse` xoá reader registry + `reader_count` + ghi FREE **VÔ ĐIỀU KIỆN** (không kiểm reader_count).
Rủi ro (bản chất): switchover gọi `pool.activate` → `reset_for_reuse(pool[N%K])`. Nếu ring đó CÒN reader đang ở pha copy-ngoài-lock (chưa drain), reset xoá bảo vệ → writer mới ghi đè slot → reader copy trúng **frame rách (torn), im lặng**. "Drain-before-reuse" chỉ là CONTRACT (docstring), **KHÔNG code nào cưỡng chế**.
Xác suất: thấp trong vận hành bình thường (switchover hiếm + K=3 đệm + reader check-on-read chuyển nhanh) — NHƯNG reader chậm/kẹt/không gọi read_ref → rủi ro thật cho sản phẩm 24/7. Test hiện KHÔNG phủ (in-process serialize, không có reader kẹt lúc reset).
ĐỀ XUẤT fix GỐC (design-first, chờ user chốt — KHÔNG tự implement vì đổi hành vi switchover):
- **A. Cưỡng chế ở `reset_for_reuse`:** kiểm `reader_count != 0` (hoặc `_reader_protects_slot`) trên mọi slot → REFUSE (raise/return False) + emit `shm_reset_blocked_active_readers` → caller retry sau. (Enforce tại cơ chế — mạnh nhất.)
- **B. Cưỡng chế ở `pool.activate`/supervisor:** kiểm drain trước khi activate; chưa drain → hoãn switchover (chờ lease reader hết) + emit. (Enforce tại điều phối.)
- **C. Dựa lease:** reset chỉ khi mọi reader lease đã hết (reap xong) — reset gọi `_reap_dead_readers` + kiểm còn reader-còn-lease không.
- **D. (yếu) giữ nguyên + tài liệu to hơn** — để lại rủi ro tiềm ẩn (KHÔNG khuyến nghị cho sản phẩm thương mại).
Khuyến nghị: **A hoặc B** (cưỡng chế, không dựa contract ngầm). Đóng khi: chốt hướng + implement + test (reader giả đang pin lúc reset → phải bị refuse/hoãn).
Trạng thái: ✅ **ĐÃ FIX (Fix A + caller-a, 2026-07-03, D-020/LOG #153).** `reset_for_reuse` giờ reap-dead → nếu còn reader hiệu lực (`_reader_protects_slot`) → REFUSE (return False, chưa đụng gì) + emit `shm_reset_blocked_active_readers`; `pool.activate` trả None; `supervisor.switchover` HOÃN (emit `shm_switchover_deferred`, không publish). +6 test `test_switchover_drain_guard.py` → full **248 passed/1 skipped · lint 5/0**. drain-before-reuse CƯỠNG CHẾ, không còn contract ngầm.

### K-010 — ℹ️ Bước kế đã xác định rõ trong end.md + activeContext
Scope: shm-ring-epoch-switchover / Wave 3
Nguồn: end.md · activeContext (2026-07-02)
Nội dung: **WAVE 3 XONG** — Task 1.1/1.2/2(→B)/3/4.1 + **4.2 Writer ✅ (D-008)** + **4.3 Reader ✅ (D-009)** + **5 teardown ✅ (D-010)** (2026-07-03). Thứ tự bước kế = **Task 6 T-B cross-process** (BLOCK ở K-012 — chờ chốt H1/H2/H3) → 7 T-C (gỡ K-003) → 8 PBT → 9 obs/regression.
Đóng: (con trỏ điều hướng — cập nhật khi tiến độ đổi.)


### K-016 — 🟡 (GHI NHẬN 2026-07-04) `BoundedQueue` là THREAD-safe, KHÔNG process-safe
Scope: #07 backpressure / `kernel/backpressure.py`
Nguồn: LOG Entry #160 · D-024 · `kernel/backpressure.py` (dùng `threading.Lock`/`Condition`)
Ảnh hưởng (bản chất): `BoundedQueue` đồng bộ bằng `threading.Lock` → chỉ an toàn cho nhiều THREAD trong CÙNG một tiến trình (vd thread capture → thread submit-inference). Truyền frame GIỮA các tiến trình vẫn phải qua SHM ring (#05) + `mp.Lock`. Nếu ai đó dùng `BoundedQueue` để chia sẻ cross-process (pickle qua Process/Queue) → mỗi process có bản lock RIÊNG → đồng bộ vô hiệu → mất item / hỏng dữ liệu ÂM THẦM.
Đã ghi: docstring `kernel/backpressure.py` cảnh báo rõ; bài học #07 sẽ nhấn.
Đóng khi: (không cần đóng — ranh giới thiết kế). Nếu cần hàng đợi cross-process → dùng cơ chế khác (SHM ring / mp.Queue), KHÔNG mở rộng BoundedQueue.

### K-017 — 🟡 (GHI NHẬN 2026-07-04) Metrics backpressure (drops/rejects/block_timeouts) CHƯA wire observability
Scope: #07 backpressure ↔ #08 observability
Nguồn: LOG Entry #160 · D-024
Ảnh hưởng: `BoundedQueue` expose 3 counter thuần (đọc được) nhưng CHƯA emit qua `ObservabilityHook` (đã có ở #05) / structlog. Dashboard/alert sản phẩm 24/7 chưa "thấy" backpressure tự động. Chủ ý hoãn tới #08 (LAW #1: một-vấn-đề-một-lần). Cũng ghi: "BLOCK cấm cho RTSP" là ràng buộc enforce ở tầng cấu hình/per-source, KHÔNG ở BoundedQueue (giữ policy-agnostic — SRP).
Đóng khi: #08 wire counter → observability/metrics (structlog + counter export).


### K-018 — 🟡 (GHI NHẬN 2026-07-04) Observability bản #08 bỏ production log handlers
Scope: #08 observability / `runtime/observability.py`
Nguồn: LOG Entry #162 · D-025 · Design step-08 ("Note vs production")
Ảnh hưởng (bản chất): bản vision_demo #08 CỐ Ý bỏ so với production (`08-observability.md`): (a) `_BoundedQueueHandler` non-blocking enqueue (fix HI-OBS-01 — log call không chặn hot path); (b) `RotatingFileHandler` xoay theo size (fix HI-OBS-02 — không đầy đĩa); (c) `LoggingHandle.shutdown()` flush queue lúc cascade shutdown (không mất log cuối). #08 chỉ dựng nền structlog + log_context + InMemoryMetrics. Sản phẩm 24/7 CẦN bổ sung 3 cái này.
Đóng khi: có sub-spec/bước bổ sung production log handlers (non-blocking + rotation + flush-on-shutdown).

### K-019 — 🟡 (GHI NHẬN 2026-07-04) Cardinality budget — label metric phải BOUNDED
Scope: #08 observability / InMemoryMetrics + mọi call site metric
Nguồn: LOG Entry #162 · Design step-08 (Cardinality budget + Self-check #3)
Ảnh hưởng: `InMemoryMetrics` KHÔNG enforce giới hạn label (không thể — là ràng buộc vận hành). Đặt label unbounded (packet_id, bbox coords, timestamp...) → mỗi giá trị = 1 key riêng → hàng triệu key → Prometheus/exporter OOM. QUY TẮC: label chỉ dùng tập hữu hạn nhỏ (camera_id<100, status<10, class...). Dữ liệu high-cardinality (coords, packet_id) → cho vào LOGS (structlog), KHÔNG vào label metric.
Đóng khi: (không cần đóng — quy tắc vận hành). Cân nhắc: khi làm Prometheus adapter thật, thêm guard/lint cardinality nếu cần.


### K-020 — 🟡 (GHI NHẬN 2026-07-04) Supervisor chỉ phát hiện CRASH, KHÔNG phát hiện HANG
Scope: #09 shutdown / `application/supervisor.py`
Nguồn: LOG Entry #164 · D-026 · Design step-09 (Self-check #5)
Ảnh hưởng (bản chất): Supervisor giám sát bằng `p.is_alive()` → chỉ biết process đã EXIT (crash). Nếu worker **hang/deadlock** (process còn sống nhưng kẹt, không làm gì) → is_alive()=True → supervisor KHÔNG restart → camera "chết thầm" mà hệ tưởng khoẻ. Sản phẩm 24/7 CẦN **heartbeat liveness**: worker ghi timestamp/gửi heartbeat định kỳ; supervisor kill+restart nếu quá hạn (Vision Platform production dùng ZMQ heartbeat reply).
Đóng khi: thêm heartbeat liveness probe (worker→file mtime / ZMQ) + test hang.

### K-021 — 🟡 (GHI NHẬN 2026-07-04) Restart không có exponential backoff
Scope: #09 shutdown / `application/supervisor.py`
Nguồn: LOG Entry #164 · Design step-09 (Restart cap — simplified)
Ảnh hưởng: worker crash liên tục → supervisor restart NGAY (không delay) tới khi chạm max_restarts → spawn/exit dồn dập (CPU spike ngắn). Production cần `sleep(2^n)` giữa restart (exponential backoff) để giảm tải + cho tài nguyên hồi. vision_demo giản lược (chỉ có restart cap).
Đóng khi: thêm backoff (sleep 2^restart_count, có cap trần) + test.


### K-022 — 🟡 (GHI NHẬN 2026-07-04) `build` là dev/ship tool, KHÔNG phải runtime dependency
Scope: #10 package / pyproject.toml
Nguồn: LOG Entry #166 · D-027
Ảnh hưởng: `python -m build` (tạo wheel/sdist) cần package `build` (+ setuptools/wheel qua build-system.requires đã có trong pyproject). `build` chỉ dùng lúc ĐÓNG GÓI/ship — KHÔNG thêm vào `[project] dependencies` (không phải thứ runtime cần). Đã cài vào venv để build (build 1.5.0). Wheel/sdist ra `dist/` (đã gitignore). CI/ship pipeline tự cài `build` khi cần.
Đóng khi: (không cần đóng — ghi để biết ranh giới dep). Nếu lập CI ship: thêm `build` vào bước đóng gói (không vào deps runtime).


### K-023 — ✅ (ĐÓNG 2026-07-04, sub-spec zmq) InlineInferenceClient KHÔNG switchover-aware + stale retryable=False — đã giải ở ZmqInferenceServer
Scope: #06 inference ↔ #05b switchover / `application/inline_inference_client.py`
Nguồn: LOG Entry #168 · đọc `inline_inference_client.py` vs `reader_epoch_coordinator.py` (đối chiếu trực tiếp)
Ảnh hưởng (bản chất — 2 mặt):
- **(a) Không tự chuyển ring:** `InlineInferenceClient` giữ `self._reader = ShmFrameReader(ring)` CỐ ĐỊNH; `infer()` chỉ `read_ref` (stale-SAFE: ref epoch cũ → None, KHÔNG đọc nhầm/torn). Nhưng KHÔNG poll `RingControlPlane` để chuyển ring như `ReaderEpochCoordinator._maybe_switch`. → sau switchover (#05b), mọi request epoch mới đọc ring CŨ → `ring_epoch` mismatch → luôn None → inference **stale vĩnh viễn, không tự hồi phục** (tới khi tạo lại client). An toàn (không corrupt) nhưng không self-heal.
- **(b) retryable sai loại:** stale-read trả `InferenceError(retryable=False)`. Nhưng stale-epoch là **transient** (retry với ref ring mới sẽ thành công) → nên `retryable=True`. Camera-side circuit-breaker dùng cờ này → hiểu nhầm "lỗi vĩnh viễn" → bỏ camera oan.
Vì sao KHÔNG fix ngay ở #06: Design step-06 = inline 1-ring, dev/test, viết TRƯỚC switchover — trong demo 1-ring không có switchover nên không lộ. Chỗ ĐÚNG để xử lý là **production inference client (ZMQ, đã hoãn)**: (1) switchover-aware (poll control-plane / swap ring như coordinator, hoặc bọc `ReaderEpochCoordinator` thay `ShmFrameReader`); (2) phân loại stale/transient → `retryable=True`. Fix vào inline giờ = đổi API (#06 phải nhận `control_plane`) + trừu tượng hóa sớm khi chưa có bản ZMQ.
Đóng khi: làm sub-spec ZMQ inference client → wire switchover-aware read + retryable classification + test switchover-trong-lúc-inference.
Bằng chứng stale-SAFE (đã có): `test_inline_client_stale_epoch_ref_returns_error` pass (ref epoch cũ → error, không đọc nhầm).
**[ĐÓNG 2026-07-04 — LOG #171]** Giải trong sub-spec `zmq-inference-service`: `InferenceServer` (application) dùng `ReaderEpochCoordinator` (switchover-aware) → đóng (a); retryable đúng (stale/timeout=True, detector=False) → đóng (b). Bằng chứng: `test_zmq_switchover.py` (server tự chuyển ring epoch1→2, đọc frame ring mới) + `test_zmq_inference_cross_process.py`. Inline #06 GIỮ NGUYÊN (stale-safe cho dev/test 1-ring, không hack).


### K-024 — ✅ (PHÁT HIỆN + FIX doubt-driven audit 2026-07-04) InferenceServer chết vì 1 request rác/malformed
Scope: zmq-inference / `application/inference_server.py` (serve loop)
Nguồn: LOG Entry #176 · đọc phản biện `inference_server.py` · test `test_zmq_server_survives_malformed_request`
Ảnh hưởng (bản chất): serve loop cũ: `ident, payload = sock.recv_multipart()` (giả định đúng 2 frame) + `_handle` gọi `msgpack.unpackb`/`dict_to_request` KHÔNG bọc try/except. → 1 request RÁC (client lỗi/frame hỏng/sai version/corrupt) → recv_multipart != 2 frame HOẶC unpackb raise → VĂNG khỏi `serve()` → **CHẾT CẢ SERVER** (mọi camera dùng nó mất inference). Bulkhead "1 request lỗi không chết server" mới đúng cho lỗi *detector* (đã có try/except trong _handle), CHƯA đúng cho lỗi *transport/deserialize*. = fragility + mini-DoS cho 24/7.
FIX (bản chất — bọc CẢ đơn-vị, không vá 1 dòng): bọc recv+handle+send trong try/except + guard `len(frames)!=2` → lỗi bất kỳ 1 request → emit `inference_request_error`/`inference_malformed_request` + metric result="error"/"malformed" + `continue` (bỏ request, phục vụ tiếp). payload rác không có request_id để echo → client timeout=retryable (an toàn).
Đóng: ✅ (2026-07-04). Bằng chứng: `test_zmq_server_survives_malformed_request` (gửi b"garbage" + frame sai số → server sống → request hợp lệ kế OK) pass; full 305 passed/1 skipped.
Ghi kèm (audit KHÔNG phải bug — đã kiểm, không sửa): mp.Value default lock=True → `.value` không torn-read; ZmqInferenceClient teardown join-before-close đúng (io-thread độc quyền socket); `_pending_respawn`+give-up nhất quán (give-up set pending False).


### K-025 — ℹ️✅ (AUDIT 2026-07-04) BoundedQueue #07 + control-plane read_current: verify SẠCH (không bug)
Scope: audit doubt-driven #07 backpressure + ring_control_plane
Nguồn: LOG Entry #177 · đọc phản biện `kernel/backpressure.py` + `runtime/ipc/ring_control_plane.py` · stress test
Nội dung (verify — không phải rủi ro):
- **BoundedQueue SẠCH:** notify đúng waiters (Condition riêng); notify() đủ (1 get → 1 slot → wake 1 producer BLOCK); DROP_OLDEST notify vô hại (full≠empty); get_or_raise CÓ notify; metrics under-lock. Thêm stress test 4×4×50 (không mất/trùng/deadlock).
- **Control-plane read_current AN TOÀN (x86):** name-trước-epoch-cuối + epoch-authority → ca xấu (epoch cũ, name mới) bị coordinator bỏ (epoch==self → không switch) → poll kế sửa; không bao giờ ra (epoch mới, name cũ).
Đóng: ℹ️ (thông tin verify). Còn phụ thuộc: ARM memory-ordering (K-001, cần HW).


### K-026 — ℹ️✅ (AUDIT 2026-07-04) SHM ring core SOUND; invariant reset_for_reuse làm EXPLICIT
Scope: audit doubt-driven #05 `runtime/ipc/shm_frame_ring.py`
Nguồn: LOG Entry #178 · đọc phản biện register_writer/quarantine/reset_for_reuse/reader-copy · docstring đã sửa
Nội dung (verify — không phải rủi ro reachable):
- **reset_for_reuse:** 2 pass (guard-all refuse-trước-clear, K-015). TOCTOU giữa guard↔clear (release rồi acquire lại lock slot) → **KHÔNG khai thác được** vì pool_size≥2 (RingPool cưỡng chế) → ring đang reset (pool[N%K]=epoch N-K) ≠ ring hiện hành (pool[(N-1)%K]) → không reader mới tới. ĐÃ document invariant này vào docstring reset_for_reuse (đừng gọi lên ring hiện hành).
- **register_writer:** read-check-write control-segment không lock cross-process → TOCTOU nếu 2 process đăng ký đồng-micro-giây; ĐÃ document = giả định startup-orchestration (composition root, không đồng thời). Known assumption (không phải bug mới; ngoài mô hình dùng).
- **quarantine/reader-copy:** double-snapshot + writer skip khi reader_count>0 → đúng.
Đóng: ℹ️ (thông tin verify). Phụ thuộc: ARM ordering (K-001); register_writer concurrent-multiprocess (giả định orchestration).

### K-027 — ℹ️✅ (2026-07-04) Timing chống-flaky khi ghép ZMQ+SHM+spawn (full-stack profile)
Scope: `profiles/vision_fullstack_profile.py` · `tests/test_fullstack_integration.py`
Nguồn: LOG Entry #180 · D-030 · chạy test THẬT PASS 13.29s
Nội dung (bản chất — quan hệ giữa các timeout, KHÔNG chọn số bừa):
- **heartbeat_timeout_s PHẢI > client infer timeout_s.** Camera-worker đập heartbeat ở ĐẦU mỗi vòng lặp, rồi
  block trong `client.infer()` (tới timeout_s). Lúc startup server chưa bind → infer block gần trọn timeout →
  nếu heartbeat_timeout ≤ timeout thì supervisor tưởng camera HANG → terminate+restart (false-positive) → flaky.
  Chọn heartbeat_timeout=20.0 > timeout=5.0. (Cái giá: hang THẬT bị phát hiện chậm hơn — chấp nhận cho v1.)
- **shutdown_grace_s PHẢI > client infer timeout_s.** Lúc cascade shutdown, camera có thể đang block trong infer
  (server đã thoát) → phải chờ tới timeout mới thoát vòng + chạy `finally` ghi artifact. grace < timeout →
  camera bị terminate() trước khi finally chạy → KHÔNG ghi artifact → test đọc file thiếu → fail. Chọn grace=8.0 > 5.0.
- **n_slots headroom:** ring bắt đầu rỗng → n_slots frame đầu ghi được BẤT KỂ reader → đảm bảo infer_ok≥1 khả thi
  ngay cả khi server đọc chậm. Chọn n_slots=8.
- **Publish epoch1 TRƯỚC spawn:** bootstrap cần epoch>0 (bootstrap_current_ring ném khi epoch=0).
Đóng: ℹ️ (nguyên tắc thiết kế timing — tái dùng khi ghép nhiều process cooperative+heartbeat).
**Bằng chứng ổn định (verify sâu #181):** chạy LẶP **5/5 PASS** (8.67–9.31s, 0 fail → KHÔNG flaky) + chạy `-W always -rw` → **KHÔNG warning / KHÔNG leaked shared_memory / KHÔNG resource_tracker warning** (shutdown sạch, không rò rỉ SHM segment tích tụ — an toàn production).

### K-028 — ℹ️✅ (2026-07-04) NMS ở domain PHẢI index-based (domain↛kernel không import Detection)
Scope: `domain/nms.py` · `adapters/detector_pipeline.py`
Nguồn: LOG Entry #183 · D-031 · contract import-linter "Kernel chi phu thuoc domain" (domain là tầng thấp nhất)
Nội dung (bản chất layer):
- `Detection` sống ở **kernel**. `domain` là tầng THẤP NHẤT → CẤM import kernel (chỉ kernel→domain, không ngược).
  Nếu `nms(list[Detection])` đặt ở domain → domain import kernel = VI PHẠM contract.
- FIX bản chất: NMS domain nhận `boxes: list[BBox]` + `scores` + `labels` (số/BBox thuần) → trả **kept indices**.
  Tầng trên `DetectorPipeline`@adapters (được import cả domain+kernel) ghép index về `Detection`.
- Cùng nguyên tắc: `LetterboxTransform`@domain chỉ thao tác `BBox`@domain (không Detection). Pipeline dùng `dataclasses.replace(det, box=...)` đổi box.
Đóng: ℹ️✅ (verify — lint 5/0, domain contract KEPT). Tái dùng: mọi thuật toán domain trên box phải index-based/BBox-based, KHÔNG chạm DTO kernel.

### K-029 — 🟡 (2026-07-04) LICENSE model detector — YOLOv8/v11 là AGPL-3.0 (rủi ro sản phẩm thương mại đóng)
Scope: `adapters/onnx_detector.py` · quyết định chọn model/weight (vận hành + pháp lý)
Nguồn: LOG Entry #184 · D-031/C-012 · kiến thức license Ultralytics [độ chắc: cao — AGPL-3.0 là license công khai của Ultralytics YOLOv5/v8/v11]
Nội dung (điều nên biết TRƯỚC khi ship):
- **YOLOv5/v8/v11 (Ultralytics) = AGPL-3.0** → dùng trong sản phẩm ĐÓNG/SaaS phải (a) mở mã theo AGPL, hoặc
  (b) MUA Enterprise License của Ultralytics. Không thể im lặng nhúng weight vào sản phẩm đóng.
- Lựa chọn license-thân-thiện (Apache-2.0/MIT, dùng thương mại đóng thoải mái): **RTMDet** (Apache-2.0, mmdetection),
  **RT-DETR** (Apache-2.0), **YOLOX** (Apache-2.0), **NanoDet** (Apache-2.0). [độ chắc: cao cho RTMDet/YOLOX; xác nhận lại bản weight cụ thể trước khi ship — [chưa kiểm] từng file weight].
- FIX bản chất: `OnnxDetector` MODEL-AGNOSTIC (preprocess/postprocess DI) → KHÔNG khoá vào AGPL; chọn model là
  quyết định tách rời, thay 2 hàm DI + file .onnx. Repo KHÔNG nhúng weight nào (tránh kéo license vào code).
Đóng khi: chọn model + weight cụ thể có license phù hợp mục tiêu thương mại + xác nhận điều khoản file weight đó.

### K-030 — ✅ (2026-07-19, #450) RTSP opencv-ffmpeg Windows mở Dahua OK khi creds ĐÚNG (401 cũ = sai mật khẩu, K-034)
Scope: `adapters/rtsp_frame_source.py` · kết nối camera thật
Nguồn: LOG Entry #189 · chạy thật (401 từ camera) · VLC xác nhận creds đúng
Nội dung:
- Máy Windows TỚI được camera (nhận `method OPTIONS failed: 401 Unauthorized` = camera phản hồi → reachable).
- ffmpeg bundled trong opencv-python (Windows) bắt tay DIGEST auth với Dahua thất bại (cả khi `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`), DÙ admin/<pass> chạy trên VLC.
- KHÔNG phải lỗi adapter (RtspFrameSource 7 test pass). Là vấn đề ffmpeg(bundled opencv) vs auth Dahua.
- **ĐÍNH CHÍNH (Entry #197, verify WSL):** giả thuyết "chạy Linux sẽ ổn" = **SAI**. Test thật trên WSL2 Ubuntu (opencv-python-headless, ffmpeg bundled) → **401 Y HỆT**. Vậy KHÔNG phụ thuộc OS; là ffmpeg-của-opencv vs Dahua này. VLC dùng live555 (stack khác) nên được. Docker/Linux KHÔNG tự giải.
Hướng CÓ THỂ giải (chưa verify): (a) SYSTEM ffmpeg (apt, cần sudo) khác bundled? (b) opencv build GStreamer (như VLC); (c) HTTP snapshot Dahua `cgi-bin/snapshot.cgi` (HTTP digest robust, né RTSP); (d) record clip VLC → video file (chạy ngay). Cho "xem detect": (d)+.onnx nhanh nhất.
Đóng khi: 1 trong các hướng trên chạy lấy được frame thật.
**✅ ĐÓNG #450:** với creds ĐÚNG (`admin:L2B40AD7` — K-034 đã chỉ 401 cũ là sai mật khẩu `L2B40AD07` dư số 0) + URL `rtsp://.../cam/realmonitor?channel=1&subtype=0`, **opencv-ffmpeg bundled trên Windows (máy `toann`) MỞ Dahua RTSP THÀNH CÔNG** → decode 1080p, `video=2588+` frame, web stream sống. ⇒ "digest 401 fail" trước đây CHỦ YẾU là red-herring MẬT-KHẨU-SAI, KHÔNG phải bất tương thích opencv-ffmpeg↔Dahua cố hữu. [chưa kiểm: có cần rtsp_transport=tcp cho ổn định 24/7 không — quan sát sau].

### K-031 — 🔴 (2026-07-05) BẢO MẬT: secret production lộ trong config syn/resources
Scope: an toàn vận hành (ngoài repo — file `C:\...\syn\resources\config\*`)
Nguồn: LOG Entry #189 · đọc config để lấy imgsz/labels
Nội dung: các file `main.yaml`/`plate.yaml`/`config.json`/`camera.json` chứa NHIỀU secret THẬT: client_secret API,
WEB_PASSWORD, mật khẩu CIFS storage, mật khẩu RTSP nhiều camera (nhiều IP). Đã lộ trong phiên chat khi đọc.
Hành động: AI KHÔNG copy config vào repo + KHÔNG echo secret. **User NÊN ĐỔI toàn bộ mật khẩu/secret đã lộ** +
không đưa file config production vào chat/AI. Weight `.pt` copy vào repo nhưng gitignore (không commit).
Đóng khi: user xác nhận đã rotate secret.

### K-032 — 🟡 (2026-07-05) Docker artifact CHƯA build/verify (máy dev không có docker)
Scope: `deploy/{Dockerfile,docker-compose.yml,README.md}`
Nguồn: LOG Entry #196 · `docker --version` → không có trên máy dev
Nội dung: đã tạo Dockerfile/compose để đóng gói web UI + RTSP + ONNX cho Linux, NHƯNG máy phát triển KHÔNG có
docker → KHÔNG build/chạy/verify được ở đây. Là artifact [chưa kiểm] tới khi user build trên Linux/Docker.
Các điểm cần kiểm khi build thật: (a) ffmpeg trong container tới được camera LAN (network_mode host); (b) .onnx
mount đúng + describe_onnx khớp layout; (c) opencv-python-headless đủ cho imencode/vẽ; (d) RTSP digest OK trên Linux.
Đóng khi: user build + chạy `docker compose up` thành công + xem được stream có box thật.


### K-033 — 🟡 (2026-07-05) Chạy .pt YOLOv5 = yolov5 package + patch torch weights_only; + rủi ro lockout camera
Scope: `adapters/yolov5_pt_detector.py` · WSL ~/vpvenv · camera RTSP
Nguồn: LOG Entry #198 · verify thật WSL
Nội dung:
- **Root cause .pt không load (đã trị):** torch>=2.6 đổi `torch.load` mặc định `weights_only=True` → chặn unpickle
  `DetectionModel`. KHÔNG phải version kiến trúc. Fix: patch `torch.load(..., weights_only=False)` (file user tin cậy).
- `Yolov5PtDetector` (yolov5 7.0.14 + torch) VERIFY chạy WSL: names **{0:car,1:motorcycle,2:truck}** (thật), detect OK.
  Box trả ORIGINAL_FRAME (yolov5 AutoShape tự letterbox+rescale) → KHÔNG bọc DetectorPipeline.
- **RTSP (verify kỹ):** opencv-ffmpeg + PyAV đều 401 "authorization failed" (URL đúng từng ký tự, mọi transport).
  VLC-CLI headless từ máy này CŨNG fail "setup RTSP session".
- **⚠️ RỦI RO tôi gây ra:** đập camera nhiều lần login-fail → Dahua có thể **khóa account/IP** ("illegal login",
  ~5 fail → khóa 5–30'). NGHI đã kích hoạt (VLC cũng fail). [suy đoán]. → DỪNG đập; chờ ~30' tự mở; user kiểm VLC GUI.
Đóng khi: lấy được frame thật (user record clip VLC → detect) HOẶC xác định + xử lý được nguồn RTSP (gstreamer/khác).


### K-034 — ✅ (2026-07-05) 🎯 HỆ CHẠY THẬT: RTSP live + YOLOv5 + Web UI — RTSP 401 chỉ là SAI MẬT KHẨU
Scope: WSL ~/vpvenv · `vision_web_app` --rtsp --pt · adapters RtspFrameSource/Yolov5PtDetector
Nguồn: LOG Entry #199 · verify chạy thật
Nội dung:
- **Nguyên nhân gốc RTSP 401 = SAI MẬT KHẨU** (URL user đưa `admin:L2B40AD07` dư ký tự '0'; đúng `L2B40AD7`).
  → TOÀN BỘ nhánh "ffmpeg không auth được / VLC live555 khác / Docker-Linux giải / nghi lockout" (#189/#197/K-030 cũ)
  đều **SAI TIỀN ĐỀ**. ffmpeg (opencv/PyAV) auth Dahua HOÀN TOÀN OK khi mật khẩu đúng.
- **BÀI HỌC QUAN TRỌNG:** khi 401 dù "creds đúng" → **NGHI SAI CREDENTIAL SỚM**, so từng ký tự; đừng đổ lỗi thư viện/OS.
  Tôi đã tốn nhiều lượt đi sai hướng vì tin URL cung cấp có pass đúng.
- **Verify chạy thật (WSL, mật khẩu đúng):** RTSP opened, frame 1920×1080; Yolov5PtDetector detect truck thật;
  Web UI live ~5fps CPU, ~84% frame có box; Windows browser `http://localhost:8000/` (WSL2 localhost forward) xem được.
- Stack chạy: WSL Ubuntu (get-pip+virtualenv, KHÔNG sudo) + opencv+torch+yolov5+flask trong ~/vpvenv.
Đóng: ✅ (hệ vehicle-detect chạy live thật). Còn: ALPR plate+OCR (chưa), ổn định chạy dài, đích cuối chờ user.


### K-035 — 🟡 (2026-07-05) full-stack test flaky DƯỚI TẢI NẶNG (timeout tune cho máy rảnh)
Scope: `tests/test_fullstack_integration.py` (spawn 2 process, heartbeat/shutdown timing)
Nguồn: LOG Entry #202 · quan sát thật
Nội dung: full-suite chạy khi server GPU WSL đang chạy SONG SONG → `test_fullstack_end_to_end` FAIL 1 lần
(FileNotFound artifact: camera_worker bị terminate trước khi ghi vì scheduler nghẽn). Chạy RIÊNG (máy nhẹ hơn) → 2/2 PASS.
→ KHÔNG phải regression. Timeout (heartbeat 20s, grace 8s, client 5s — K-027) tune cho máy RẢNH; dưới tải rất nặng
(GPU inference liên tục) spawn Windows chậm → có thể vượt. Nếu cần chạy CI dưới tải: nới timeout hoặc chạy cô lập.
Đóng khi: (nếu cần) nới timeout full-stack cho robust dưới tải, HOẶC chấp nhận chạy test lúc máy không tải nặng.


### K-036 — 🟡 (2026-07-05) 2 bug live web: detect-thread chết vì CUDA (thiếu bulkhead) + orphan WSL process giữ port
Scope: `profiles/vision_web_app.py` · vận hành WSL
Nguồn: LOG Entry #203 · đọc traceback + ps thật
Nội dung:
- **Bug A (bbox đứng yên):** detect thread không try/except → 1 lỗi inference (CUDA "unknown error" khi máy tải nặng/
  GPU nhiễu) giết cả thread → `/boxes` frozen còn video vẫn chạy. FIX: bulkhead try/except mỗi frame + tự reload
  detector sau ≥3 lỗi (CUDA context có thể hỏng vĩnh viễn → phải re-init). BÀI HỌC: mọi vòng-lặp-worker phải chịu lỗi (như K-024).
- **Bug B (vận hành):** `stop` terminal Kiro (wsl.exe) KHÔNG giết python trong WSL → orphan giữ port 8000 → server
  mới bind fail âm thầm → curl trúng server cũ (số liệu tích luỹ vô lý, vd 24000 frame/38s). FIX: `pkill -9 -f <module>`
  trước khi start lại; kiểm `ps | grep` để chắc sạch. Đừng tin "đã stop" = process WSL đã chết.
- Phụ: version-counter thay id() (id-reuse sau GC); fetch cache:'no-store'; tắt werkzeug access-log (spam).
Đóng khi: (đã fix code) — lưu ý vận hành pkill khi chạy WSL server.


### K-037 — ℹ️ (2026-07-06) AUDIT base extensibility: lõi tốt, thiếu vision-layer (KHÔNG rebuild)
Scope: `kernel/{stage_contract,media_packet}.py` · `runtime/sync_linear_executor.py` · `runtime/stages/` · `kernel/ports/`
Nguồn: đọc code thật (audit theo yêu cầu user "xem kỹ base")
Nội dung — base GENERIC (giữ): IStage + StageResult/ExecutionResult (status tường minh, không None) + MediaPacket immutable CoW (pickle/E-16 xử lý đúng) + SyncLinearExecutor (setup-rollback, ctx-mgr). Sạch, đúng.
5 GAP để thành "base vision chuẩn, đẻ nghiệp vụ dễ" (ADDITIVE, không rebuild):
1. **Chưa có PipelineRunner chuẩn** (source→stages→sink + backpressure/drop) → demo/web/full-stack MỖI cái tự viết vòng lặp = ma sát lớn nhất.
2. **Chưa có Stage vision** (chỉ brightness/dark demo); thiếu ports ITracker/IOcr/IEventSink; detector gọi thẳng chưa-là-Stage.
3. Chỉ 1 executor (sync_linear) — thiếu concurrent/batch/multiprocess (scale).
4. Chưa mô hình FAN-OUT (1 frame→N xe→biển→OCR) bậc-nhất (đang nhét list vào artifacts).
5. `artifacts: Mapping[str,Any]` stringly-typed → maintainability giảm khi nhiều stage.
Ưu tiên: Gap 1 (PipelineRunner) + Gap 2 (Stage hoá detect/track/ocr + ports). Đóng khi: dựng 2 cái đó (design-first).


### K-038 — ℹ️ (2026-07-06) AUDIT base vòng 2: seam World-A(Stage/in-mem) ⟂ World-B(SHM/cross-proc) — gốc media_ref cứng kiểu
Scope: `kernel/media_packet.py` (media_ref: InMemoryArrayRef) · `kernel/shm_frame_ref.py` · `runtime/base_stage.py` · `runtime/stages/*`
Nguồn: đọc code thật (audit sâu vòng 2 theo yêu cầu user)
Nội dung:
- **Mạnh:** viết Stage cực dễ (`BaseStage`→`_do_process` ~6 dòng); contracts status-tường-minh; MediaPacket immutable+CoW+pickle-safe; layering cưỡng chế. Ergonomics mở-rộng = A.
- **Seam chính:** 2 thế giới xử lý CHƯA hợp: World A = Stage pipeline (MediaPacket + InMemoryArrayRef, in-process, chỉ dùng ở demo Step 04); World B = SHM/ZMQ/Supervisor (ShmFrameRefData + InferenceRequest, cross-process scale) — World B KHÔNG dùng Stage, nối adapter trực tiếp.
- **Gốc bản chất:** `MediaPacket.media_ref` CỨNG kiểu `InMemoryArrayRef` (không phải port), trong khi `shm_frame_ref` docstring nói "gắn vào MediaPacket" → mâu thuẫn → không bỏ frame-SHM vào packet sạch → Stage(World A) không chạy trên hạ tầng SHM(World B).
- **Khuyến nghị (KHÔNG rebuild):** nếu nghiệp vụ tương lai chỉ single-process → base đủ. Nếu cần scale đa-tiến-trình qua SHM → trừu tượng `media_ref` thành port `IMediaRef` (InMemoryArrayRef + ShmMediaRef) — refactor nhỏ additive, chốt TRƯỚC khi xây nghiệp vụ scale.
- Bảng điểm: layer A · contracts A · ergonomics A · runtime-IPC A− (🔴 POSIX/ARM) · kiểm-chứng A− (Stage-pipeline test mỏng) · liền-mạch-in-mem↔SHM C+.
Đóng khi: user chốt hướng scale → (nếu cần) làm IMediaRef port.


### K-039 — 2026-07-06 — Seam K-038 ĐÃ ĐÓNG PHẦN 1: port `IMediaRef` (bước đầu của lộ trình scale)
Status: ✅ code + verify THẬT (369/1 · lint 5/0). Nguồn: LOG #206/#207 · D-038 · T-008 · spec media-ref-port.
- **Đã làm:** `kernel/media_ref.py::IMediaRef` (Protocol @runtime_checkable, tối thiểu `array: np.ndarray`).
  `MediaPacket.media_ref` nới `InMemoryArrayRef → IMediaRef`. InMemoryArrayRef KHÔNG sửa (thoả structural).
- **Bằng chứng abstraction THẬT (không chỉ type-hint):** test `_FakeMediaRef` (impl khác, materialize từ
  bytes) cắm vào MediaPacket → `BrightnessStage` chạy đúng, brightness khớp. Pickle round-trip giữ read-only.
- **Vì sao mới là PHẦN 1:** đây chỉ mở CHỖ CẮM. Muốn Stage chạy THẬT trên SHM còn cần (Non-Goal đã hoãn):
  (a) `ShmMediaRef` ở `runtime/ipc` (kernel CẤM shared_memory → không đặt ở kernel được) đọc slot→ndarray,
  verify generation/ring_epoch (stale → chính sách rõ); (b) `PipelineRunner` chuẩn (Gap-1 K-037);
  (c) wiring end-to-end source→stages→sink over SHM. → các sub-spec riêng khi user xây nghiệp vụ scale.
- **Điều nên nhớ:** giờ thêm 1 backend frame = THÊM 1 impl IMediaRef, KHÔNG phải sửa packet/Stage. Đây là
  đòn bẩy chống sửa-ngọn về sau. Nếu ai đó lại hard-code `InMemoryArrayRef` vào field packet → là hồi quy.


### K-040 — 2026-07-06 — SỔ LỖ HỔNG KIẾN TRÚC (audit đối kháng, đối chiếu DeepStream/Frigate/Triton)
Status: ℹ️ audit (KHÔNG phải bug trong code hiện có — là TRỤC kiến trúc CHƯA có cho quy mô thương mại).
Nguồn: LOG #211 · đọc thật inference_server.py/zmq_inference_client.py/backpressure.py + grep HWM/clock. Đối chiếu
hệ lớn = kiến thức nền [chưa fetch nguồn lượt này]. Chỉ đáng đóng KHI chạy nhiều camera + GPU tải cao.
Xếp theo mức nghiêm trọng cho sản phẩm thương mại:
- **A1 🔴 (throughput #1): inference single-request, KHÔNG batching.** `serve()` recv→detect→send tuần tự →
  GPU xử 1 frame/lần + head-of-line blocking (1 detect chậm chặn mọi camera). Hệ lớn: DeepStream nvstreammux
  gộp batch N-camera · Triton dynamic batching · Frigate detector-process-pool. → cần mô hình batch + pool.
- **A2 🔴: không backpressure cross-process — quá tải = mất frame IM LẶNG.** BoundedQueue chỉ thread (K-016);
  giữa process chỉ có SHM ring GHI ĐÈ frame chưa đọc + DEALER tới HWM rồi block. Hành vi quá tải không
  thiết-kế/không quan-sát. → cần chính sách shed tường minh + đếm được + tín hiệu ngược.
- **C2 🔴 (vận hành): không có config khai báo.** Wire trong profiles+argparse → thêm camera/đổi model = sửa
  code+build. Frigate/DeepStream dùng YAML validate. → cần config-driven N camera.
- **C1 🟠: metrics KHÔNG gom cross-process** (InMemoryMetrics per-process, không endpoint) → không quan sát fleet.
- **B2 🟠: retry gây xử lý TRÙNG** (client retryable=True, server không dedup theo request_id). Vô hại với
  inference thuần; NGUY khi sink ghi event/DB → event trùng. Chốt semantics at-least-once + sink idempotent
  TRƯỚC khi có nghiệp vụ ghi.
- **D2 🟠: SHM rò khi crash cứng** (SIGKILL) — teardown graceful-only; K-003 (POSIX) chưa verify.
- **C4 🟠 bảo mật: ZMQ plaintext/không auth** (CURVE off, tcp loopback) — nguy khi multi-host. + K-031 secret lộ.
- **D1 🟡: copy frame hot-path** (`from_copy` mỗi frame ở profiles, 1080p×3×fps×N = băng thông+GC). from_owned_array né được.
- **A3 🟡: ZMQ HWM không set** (chỉ LINGER=0) → mặc định 1000, đầy thì DEALER block/queue vô định.
- **B1 (tinh tế): `capture_time_ns`=monotonic_ns**, còn heartbeat=wall-clock time.time() → 2 đồng hồ. monotonic
  cross-process đúng trên Linux/Windows cùng boot nhưng KHÔNG đảm bảo bởi hợp đồng Python → document+guard.
Điểm MẠNH (công bằng): result-object tường minh · packet immutable/pickle-safe/read-only re-lock · import-linter
negative-test · bulkhead per-request (K-024) · reader switchover-aware+lease liveness. Base ĐÚNG+SẠCH ở mốc học.
Đóng khi: user vào giai đoạn scale thật → viết spec design-first từng trục (A1 trước = trần throughput lớn nhất).


### K-041 — 2026-07-06 — THỰC TẾ CÔNG SUẤT: 100 cam @ max trên 1×RTX 2060 (6GB) KHÔNG khả thi (~10–40×)
Status: ⚠️ phát hiện khả thi (số [ước lượng — PHẢI benchmark], nhưng khoảng cách đủ lớn để chắc chắn).
Nguồn: user chốt (1 máy/1 GPU/max fps/nhiều analytics detect+classify+đếm/lưu tùy) · LOG #213 · C-014.
Nội dung:
- **Ràng buộc VẬT LÝ (không phải code):** decode 100×25fps = 2500 frame/s (NVDEC 2060 ~vài trăm fps 1080p →
  không kịp); inference ×nhiều-analytics = 5.000–10.000 infer/s vs 2060 ~vài trăm/s → **lệch 10–40×**; VRAM 6GB
  nhiều model + 100 decode-ctx → nguy OOM. → 1×2060 gánh cỡ CHỤC cam fps thấp, KHÔNG 100 ở max.
- **"Làm max rồi giảm" LẬT NGƯỢC với GPU-bound:** max không với tới → phải thiết kế theo **NGÂN SÁCH GPU cố
  định + config GIẢM xuống + degrade có kiểm soát**. 5 trụ (kiểu Frigate): (1) motion-gating (detect rẻ CPU gate
  inference) · (2) sub-stream cho detect + main-stream chỉ khi crop/record · (3) batching · (4) scheduler ngân
  sách chia N cam · (5) shed quan-sát-được (bỏ frame có chủ đích, đếm được).
- **Bước ĐÚNG trước thiết kế (đo, đừng đoán):** benchmark THẬT trên 2060 (env WSL+yolov5 sẵn) — decode fps,
  YOLO fps batch1/8/16, VRAM/model → suy N-cam-thật. Rồi mới viết tài liệu capacity+cụm trên SỐ THẬT.
- **Nghiệp vụ (user): nhiều analytics** (detect→classify→đếm...) → fan-out đa-tầng + nhiều model chia 1 GPU →
  scheduler phải arbitrate cả giữa các analytics. **Lưu trữ: tùy chọn** → storage = 1 ISink cắm/rút được.
Đóng khi: có số benchmark thật + user chốt phần cứng (giữ 1×2060 → mục tiêu N chục cam; hay tăng GPU → 100).


### K-042 — 2026-07-06 — SELF-REVIEW (doubt-driven) spec scale-architecture: 4 lỗ tìm được + đã vá
Status: ℹ️✅ (đã phản biện + vá vào design.md; 0 diagnostic). Nguồn: user "tự valid, phản biện bảo vệ" · LOG #215.
4 lỗ trong CHÍNH thiết kế scale (đã vá):
- **Lỗ 1 — capacity model bậc-1:** chỉ throughput, thiếu (a) LATENCY-SLA (batching tăng latency — cần
  latency_p99≤SLA + batch_timeout); (b) `A` fan-out biến thiên theo dữ liệu (dùng p95/p99 + worst-case, không TB);
  (c) decode/inference TRANH GPU (NVDEC+CUDA) → phải benchmark ĐỒNG THỜI, không tách. → thêm mục "GIỚI HẠN MÔ HÌNH".
- **Lỗ 2 — decode bỏ trống:** cv2-per-process KHÔNG scale ~100 → hardware decode (ffmpeg+NVDEC/GStreamer) + sub-stream.
  `C_dec` phải đo trên cơ chế đã chọn. → thêm mục "Cơ chế DECODE".
- **Lỗ 3 (NẶNG NHẤT) — analytics CÓ TRẠNG THÁI:** count/track cần state xuyên-frame per-camera, nhưng Stage
  stateless-per-frame → KHÔNG khớp. Cần StatefulStage + **camera-affinity** (1 cam cố định 1 worker, không
  round-robin) → ràng buộc MỚI cho scheduler (khác inference stateless batch tự do). → thêm mục riêng.
- **Lỗ 4 — failover coi nhẹ:** re-shard camera khi node chết = phân tán KHÓ (split-brain/2-writer vỡ 1writer/ring
  + ABA) → cần fencing token/lease phân tán. → nâng thành RỦI RO CAO, sub-spec riêng.
Còn mở có chủ đích (sub-spec sau): transport quy mô · config hot-reload · metrics backend · batch-mux tự-viết vs Triton.
Phán quyết: ĐỦ TỐT làm bản ĐỊNH HƯỚNG PHA-1 (trung thực về giới hạn/lỗ/rủi ro); KHÔNG đủ làm thiết kế thi công →
mỗi mảnh cần sub-spec design-first (đặc biệt batch-mux, stateful-analytics, failover). Bài học: Stage stateless là
giả định NGẦM của base — mọi analytics có state (track/count/dedup) phải xử camera-affinity, ghi nhớ khi thiết kế fan-out.


### K-043 — 2026-07-06 — ĐÀO SÂU slice design: 5 lỗ (A–E) tìm khi đọc code thật + đã đưa vào design
Status: ℹ️✅ (đã sửa vào design.md vision-vertical-slice; 3 file 0-diagnostic). Nguồn: LOG #217 · đọc thật
Detection/BBox/FakeDetector/DetectorPipeline/Fake&NoiseFrameSource.
5 lỗ của bản design NÔNG (đã vá):
- **Lỗ A — timestamp:** dùng `capture_time_ns` (monotonic, mốc gốc KHÔNG xác định) làm mốc event = SAI cho log
  lưu trữ (đọc lại sau vô nghĩa) → thêm `event_ts` **wall-clock UTC ISO-8601** làm mốc chính; monotonic chỉ phụ (đo trễ).
- **Lỗ B — CompositeSink:** PipelineRunner nhận 1 sink, nhưng slice cần VỪA gom (test) VỪA ghi file → thêm
  `CompositeSink(list[ISink])` (setup thuận/teardown ngược, forward handle).
- **Lỗ C — thiếu-key vs rỗng:** CountStage phải phân biệt `artifacts` KHÔNG có "detections" (sai thứ tự stage →
  ERROR) vs tuple RỖNG (không có object → count=0 hợp lệ). Không đếm 0 âm thầm.
- **Lỗ D — không gian toạ độ:** FakeDetector trả box **MODEL_INPUT**; bọc trần → box sai khi lưu/vẽ → DetectStage
  phải bọc qua **DetectorPipeline** (→ ORIGINAL_FRAME). Event JSONL GIỮ `box.space` tag (invariant Step 02, không strip).
- **Lỗ E — sync vs live (giới hạn, không phải bug):** PipelineRunner v1 đồng bộ, detect CHẶN read → hợp video/
  synthetic (throughput), KHÔNG phải RTSP real-time (frame dồn/rớt). `--rtsp` trên slice = kiểm chức năng, không
  hiệu năng. Live low-latency = async split (tái dùng pattern web_app) — sub-spec sau.
Bài học chung: **đọc API thật TRƯỚC khi đặc tả** lộ ra schema/không-gian/timestamp/lifecycle mà design nông bỏ sót.
Còn mở (sub-spec sau): tracking(Lỗ3) · async live · confidence FilterStage · classify tầng-2 · cross-process SHM.


### K-044 — ℹ️✅ (2026-07-06) Diệt-virus chặn `lint-imports.exe` → verify lint qua `importlinter.api`; + `.venv` per-machine (K-013 lặp lại)
Scope: môi trường verify (lint + venv)
Nguồn: LOG Entry #219, #223 · end.md §0
Nội dung (2 điều nên biết để verify được):
- **AV chặn KHỞI ĐỘNG `lint-imports.exe`** (Access denied khi chạy console-script wrapper .exe). Workaround (fix GỐC, không né bằng tắt AV): chạy import-linter qua API trong `python.exe` (không bị chặn):
  ```
  python -c "from importlinter.api import configuration,use_cases; configuration.configure(); print(use_cases.lint_imports(config_filename='pyproject.toml'))"
  ```
  → verify được **5 kept / 0 broken** mà không cần .exe.
- **`.venv` gắn chặt máy tạo nó** (đường dẫn Python tuyệt đối trong `pyvenv.cfg`): sang máy khác → hỏng (pytest exit 103 / "No Python at ..."). PHẢI dựng lại venv trên mỗi máy (xem end.md §0). Đây là biểu hiện tiếp của K-013.
Đóng: ℹ️✅ (thông tin verify — quy trình đã biết). Xem thêm K-047 (biểu hiện cụ thể trên máy `endgame`).

### K-045 — ✅ (ĐÓNG 2026-07-06, D-044) `_run_from_config` ĐÃ có bulkhead per-pipeline — 1 pipeline lỗi KHÔNG còn kéo sập loop
Scope: `profiles/vision_slice_app.py::_run_from_config` · config-declarative (D-043)
Nguồn: LOG Entry #226 (đánh giá doubt-driven config-declarative — lộ 3 lỗ, mới vá lỗ #1)
Ảnh hưởng (bản chất — QUAN TRỌNG cho ~100 cam / C-014): `_run_from_config` chạy các pipeline TUẦN TỰ trong 1 vòng lặp (T-015). Hiện KHÔNG cô lập lỗi per-pipeline → nếu 1 pipeline ném exception (camera hỏng / detector lỗi / config runtime sai) → **văng khỏi vòng lặp → các pipeline còn lại KHÔNG chạy**. Trong sản phẩm nhiều camera, 1 cam sự cố KHÔNG được phép làm chết toàn hệ (đây chính là pattern **bulkhead** — cô lập khoang). Base đã có tiền lệ bulkhead đúng chỗ khác (K-024 InferenceServer per-request try/except; K-036 detect-thread try/except+reload) → cần áp cùng nguyên tắc ở đây.
Đề xuất fix GỐC (design-first, CHƯA làm — chờ user duyệt): bọc mỗi pipeline trong try/except riêng → 1 pipeline lỗi thì log/emit + `continue` sang pipeline kế (không kéo sập); tổng hợp trạng thái từng pipeline vào summary. (Đây là ứng viên "làm kế" theo end.md §6.)
Đóng khi: implement bulkhead per-pipeline + test (1 pipeline ném lỗi → các pipeline khác vẫn chạy xong).
**[ĐÓNG 2026-07-06 — D-044/LOG #229]** ĐÃ vá tận gốc: bọc mỗi pipeline trong `try/except Exception` (chừa BaseException — T-016) tại vòng lặp `_run_from_config` → lỗi BUILD hoặc RUN của 1 pipeline → log rõ + `continue` sang pipeline kế; return 0 nếu mọi pipeline ok / 1 nếu có lỗi (C-016, chống giấu lỗi). Thêm DI `build` để test xác định. **VERIFY THẬT: 2 test bulkhead pass (pipeline a build-fail + b run-fail → c VẪN chạy; all-ok→0); full 423 passed/1 skipped · lint 5/0.** Còn K-046 (params typo) chưa làm.

### K-046 — ✅ (ĐÓNG 2026-07-06, D-045) Params typo trong config ĐÃ bị chặn (strict-key fail-fast) — không còn nuốt im lặng
Scope: config-declarative — các builder trong `pipeline_factory` + `vision_slice_app._build_detector`
Nguồn: LOG Entry #226 (lỗ #3, chưa vá)
Ảnh hưởng (bản chất): builder đọc tham số bằng `params.get("key", default)` → nếu user gõ SAI tên key trong file .toml (vd `wieghts` thay `weights`, `devcie` thay `device`) → giá trị bị BỎ QUA im lặng, dùng default → hệ chạy SAI cấu hình mà KHÔNG báo lỗi (vd chạy CPU thay GPU, sai đường weight). Khó phát hiện trong sản phẩm — cấu hình "trông như đã set" nhưng không có tác dụng.
Đề xuất fix (chờ user duyệt): validate STRICT key — mỗi builder khai báo tập key hợp lệ; key lạ trong `params` → `ConfigError` liệt kê key không nhận diện (fail-fast, đồng bộ tinh thần `validate_config`/T-014). Cân nhắc gộp vào `validate_config` để bắt trên máy dev no-GPU.
Đóng khi: implement strict-key validation + test (key lạ → ConfigError).
**[ĐÓNG 2026-07-06 — D-045/LOG #230]** ĐÃ vá tận gốc: mỗi builder khai báo `allowed_params` (frozenset key hợp lệ); `_check_params` từ chối key lạ (`ConfigError` fail-fast) — chạy ở CẢ `validate_config` (dry-run `--validate`, máy dev) LẪN `build_runner` (đường chạy thật, TRƯỚC lazy-import torch). **VERIFY THẬT: 4 test (validate typo→ConfigError kèm id; key đúng→ok; build_runner detector-pt typo→bắt trước torch; CLI --validate typo→2); full 427 passed/1 skipped · lint 5/0.** Builder chưa khai báo → lenient (T-017). → 2 lỗ review config (K-045+K-046) ĐÃ đóng hết.

### K-047 — ✅ (ĐÓNG 2026-07-06) Máy THỨ BA (`endgame`) — venv trỏ máy khác → ĐÃ dựng lại (scoop py3.13) + verify baseline THẬT khớp #226
Scope: môi trường verify (máy hiện tại)
Nguồn: phiên này — `whoami`=`endgame\endgame`; `Get-Content .venv\pyvenv.cfg` → `home = C:\Users\k.nguyen.manh.toan\...Python311` + `command = ...\k.nguyen.manh.toan\Desktop\TOANM\PERSONAL\VisionPlatform\...`; `py -0p` → "No installed Pythons found!"; `Get-Command python` → `C:\Users\toann\scoop\apps\python313\current\python.exe`
Nội dung (trung thực — vì sao KHÔNG tự verify được baseline phiên này):
- Repo hiện ở `c:\Users\toann\Desktop\WORK\VisionPlatform` (user `endgame`, home `c:\Users\toann`) — **KHÁC máy đã dựng venv** (`k.nguyen.manh.toan`, path `...TOANM\PERSONAL\...`). Đây là máy thứ 3 (sau `k.nguyen.manh.toan` #219 và các máy trước).
- `.venv` hiện trỏ Python của máy `k.nguyen.manh.toan` (3.11.9) → chạy `.venv\Scripts\python.exe` → lỗi `No Python at '...k.nguyen.manh.toan\...python.exe'`. Venv HỎNG trên máy này.
- `py -0p` không thấy Python nào đăng ký; NHƯNG có **`python` 3.13 qua scoop** trên PATH (`c:\Users\toann\scoop\apps\python313`).
- HỆ QUẢ: baseline **421 passed/1 skipped · lint 5/0** là **số từ LOG #226 (phiên máy `k.nguyen.manh.toan`)**, KHÔNG được xác nhận lại trong phiên máy `endgame` này. Mọi entry ghi baseline phiên này gắn nhãn "[từ LOG #226; CHƯA tự chạy lại — venv hỏng]".
Cách verify lại (khi user cho phép — thao tác môi trường, đổi py3.11.9→3.13): dựng lại venv bằng scoop python 3.13 rồi chạy pytest (theo end.md §0):
```
Remove-Item -Recurse -Force .venv
python -m venv .venv          # python = scoop 3.13
.venv\Scripts\python.exe -m pip install -e ".[dev,onnx,cv2,web]"
.venv\Scripts\python.exe -m pytest -q
```
Lưu ý: đổi 3.11.9→3.13 là nghi phạm đầu tiên nếu sau có lệch hành vi (như K-013). config-declarative dùng `tomllib` — stdlib từ 3.11, OK trên 3.13.
Đóng khi: dựng lại venv trên máy `endgame` + chạy pytest xác nhận baseline thật (rồi cập nhật số + hạ nhãn [chưa kiểm]).
**[ĐÓNG 2026-07-06 — LOG #228]** ĐÃ dựng lại venv bằng scoop python 3.13.12 (`Remove-Item .venv` → `python -m venv .venv` → `pip install -e ".[dev,onnx,cv2,web]"`, KHÔNG pt). **VERIFY TỰ CHẠY THẬT trên máy `endgame`:** `pytest -q` = **421 passed/1 skipped** (37.79s, EXIT 0) — KHỚP CHÍNH XÁC LOG #226; lint qua `importlinter.api` = **5 kept/0 broken** (LINT_OK True). Baseline 421/1 giờ = ĐÃ VERIFY phiên này (hết nhãn [chưa kiểm]).
**Version drift ghi để truy vết (K-013):** máy `endgame` = py **3.13.12** · numpy **2.5.1** · import-linter **2.13** · pytest 9.1.1 (khác máy `k.nguyen.manh.toan` #219: py3.11.9). Baseline giữ 421/1 → tương thích; nhưng nếu sau có lệch hành vi, version 3.13 là nghi phạm đầu. `tomllib` OK trên 3.13 (stdlib từ 3.11).


### K-048 — 🟡 (ĐÍNH CHÍNH 2026-07-06) Máy `endgame` CÓ GPU RTX 2060 (nvidia-smi) — trước đó nói "no-GPU" là SAI (chưa kiểm nvidia-smi)
Scope: môi trường đo · đính chính các entry #219–#231 nói "máy no-GPU"
Nguồn: LOG Entry #232 · harness `_env.py` in `nvidia-smi --query-gpu=name` → **"NVIDIA GeForce RTX 2060"** (driver OK); `torch` = not-installed (venv chỉ `.[dev,onnx,cv2,web]`, KHÔNG `.[pt]`)
Nội dung (TRUNG THỰC — sửa khẳng định sai):
- **Đã kiểm (bằng chứng):** máy `endgame` CÓ card **RTX 2060** + driver (nvidia-smi trả tên card). Vậy KHÔNG phải "no-GPU".
- **Điều mình nói sai trước:** #219–#231 (D-042/D-043/D-046 + activeContext) lặp lại "máy dev no-GPU" — đó là SUY ĐOÁN dựa trên venv hỏng + `py -0p` rỗng, **CHƯA chạy nvidia-smi**. Bản chất đúng: **GPU CÓ, nhưng `torch`/`yolov5` CHƯA cài** (thiếu `.[pt]`). "no-GPU" nên đọc là "no-torch / chưa xác nhận CUDA-compute".
- **CHƯA kiểm:** `torch.cuda.is_available()` (torch chưa cài) → chưa chắc CUDA-compute chạy được. Muốn chắc: `pip install -e ".[pt]"` (kéo torch CUDA ~vài GB) → `python -c "import torch; print(torch.cuda.is_available())"`.
- **Hệ quả (cơ hội):** benchmark THẬT (M1 C_inf dùng synthetic frame — KHÔNG cần camera/video) CÓ THỂ chạy NGAY trên máy này sau khi cài `.[pt]` + có 1 weight `.pt` (yolov5.load tự tải yolov5s). → không nhất thiết phải đợi "máy GPU khác".
Đóng khi: cài `.[pt]` + xác nhận `torch.cuda.is_available()=True` (rồi chạy benchmark thật, điền template D-046) — HOẶC user xác nhận không cài trên máy này.


### K-049 — 🔴 (2026-07-06) `pip install .[pt]` trên Windows kéo torch **CPU-only** (2.12.1+cpu) → benchmark GPU CHƯA chạy được dù có RTX 2060
Scope: môi trường đo GPU · venv máy `endgame`
Nguồn: LOG Entry #233 · `torch.__version__`=**2.12.1+cpu** · `torch.version.cuda`=None · `torch.cuda.is_available()`=**False** (chạy thật, đọc output)
Nội dung (TRUNG THỰC — chặn benchmark GPU):
- User duyệt cài `.[pt]` → cài xong **torch 2.12.1+cpu · torchvision 0.27.1 · yolov5 7.0.14 · ultralytics 8.4.89**. NHƯNG là wheel **CPU-only** (PyPI mặc định trên Windows) → `torch.cuda.is_available()=False` → **KHÔNG chạy inference trên RTX 2060**. Harness `--device cuda` đúng thiết kế: dừng exit 3, KHÔNG tạo số giả.
- **Muốn số GPU thật:** cài lại torch bản CUDA từ index PyTorch, vd `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124` (tải ~2.5GB thay wheel CPU) → kiểm lại `torch.cuda.is_available()` + driver 2060 hỗ trợ CUDA đó. [chưa kiểm driver/CUDA version tương thích — cần thử].
- **Version drift (K-013):** cài `.[pt]` HẠ **numpy 2.5.1→2.4.6** + đổi **opencv-python→opencv-python-headless** (yolov5 ràng buộc). **Baseline verify lại: full 436 passed/1 skipped khi máy IDLE** → không phá logic.
- **Flaky KHÔNG phải regression (K-035 xác nhận):** ngay sau cài (máy tải nặng: AV quét 2.5GB + đĩa), `test_fullstack_end_to_end` fail (3s budget cross-process hụt). Sau khi tải lắng: **chạy riêng 6/6 PASS + full suite 436/1 PASS**. → load-induced, không phải lỗi dep. Củng cố K-027 (timing) + K-035.
Đóng khi: (a) cài torch CUDA wheel + `torch.cuda.is_available()=True` → chạy benchmark GPU thật; HOẶC (b) user quyết đo ở môi trường GPU khác / không đo GPU trên máy này.


### K-050 — 🟢 (2026-07-07) SỰ CỐ `.git` bị xoá giữa phiên (máy `k.nguyen.manh.toan`) — ĐÃ cứu dữ liệu, còn rủi ro lặp
Status: 🟢 (dữ liệu đã cứu + backup ngoài folder) · 🔴 (nguyên nhân xoá [chưa xác định] + rủi ro xoá lại)
Scope: máy `k.nguyen.manh.toan` (không phải máy `toann` hiện tại) · git lifecycle
Nguồn: LOG Entry #235 (chẩn đoán), #236 (khôi phục + bundle)
Evidence (verify THẬT + đọc output): đầu phiên `git status` OK → giữa phiên "not a git repository"; Recycle Bin có `.git` (Original Location khớp path, DEL 2026-07-07 09:47, 5.41MB); restore → `Test-Path .git`=True; `git fsck --full` chỉ dangling (không hỏng); HEAD=`5c1f5c1`, develop ahead 43, 72 commit (khớp đầu phiên); `git bundle --all` → `C:\Users\k.nguyen.manh.toan\git-backups\VisionPlatform-20260707-110408.bundle`, `bundle verify` OK + clone-test HEAD+count khớp.
Đóng khi: có biện pháp phòng xoá-lại (push remote / chuyển repo ra vị trí DLP không quét) + xác định được công cụ xoá.
Nội dung: một tiến trình NGOÀI (KHÔNG phải lệnh AI — verify bằng thứ tự transcript: AI chỉ xoá `vision-platform\.venv` SAU khi `.git` đã mất) chuyển `.git` vào Recycle Bin lúc 09:47. Máy còn xoá `.git` của NHIỀU project khác + archive VisionPlatform → **mẫu xoá lặp**. Cơ chế cụ thể (nghi DLP/bảo mật doanh nghiệp) **[chưa xác định — không đủ bằng chứng định danh]**.
Rủi ro còn lại: (a) bundle CHỈ có 43 commit đã commit, KHÔNG có working-tree chưa commit (file trên đĩa vẫn rủi ro nếu cả folder bị xoá); (b) có thể bị xoá lại. Fix lâu dài (chờ user): commit working-tree + re-bundle (soi secret K-031 trước) · push remote · chuyển repo ra vị trí an toàn.

### K-051 — 🔵 (2026-07-07) BẤT BIẾN correctness: `frames_submitted` phải đếm TẠI LÚC GỬI, KHÔNG lúc enqueue (Mô hình A)
Status: 🔵 (phát hiện ở design; PHẢI verify khi code — nếu sai sẽ vỡ bất biến bảo toàn)
Scope: spec backpressure-cross-process · client async submit path
Nguồn: LOG Entry #238 · design.md §Data Models / mục 4.2 · tasks.md task 2.4 (ghi rõ "đếm frames_submitted TẠI ĐÂY")
Evidence: lập luận correctness trong design (chưa có test chạy — sẽ verify ở PHA code wave 2.4/2.5 bằng property-based Hypothesis `metrics.conserved is True`)
Đóng khi: có test chạy thật chứng minh `frames_submitted + frames_dropped_backpressure == frames_captured` dưới DROP_OLDEST quá tải.
Nội dung: dưới Mô hình A, hàng đợi outbound chỉ chứa frame CHƯA gửi. Nếu đếm `frames_submitted` lúc ENQUEUE thì một frame đã tính submitted có thể bị DROP_OLDEST evict sau đó → frame đó bị tính CẢ submitted LẪN dropped → đếm trùng → vỡ bất biến `submitted + dropped == captured`. Phải đếm `frames_submitted` tại thời điểm `send()` (khi rời hàng đợi vào in-flight) → mỗi captured frame được tính đúng MỘT trong {submitted, dropped}.
Vì sao quan trọng: đây là chỗ CỰC dễ "fix ngọn" bỏ sót — code trông hợp lý nhưng bất biến âm thầm sai dưới tải. Ghi lại để khi code (wave 2.4) không đặt sai chỗ đếm.

### K-052 — 🟢 baseline ĐÃ tự-verify máy `toann` · 🔴 vẫn thiếu `.git` (2026-07-07)
Status: 🟢 (baseline tự-verify XONG máy toann) · 🔴 (repo máy này KHÔNG có `.git` → git drift-check không áp dụng)
Scope: máy `toann` (`c:\Users\toann\Desktop\WORK_PRO\VisionPlatform`) · môi trường + quy trình đầu phiên
Nguồn: LOG Entry #240 (phát hiện), #241 (rebuild venv + verify) · end.md đến từ máy `k.nguyen.manh.toan` (path khác)
Evidence: (a) `git status` = "fatal: not a git repository" (chạy thật). (b) `.venv` cũ trỏ `C:\Users\k.nguyen.manh.toan\...Python311` (không tồn tại máy này) → rebuild bằng scoop **py3.13.12**. (c) **CHẠY THẬT + ĐỌC OUTPUT máy `toann`:** `pytest -q` = **436 passed / 1 skipped (45.92s, EXIT 0)**; lint qua `importlinter.api` = **5 kept / 0 broken** (104 files, 326 deps, LINT_RESULT=True). Version: numpy 2.5.1 · pytest 9.1.1 · il 2.13 · onnxruntime 1.27 · opencv 5.0.0.93 · onnx 1.22 · Flask 3.1.3 (khớp #232/#234, KHÔNG cài pt/torch).
Đóng khi: (phần .git) repo được đặt dưới git trên máy này HOẶC xác nhận đây chỉ là bản sao working-tree.
Nội dung: baseline **436/1 · lint 5/0** GIỜ đã tự-kiểm trên máy `toann` (không còn kế thừa suông từ máy khác) → có gốc so sánh "không hồi quy" khi code. Riêng repo máy này KHÔNG có `.git` → drift-check dùng file-state + diagnostics thay git. (venv rebuild lặp lại K-013: venv per-machine, artifact gitignore, dựng lại là đúng gốc.)
Vì sao ghi: (1) chốt mốc baseline THẬT tại đây trước khi triển khai (đúng nguyên tắc user "valid trước khi làm"); (2) trung thực đa-máy (K-013) — số 436/1 trước phiên này là kế thừa, nay đã tự chạy lại.


### K-053 — ✅ (2026-07-08) `camera_worker` có HAI tầng backpressure độc lập (SHM ring ⊥ client submission-window)
Status: ✅ (đã hiện thực Wave 3.1 + ASSERT bất biến 2-tầng cross-process Wave 4, D-051 — 465/1)
Scope: `profiles/vision_fullstack_profile.py::camera_worker` · spec backpressure-cross-process
Nguồn: LOG Entry #244 · đọc code camera_worker + `WriterEpochCoordinator.write` (trả None khi ring đầy) + `ZmqInferenceClient` (BoundedQueue outbound)
Evidence: (chờ) test Wave 3.1/Wave 4 + bất biến
Đóng khi: Wave 3.1 code xong + verify bất biến `submitted+dropped==captured` (dropped gộp 2 tầng) qua test.
Nội dung: Frame trong `camera_worker` đi qua 2 chốt điều tiết KHÁC NHAU: (1) **SHM ring** — `wcoord.write()` trả None khi ring đầy (backpressure tầng truyền cross-process, có trước spec này); (2) **cửa sổ submit client** — `BoundedQueue` DROP_OLDEST khi in-flight window đầy (spec này thêm). `metrics_snapshot()` CHỈ đếm tầng (2). Để bất biến `submitted+dropped==captured` đúng, `camera_worker` PHẢI cộng thêm drop tầng (1) (`frames_dropped_shm`) vào dropped khi ghi artifact (C-019/T-020).
Vì sao ghi: đây là điểm CỰC dễ "fix ngọn" — nếu chỉ lấy dropped từ `metrics_snapshot()` mà bỏ nhánh SHM-full, bất biến vỡ âm thầm dưới tải (đúng lỗ A2). Ai code/đọc sau phải nhớ 2 tầng này tách biệt.


### K-054 — ✅ (2026-07-08) Drift TỒN ĐỌNG bị linter D-052 bắt + xử lý — LOG dup legacy #90/91/95/96 + thiếu detail D-036
Status: ✅ (đã xử lý; linter PASS)
Scope: `AI-IMPLEMENTATION-LOG.md` + `ai-decision-journal/01-decisions.md` · phát hiện bởi `tests/test_memory_consistency.py`
Nguồn: LOG Entry #248 · dogfood linter D-052 lần đầu
Evidence: linter lần đầu FAIL (C1 dup=[90,91,95,96] · C3-D thiếu=[36] · C5-D orphan=[36]) → sau xử lý PASS toàn bộ
Đóng khi: (đã đóng — nhưng lưu để audit hiểu vì sao có allowlist + D-036 khôi phục)
Nội dung: (1) **LOG dup #90/91/95/96** — mỗi số 2 entry do 2 AI (Gemini+Kiro) append cùng ngày 2026-06-21..24 (va chạm số). Lịch sử THẬT → KHÔNG renumber (append-only + tránh vỡ tham chiếu); linter allowlist 4 số này (documented) + fail mọi dup MỚI. (2) **D-036 detail thiếu** khỏi 01-decisions.md (nghi mất khi sync đa-máy) dù INDEX có dòng → khôi phục từ LOG #198 (C-020).
Vì sao ghi: chứng minh giá trị linter (bắt drift người không thấy) + giải thích vì sao có allowlist (không phải giấu lỗi mà là tôn trọng append-only cho lịch sử đông cứng, siết chặt cho tương lai).



### K-055 — ✅ (2026-07-08) Hook `runCommand` KHÔNG hiểu `;` là separator → dán vào argv → HỎNG. Dùng 1-script entry.
Status: ✅ (đã fix gốc: drift_check.py; verify chạy thật EXIT=0)
Scope: `.kiro/hooks/{auto-drift-check,kiem-drift-bo-nho}.kiro.hook` · `tests/drift_check.py`
Nguồn: LOG Entry #250 · lỗi thật hook: `python: can't open file '...test_memory_consistency.py;'`
Evidence: `python tests/drift_check.py` (đúng dạng hook) chạy cả 2 linter, EXIT=0 (đọc output thật)
Đóng khi: (đã đóng)
Nội dung: Hook `runCommand` command `"python A.py; python B.py"` bị mangle — `;` KHÔNG được hiểu là dấu phân tách lệnh mà bị dán vào argv → `python` nhận filename `A.py;` → "No such file". Bằng chứng gốc = chính thông báo lỗi (không đoán). Fix GỐC: tạo `tests/drift_check.py` (điểm vào DUY NHẤT gọi cả 2 linter nội bộ) → hook chỉ cần 1 lệnh `python tests/drift_check.py` (không separator, shell-agnostic). Cập nhật cả §0/§2 (4 mirror + kit) dùng 1 lệnh này = một-nguồn-sự-thật.
Vì sao ghi: (a) bài học cho MỌI hook sau — KHÔNG ghép nhiều lệnh bằng `;`/`&&` trong runCommand; gói vào 1 script. (b) chống-drift đầu phiên giờ dùng `py tests/drift_check.py` (1 lệnh), không phải 2 lệnh rời.
**CẬP NHẬT #251 (VERIFIED):** hook `auto-drift-check` (agentStop) ĐÃ TỰ KÍCH HOẠT thật sau lượt #250 → chạy `python tests/drift_check.py` → **PASS, EXIT 0** (bằng chứng: output user dán). → đóng nốt "chưa verify hook trigger" của #249/#250. Cơ chế chống-drift 3 tầng hoạt động end-to-end.



### K-056 — 🟡 (2026-07-08) Ranh giới client backpressure (KHÔNG phải bug — dùng đúng cách): snapshot-đọc-sau-quiesce + không-trộn sync/async
Status: 🟡 (ranh giới thiết kế, ghi để dùng đúng — không cần fix)
Scope: `adapters/zmq_inference_client.py` (metrics_snapshot · infer() sync vs submit() async)
Nguồn: LOG Entry #252 · review đối kháng D-054
Evidence: đọc code io_loop + metrics_snapshot; test hiện có gọi snapshot SAU drain (io idle) → không lộ vấn đề
Đóng khi: (ranh giới, không đóng — tuân thủ khi dùng)
Nội dung: (F2) `metrics_snapshot()` đọc `_sent/_ok/_err/_timeout` + `queue.drops/rejects` từ thread GỌI trong khi io thread có thể ghi → 6 field KHÔNG chụp nguyên tử. An toàn khi đọc SAU khi io quiesce (in_flight==0 & outbound rỗng, tức sau drain — đúng cách camera_worker + test dùng). Đọc giữa lúc tải cao → snapshot có thể lệch tức thời (không vỡ bất biến sau drain). (F3) `infer()` sync gửi qua `_outbound` KHÔNG qua flow-control window (chỉ async `submit()` bị window giới hạn) → nếu TRỘN infer()+submit() nặng trên cùng client, đường sync bỏ qua window có thể làm ngập server. Dùng: 1 client cho 1 kiểu (profile hiện chỉ dùng submit()).
Vì sao ghi: chống hiểu nhầm "snapshot realtime chính xác" + chống dùng sai (trộn 2 đường). Không phải lỗi — là hợp đồng sử dụng.
**CẬP NHẬT #253 (D-055):** F2 giờ được xử lý CẤU TRÚC trong `camera_worker` — `finally` teardown TRƯỚC (dừng io thread → quiesce) rồi mới `metrics_snapshot()` → snapshot luôn đọc sau quiesce (không còn dựa "nhớ đọc đúng lúc"). F3 vẫn là hợp đồng dùng (không trộn sync/async nặng).



### K-057 — ✅ (2026-07-09) Interpreter Python KHÔNG portable giữa máy Windows → hook/CI phải dò capability, không hardcode tên
Status: ✅ (đóng bằng launcher D-056; ghi để không tái phạm)
Scope: mọi hook `runCommand` / CI gọi Python trên Windows (`tests/drift_check.cmd`)
Nguồn: LOG Entry #254 · lỗi thật hook EXIT 9009
Evidence: máy `k.nguyen.manh.toan`: `py -3 --version` EXIT 0 · `python --version` EXIT≠0 (Store-alias). Máy `toann` (#251): `python` chạy hook OK.
Đóng khi: đã đóng bằng launcher capability-test (D-056)
Nội dung: 3 kiểu Python trên Windows KHÁC nhau theo máy: (a) python.org → có `py` (Python Launcher), `python` có thể thiếu; (b) scoop → có `python`, thường THIẾU `py`; (c) Windows Store alias `python` → TỒN TẠI trên PATH nhưng chạy in "Python was not found" + EXIT 9009. ⇒ Hook hardcode 1 tên (`python` HAY `py`) sẽ hỏng trên ít nhất 1 loại máy. Giải: launcher dò bằng KHẢ NĂNG (`X --version` exit 0), KHÔNG bằng tồn tại (`where` thấy Store-alias nhưng nó hỏng).
Vì sao ghi: đây là bẫy môi trường lặp lại (họ K-013/K-044/K-047 "venv/interpreter per-machine"). Ghi để phiên sau KHÔNG "sửa nhanh" bằng cách đổi tên interpreter (fix ngọn) mà tái phạm.

**CẬP NHẬT #255 (VERIFIED):** hook `agentStop` `auto-drift-check` ĐÃ TỰ KÍCH HOẠT sau lượt #254 → chạy `cmd /c tests\drift_check.cmd` → **PASS/EXIT 0** trên chính máy `k.nguyen.manh.toan` (nơi trước đó EXIT 9009). Launcher capability-test (D-056) xác nhận đóng lỗ THẬT trong cơ chế hook tự động, không chỉ chạy tay. → K-057 = VERIFIED.


### K-058 — ✅ (2026-07-09) Dev-env launcher `scripts/vp.cmd` — cách chạy mọi máy + profile per-máy
Status: ✅ (dùng được — verify EXIT 0)
Scope: `scripts/vp.cmd` · `scripts/env.local.cmd` (gitignored) · `scripts/README.md`
Nguồn: LOG Entry #256 · D-057
Evidence: `vp env/verify/setup` chạy thật EXIT 0 trên máy `k.nguyen.manh.toan` (no-GPU)
Đóng khi: đã dùng được (ghi để dùng đúng)
Nội dung: Đổi máy → chỉ cần `scripts\vp.cmd setup` rồi `scripts\vp.cmd verify`. Auto-detect interpreter/GPU; nếu sai, tạo `scripts\env.local.cmd` (copy từ `.example`, gitignored) đặt `VP_PYTHON`/`VP_EXTRAS`. Máy CÓ GPU + muốn torch: `set "VP_EXTRAS=dev,onnx,cv2,web,pt"` (lưu ý K-049: Windows dễ ra torch-CPU, cần CUDA wheel riêng nếu muốn GPU thật). `vp lint` đã né AV (K-044) sẵn. `vp check` = drift-check.
Vì sao ghi: để phiên/máy sau KHÔNG lặp lại chuỗi tay (dò python + dựng venv + nhớ workaround lint) — 1 lệnh thay tất cả; là hiện thực hoá lớp chống-ma-sát-môi-trường (đồng họ K-013/44/47/52/57).


### K-059 — 🔵 (2026-07-09) CI `verify.yml` — ranh giới verify + rủi ro cần biết
Status: 🔵 (chờ lần chạy CI đầu để chuyển ✅ hoặc sửa)
Scope: `.github/workflows/verify.yml`
Nguồn: LOG Entry #257 · D-058
Evidence: file tạo tại chỗ; CHƯA có run CI nào (không chạy Actions cục bộ)
Đóng khi: CI chạy xanh lần đầu (xem tab Actions / dán log)
Nội dung: (a) KHÔNG verify được CI cục bộ → chỉ biết xanh/đỏ khi push kích hoạt (giống cách hook được verify qua output dán). (b) Rủi ro flaky trên CI (K-035: cross-process/shutdown nhạy tải) → đỏ-do-flaky ≠ regression. (c) `actions/checkout@v4`+`actions/setup-python@v5` [chưa kiểm trên chính CI này]. (d) Token PAT nhúng URL origin KHÔNG ảnh hưởng Actions (dùng GITHUB_TOKEN). (e) CI = cùng cổng `vp verify`, chỉ khác chạy server-side.
Vì sao ghi: đánh dấu rõ đây là hạng mục "verify-khi-chạy", tránh tự nhận "CI xong" khi chưa có 1 run xanh thật.


### K-060 — 🟡 (2026-07-09) IouTracker v1 = greedy IoU: giới hạn cross-over + phạm vi (biết để dùng đúng)
Status: 🟡 (giới hạn thiết kế đã-biết, KHÔNG phải bug — nâng cấp qua port khi cần)
Scope: `runtime/iou_tracker.py` · `domain/tracking.py` · `runtime/stages/tracking_stage.py`
Nguồn: LOG Entry #259 · design `object-tracking-count` self-review Lỗ 5
Evidence: `vp verify` 479/1 · 14 test tracking pass (giữ-id/id-mới/retire/deterministic/edge)
Đóng khi: (giới hạn — đóng nếu thay ML tracker qua ITracker)
Nội dung: (a) greedy IoU ≠ tối ưu toàn cục → 2 vật ĐI QUA NHAU (box giao) có thể HOÁN track_id — chấp nhận v1. Nâng cấp = impl `ITracker` khác (Kalman/DeepSORT) KHÔNG đụng TrackingStage. (b) camera-affinity: 1 instance/1 camera; trộn source_id → ERROR (fail-fast). (c) unique_count đơn điệu (đã-thấy = đã-đếm, không giảm khi retire); active_count = hiện tại. (d) Non-Goal v1: line/zone-crossing count, cross-process state, re-ID. (e) CHƯA wire profile `--track` (lõi+test xong; wire là bước tuỳ chọn sau).
Vì sao ghi: chống kỳ vọng sai ("tracker hoàn hảo") + chỉ rõ điểm nâng cấp (port) — đúng bản chất, không cần rebuild.

**CẬP NHẬT #260:** ĐÃ wire `--track` vào `vision_slice_app` (append TrackingStage sau CountStage; cờ `--track`/`--track-iou`/`--track-max-age`). `unique_count` in ra đọc từ ARTIFACTS qua `_TrackSummarySink` (KHÔNG đọc tracker sau run — vì `run()` teardown→`reset()` làm về 0). Verify: `main(--source fake --frames 5 --track)` → unique_tracks=1; full 480/1 sạch. Còn lại của K-060 (cross-over id-swap, no line-crossing/cross-process/re-ID) vẫn nguyên.


### K-061 — 🟡 (2026-07-09) LineCrossingStage v1: giới hạn + cách dùng (biết để dùng đúng)
Status: 🟡 (giới hạn thiết kế đã-biết, KHÔNG bug)
Scope: `runtime/stages/line_crossing_stage.py` · `domain/geometry.py` · wire `--line` trong `vision_slice_app`
Nguồn: LOG Entry #262 · design `line-crossing-count` self-review
Evidence: `vp verify` 494/1 · 14 test line-crossing pass (qua/không/hướng/edge/prune/wiring)
Đóng khi: (giới hạn — đóng nếu nâng cấp: giữ history có max_age / đa-vạch / CrossingEvent)
Nội dung: (a) prune id vắng mỗi frame → bounded memory 24/7, ĐỔI LẠI track nhấp-nháy (vắng 1 frame) reset mốc → có thể SÓT 1 lượt. (b) collinear (đi DỌC vạch) = không cắt (đúng nghĩa "đi dọc ≠ qua"). (c) 1 vạch/1 instance/1 camera (đa-vạch = nhiều LineCrossingStage). (d) quy ước in/out PHỤ THUỘC thứ tự (A,B) — đảo A,B đảo in/out → cấu hình đúng chiều. (e) `--line` cần `--track`; đường sync (hợp video/synthetic, không real-time RTSP). (f) chưa có CrossingEvent DTO (log lúc-nào-ai-qua) — Non-Goal v1.
Vì sao ghi: chống kỳ vọng sai + chỉ điểm nâng cấp; các giới hạn là đánh đổi CÓ CHỦ ĐÍCH (bounded memory > chính xác nhấp-nháy) đúng cho sản phẩm 24/7.


### K-062 — 🟡 (2026-07-09) CrossingEventJsonlSink / event-log v1: giới hạn + cách dùng
Status: 🟡 (giới hạn thiết kế đã-biết, KHÔNG bug)
Scope: `kernel/crossing_event.py` · `adapters/crossing_event_sink.py` · `LineCrossingStage` (clock/crossing_events) · wire `--crossing-out`
Nguồn: LOG Entry #264 · design `crossing-event-log`
Evidence: `vp verify` 501/1 · 7 test crossing-event pass
Đóng khi: (giới hạn — đóng nếu thêm DB sink / dedupe / schema-version)
Nội dung: (a) chỉ JSONL (DB/queue = impl ISink khác sau — Non-Goal v1). (b) KHÔNG dedupe qua restart: sink mở "a" (append) → chạy lại ghi TIẾP (trùng nếu re-process cùng frame); dedupe/idempotency là bước sau. (c) `event_ts` wall-clock UTC "Z" (giờ thật, không monotonic); flush mỗi dòng → crash cứng mất tối đa 1 event (đánh đổi durability/tốc độ). (d) `--crossing-out` cần `--line` (cần `--track`); đường sync. (e) clock TIÊM được cho test xác định.
Vì sao ghi: rõ ranh giới dùng (append→có thể trùng khi re-run) + điểm nâng cấp (DB/dedupe) — tránh kỳ vọng "exactly-once" mà v1 chưa có.


### K-063 — 🟡 (2026-07-09) MotionGateStage v1: giới hạn + cách dùng
Status: 🟡 (giới hạn thiết kế đã-biết, KHÔNG bug)
Scope: `domain/motion.py` · `runtime/stages/motion_gate_stage.py` · config `motion_gate` · CLI `--motion-gate`
Nguồn: LOG Entry #267 · design motion-gate self-review
Evidence: `vp verify` 519/1 · 8 test (gồm integration gate giảm downstream calls)
Đóng khi: (giới hạn — đóng nếu thêm MOG2/ROI/min-interval)
Nội dung: (a) motion = tỉ-lệ-pixel-đổi full-frame → NHẠY với đổi-ánh-sáng-toàn-cục (đèn bật/tắt, mây qua → coi là motion, chạy detector thừa). MOG2/background-subtraction chịu tốt hơn = Non-Goal v1. (b) KHÔNG ROI-mask (gate cả khung, không chỉ vùng quan tâm). (c) KHÔNG min-frame-interval (tĩnh liên tục → detector KHÔNG chạy suốt; nếu cần "chắc chắn chạy 1 frame/N" để không miss → thêm sau). (d) cast int16 BẮT BUỘC (uint8 underflow). (e) frame đầu/đổi-shape → đi tiếp (không bỏ nhầm). (f) camera-affinity 1-instance/1-camera. (g) đặt TRƯỚC detect trong chuỗi.
Vì sao ghi: rõ khi nào gate đếm nhầm motion (ánh sáng) + điểm nâng cấp (MOG2/ROI/min-interval); tránh kỳ vọng "lọc hoàn hảo".


### K-064 — ✅ (2026-07-09) BÀI HỌC chống-drift: KHÔNG tin output tool DÁN trong tin nhắn là trạng thái hiện tại — TỰ chạy drift-check đầu phiên (§0)
Status: ✅ (sự cố đã sửa; drift-check PASS #268)
Scope: quy trình đầu phiên · AI-IMPLEMENTATION-LOG (#269)
Nguồn: LOG Entry #269
Evidence: log từng có 2× `### Entry #254` (Select-String) → sau xoá dup: drift-check PASS (#268, 172 entry); baseline 521/1 verify máy toann
Đóng khi: (bài học — luôn áp dụng)
Nội dung: Lượt #269 tôi TIN output drift-check user DÁN (hiển thị #253) là trạng thái hiện tại → append entry #254 → TRÙNG số với #254 thật (repo đã sync đè lên #268 giữa chừng). Output dán là SNAPSHOT CŨ (hook chụp sau lượt #253, trước khi #268 sync về). Anti-drift tự bắt: đọc INDEX thấy header #268 ≠ #253 → điều tra → xoá dup → PASS.
Vì sao ghi (bài học vận hành): (1) §0 "TỰ chạy `py tests/drift_check.py` đầu phiên" là BẮT BUỘC — output dán/nhớ KHÔNG thay được (repo đa-máy có thể sync đè bất kỳ lúc nào, K-052). (2) Trước khi APPEND log/journal, luôn xác nhận max entry THẬT bằng grep/drift-check (chống trùng số). (3) Anti-drift linter (D-052) chứng minh giá trị lần nữa: nó là thứ phát hiện #268 vs #253.

### K-065 — ✅ (2026-07-09) BÀI HỌC thiết kế: "0 diagnostic" chứng nhận CẤU TRÚC, KHÔNG chứng nhận ĐÚNG-BẢN-CHẤT — phải đọc-lại + đối chiếu code thật
Status: ✅ (đã fix 3 lỗ design motion-gate-roi trước khi code)
Scope: quy trình design-first · `.kiro/specs/motion-gate-roi/design.md` · LOG Entry #271
Nguồn: LOG Entry #271
Evidence: design #270 tuy `get_diagnostics`=No diagnostics (đúng Kiro Spec Format) VẪN chứa 3 lỗ logic; sau đọc code thật (`motion.py`/`MotionGateStage`/`pipeline_factory`/CLI) + đối chiếu → lộ 3 lỗ → sửa; get_diagnostics vẫn 0.
Đóng khi: (bài học — luôn áp dụng cho mọi spec design-first)
Nội dung: Review đối kháng design `motion-gate-roi` tìm 3 lỗ THIẾT KẾ: (1) mâu thuẫn thứ-tự mask/mean trong `changed_ratio` (pseudo-code mean-toàn-mảng ⟂ chú thích mean-trong-mask) → fix: mask-TRƯỚC-rồi-mean-sub (mean trong vùng xét, tránh đổi-sáng-ngoài-ROI tạo motion giả); (2) khoảng hở fail-fast — validate ROI range nằm trong `roi_mask` (cần shape→chỉ chạy runtime) → tách `validate_roi` thuần-số gọi ở config-time (ConfigError sớm); (3) CLI naming lạc prefix `--motion-gate-*`.
Vì sao ghi (bài học vận hành): (1) checker format (0 diagnostic) là ĐIỀU KIỆN CẦN, KHÔNG đủ — nó không đọc được logic. Muốn design đúng-bản-chất phải TỰ đọc-lại + đối chiếu CODE THẬT nền tảng (chống bịa: mọi tham chiếu design phải khớp code đang chạy). (2) Fix ở tầng thiết kế (tài liệu) RẺ hơn fix sau khi code nhiều lần — đúng triết lý "valid thiết kế kiểm-chứng-được RỒI mới triển khai". (3) Nguyên tắc "kiểm cái gì ở nơi có đủ dữ kiện để kiểm" (range→config-time; rỗng-pixel→runtime-có-shape).

### K-066 — 🟡 (2026-07-09) Cài torch CUDA (RTX 2060) trên máy `toann`: bẫy CPU-wheel + CDN PyTorch chậm → hoãn chờ mirror/mạng
Status: 🟡 (torch CHƯA cài — network-bound; lệnh+version đã đúng, chờ mạng/mirror)
Scope: môi trường GPU máy `toann` · LOG Entry #273 · liên quan K-048/K-049
Nguồn: LOG Entry #273
Evidence: `nvidia-smi` RTX 2060 6GB driver 591.86; wheel CPU 122MB vs CUDA 2532MB (quan sát pip); tốc độ CDN 11–615 kB/s eta tới 61h (đọc thật); venv sau hủy = numpy 2.5.1/opencv 5.0.0/torch chưa cài + `pytest` 546/1
Đóng khi: cài được torch CUDA + `torch.cuda.is_available()==True` + re-verify baseline
Nội dung: (1) **Bẫy CPU-wheel:** `--extra-index-url pypi` KHÔNG kèm pin → pip lấy torch bản cao từ PyPI (Windows = CPU-only, ~122MB) thay vì CUDA (~2.5GB). FIX: PIN `torch==2.6.0+cu124` (local-version `+cu124` chỉ có ở pytorch index) → buộc CUDA build, dep phụ vẫn lấy PyPI. (2) **CDN chậm:** download.pytorch.org từ mạng này 11–615 kB/s (eta 1.5–61h) → không khả dụng; fix gốc = mirror (bên thứ ba → cần user duyệt) hoặc chờ mạng tốt. (3) pip tải hết wheel TRƯỚC khi install → hủy giữa tải KHÔNG trôi gói (loại trừ K-049 lần này).
Vì sao ghi (chống lặp công + chống bịa): phiên sau retry cài torch phải dùng NGAY lệnh đúng (`pip install "torch==2.6.0+cu124" "torchvision==0.21.0+cu124" --index-url .../cu124 --extra-index-url pypi`) + hiểu bẫy CPU-wheel, KHÔNG mất lượt phát hiện lại. Motion-gate-roi core đã xong (D-067) độc lập torch; GPU chỉ cần cho detector+tune thực địa.

### K-067 — ✅ (2026-07-10) BÀI HỌC (củng cố K-065): review đối chiếu LUỒNG THỰC THI lộ lỗ "mù-lúc-outage" mà 0-diagnostic không bắt
Status: ✅ (đã fix 3 lỗ design pipeline-observability trước khi code)
Scope: quy trình design-first · `.kiro/specs/pipeline-observability/design.md` · LOG Entry #275
Nguồn: LOG Entry #275
Evidence: design #274 (0-diagnostic) vẫn có lỗ: emit-theo-giờ đặt sau `frames_read++` → camera reconnecting (read→no-data→continue) không bao giờ emit; lộ khi đọc-lại vòng lặp `PipelineRunner.run` thật; sau fix get_diagnostics vẫn 0.
Đóng khi: (bài học — luôn áp dụng)
Nội dung: Review đối kháng design pipeline-observability tìm 3 lỗ: (A) emit-theo-giờ phải ở ĐẦU vòng lặp (không sau frames_read++) → nếu không, mất-camera = mù đúng lúc cần quan sát; (B) "emit-cuối chỉ khi khác no-op" = isinstance coupling → luôn emit, noop là guard; (C) fps tích-luỹ che sự cố → dùng interval-fps.
Vì sao ghi (bài học vận hành): củng cố K-065 — "0 diagnostic" chứng nhận CẤU TRÚC, KHÔNG chứng nhận LOGIC. Lỗ A đặc biệt tinh vi: chỉ lộ khi đọc-lại theo LUỒNG THỰC THI (nhánh no-data/continue), không lộ khi đọc từng phần. Nguyên tắc: review design phải TRACE luồng thật (gồm nhánh edge: no-data, reconnecting, raise) đối chiếu code nền, KHÔNG chỉ đọc mô tả xuôi. Fix ở tầng design rẻ hơn sau khi code.

### K-068 — ✅ (2026-07-10) BÀI HỌC (củng cố K-065/K-067): review đối chiếu NGỮ NGHĨA LƯU TRỮ lộ lỗ tính-đúng-exposition mà 0-diagnostic không bắt
Status: ✅ (đã fix 2 lỗ design metrics-exposition trước khi code)
Scope: quy trình design-first · `.kiro/specs/metrics-exposition/design.md` · LOG Entry #280
Nguồn: LOG Entry #280
Evidence: design #279 (0-diagnostic) vẫn có 2 lỗ: (A) `InMemoryMetrics._counters`/`_gauges` là 2 dict RIÊNG cùng key → cùng tên vừa counter vừa gauge → 2 `# TYPE` mâu thuẫn = exposition hỏng; (B) value inf/nan qua `str()` = `'inf'`/`'nan'` chữ thường ≠ chuẩn `+Inf`/`-Inf`/`NaN`. Lộ khi đối chiếu ngữ nghĩa lưu trữ thật + biên số học; sau fix get_diagnostics vẫn 0.
Đóng khi: (bài học — luôn áp dụng)
Nội dung: Review đối kháng design metrics-exposition tìm 2 lỗ tính-đúng: (A) xung đột name↔type → renderer raise ValueError (fail-fast, hàm thuần); (B) fmt_value guard inf/nan → `+Inf`/`-Inf`/`NaN`, số hữu hạn `repr(float)`. +Property 10/11.
Vì sao ghi (bài học vận hành): củng cố K-065/K-067 — "0 diagnostic" chứng nhận CẤU TRÚC, KHÔNG chứng nhận tính-ĐÚNG output-chuẩn. 2 lỗ chỉ lộ khi TRACE ngữ nghĩa LƯU TRỮ thật (2 dict cùng key) + biên giá trị (inf/nan), không lộ khi đọc mô tả xuôi. Nguyên tắc: review adapter phơi-chuẩn phải kiểm cả (a) nguồn dữ liệu có thể sinh trạng thái bất hợp lệ nào + (b) biên giá trị đặc biệt map ra chuẩn ra sao.

### K-069 — ✅ (2026-07-10) BÀI HỌC (củng cố K-065/K-067/K-068): review đối chiếu CHÍNH SÁCH với ràng buộc PHẦN CỨNG/ADAPTER thật lộ lỗ mà 0-diagnostic không bắt
Status: ✅ (đã fix 4 lỗ design capability-aware-execution trước khi code)
Scope: quy trình design-first · `.kiro/specs/capability-aware-execution/design.md` · LOG Entry #282
Nguồn: LOG Entry #282
Evidence: design #281 (0-diag) vẫn 4 lỗ: (A) resolve chỉ kiểm has_cuda bool → cuda:3 máy 1-GPU lọt rồi fail mù torch; (B) trả device gốc "CUDA:0" ≠ chữ-thường adapter khớp; (C) has_cuda chưa gồm device_count>0; (D) CapabilityError chưa phơi sạch ở CLI. Lộ khi đối chiếu policy với số-GPU thật + adapter `yolov5_pt_detector.setup` thật.
Đóng khi: (bài học — luôn áp dụng)
Nội dung: Review capability-aware-execution tìm 4 lỗ tính-đúng-chính-sách: (A) kiểm ordinal cuda:N vs cuda_device_count→fail-fast; (B) chuẩn hoá device về lower 1 dạng; (C) has_cuda = is_available AND count>0; (D) CLI bắt CapabilityError→stderr gọn+exit code (mẫu ConfigError). +Property 8/9.
Vì sao ghi (bài học vận hành): củng cố K-065/K-067/K-068 — "0 diagnostic" chứng nhận CẤU TRÚC, KHÔNG chứng nhận tính-đúng-CHÍNH-SÁCH. Lỗ chỉ lộ khi đối chiếu POLICY (resolve_device) với (a) ràng buộc PHẦN CỨNG thật (số GPU hữu hạn) + (b) hợp đồng ADAPTER tiêu thụ thật (chuẩn hoá chữ). Nguyên tắc: review chính-sách phải trace tới đầu-vào-thực-tế (hardware) + đầu-ra-tiêu-thụ (adapter), không chỉ đọc policy cô lập.

### K-070 — ✅ (2026-07-10) BÀI HỌC (củng cố K-068): helper đồng-bộ event-driven PHẢI an-toàn-ngoại-lệ với side-effect CHƯA xảy ra
Status: ✅ (đã fix design test-stability-hardening trước khi code)
Scope: quy trình design-first · `.kiro/specs/test-stability-hardening/design.md` · LOG Entry #287
Nguồn: LOG Entry #287
Evidence: design #286 (`wait_until`) predicate `"alive_" in log.read_text()` sẽ ném FileNotFoundError lúc log CHƯA tạo → crash chính bản-fix; lộ khi trace trạng-thái-KHỞI-ĐẦU (worker chưa spawn/ghi); sau fix `_safe` bọc → get_diagnostics vẫn 0.
Đóng khi: (bài học — luôn áp dụng)
Nội dung: `wait_until(predicate,...)` phải coi predicate NÉM = "chưa thoả" (bọc try/except→False, poll tiếp), + helper `log_text` (rỗng nếu chưa tạo). Nếu không: predicate đọc file/state CHƯA tồn tại lúc bắt đầu chờ → crash → giải-pháp-chống-flaky tự nó vỡ. +Property 8.
Vì sao ghi (bài học vận hành): củng cố K-068 — review fix-test phải trace tới TRẠNG-THÁI-KHỞI-ĐẦU (file chưa có, state chưa set), không chỉ trạng-thái-đã-ổn-định. Event-driven wait mà không an-toàn-ngoại-lệ = nguồn flaky/crash mới. Nguyên tắc: helper đồng-bộ = phòng thủ ngoại lệ ở ranh giới quan-sát (I/O side-effect chưa xảy ra).

### K-071 — ✅ (2026-07-10) BÀI HỌC (củng cố K-069): review adapter I/O phải trace HỢP ĐỒNG THƯ VIỆN THẬT (lifecycle/thread), không chỉ logic app
Status: ✅ (đã fix design metrics-http-endpoint trước khi code)
Scope: quy trình design-first · `.kiro/specs/metrics-http-endpoint/design.md` · LOG Entry #290
Nguồn: LOG Entry #290
Evidence: design #289 `stop()`=`shutdown()+server_close()` sẽ DEADLOCK nếu gọi trước khi `serve_forever()` vào (hợp đồng `socketserver.BaseServer`: shutdown phải khi serve_forever đang chạy thread khác). Lộ khi trace lifecycle stdlib + kịch bản start→stop nhanh (test P5). Sau fix `_serving` Event → get_diagnostics vẫn 0.
Đóng khi: (bài học — luôn áp dụng)
Nội dung: Exporter dùng `http.server.ThreadingHTTPServer` chạy `serve_forever` trong daemon thread. `stop()` phải CHỜ (`threading.Event` set ngay trước serve_forever) tới khi serve_forever đã vào rồi mới `shutdown()` → chống deadlock stop-sớm. +`poll_interval` để shutdown phản hồi nhanh.
Vì sao ghi (bài học vận hành): củng cố K-069 — review thành phần I/O/hạ-tầng phải đối chiếu HỢP ĐỒNG THƯ VIỆN THẬT (thread-safety, thứ tự lifecycle, điều kiện tiên quyết của API như "shutdown cần serve_forever đang chạy"), không chỉ logic ứng dụng. Nhiều lỗi deadlock/race chỉ lộ ở tầng hợp đồng thư viện.

### K-072 — ✅ (2026-07-10) REVIEW bảo mật observability HTTP `/metrics` + Prometheus exposition = SOUND (đọc code thật)
Status: ✅ (reviewed, no critical bug — không vá speculative)
Scope: `adapters/metrics_http_server.py` · `adapters/metrics_exposition.py` · `kernel/metric_sample.py` · LOG Entry #296
Nguồn: LOG Entry #296
Evidence: đọc 3 file — `_esc_label_value` escape `\`→`\\`(trước)/`"`→`\"`/`\n`→`\n` (khớp spec Prometheus 0.0.4 label-value); MetricsHttpExporter bind default `127.0.0.1`; do_GET provider-lỗi→`send_error(500)` không stack-trace; `_serving` Event chống deadlock shutdown; render type-conflict→ValueError fail-fast; `_fmt_value` inf/nan→+Inf/-Inf/NaN.
Đóng khi: (bài học — kết luận review, không cần đóng)
Nội dung: Endpoint `/metrics` + renderer (máy `k.nguyen.manh.toan` #279–#291) ĐÚNG + AN TOÀN: (a) không inject/vỡ Prometheus text qua label value ký tự lạ (escape đúng); (b) secure-by-default localhost, 0.0.0.0=opt-in+cảnh báo; (c) lỗi không lộ chi tiết; (d) MetricSample DTO giữ (name,labels) tách rời → không parse-ngược lossy (fix gốc D-071). Cứng-hoá NHỎ chưa làm (không cần): validate NAME regex `[a-zA-Z_]...` (name code-controlled), escape `\r` (spec không bắt), auth/rate-limit (localhost nội bộ).
Vì sao ghi: (1) preserve kết luận review → phiên/máy sau KHÔNG review lại endpoint mạng này. (2) Nêu RÕ điều kiện khi cần cứng-hoá thêm (phơi 0.0.0.0 ra internet KHÔNG firewall, hoặc label nhận input ngoài) → biết ngưỡng phải hành động. (3) Minh hoạ "không bịa fix cho vấn-đề-không-tồn-tại".

### K-073 — ✅ (2026-07-11) BÀI HỌC (củng cố K-065): "0-diagnostic" của spec KHÔNG chứng nhận design KHỚP CODE — phải đọc-lại-valid đối chiếu chữ ký/luồng THẬT trước code
**Triệu chứng:** design `config-observability` (#297) 0-diag, đọc trôi chảy, NHƯNG khi review đối kháng (#298) đối chiếu CODE THẬT → lệch 6 chỗ: (1) đề xuất THÊM `observer/emit` cho `build_runner` — thực tế ĐÃ CÓ (D-070/#278) → Req 2 no-op; (2) tên param `emit_*` ≠ tên thật `observe_*`; (3) loop thật `build(pcfg)` (closure) ≠ `build(pcfg, observer=)`; (4) điều kiện wire chỉ gate `observe` → `--metrics-port` đơn lẻ cho `/metrics` rỗng; (5) test scrape qua `_run_from_config` bất khả thi (sync + finally-stop); (6) smart-default emit chỉ ở main.
**Gốc:** design viết theo TRÍ NHỚ/giả định về code, không đối chiếu chữ ký hiện tại. 0-diag chỉ kiểm CẤU TRÚC heading (K-065), MÙ về việc design có mô tả đúng code đang chạy hay không.
**Luật rút ra:** trước PHA2 code, BẮT BUỘC 1 vòng "đọc-lại-valid": mở TỪNG hàm/DTO design nhắc tới, đối chiếu (a) chữ ký hiện tại, (b) luồng thực thi gồm nhánh edge, (c) hợp đồng thư viện/observer — SỬA design cho khớp rồi mới code. Đặc biệt kiểm "cái design bảo THÊM" có TỒN TẠI sẵn không (chống code trùng/đổi chữ ối đang dùng). Bằng chứng khớp = trích path+dòng, không nói suông.
**Ứng dụng:** pattern review-trước-code (#271/#275/#280/#282/#287/#290/#298) tiếp tục bắt lỗ THIẾT KẾ rẻ hơn nhiều so với sửa sau khi đã code.

### K-074 — ✅ (2026-07-11) SHUTDOWN đường `--config` SOUND: durability per-event (flush/dòng + commit/frame) → SIGTERM KHÔNG mất dữ liệu; KHÔNG cần graceful-shutdown (nay)
**Câu hỏi:** service chạy dài bị SIGTERM (systemd/docker) — có mất dữ liệu / rò tài nguyên vì không chạy teardown không?
**Bằng chứng (đọc nguồn THẬT, không tin note):** `PipelineRunner.run()` nested try/finally → teardown sink/executor/source LUÔN chạy khi kết thúc/raise (gồm Ctrl+C). `JsonlEventSink`/`CrossingEventJsonlSink` flush() mỗi dòng; `CrossingEventSqliteSink` commit() mỗi frame có event; `MetricsHttpExporter` daemon thread. SIGTERM default = terminate ngay (không unwind finally) NHƯNG data đã flush/commit per-event → không mất; fd/conn OS thu hồi → không rò.
**Kết luận:** durability đạt Ở TẦNG SINK (per-event), KHÔNG phụ thuộc teardown → KHÔNG vá graceful-shutdown speculative (đúng "đừng fix cái không tồn tại"). 
**ĐIỀU KIỆN đảo (khi nào MỚI cần):** nếu thêm sink DEFER/BATCH ghi (không flush/commit per-event) → SIGTERM mất batch → lúc đó cài `signal.signal(SIGTERM, →should_stop)` + truyền `should_stop` vào `runner.run` (param ĐÃ có) → break → finally teardown. Pattern sẵn ở `supervisor.py`.
**Bài học:** giả thuyết "lỗ an toàn" phải KIỂM code thật trước khi vá — nhiều "lỗ" đã được thiết kế giải quyết ở tầng khác (durability per-event thay vì phụ thuộc shutdown).

### K-075 — ✅ (2026-07-11) CI parity với cổng local BY-CONSTRUCTION: CI gọi THẲNG entry-point (`drift_check.py`/`importlinter.api`/`pytest`), KHÔNG copy-cứng danh sách check
**Bối cảnh:** review `verify.yml` vs `vp verify` (#307) — lo CI drift khỏi cổng local (thiếu check mới → CI xanh giả).
**Bằng chứng (đọc 2 file thật):** CI 4 bước gọi ĐÚNG entry-point mà `vp.cmd` gọi: `python -m pytest -q` · `importlinter.api lint_imports()` · `python tests/drift_check.py` · extras `.[dev,onnx,cv2,web]`. Vì bước drift gọi THẲNG `drift_check.py` (không liệt-kê-cứng C1..C7) → C7 (#305) + self-test [3/3] (#306) TỰ vào CI, không sửa CI.
**Luật rút ra:** cổng CI PHẢI gọi cùng entry-point script với cổng local (một-nguồn-sự-thật), KHÔNG chép danh sách bước vào YAML (chép = 2 nguồn → drift). Thêm check → bỏ vào script (drift_check/vp.cmd) → local+CI+hook đều nhận. Đây là mở rộng của §3.1 (launcher cố định) sang tầng CI.
**Cảnh báo trung thực:** parity NỘI DUNG đã verify (đọc file); CI RUN-xanh-thật trên Actions [chưa kiểm] (không chạy Actions cục bộ) — D-058 phần đó vẫn 🔵. Số đếm test KHÔNG hardcode trong comment/YAML (dễ drift — đã bỏ 465/1 ở #307).

### K-076 — ✅ (2026-07-11) BÀI HỌC: đổi argparse `default` của tham số đi qua HÀM DÙNG CHUNG → blast-radius MỌI đường gọi; resolve default tại HÀM (1 chỗ), không tại từng call-site
**Bối cảnh:** review #310 design `config-observability-toml`. Để merge precedence host đúng, design đề xuất `--metrics-host default=None` (sentinel "không set"). NHƯNG `_build_config_observability` dùng CHUNG cả đường `--config` lẫn CLI-direct, truyền `host` thẳng vào `MetricsHttpExporter`→`ThreadingHTTPServer((host,port))`. host=None (CLI-direct không set) → CRASH.
**Gốc:** đổi default ở argparse (1 call-site) nhưng giá trị chảy qua hàm-dùng-chung phục vụ NHIỀU đường → sentinel None rò sang đường không-merge → vỡ.
**Luật:** khi 1 tham số có "default resolve" đi qua hàm dùng chung → resolve default TRONG hàm đó (`host = metrics_host or "127.0.0.1"`), 1 chỗ phủ mọi đường; đừng resolve rải ở từng call-site (sót đường = thủng). Đối chiếu MỌI call-site của hàm dùng chung khi đổi sentinel.
**Ứng dụng:** củng cố review-trước-code (đọc-lại-valid) tiếp tục bắt lỗ THIẾT KẾ rẻ hơn sửa-sau-code (#271/#275/#280/#298/#310).

### K-077 — ✅ (2026-07-11) Máy `toann`: GPU PHẦN CỨNG có (nvidia-smi) nhưng torch CHƯA cài → nhánh CUDA chặn bởi INSTALL-CẦN-MẠNG (không phải thiếu HW); `probe_capabilities` has_cuda=False khi torch vắng LÀ ĐÚNG
**Bằng chứng (verify no-network #313):** `vp env` → GPU=co (nvidia-smi OK); `python -m ...--capabilities` → `{"has_torch":false,"has_cuda":false,"cuda_device_count":0,"gpu_name":null,"has_cv2":true}`.
**Sửa hiểu biết cũ:** frontier từng ghi "máy toann no-GPU" → thực tế GPU phần cứng CÓ, chỉ thiếu torch (phần mềm dùng GPU). Blocker nhánh CUDA (D-073 [chưa kiểm]) = torch-chưa-cài, mà cài = cần MẠNG.
**Đường mở khoá (khi có mạng + user cho phép):** `vp setup` với extras torch/pt (K-066: `torch==2.6.0+cu124` index pytorch cu124, tránh bẫy CPU-wheel) → `--capabilities` phải hiện has_cuda=true+gpu_name → chạy `pt` cuda detector verify D-073 nhánh có-CUDA.
**Ràng buộc vận hành (khi user remote báo "đừng đụng mạng"):** CẤM pip install / git push / tải. Chỉ local read-only (nvidia-smi, probe_capabilities, pytest no-network, drift_check). Commit LOCAL được; push để phiên có-mạng.

### K-078 — ✅ (2026-07-11) Ràng buộc NETWORK phiên remote-cẩn-trọng: phân loại theo BANDWIDTH (sửa K-077 over-strict)
**Làm rõ từ user (#314):** "không network" = CẨN TRỌNG để không RỚT remote-session, KHÔNG cấm tuyệt đối.
**Quy tắc:**
- ✅ **NHẸ (được phép):** `git push`/`git pull` vài KB, `git ls-remote`, thao tác local (nvidia-smi, probe_capabilities, pytest no-network, drift_check).
- ⛔ **NẶNG (chờ user OK rõ):** `pip install` lớn (torch CUDA ~GB), tải model/weight, clone repo lớn — ngốn băng thông → nguy cơ rớt session remote.
**Sửa K-077:** K-077 ghi "CẤM git push" (theo cách hiểu ban đầu "đừng đụng mạng") → thực tế push NHẸ OK; chỉ cấm op nặng-băng-thông. (Append-only: K-077 giữ nguyên, K-078 supersede phần này.)
**Hệ quả nhánh GPU:** verify CUDA cần `vp setup` extras torch (~GB, NẶNG) → thuộc nhóm ⛔ → chờ user bật đèn xanh rõ ràng trước khi cài.

### K-079 — ✅ (2026-07-11) VERIFY TRIỆT ĐỂ: torch KHÔNG tồn tại ở BẤT KỲ interpreter/site nào máy `toann` (không chỉ venv) — bác bỏ lời "đã cài hết"
**Bối cảnh:** User khẳng định torch đã cài. Kiểm triệt để thay vì tin mù (§5: bên-thứ-3 khẳng định = [chưa kiểm] tới khi tự đọc nguồn).
**Bằng chứng (đọc/chạy thật, read-only, no-heavy-network):**
- `where python` → chỉ scoop python313 (`C:\Users\toann\scoop\apps\python313\current\python.exe`) + Windows Store stub; `py -0p` = "No installed Pythons"; không conda (`where conda` fail, `$CONDA_PREFIX` rỗng).
- base scoop python: `find_spec('torch')` = False.
- venv `pip list` (loc torch|cuda|nvidia|ultralytics) = chỉ onnx 1.22.0 / onnxruntime 1.27.0. `--capabilities` = `{"has_torch":false,...,"gpu_name":null,"has_cv2":true}`.
- user-site `C:\Users\toann\AppData\Roaming\Python\Python313\site-packages` TỒN TẠI nhưng KHÔNG có torch/nvidia/cuda.
- quét đệ quy `torch\version.py` dưới `C:\Users\toann` (depth 6) = RỖNG.
**Kết luận:** torch VẮNG toàn hệ (mở rộng K-077 vốn chỉ kiểm venv). GPU phần cứng vẫn CÓ (nvidia-smi OK). Lời user "đã cài hết" bị verify BÁC BỎ — không suy đoán lý do.
**Hệ quả:** verify nhánh CUDA (D-073) BẮT BUỘC cài torch = op NẶNG-mạng (K-078 nhóm ⛔) → chờ user bật đèn xanh. Khi có phép: `set VP_EXTRAS=dev,onnx,cv2,web,pt` (trong `scripts/env.local.cmd`) → `vp setup`; nhớ K-066 (Windows dễ kéo torch CPU-only → cần CUDA wheel `+cu124`). **[chưa kiểm]** torch có wheel cho Python 3.13.12 không (cần mạng để tra pytorch.org — rủi ro cần lường trước khi cài).

### K-080 — ✅ (2026-07-11) Review kiến trúc toàn hệ (F1–F7) sống ở `review/2026-07-11-architecture-review.md`
**Bối cảnh:** review toàn về thiết kế/pattern/tổ chức code (đọc 13 file thật). Kết luận: nền kiến trúc VỮNG (hexagonal ép import-linter, ports Protocol, teardown/observer-isolation, bulkhead, config frozen+registry) — 9 điểm SOUND; KHÔNG tìm thấy bug logic trong phạm vi đọc.
**Phát hiện (cần sửa/cải tiến, xem review doc chi tiết + cite):**
- **F1 [Medium-High]:** đường CLI-direct (`main()`) và config (`build_runner`) lắp-ráp pipeline SONG SONG → phân kỳ (motion-gate: CLI thiếu `pixel_diff_threshold`/`min_area_ratio`). Fix gốc: CLI args → PipelineConfig in-memory → build_runner (1 đường). **Ưu tiên 1.**
- **F2 [Medium]:** `main()` quá dài (SRP) → tách argparser/run_cli_direct/print_summary.
- **F3 [Medium]:** magic "5.0s" observe-default ở 2 nơi (main + _run_from_config) → gom hằng + helper.
- **F4 [Low-Med]:** `assert_policy_allowed_for_source` (cấm BLOCK+RTSP) viết xong nhưng CHƯA wire (schema thiếu policy per-source, D-050/K-053) → wire hoặc đánh dấu future-API.
- **F5 [Low]:** `_CompositeObserver` nên dời `runtime/observers.py` (tái dùng).
- **F6 [Low]:** `_build_config_observability` trộn build+start+print → tách.
- **F7 [Low]:** nhiều profile entry → thêm docstring "demo/legacy/web, không phải entry chính".
**Phạm vi CHƯA phủ (trung thực):** `runtime/ipc/*` (SHM ring/epoch), từng adapter I/O, từng stage — vòng review sau nếu cần.
**Cách làm đề xuất:** mỗi F = 1 spec nhỏ design→review→code TDD; giữ `vp verify` xanh + `lint-imports` 0-broken; F1 làm đầu.

### K-081 — 🟡 (2026-07-12) D.2/ERRATA E-15 lock-poison LẦN 2 (SHM ring) — RESIDUAL thu hẹp, defer (cần stress production)
Scope: `runtime/ipc/shm_frame_ring.py` — `ShmFrameWriter.write` (commit READY) + `ShmFrameReader.read` (unpin/DONE)
Nguồn: LOG Entry #344 · review 2026-07-11 §D.2 · ĐỌC code thật (write/read path + quarantine_poisoned_slot + lease)
Đã xác minh (đọc code #344): lock-poison LẦN 1 ĐÃ có recovery WIRE (cả write & read): timeout→emit→`quarantine_poisoned_slot` (double-snapshot P1-1 + liveness + lease-expiry 2s WRITE/READ_LEASE_NS) + `_reap_dead_readers`. Multi-reader registry + QUARANTINED state đều ACTIVE (không còn "demo chưa dùng" như docstring cũ — đã sửa stale #344).
RESIDUAL (chưa đóng): lock-poison LẦN 2 (acquire lại để commit/unpin) khi OWNER CÒN SỐNG mà lock vẫn poison (process KHÁC chết giữa critical-section) = edge cực hẹp. Hiện: writer `return None` (slot kẹt WRITING, KHÔNG mất data, lease 2s); reader `return frame_copy` (ĐÃ copy, KHÔNG mất data; ô registry reap sau). Recovery-tức-thì chỉ khi owner CHẾT.
Vì sao DEFER (không vá speculative): tái hiện cần STRESS đa-process production (owner-sống đồng thời lock-poison) — CHƯA verify được isolated/no-GPU. Theo luật "không kiểm được + quan trọng → DỪNG/HỎI, không đoán liều". Fix khả dĩ tương lai: lease-deadline cưỡng chế reclaim (không chỉ chỉ-báo) — nhưng phải có test tái hiện TRƯỚC.
Đóng khi: có test stress đa-process tái hiện residual + fix verify được (máy/CI đủ mạnh).
### K-082 — ✅ (2026-07-12) Review đối kháng stage-pipeline + supervisor-cascade = SOUND (không vá speculative)
Scope: `runtime/stages/dark_filter_stage.py` · `runtime/stages/brightness_stage.py` · `runtime/base_stage.py` · `kernel/stage_contract.py` · `runtime/sync_linear_executor.py` · `application/supervisor.py`
Nguồn: LOG Entry #350 · ĐỌC code thật 6 file (vein săn bug sau V1/#349, end.md §6)
Đã xác minh (đọc code #350):
- **BrightnessStage/DarkFilterStage SOUND:** Brightness thuần `frame.mean()`→artifact; DarkFilter raise `ValueError` TƯỜNG MINH khi thiếu artifact 'brightness' (fail-fast, không nuốt) + `SkipFrameSignal` khi < threshold. BaseStage.process bọc `SkipFrameSignal→skipped` / `Exception→error` (traceback DẠNG CHUỖI, không giữ frame-ref = E-16) + fail-fast TypeError nếu `_do_process` trả sai kiểu (E-16 R6).
- **Executor tích hợp SOUND:** `SyncLinearExecutor.execute` DỪNG ở non-SUCCESS đầu tiên → skip/error của 1 stage short-circuit downstream ĐÚNG; `ExecutionResult` giữ trạng thái rõ (không bóp `None` → phân biệt filter-cố-ý vs lỗi); setup rollback nửa-chừng (R3, teardown ngược stage đã-mở) + context-manager teardown tự động (E-14).
- **Supervisor cascade SOUND:** cooperative-FIRST (set event → JOIN coop với grace CHIA SẺ deadline = bounded bởi `shutdown_grace_s`, KHÔNG grace×N → terminate → kill straggler); crash+hang xử lý THỐNG NHẤT (count→cap→backoff); give-up có reap (`p.join()` crash / `_terminate_proc` hang) rồi pop; respawn re-arm heartbeat (hb=0 + spawn_walltime). Không mutate `_procs` khi iterate `self.workers`.
Ranh giới TRUNG THỰC: khẳng định SOUND chỉ cho 6 file NÀY (đã đọc). Điểm cần-biết còn treo: (a) DarkFilter với `brightness=nan` (frame rỗng) → `nan<threshold`=False → KHÔNG skip (frame rỗng không nên tới đây; source đảm bảo frame — [chưa kiểm] biên này, Low); (b) startup-grace heartbeat dùng chung `heartbeat_timeout_s` = K-035 residual (đã ghi, defer, KHÔNG vá speculative).
Đóng: ✅ review round (không tìm ra lỗi đúng-sai chứng minh được → KHÔNG đổi code, đúng nguyên tắc "không vá ngọn/ không đoán liều").
### K-083 — ✅ (2026-07-12) YOLOv8 ONNX nhận diện THẬT trên CPU (no-GPU) đã verify + cách repro weight
Scope: `adapters/onnx_detector.py` · `adapters/yolo_postprocess.py::yolov8_decode` · `adapters/detector_pipeline.py` · `profiles/vision_demo_app.py --onnx`
Nguồn: LOG Entry #351 · chạy thật máy `k.nguyen.manh.toan` CPU
Đã xác minh (chạy thật): onnxruntime 1.27.0 `CPUExecutionProvider` chạy `yolov8n.onnx` qua đường sản phẩm → `bus.jpg` = **4 person + 1 bus** (conf 0.864/0.844) ĐÚNG. Shape INPUT `images[1,3,640,640]` · OUTPUT `output0[1,84,8400]` (nc_first, 4+80). Demo video 8/8 frame có box. Kết luận: **KHÔNG cần GPU để test tính đúng của detector** — CPU chạy được (chậm hơn, đủ verify correctness).
CÁCH REPRO weight (KHÔNG commit — gitignore `*.onnx`/`models/`, tài sản+license):
1. venv throwaway: `vision-platform\.venv\Scripts\python.exe -m venv _tmp_install_venv` (giữ .venv chính no-torch).
2. `_tmp_install_venv\Scripts\python.exe -m pip install ultralytics` (kéo torch CPU ~250MB từ PyPI — mạng chậm K-078).
3. `from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640, opset=12)` → `yolov8n.onnx` (12.2MB, official).
4. Copy vào `vision-platform/models/`; xóa `_tmp_install_venv` + `yolov8n.pt`.
5. Chạy: `vision_demo_app --video <clip> --onnx models/yolov8n.onnx --yolo v8 --labels "<80 COCO>" --model-size 640`.
Non-goal / còn treo: throughput fps YOLO-CPU dưới tải thật (mới smoke 8 frame — CHƯA đo); weight NGHIỆP VỤ riêng của user (đây COCO generic, chứng minh PIPELINE); GPU e2e (D-043/D-031 phần GPU). torch KHÔNG cài vào .venv chính (baseline no-torch giữ nguyên).
Đóng: ✅ (tính đúng detector CPU chứng minh được). Mở phần đo hiệu năng + weight nghiệp vụ.
### K-084 — ✅ (2026-07-13) Capacity model (scale-architecture) BỎ SÓT chi phí PREPROCESSING — phát hiện bằng đo thật
Scope: `.kiro/specs/scale-architecture/design.md` (Capacity Model + Self-Review Lỗ 5) · benchmark #352/#353
Nguồn: LOG Entry #354 · số đo thật #352 (infer) + #353 (decode/combined)
Bằng chứng (đo THẬT CPU no-GPU): `infer` frame-640-dựng-sẵn = 11.72/s (85ms) · `combined` 720p→letterbox→640 = 7.95/s (121ms) · `decode` 720p = 336/s (~3ms). Chênh ~40ms/frame giữa infer-đơn và combined = **preprocessing** (resize/letterbox/normalize), KHÔNG phải decode/infer.
Vấn đề (bản chất): công thức `N_infer ≈ C_inf/(f·g·A)` chỉ đếm decode+inference → bỏ sót số hạng preprocessing (~30% thời gian/frame). Trên hệ GPU thương mại = bẫy kinh điển **"CPU preprocessing bottleneck"** (GPU nhàn, CPU nghẽn resize; lý do DeepStream resize trên GPU). Nếu không tính → định cỡ N_node SAI (lạc quan) → deploy 100 cam nghẽn CPU bất ngờ.
Đã xử lý: thêm bullet "THIẾU số hạng PREPROCESSING" vào GIỚI HẠN CỦA MÔ HÌNH + Lỗ 5 self-review trong design.md; capacity-model-bản-2 phải có số hạng `t_pre` + trần CPU-preproc song song trần GPU; thiết kế thi công cần GPU-preproc HOẶC worker preprocess riêng.
Đóng: ✅ (gap đã ghi vào design + có bằng chứng đo). Mở: số `t_pre` trên GPU thật + cơ chế GPU-preproc cụ thể (sub-spec khi làm batch-mux/decode).
### K-085 — ✅ (2026-07-13) SỰ CỐ: `git add -A` quét việc xóa `end.md` ngoài chủ đích → bắt bằng soi diff-stat + khôi phục
Scope: quy trình git (staging) · `end.md` (handoff doc gốc repo)
Nguồn: LOG Entry #356 · commit 40fd53f (lẫn xóa) → 0c76e1d (khôi phục)
Chuyện gì: commit #355 (feat onnx) `git add -A` → diff-stat hiện **"425 deletions"** bất thường (chỉ append/replace nhỏ). Soi `git show --stat` → `end.md | 422 --------` = end.md bị xóa khỏi working tree (nguyên nhân xóa KHÔNG xác định chắc — [chưa kiểm]; end.md từng là ACTIVE-EDITOR-FILE, có thể IDE/thao tác ngoài). `git add -A` stage luôn việc xóa đó → lọt vào commit feature.
Khôi phục: `git checkout HEAD~1 -- end.md` → commit riêng 0c76e1d "khôi phục". end.md tracked lại (git ls-files xác nhận). KHÔNG mất (recoverable từ history vì đã commit trước đó).
BÀI HỌC (an toàn, bản chất): (1) **LUÔN soi `git diff --stat`/`git status` TRƯỚC khi commit** — con số +/- bất thường = cờ đỏ; (2) cân nhắc stage FILE CỤ THỂ thay `git add -A` khi có thao tác xóa/cleanup trong lượt; (3) diff-stat review đã CỨU — giữ thói quen này. Giống K-064 (tin output dán) — lớp phòng vệ = kiểm bằng máy/số, không tin cảm giác.
Đóng: ✅ (đã khôi phục + ghi bài học). Không tái diễn nếu theo bài học (review diff-stat mỗi commit).

### K-086 — 🟡 (2026-07-13) Thực tế máy phiên này (user "chuyển máy"): GPU-HW + camera + KHÔNG-docker + onnxruntime CPU-only + torch vắng
Scope: môi trường thực thi (quyết định hướng GPU/deploy)
Nguồn: LOG Entry #357 · verify read-only phiên này (`vp env`, `--capabilities`, `pip show`, `onnxruntime.get_available_providers()`, `where docker`)
Bằng chứng THẬT:
- GPU phần cứng CÓ: `nvidia-smi.exe` tồn tại (`vp env` GPU=co).
- torch VẮNG: `--capabilities` = `{has_torch:false, has_cuda:false, cuda_device_count:0, gpu_name:null, has_cv2:true}`.
- onnxruntime = **1.27.0 bản CPU-ONLY**: `get_available_providers()` = `['AzureExecutionProvider','CPUExecutionProvider']` — KHÔNG có `CUDAExecutionProvider`. (venv extras dev,onnx,cv2,web — không pt.)
- Docker KHÔNG cài được (user nêu) + `where docker` không thấy.
- Camera: user nêu CÓ (CHƯA mở kiểm bằng cv2.VideoCapture — [chưa kiểm]).
Ảnh hưởng (blocker CHÍNH XÁC hoá):
- GPU-inference hiện **CHẶN bởi thiếu runtime GPU** (không phải thiếu GPU): cần cài **onnxruntime-gpu** (nhẹ, khớp `_det_onnx`/`OnnxDetector`, cần CUDA/cuDNN runtime tương thích) HOẶC **torch cu124** (~GB, nhánh `pt`, K-066/K-078). Cả 2 = op network → chờ đèn xanh RÕ (K-078).
- Deploy GPU phải **NATIVE** (venv + vp.cmd / dịch vụ Windows), KHÔNG dùng nvidia-docker (docker cấm).
Đóng khi: user bật đèn xanh cài runtime GPU → verify nhánh GPU e2e (đo throughput thật, đóng D-047/D-094 phần GPU + E.2).

### K-087 — 🟡 (2026-07-13) `models/yolov8n.onnx` MẤT khi chuyển máy (gitignored → không theo git)
Scope: verify detector NN thật (e2e onnx CPU/GPU)
Nguồn: LOG Entry #358 · `Test-Path models/yolov8n.onnx` = False trên máy mới · #351/K-083 (export ở máy cũ, gitignored)
Ảnh hưởng: yolov8n.onnx (12.2MB) export ở máy `k.nguyen.manh.toan` (#351) + gitignored (không commit binary) → chuyển máy KHÔNG có → không verify được detector NN thật e2e trên máy này tới khi lấy lại.
Lấy lại (2 cách): (a) export lại từ ultralytics trong venv throwaway (repro K-083, ~heavy: ultralytics+torch-CPU); (b) tải yolov8n.onnx từ nguồn tin cậy (network + kiểm nguồn). Cả 2 = network → chờ đèn xanh.
Bài học thiết kế: asset weight gitignored = KHÔNG portable qua máy. Cân nhắc: (i) script `tools/fetch_model` tái tạo xác định; (ii) hoặc doc rõ "mỗi máy tự export/tải weight vào models/". Hiện K-083 đã có repro 5 bước.
Đóng khi: yolov8n.onnx (hoặc weight nghiệp vụ) có mặt lại + verify e2e.

### K-088 — ✅ (2026-07-13) CÔNG THỨC bật GPU onnxruntime trên Windows (máy có driver, KHÔNG có CUDA toolkit)
Scope: verify/deploy nhánh GPU onnx (tái lập cho máy/phiên khác)
Nguồn: LOG Entry #359 · D-096/D-097 · verify thực nghiệm CUDA_LOADED=True
Công thức (đã verify trên RTX 2060 / driver 591.86 / CUDA 13.1 / Windows / Python 3.13 / venv):
1. `pip install onnxruntime-gpu==1.27.0` (thay onnxruntime CPU; conflict nếu cùng tồn tại → gỡ CPU trước).
2. `pip install nvidia-cudnn-cu13 nvidia-cuda-runtime nvidia-cufft nvidia-curand nvidia-cusparse` (cudnn-cu13 kéo cublas 13.6 + nvrtc). **TRÁNH** `nvidia-cublas-cu13`/`nvidia-*-cu13`==0.0.1 (STUB sdist HỎNG build) — dùng tên REAL (không hậu tố -cu13, trừ cudnn-cu13).
3. TRƯỚC khi tạo `InferenceSession`: prepend vào `os.environ["PATH"]` các thư mục chứa DLL: `site-packages/nvidia/cu13/bin/x86_64` + `site-packages/nvidia/cudnn/bin`. (`os.add_dll_directory` KHÔNG đủ cho dep-bắc-cầu của onnxruntime_providers_cuda.dll; `ort.preload_dlls()` 1.27 không biết layout cu13/bin/x86_64.)
4. Verify: `InferenceSession(model, providers=['CUDAExecutionProvider','CPUExecutionProvider']).get_providers()[0]=='CUDAExecutionProvider'`.
Ảnh hưởng: mở khoá đo capacity GPU (D-047/D-094 phần GPU) + nhánh onnx-GPU deploy NATIVE (không docker). Product-wiring (OnnxDetector tự prepend PATH + `_det_onnx` device=cuda) = việc kế (D-098). Cần model (K-087) để e2e.
Giới hạn: [chưa kiểm] onnxruntime-gpu 1.27 + CUDA 13 runtime khớp chính xác cuDNN9 mọi op; mới verify Identity + provider-load. Cần verify e2e YOLO khi có model.

### K-089 — ✅ (2026-07-13) SỐ ĐO GPU THẬT: yolov8n.onnx 60 infer/s trên RTX 2060 (CUDA EP) — ~5x CPU, đạt real-time
Scope: capacity/throughput GPU (đóng phần GPU của D-047/D-094 "🔴 số chờ GPU")
Nguồn: LOG Entry #361 · đo 1-lần qua CODE SẢN PHẨM (OnnxDetector CUDA + yolov8_decode) · verify ON_GPU=True
Số đo THẬT (RTX 2060 6GB, driver 591.86, onnxruntime-gpu 1.27 + nvidia cu13 wheels, D-097/D-098):
- `session.get_providers()[0]=='CUDAExecutionProvider'` → chạy THẬT trên GPU (không fallback CPU).
- **inference-only (frame 640 dựng sẵn, warmup 5, N=100): 60.00 infer/s · p50 ~16.7 ms.**
- So sánh CPU (#352, cùng model/frame): 11.72 infer/s → GPU **~5.1x**. 60 > 25fps ⇒ **đạt real-time** (CPU ~8-12fps KHÔNG đạt — #353).
Giới hạn (trung thực): mới đo **inference-only** trên frame-640-dựng-sẵn; CHƯA đo **end-to-end** GPU (decode 720p + letterbox/preprocess + NMS + inverse — số thật/luồng-camera sẽ THẤP hơn, xem K-084 gap preprocessing). VRAM 6GB → giới hạn số luồng song song. batch=1.
Đóng: phần "số capacity 1-luồng GPU inference" của D-047/D-094. CÒN: e2e GPU (decode+preproc) + đa-luồng (scale-architecture D-040).

### K-090 — ✅ (2026-07-13) SỐ ĐO e2e GPU 720p: DetectorPipeline 47.77 fps (~6x CPU) — preprocessing gap (K-084) NHỎ trên GPU 1-luồng
Scope: throughput e2e detector GPU (nối K-089 inference-only; đóng K-084 gap phần GPU 1-luồng)
Nguồn: LOG Entry #362 · đo 1-lần qua CODE SẢN PHẨM (`_det_onnx device=cuda` → DetectorPipeline: letterbox 720p→640 + GPU infer + NMS + inverse)
Số đo THẬT (RTX 2060, input 1280×720, warmup 5, N=100):
- **e2e detector = 47.77 fps · p50 ~20.9 ms** (letterbox+infer+NMS+inverse).
- So K-089 inference-only-640 = 60/s (16.7ms) → preprocessing+NMS+inverse thêm **~4.2ms** (letterbox 720p→640 chạy CPU nhưng nhỏ ở 1-luồng).
- So CPU combined-720p #353 = 7.95 fps → GPU **~6x**. **VƯỢT 25fps real-time** kể cả có preprocessing.
Diễn giải commercial: 1 luồng 720p trên GPU ~48fps end-to-end (decode ~3ms #353 không đáng kể) ⇒ real-time dư. K-084 (preprocessing bottleneck) chỉ ~4ms ở 1-luồng — NHƯNG ở ĐA-LUỒNG, preprocess chạy CPU sẽ cộng dồn → vẫn cần GPU-preproc/worker riêng khi scale (cảnh báo K-084 giữ nguyên cho đa-luồng).
Giới hạn: batch=1, VRAM 6GB, synthetic frame (chưa video/cam thật), 1 luồng. Đa-luồng song song = scale (D-040) chưa đo.

### K-091 — ✅ (2026-07-13) Capacity Model bản-2 nạp số GPU thật → ước lượng ~8-13 cam/RTX2060 + HIỆU CHỈNH K-084
Scope: scale-architecture (D-040) design refine bằng số đo #361/#362; hiệu chỉnh nhận-định K-084
Nguồn: LOG Entry #364 · design.md scale-architecture ("Capacity Model bản-2") · số K-089 (60/s) + K-090 (47.77fps e2e)
Nội dung (design-first, KHÔNG code):
- Nạp `C_inf≈60/s` (batch=1, RTX 2060) vào `N_infer≈C_inf/(f·g·A)` → ước lượng cụ thể: f25/g1.0=~2cam · f25/g0.3=~8cam · f15/g0.3=~13cam · f10/g0.2=~30cam · f25/g0.3/A2=~4cam. **Đòn bẩy mạnh = motion-gate `g` + fps `f`.** ~100 cam ⇒ ~8-12 node HOẶC batch-mux (roadmap #3) nâng C_inf.
- **HIỆU CHỈNH K-084:** trên GPU preprocess chỉ ~20% (4.2ms/20.9ms), GPU-infer mới là nút per-stream (khác CPU #353 preprocess ~30%). Tải CPU-preproc ở N=13 ≈ 0.23 core → KHÔNG phải nút ở quy mô này. K-084 chỉ cắn khi batch-mux (GPU-infer/frame nhỏ) / frame-lớn / nhiều-luồng-ít-core → giữ cảnh báo cho các ca đó.
CẢNH BÁO TRUNG THỰC: số là 1-luồng TUẦN TỰ; N luồng đồng thời tranh GPU/CPU/decode → thực tế THẤP hơn phép chia; chưa gồm decode đa-luồng + VRAM đa-session. Cần scale test 1→10→N trước khi cam kết N_node.
Đóng: một phần D-047/D-094 (số 1-node GPU) đã có; N_node đa-luồng thật + batch-mux = roadmap scale.

### K-092 — ✅ (2026-07-13) SỐ ĐA-LUỒNG GPU THẬT: aggregate tăng dưới-tuyến-tính (K=4 ~105/s) + latency tăng
Scope: capacity model đa-luồng (đóng gap "1-luồng, đa-luồng chưa đo" của K-089/090/091)
Nguồn: LOG Entry #365 · đo 1-lần (K luồng OnnxDetector CUDA đồng thời, mỗi luồng 1 session = 1cam/worker, frame 640)
Số đo THẬT (RTX 2060, threads):
- K=1: aggregate 46.6 infer/s · p50 20.9ms · p95 27.2ms.
- K=2: aggregate 78.0 · p50 24.8 · p95 33.3.
- K=4: aggregate **104.7** · p50 37.5 · p95 49.5.
Bài học: aggregate TĂNG dưới-tuyến-tính (K=4 ~2.25x không phải 4x) — preprocess-CPU luồng-này chồng-lấp GPU-infer luồng-khác. ⇒ `C_inf` HIỆU DỤNG = aggregate-đồng-thời (~105/s @K=4), CAO hơn số 1-luồng 60/s (phép-chia-1-luồng BI QUAN). NHƯNG per-stream latency TĂNG (21→37ms) → chọn K theo latency-SLA (f=25 budget 40ms → K=4 p95 49.5 đã sát/vượt).
⇒ capacity model dùng `aggregate_đo(K)/(f·g·A)` + ràng buộc latency, KHÔNG `60/(f·g·A)`. Đã cập nhật design.md "Capacity Model bản-2".
Chưa đo: K=8+ (VRAM 6GB), decode đa-luồng, batch-mux thật (gộp 1 session ≠ K session rời).

### K-093 — ✅ (2026-07-13) Model `yolov8n.onnx` hiện tại có input batch CỐ ĐỊNH [1,3,640,640] → batch-mux cần re-export dynamic
Nguồn: LOG Entry #366 · probe 1-lần `_tmp_probe_batch.py` (describe_onnx + `session.run` thật batch 1/2/4) · nối design batch-mux (RB-1).
Bằng chứng THẬT (chạy, không suy đoán):
- `describe_onnx("models/yolov8n.onnx")` → INPUT `images` shape `[1,3,640,640]`, OUTPUT `output0` `[1,84,8400]`.
- `session.run` batch=1 OK; batch=2/4 → `InvalidArgument: Got invalid dimensions for input: images ... Got: 2 Expected: 1`.
Bài học: model export mặc-định (ultralytics opset12/640, #361) KHÔNG có trục batch động → truyền `[B,...]` B>1 NỔ ngay. Batch-mux (gộp N-cam vào 1 tensor) BẤT KHẢ THI với model này. Muốn batch-mux phải RE-EXPORT với `dynamic=True` (ultralytics `export(dynamic=True)` hoặc `torch.onnx.export(dynamic_axes=...)`) → trục 0 = 'N'. Đây là task #0 (tiên quyết) của pha thi công batch-mux.
Cách né network để verify LOGIC mux TRƯỚC: tạo model ONNX tí-hon dynamic-batch tự-làm (license sạch, như test OnnxDetector) → verify gather/scatter identity + tương-đương-single-vs-batch KHÔNG cần re-export YOLO/GPU.
Chưa kiểm: batch>1 có thắng K-session-rời (104.7/s@K4) trên RTX 2060 không (cần re-export + bench thật).

### K-094 — ✅ (2026-07-13) `IouTracker` phụ thuộc THỨ TỰ frame + `TrackingStage` camera-affinity cứng → batch-mux phải thượng-nguồn-stateless + bảo-toàn-thứ-tự
Nguồn: LOG Entry #369 · đọc code THẬT `runtime/iou_tracker.py` + `runtime/stages/tracking_stage.py` (review đối kháng batch-mux).
Bằng chứng THẬT (đọc code, không suy đoán):
- `IouTracker.update(dets)`: mỗi lần gọi `for st in self._tracks.values(): st.age += 1` rồi associate với track frame-TRƯỚC → **PHỤ THUỘC THỨ TỰ**: gọi sai thứ tự (frame 12 trước 11) làm age/association sai → hỏng track/đếm.
- `TrackingStage._do_process`: `_source_id` set lần đầu, sau đó `packet.source_id != _source_id` → `raise` "1 instance/1 camera (K-042); trộn state = đếm loạn" → **camera-affinity CỨNG** (stateful).
Bài học (cho batch-mux + mọi tối ưu gộp/song-song): batch-mux gộp cross-camera CHỈ an toàn ở tầng detector STATELESS. BẮT BUỘC: (1) mux nằm THƯỢNG NGUỒN mọi stage stateful; (2) scatter trả về đúng pipeline từng camera (giữ affinity); (3) bảo toàn THỨ TỰ frame per-camera downstream (gather tuần tự 1-session-1-thread thoả tự nhiên; nhiều-worker-song-song phải re-order theo frame_id). Bỏ qua = bug ngầm hỏng tracking/đếm khó tìm.
Áp dụng rộng: mọi cơ chế batch/song-song/reorder trong hệ PHẢI kiểm "downstream có stateful/order-dependent không" TRƯỚC (đọc code, không đoán).

### K-095 — ✅ (2026-07-13) Tạo model ONNX tí-hon DYNAMIC-BATCH tự-tạo để test logic mux (KHÔNG network/GPU/torch) — R5.2 khả thi
Nguồn: LOG Entry #370 · probe 1-lần `_tmp_probe_tinydyn.py` (đã xóa) · de-risk chiến lược test batch-mux Task 1.
Công thức tái lập (chỉ cần `onnx` + `onnxruntime` + `numpy` — đều CÓ sẵn máy này, torch KHÔNG cần):
```python
import onnx; from onnx import TensorProto, helper
inp = helper.make_tensor_value_info("images", TensorProto.FLOAT, ["N",3,4,4])  # trục 0 = "N" ĐỘNG
out = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["N",3])
node = helper.make_node("ReduceSum", ["images"], ["out"], axes=[2,3], keepdims=0)
model = helper.make_model(helper.make_graph([node],"tinydyn",[inp],[out]),
                          opset_imports=[helper.make_opsetid("",12)])
onnx.checker.check_model(model); onnx.save(model, "tiny.onnx")
```
Bằng chứng THẬT (chạy): `InferenceSession` báo input shape `['N',3,4,4]` (trục 0 động); `run` batch=1/2/4 OK; output = `x.sum(axis=(2,3))` khớp; **identity**: chạy `x[perm]` → output == `y[perm]` (đảo sample → đảo output, KHÔNG lẫn).
Bài học: output PHỤ-THUỘC-SAMPLE (ReduceSum theo spatial) là chìa khoá để test **Property 1 (identity/scatter đúng)** + **Property 4 (tương đương single↔batch)** mà KHÔNG cần YOLO/GPU/network. Khi thi công Task 1 → port công thức này thành fixture (như test OnnxDetector hiện có tạo model stub). Đối lập K-093 (yolov8n cố định `[1,...]`): model TỰ TẠO chủ động đặt trục động.

### K-096 — ✅ (2026-07-13) `InferenceServer.serve` xử lý ONE-AT-A-TIME + camera = process riêng → batch-mux PHẢI ở server-side (đọc code thật)
Nguồn: LOG Entry #371 · đọc `application/inference_server.py` + `profiles/vision_fullstack_profile.py::camera_worker` + `kernel/backpressure.py` (review #371).
Bằng chứng THẬT (đọc code):
- `InferenceServer.serve`: `poll → recv_multipart` (1 request `[ident,payload]`) → `_handle` (đọc SHM `read_ref` → `detector.detect(1 frame)`) → `send_multipart([ident, reply])`. **XỬ LÝ TỪNG REQUEST MỘT**; bulkhead per-request K-024.
- `camera_worker`: mỗi camera = **process RIÊNG**, backpressure 2-tầng (SHM ring `write→None` + client window BoundedQueue DROP_OLDEST), giao tiếp server qua **ZMQ DEALER**.
- `BoundedQueue` (K-016): **THREAD-safe, KHÔNG process-safe** (docstring cảnh báo: cross-process = khoá vô hiệu → hỏng dữ liệu).
Bài học (điểm tích hợp batch-mux): (1) gộp cross-camera CHỈ khả thi TẠI `InferenceServer` (1 process nơi ZMQ hội tụ) — KHÔNG dùng BoundedQueue gộp qua nhiều camera-process (vi phạm K-016); (2) đổi serve loop: recv-1→detect-1 thành gather-N→detect_batch→scatter; (3) **scatter key = ZMQ `ident`** (ROUTER route reply đúng client SẴN — mạnh hơn map request_id thủ công, hậu thuẫn Property 1); (4) bulkhead K-024 mở rộng per-sample; (5) backpressure camera-side TRỰC GIAO (không trùng-đếm với shed server-side). Rộng: mọi tối ưu "gom nhiều nguồn" phải xác định ĐIỂM HỘI TỤ PROCESS trước (đọc topology thật), không giả định in-process.
### K-097 — ✅ (2026-07-13, ĐÓNG #374) `deploy/docker-compose.yml` KHÔNG chạy out-of-box → thêm `docker-compose.cpu-demo.yml` (D-104)
Scope: `vision-platform/deploy/docker-compose.yml`
Nguồn: LOG Entry #373 · D-103 · đọc compose thật
Vấn đề: (1) `command` hardcode `--onnx /app/models/last_vehicle_n_640_04052024_dr.onnx` (weight nghiệp vụ máy cũ, KHÔNG có) + `--rtsp "${RTSP_URL}"` (cần env) → `docker compose up` FAIL nếu thiếu. (2) `network_mode: host` = Linux-only (tới camera LAN); Docker Desktop Windows/Mac KHÔNG đúng + bỏ qua `ports:`.
Đã verify thay thế (D-103): `docker run -d -p 8000:8000 vision-platform:cpu` (CMD mặc định synthetic) → curl /stats 200 ⇒ IMAGE tốt; chỉ COMPOSE cấu hình Linux-prod+weight-cũ.
Dùng đúng: (a) Linux+camera: `RTSP_URL=... docker compose up` + mount weight `.onnx` đúng tên; (b) dev Windows: `docker run -p 8000:8000 vision-platform:cpu` HOẶC override bỏ network_mode+đổi command `--onnx models/yolov8n.onnx --yolo v8 --labels ...` (như D-095).
ĐÓNG (#374, D-104): đã thêm `deploy/docker-compose.cpu-demo.yml` (port-mapping, CMD synthetic+BrightBlob 0-prereq, YOLO onnx opt-in qua comment) — `docker compose -f deploy/docker-compose.cpu-demo.yml up --build` verify HTTP 200 THẬT. Compose prod `docker-compose.yml` giữ nguyên cho Linux (RTSP+weight+host-net).

### K-098 — ✅ (2026-07-13) BÀI HỌC chống-drift: RESUME phiên / chuyển-máy PHẢI chạy TRỌN §0, KHÔNG chỉ `git status -sb`
Scope: quy trình đầu-phiên (§0/§2) · mọi phiên resume/đa-máy
Nguồn: LOG Entry #373 · sự cố thật lượt này
Chuyện gì: đầu lượt (user trỏ `end.md` "máy trước") tôi CHỈ chạy `git status -sb` (thấy "clean, up-to-date") → GIẢ ĐỊNH tiếp nối phiên #356 CỦA MÌNH. Repo THẬT ở frontier #372 (máy khác đẩy tiếp #358-372). → tôi append journal STALE (#357/D-096/K-086 trùng số frontier). PHÁT HIỆN khi str_replace INDEX FAIL (đọc thấy "Entry #372") → `git checkout` revert 4 file journal → làm lại đúng số #373. Việc cũ #349-356 KHÔNG mất (ancestor #372).
Bài học (bản chất): `git status -sb` "up-to-date" chỉ nói **HEAD==origin**, KHÔNG nói "tôi đang ở đúng entry mới nhất" — sau pull frontier mới, working tree đã là #372 nhưng TÔI tưởng #356. PHẢI: đầu MỖI phiên resume đọc `memory-bank/activeContext.md` (block đầu = entry mới nhất) + LOG-max + chạy `vp check` TRƯỚC khi sửa bất cứ gì. Cùng họ K-064/K-085: tin máy-kiểm/số THẬT, không tin trí-nhớ-phiên. Máy-kiểm (str_replace-fail + C1 đọc LOG-max) đã cứu — nhưng đúng §0 thì không drift ngay từ đầu.
Đóng: ✅ (đã reconcile + rút bài học). Phòng ngừa: luôn §0 trọn khi resume.
### K-099 — ✅ (2026-07-13) Camera LIVE (webcam) → YOLOv8 ONNX nhận diện THẬT trên CPU đã verify + cách repro
Scope: `adapters/rtsp_frame_source.py`/webcam cv2 · `OnnxDetector`+`DetectorPipeline` · nguồn-live
Nguồn: LOG Entry #376 · chạy thật máy `k.nguyen.manh.toan` no-GPU webcam USB
Đã xác minh (chạy thật): `cv2.VideoCapture(0)` opened 640×480 (index 1 không có). Pipeline `webcam→DetectorPipeline(OnnxDetector yolov8n)→CPU`: 20 frame (bỏ 5 warmup) → **20/20 CÓ detection · person ×20 conf 0.895**. Tên lớp lấy từ metadata model (`session.get_modelmeta().custom_metadata_map['names']` = dict 80 lớp) → chính xác, KHÔNG bịa. ⇒ nguồn-LIVE → NN thật CPU CHẠY (không GPU).
Repro: `cv2.VideoCapture(0).read()` loop → `DetectorPipeline(OnnxDetector("models/yolov8n.onnx", chw_float_normalize, yolov8_decode(labels=names_metadata, layout="nc_first")), 640, 640).detect(frame)`; bỏ ~5 frame warmup; conf>=0.35. Headless (KHÔNG cv2.imshow); chạy `.venv` (webcam-trong-Docker/Windows khó).
Bức tranh "input thật" TRỌN trên CPU: host-image (#351 bus.jpg person×4+bus×1) · config-TOML (#355) · container (#375) · **camera-live (#376)**.
Non-goal / mở: RTSP IP-camera (K-030 digest Windows — cần URL cam IP thật, path khác webcam); webcam-trong-container (Windows Docker khó passthrough); đa-lớp/đa-người (phụ thuộc cảnh).

### K-100 — 🟡 (2026-07-14) `HOLD_MS=500` là mitigation SAI TẦNG; root-cause class = semantic freshness / frame identity
Scope: `profiles/vision_web_app.py` (patch client #377) · spec `web-live-overlay-sync`
Nguồn: LOG Entry #378 · static review toàn bộ `vision_web_app.py` + `webcam_frame_source.py` + detector pipeline · context-gatherer cross-thread/API/frontend map
Nội dung (điều nên biết — phân biệt triệu chứng vs gốc):
- **Triệu chứng:** bbox web nhấp nháy liên tục (user quan sát trực quan #377).
- **Vá đã thử (KHÔNG đạt):** client `HOLD_MS=500` giữ `lastBoxes` theo thời-gian-poll → làm mới `lastSeen` bằng CÙNG snapshot non-empty ⇒ vừa có thể blink khi empty-run, vừa giữ ghost box VÔ HẠN nếu server lặp snapshot cũ. Không biết tuổi detection ⇒ mitigation mù, không phải fix.
- **Root-cause class (đọc code CHỨNG MINH tĩnh, chưa đo runtime):** (a) detection publish `_boxes` MẤT `raw_ver` của frame input → không có frame identity; (b) `/boxes` chỉ trả list, thiếu generation/timestamp/freshness/health; (c) `setInterval(async,80)` cho fetch overlap + không sequence để loại response cũ (out-of-order); (d) `_video_loop` bỏ qua `retry_after_ms` lúc RECONNECTING → đường busy-spin; (e) detector exception giữ state cũ, không phân biệt lỗi với freshness. Lock hiện tại CHỈ chống torn assignment — KHÔNG có bằng chứng thiếu mutex.
- **Chưa chứng minh runtime (trung thực):** trigger cụ thể (empty-run / out-of-order HTTP / source reconnect / canvas resize / temporal skew) CHƯA đo → Task 0 diagnostic instrumentation phải đứng trước code fix, không suy diễn trigger chỉ từ đọc code.
- **Hướng gốc:** sub-spec `web-live-overlay-sync` (D-106) — atomic authority + epoch/lease/frame-identity + tách raw truth ⊥ display projection.
Đóng khi: root-fix theo D-106 được code + verify (targeted + webcam E2E + full vp verify) + Task 0 trace xác nhận trigger; gỡ `HOLD_MS` client patch khi overlay mới thay thế.

### K-101 — 2026-07-15 — Backlog production-readiness cho `vision_web_app.py` (hoãn có chủ đích, chống-quên)
Status: 🟡 (nợ đã biết — hoãn theo quyết định user, D-116)
Nguồn: LOG Entry #392 · review code + user triage
Nội dung (điều nên biết — các mục HOÃN, kèm lý do + khi nào nên làm):
- **(1) `vision_web_app.py` không có test tự động nào.** Wire (#391) mới chỉ E2E thủ công 1 lần. Rủi ro: regression thầm lặng khi sửa. Hoãn theo user TRỪ KHI phục vụ đo performance. → Task 9 (barrier video-indep) / 11 (legacy snapshot) / 12 (property E2E) trong spec `web-live-overlay-sync` vẫn `[ ]`.
- **(2) Flask dev-server (`app.run`).** Werkzeug dev-server KHÔNG dành production (chính Flask cảnh báo). Thương mại → WSGI thật: Windows `waitress`, Linux `gunicorn`/`uvicorn`. Hoãn (demo/nội bộ đủ dùng).
- **(3) Không auth trên endpoint.** `/stream`/`/overlay`/`/boxes`/`/stats` mở cho mọi client trong mạng. Hoãn — khi expose ngoài localhost phải thêm auth + bind cẩn thận (đã có tiền lệ secure-default localhost ở metrics D-079).
- **(4-INT8) Quantize INT8 model ONNX** (onnxruntime static quantization): giải thích ngắn cho user — chuyển trọng số model từ float32 sang int8 → ít bộ nhớ + CPU tính nhanh hơn nhiều; ĐỔI LẠI cần "dữ liệu calibration" (một ít ảnh đại diện để dò dải giá trị) và phải ĐO sụt độ chính xác. Hoãn — cân nhắc trong sub-spec perf.
- **Cảnh báo license (nhắc lại K-029):** YOLOv8 = AGPL-3.0 → sản phẩm đóng thương mại phải mua license Ultralytics HOẶC đổi model Apache-2.0 (RTMDet/RT-DETR/YOLOX). Quyết định pháp lý cần user chốt.
Đóng khi: từng mục được làm trong spec tương ứng (perf/frontend/production-hardening) → rút khỏi backlog.

### K-102 — 2026-07-15 — Baseline perf CPU máy này (verify #395) + input-size cố định (empiric)
Status: ✅ (đo thật phiên #395)
Nguồn: LOG Entry #395 · `bench_capacity --mode infer --onnx yolov8n.onnx`
Nội dung (SỐ THẬT — dùng chốt default adaptive-detection-perf, chống bịa):
- **`yolov8n@640` CPU (máy `k.nguyen.manh.toan`) = 8.52 infer/s** · p50 110.9ms · p95 177.5ms · p99 203.0ms · min 66ms · max 261ms (n=120, warmup 15). ⚠️ #352 ghi 11.72/s = máy/điều-kiện KHÁC → dùng 8.52 cho máy này.
- **Input-size CỐ ĐỊNH 640 (empiric):** `bench --imgsz 416` → `onnxruntime InvalidArgument: Got 416 Expected 640`. ⇒ (a) đổi input-size KHÔNG khả thi lúc runtime (phải re-export .onnx / dynamic-axes = deploy-time); (b) lỗi hiện tối nghĩa → cần fail-fast rõ lúc setup (Task 3).
- **Hệ quả default:** budget detect ~8.5/s; overlay `displayLeaseMs=600` → detect min-interval tới ~600ms (~1.6/s) vẫn không giật (Property 5) → dư địa throttle lớn.
Đóng khi: (số baseline — giữ tham chiếu; cập nhật nếu đo lại máy khác/điều-kiện khác).

### K-103 — 2026-07-15 — Webcam E2E: tradeoff motion-gate↔lease (vật đứng-yên mất box) + min-interval an toàn
Status: ✅ (ĐÓNG bởi D-120 #399 — heartbeat `detectMaxIntervalMs`; dùng `--motion-gate --detect-max-interval-ms <= lease`)
Nguồn: LOG Entry #398 · đọc /stats+/overlay THẬT (cam0+yolov8n CPU), nhiều mẫu
Nội dung (điều nên biết — chống bịa, đã verify E2E):
- **min-interval throttle AN TOÀN:** `--detect-min-interval-ms 200` → detect ~5/s (vs 8.5/s baseline, ~40% ít inference) mà box GIỮ ổn định (interval 200ms < displayLease 600ms → refresh trước khi hết hạn), health LIVE, không giật. Đây là lever tiết kiệm CPU AN TOÀN mặc-định-khuyên-dùng.
- **motion-gate có TRADEOFF:** `--motion-gate` (max-skip=0) cắt CPU cực mạnh khi cảnh tĩnh (video=1627·detect=5) NHƯNG vật ĐỨNG YÊN mất box (display=[] reason TICK_EXPIRE — box hết lease 600ms vì không detect lại). health vẫn LIVE đúng (detector khỏe, chỉ gated).
- **BẢN CHẤT:** `motionMaxConsecutiveSkip` ép re-detect theo FRAME-count, KHÔNG bounded theo lease-TIME → không đảm bảo detect lại trước khi box hết hạn. P5 (`detectMinIntervalMs<=displayLeaseMs`) CẦN nhưng CHƯA ĐỦ cho motion-gate.
- **HƯỚNG (candidate refine, chưa làm):** (a) motion-gate hợp scene "motion=sự-kiện" (line-crossing/vào-ra) — vật đứng-yên không phải mục tiêu; (b) cho scene "giữ box vật tồn tại": thêm force-re-detect THEO THỜI GIAN (≤ displayLease) thay/kèm frame-count; (c) mặc định khuyên dùng min-interval (an toàn) hơn motion-gate.
Đóng khi: bổ sung ràng buộc time-based cho motion-gate (Task tinh chỉnh trong spec) HOẶC ghi rõ motion-gate chỉ cho scene motion=event → cập nhật design/requirements.

### K-104 — Đổi máy sang `toann`: CÓ GPU + CÓ RTSP + KHÔNG Docker (khác máy cũ NO-GPU/CÓ-Docker)
Trạng thái: ✅ (dữ kiện môi trường, #400).
Sự thật: phiên #396-399 chạy máy cũ `k.nguyen.manh.toan` (NO-GPU, CÓ Docker+webcam). Từ #400 chuyển máy `toann` — user xác nhận: **CÓ GPU · CÓ luồng RTSP · KHÔNG Docker**. venv tại `vision-platform/.venv` (Python 3.13.12; máy cũ 3.11.9); `py` launcher hệ thống KHÔNG có → chạy qua `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd` (tự dò venv). `vp check` PASS đầu phiên (#399/Σ280 khớp, commit c449527).
Ảnh hưởng backlog (progress.md "CHẶN bởi điều kiện"):
- 🟢 MỞ được (trước chặn): nhánh `Yolov5PtDetector` CUDA · `probe_capabilities` nhánh có-CUDA (D-073) · RTSP E2E `RtspFrameSource` (K-030) · tune motion-gate-roi RTSP. NHƯNG [chưa kiểm]: venv extras hiện `dev,onnx,cv2,web` — **torch CHƯA cài** → GPU-path CHƯA chạy được; cần `vp setup` với extras `pt` (tải torch cu, cần MẠNG). GPU phần cứng có ≠ torch sẵn.
- 🔴 chặn thêm: bài cần Docker (máy này KHÔNG có Docker) → hoãn (máy cũ đã verify Docker #373-375). **KHÔNG có webcam** (verify #401: `cv2.VideoCapture(0)` out-of-range) → E2E trực quan cần URL RTSP (máy CÓ luồng RTSP theo user).
- **MCP:** workspace `.kiro/settings/mcp.json` chỉ có `fetch` (mcp-server-fetch, content-only, CHƯA surface thành Kiro Power → AI không gọi trực tiếp) — KHÔNG chụp được pixel. `web_fetch` native chỉ HTTPS (không hit localhost HTTP). Muốn AI tự "xem"/screenshot web → cần MCP browser (Playwright) — chưa cài. Xem web = USER mở trình duyệt; AI verify server-side qua `curl /stats`+`/overlay`.
Việc cần làm khi dùng GPU/RTSP: (a) kiểm `nvidia-smi` + `torch.cuda.is_available()` trong venv TRƯỚC khi khẳng định; (b) RTSP cần URL thật (KHÔNG commit secret — K-031).
Links: K-066/K-077 (torch-install cần mạng), K-030 (RTSP), D-073 (capability probe).

### K-105 — SỐ đo cadence CPU máy `toann` (onnx yolov8n CPU): min-interval giảm CPU tuyến tính
Trạng thái: ✅ (verify đo thật, #401 · công cụ `benchmarks/measure_cadence_cpu.py`).
Số THẬT (window 8s/variant, frame 480x640, video-fps 120 mô phỏng, CPUExecutionProvider):
- baseline min-interval=0: **12.88 detect/s · CPU 504.7%** (onnxruntime đa-thread ~5 lõi).
- min-interval=200ms: **3.88 detect/s · CPU 203.5%** → **−59.7% CPU** vs baseline.
- min-interval=500ms: **1.88 detect/s · CPU 100.5%** → **−80.1% CPU** vs baseline.
Ý nghĩa: cadence giảm CPU ~tuyến tính theo tần suất detect → lever THẬT tiết kiệm (R3.1 PASS, R3.2 giữ lever). Với overlay lease 600ms, min-interval tới ~500ms vẫn không mất box (P5) → dư địa cắt ~80% CPU detect mà vẫn mượt.
LƯU Ý so K-102: baseline 12.88/s ≠ K-102 8.52/s (máy cũ `k.nguyen.manh.toan`). Khác vì: (a) máy khác (`toann`); (b) K-102 đo `measure_infer` batch=1 latency-based, K-105 đo loop-throughput đa-thread onnxruntime. Cả hai đúng trong ngữ cảnh của nó — dùng K-105 cho quyết định cadence trên máy này.
Còn thiếu (Task 7): motion-gate CPU (cần scene TĨNH thật, synthetic không đại diện); độ-trễ-bắt-vật-mới; E2E RTSP/webcam.
Links: D-122 (phương pháp), D-121 (Task 5), K-102 (baseline cũ), K-104 (máy toann).

### K-106 — Bug flicker vật ở XA (bbox có/mất/lại-có): GỐC = conf dao động quanh ngưỡng + stabilizer giòn (verify browser MCP #404)
Trạng thái: ✅ root-cause verified (chưa sửa) · bằng chứng: poll /overlay 16 mẫu qua Playwright MCP.
Triệu chứng: user mở browser thấy vật ở xa "có bbox rồi mất rồi lại có". Vật gần KHÔNG bị.
Bằng chứng THẬT (video vtest.avi + yolov8n, cadence motion-gate+min-interval 200ms):
- Vật gần: displayId 1:724, 1:1041 xuất hiện 16/16 mẫu (ổn định).
- Vật xa (box height<0.12): 7 displayId mới trong 3s (1522→1530), mỗi ID sống 2-6 mẫu → churn.
- Conf vật xa dao động quanh 0.25: 0.251/0.257/0.259/0.268/0.273/0.277/0.284... → rớt <0.25 thì mất khỏi rawResult.
Gốc 3 tầng:
1. **@decode:** 1 ngưỡng conf CỨNG (0.25) → vật ~0.26 nhảy vào/ra từng inference.
2. **@stabilizer (display_stabilizer.py):** candidate bị XÓA NGAY nếu 1 accepted-result không match (step 4) → cần minHits=2 hit LIÊN TIẾP mới promote → vật nhấp nháy không đạt → mỗi lần vượt ngưỡng lại promote displayId MỚI (counter++). Confirmed xóa sau maxMisses=2 (3 miss) hoặc hết displayLease 600ms.
3. **@cadence (config #400):** motion-gate+min-interval 200ms → detect thưa → khoảng trống dài hơn → dễ vượt ngưỡng xóa (đòn bẩy tiết kiệm CPU XUNG ĐỘT với giữ track vật nhỏ — Forces cadence↔lease↔flicker).
Hướng sửa (chờ chốt design, cân ghost vs flicker):
- (A) stabilizer temporal-hysteresis: candidate có miss-tolerance (không xóa ngay) → promote ổn định + giữ 1 displayId; ± nới maxMisses/displayLease cho vật nhỏ.
- (B) confidence-hysteresis @decode: 2 ngưỡng (cao tạo mới, thấp duy trì) → giảm dao động tận nguồn.
- (C) cấu hình: giảm throttle khi cảnh cần bắt vật nhỏ.
Đóng khi: chốt design fix + TDD + verify browser lại (churn giảm rõ, ghost trong ngưỡng chấp nhận).
Links: display_stabilizer.py (minHits/maxMisses/lease), OverlayConfig, D-121/#400 (cadence), K-100/K-103 (họ overlay flicker/lease).

### K-107 — Fix flicker thử-1 (conf-hysteresis) CHƯA ĐỦ trên vtest.avi: gốc trội = IoU-association vật nhỏ di chuyển (verify browser MCP #405)
Trạng thái: ✅ empiric-verified (âm tính) · fix flicker CÒN MỞ.
Bằng chứng THẬT (browser MCP poll /overlay, đo churn = số displayId phân biệt/16 mẫu ~3s):
- #404 baseline (throttle, decode 0.25, KHÔNG hysteresis): 7 displayId (2 ổn định + churn).
- throttle + hysteresis (create 0.35/sustain 0.12): **7 displayId** → KHÔNG cải thiện.
- KHÔNG throttle + hysteresis: **28 displayId** (24 promote mới/3s) → TỆ HƠN; weakRaw 3-6 box/mẫu (hạ decode 0.12 NGẬP box yếu cảnh đông).
Kết luận (chống overclaim): confidence-hysteresis (D-123) logic ĐÚNG (unit `test_oscillating_conf_no_churn`) nhưng chỉ trị nguyên nhân PHỤ. GỐC TRỘI ở vtest.avi (đông người, vật nhỏ di chuyển nhanh):
1. **IoU-association fail:** box nhỏ dịch chuyển → overlap giữa 2 detect < iouThreshold 0.3 → `greedy_associate` không match → confirmed miss→chết (maxMisses) → promote displayId MỚI. Box NHỎ mất overlap nhanh hơn box lớn → đúng "vật ở xa" bị.
2. **Ngập box yếu:** hạ decode conf về sustain (0.12) để feed hysteresis → cảnh đông sinh nhiều detection yếu → nhiều candidate/promote thoáng qua.
3. Cadence throttle (motion-gate+min-interval) làm khoảng trống detect dài → association càng dễ fail.
Hướng fix THẬT (chờ chốt design): (A) association motion-aware/center-distance/size-aware IoU (box nhỏ nới tolerance) thay/kèm IoU thuần; (B) KHÔNG hạ decode conf mù (giữ ngưỡng vừa, tránh ngập); (C) test trên RTSP thật (ít đông hơn vtest.avi có thể đã đủ). Giữ D-123 làm lever.
Links: K-106 (triệu chứng+gốc conf), D-123 (hysteresis), display_smoothing.greedy_associate (IoU matching), D-121/#400 (cadence).

### K-108 — Ghost "người đi qua rồi bbox 1 lúc mới tắt": gốc = display không có motion model → fix motion-aware eviction (D-124)
Trạng thái: ✅ code+unit (D-124) · E2E A/B video: giảm NHẸ (chưa kịch tính trên cảnh đông).
E2E A/B (browser MCP, vtest.avi, 20 mẫu/run — metric: display box KHÔNG có raw backing = "treo"):
- evict ON: 105 box, treo 17 (16.2%), treo-gần-mép 7.
- evict OFF: 118 box, treo 23 (19.5%), treo-gần-mép 8.
⇒ có tác dụng thật (16.2% < 19.5%) nhưng nhỏ trên cảnh ĐÔNG (nhiều "treo" là dropout ngắn hợp lệ ≠ rời-khung + đo nhiễu). Unit test chứng minh hành vi đúng (rời-khung→xoá-ngay). Cảnh RTSP thật (người đi rõ ra khỏi khung, thưa) kỳ vọng rõ hơn — verify khi có URL.
Triệu chứng (user #405): người di chuyển nhanh rời khung → bbox nán lại ~displayLease (600ms) mới tắt.
Gốc: `DisplayStabilizer` giữ confirmed track theo lease/maxMisses cố định sau lần khớp cuối — KHÔNG biết người đã RỜI khung → box đứng ở vị trí cũ tới khi hết lease. Cùng gốc với flicker (K-106/107): thiếu MODEL CHUYỂN ĐỘNG.
Fix (D-124, additive default-off): ước lượng vận tốc tâm (2 lần khớp) → khi miss, dự đoán tâm; ra ngoài [0,1] → xoá ngay (đã rời). Vật đứng-yên/bị-che (dự đoán trong khung) → giữ theo lease (không hại). Cờ `evictPredictedOffFrame` / `--overlay-evict-offframe`.
Lưu ý bản chất (2 đầu 1 gốc): flicker vật-xa = chết-quá-sớm; ghost người-rời = chết-quá-muộn. Cả hai vì giữ box theo đồng hồ mù. Motion model (mini-SORT: vận tốc + dự đoán + xoá-khi-ra-khung) là hướng thống nhất; nâng cấp: Kalman + association motion-aware (K-107) nếu RTSP thật còn flicker.
Links: D-124 (fix), K-106/K-107 (flicker cùng gốc), OverlayConfig.evictPredictedOffFrame.

### K-109 — Web app đang chạy CPU cho YOLO; GPU (onnxruntime-gpu) SẴN cho ONNX KHÔNG cần torch (đính chính K-104)
Trạng thái: ✅ verify (#407, đọc code + query onnxruntime).
Sự thật:
- `onnxruntime` trong venv = **onnxruntime-gpu 1.27.0**, `get_available_providers()` = ['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider'] → CUDA khả dụng (RTX 2060).
- `OnnxDetector` default `providers=("CPUExecutionProvider",)`; `vision_demo_app._build_detector` nhánh onnx KHÔNG truyền providers + KHÔNG map `--device` → **web app + mọi demo onnx đang chạy CPU** (hard-code). (bench_capacity CÓ map --device→providers → chỉ bench mới ra GPU.)
- ⇒ Câu trả lời "CPU hay GPU": hiện **CPU**. Số K-105 (8.5/s...) là CPU.
**ĐÍNH CHÍNH K-104:** "GPU cần torch" chỉ đúng nhánh `.pt` (Yolov5PtDetector). Nhánh **ONNX chạy GPU qua onnxruntime-gpu, KHÔNG cần torch**. K-104 imprecise ở điểm này.
Hệ quả (hướng): bật GPU cho web app = wire `--device cuda → providers=[CUDAExecutionProvider, CPUExecutionProvider]` vào `_build_detector` (nhánh onnx) + `ensure_cuda_dll_path` (D-098 đã có). GPU tăng detect-rate mạnh → GIÁN TIẾP giảm flicker (K-107) + ghost (K-108) vì bớt phải throttle cadence. Verify bằng `session.get_providers()` ra CUDA + đo throughput.
Links: K-104 (máy toann GPU/torch), K-105 (số CPU), D-098/K-088 (cuda_dll_path), onnx_detector.py, vision_demo_app._build_detector.

### K-110 — Ngưỡng conf: 0.45 khử false-positive (data-driven, verify) — trade-off recall vật xa
Trạng thái: ✅ verify (browser MCP #409).
Vấn đề: conf mặc định 0.25 → vật lạ conf thấp gán nhầm "person" + nhãn rác (backpack/skis/surfboard trong cảnh phố).
Data (176 detect vtest.avi): 72% conf≥0.6; band 0.25-0.45 (~16%) = noise. `--conf 0.45` → minConf 0.456, 0 box<0.45, nhãn còn person/truck/car (hết rác). False-positive sạch.
TRADE-OFF (bản chất, đối nghịch K-106): nâng conf = ít false-positive NHƯNG **recall giảm** — người XA/nhỏ (conf thấp) bị bỏ → tăng "missing vật xa". Ngược mục tiêu chống-flicker-vật-xa. Không có 1 ngưỡng đúng cho mọi cảnh:
- cảnh cần độ TIN CẬY (ít báo nhầm) → conf cao (0.45-0.5).
- cảnh cần bắt VẬT XA/nhỏ → conf thấp (0.25-0.35) + dựa mini-tracker (D-123/124/125) ổn định hiển thị.
Runtime: cờ `--conf` (KHÔNG đổi default 0.25 trong code). Ứng dụng thương mại nên cho chỉnh per-camera.
Links: K-106 (flicker vật xa — đối nghịch), K-109 (CPU), D-123..125 (mini-tracker).

### K-111 — Bug #410 (crash detect) + churn trên video THẬT A.mp4: metric ID-churn ≠ visual flicker
Trạng thái: ✅ bug fixed (#411) · churn visual chờ user đánh giá.
Bug #410 (đã fix): `_predict_box` (D-125) dựng `BBox(NORMALIZED)` với toạ độ dự đoán ÂM/>1 (vật gần mép di chuyển ra) → BBox validate [0,1] ném ValueError → detect crash liên tục trên A.mp4. Fix: clamp x,y về [0,1] trong `_predict_box`. Test hồi quy `test_prediction_offframe_clamped_no_crash`. BÀI HỌC: extrapolate/predict PHẢI clamp trước khi dựng đối tượng validated.
Quan sát A.mp4 (~5 người, browser MCP): detect person conf 0.46-0.91 OK; false-positive nhãn lạ frisbee×7/potted-plant×1 (nâng conf 0.5 nếu phiền); **displayID churn cao (88 distinct/25 mẫu, 0 ổn định)**.
LƯU Ý QUAN TRỌNG (chống hiểu sai metric): **displayID churn VÔ HÌNH với user** — họ thấy BOX có/mất, KHÔNG thấy ID. Box coverage ~5.4/khung (phủ người khá liên tục). ID mới ở CÙNG vị trí = KHÔNG nhấp nháy nhìn thấy. ⇒ đánh giá đúng phải là **visual box-continuity**, không phải đếm displayID. Nếu user nhìn thấy nhấp nháy THẬT → mới cần nâng association (center-distance/Hungarian/Kalman). Đo đúng: box có phủ liên tục mỗi người không, không phải ID có đổi không.
Links: D-125 (_predict_box), K-106/107 (flicker), K-110 (conf).

### K-112 — 2026-07-16 — Nguồn synthetic moving-square KHÔNG đủ đánh giá tracking (bệnh lý testbed) + S1 root verify browser
Status: 🟡 (điều nên biết khi verify overlay/tracking không có video/RTSP thật)
Nguồn: LOG Entry #414 · browser MCP (Playwright) đo /overlay THẬT frontier #412
Nội dung (chống kết-luận-sai — đã verify browser):
- **XÁC NHẬN S1 root:** `/overlay` display box KHÔNG có `vx/vy/updatedAtMs` → client không có gì để ngoại suy → vẽ vị trí báo-cuối (tĩnh). Wave A cần server phơi vận tốc trước.
- **Bệnh lý synthetic moving-square (`moving_square_frame`):** (a) `x=(i*step)%(max_x+1)` → TELEPORT-wraparound khi tới mép phải (gián đoạn thật → đổi ID đúng, không phải bug); (b) video-loop unthrottled chạy ~15× detect → ô nhảy ~120px/detect (> box 80px) → IoU association fail → churn giả; (c) BrightBlob conf 0.0833 THẤP → `--overlay-motion` (hysteresis create-threshold) lọc hết → display 0/20 (không phải bug tracking).
- **De-confound bằng `--pace 0.06`** (detect kịp video): box present **20/20**, x tiến mượt, chỉ đổi ID sau teleport → **tracking/display CHẠY ĐÚNG khi detect kịp chuyển động**.
- **Hệ quả:** churn/flicker xuất hiện khi detect-rate << tốc-độ-vật (CPU thật). Fix: (Wave A) client ngoại suy vận tốc để bù lag giữa detect + (association tốt hơn khi vật nhanh). Đánh giá per-object flicker/ghost SẠCH cần **video/RTSP THẬT** (không có ở máy này — video toann gitignored/vắng; cân nhắc tải people-detection.mp4 nếu có mạng, hoặc chờ RTSP user).
Đóng khi: có nguồn thật (RTSP/video) đo per-object với/không Wave A; hoặc thêm nguồn synthetic "bounce smooth throttled" làm testbed hợp lệ cho tracking.

### K-113 — 2026-07-16 — removal-timeout = displayLeaseMs (đừng thêm maxAgeMs trùng cơ chế)
Status: ✅ (verify code + empiric browser #417)
Nguồn: LOG Entry #417 · đọc display_stabilizer + browser MCP webcam
Nội dung (chống thêm phức tạp vô ích — R3.2):
- `DisplayStabilizer`: `st.lease_deadline_ns = now + displayLeaseMs` refresh MỖI khớp; on_tick xoá khi `lease_deadline <= now` → track bị xoá tại **`last_match + displayLeaseMs`**. Vậy `displayLeaseMs` CHÍNH LÀ "time-since-update removal timeout".
- Design D-126 đề xuất `maxAgeMs` (removal theo time_since_update) = **TRÙNG hoàn toàn** displayLeaseMs → KHÔNG thêm (đẻ config trùng = phức tạp vô ích + 2 nguồn điều-khiển 1 hành vi).
- **S2 "tắt chậm" fix = giảm displayLeaseMs** (expose CLI `--overlay-display-lease-ms`). Ràng buộc: lease phải > detect-gap để không flicker vật hiện diện. Empiric webcam: lease 350 (> gap CPU ~80-200ms) → box present 25/25 KHÔNG flicker, max_remainingLeaseMs 335<350 (chứng minh lease=timeout). Mặc định giữ 600 (additive); tune per-camera theo cadence.
- Bài học rộng: TRƯỚC khi thêm config/cơ-chế mới, đọc code xem cơ-chế-sẵn-có đã làm điều đó chưa (valid design bằng code thật) → tránh trùng lặp.
Đóng khi: (bài học — tham chiếu khi thiết kế removal/lease).

### K-114 — 2026-07-16 — Churn "mất bbox nhiều" GỐC = spurious conf thấp → fix hysteresis; churn↔clear tension theo sustain
Status: ✅ (đo thật browser MCP webcam #421; fix verify)
Nguồn: LOG Entry #421 · browser MCP đo /overlay webcam THẬT
Nội dung (chống đoán — số đo):
- **Churn GỐC (đo):** detection thứ-3+ chập chờn conf **0.25–0.33** (avg 0.275, chỉ nhỉnh hơn decode-conf mặc định 0.25) → mỗi lần xuất hiện lại tạo displayId MỚI (counter leo nhanh) → box "mất rồi hiện" = flicker. 2 người thật conf 0.37–0.93 + raw jitter cực nhỏ (dx_avg 0.0005) → detector KHÔNG nhiễu cho vật rõ; churn CHỈ ở detection yếu.
- **FIX (verify 5+→2 ID, ổn định 50/50):** confidence hysteresis (D-123) `--overlay-create-conf 0.45 --overlay-sustain-conf 0.30` — spurious < 0.45 KHÔNG tạo track; người thật conf tụt vẫn nuôi (≥0.30). Tốt hơn `--conf` đơn (không rớt người thật quanh 0.37).
- **Removal-latency (đo):** track xoá khi remainingLeaseMs còn ~180-225ms (bằng MISS, không đợi hết lease) → server clear ~350ms/nhanh hơn. "~1s user thấy" ≈ detector còn bắt người lúc đang rời khung (conf≥sustain) + 350ms.
- **TENSION churn↔clear (bản chất):** sustain THẤP → ít churn NHƯNG giữ box người-đang-rời lâu (clear chậm); sustain CAO → clear nhanh NHƯNG churn. off-frame-evict (D-124) xoá tức thì khi rời qua mép (giảm clear-latency lối-ra-mép, không hại churn). Không có 1 ngưỡng đúng mọi cảnh → tune per-camera; cân nhắc hysteresis làm default thương mại.
Đóng khi: user xác nhận thị giác hết churn + clear chấp nhận được; hoặc chốt default thương mại.

### K-115 — 2026-07-16 — Tuning `intra_op_num_threads` onnxruntime KHÔNG là lever (default gần tối ưu + portable)
Status: ✅ (đo thật, kết luận âm tính — 0 đổi code)
Nguồn: LOG Entry #422 · probe process-riêng · 120 iter · median-of-3 (yolov8n@640 CPU, máy 16 core)
Nội dung (chống đoán — số đo):
- **Số THẬT:** default(no SessionOptions)=**30.61 fps** · intra=1→13.41 · 2→21.45 · 4→28.22 · 6→28.82 · 8→**32.85** · 16→14.02. → default ≈ best (intra=8 hơn ~7% NẰM TRONG NHIỄU: default raw lên 35.2 trùng dải intra=8); intra=1/16 rõ ràng tệ.
- **KẾT LUẬN:** onnxruntime tự chọn thread-count gần tối ưu → **KHÔNG thêm `SessionOptions(intra_op_num_threads=)`**. Hard-code hại tính di động (máy 4 core ép 8/16 = oversubscription như intra=16→14fps << 30.6). Premature-opt + đổi hệ đã verify cho cái lợi trong-nhiễu = vi phạm chống-phức-tạp (R3.2).
- **BẪY ĐO (bài học phương pháp):** probe cũ tạo 7 `InferenceSession` TUẦN TỰ trong 1 process (không teardown) + cửa sổ 60 iter → variance 2-3× (run1 intra=4 tốt, run2 intra=8 tốt) = NHIỄU, kết luận sai. Đo throughput onnxruntime PHẢI: 1 session/process riêng + warmup + cửa sổ đủ dài + median nhiều vòng. Số ~30fps là session.run THUẦN (cao hơn pipeline thật ~16.5/s có pre/letterbox+post/NMS).
- **Nhanh hơn NỮA cần deploy-time (không phải runtime tuning):** input 416 re-export (~2×) / INT8 quant / GPU (máy này KHÔNG có). Overlay ĐÃ mượt bất kể detect-rate nhờ client extrapolation (#416) → detect-rate KHÔNG còn nút thắt UX.
Đóng khi: (không cần đóng — kết luận âm tính). Mở tiếp nếu muốn đo live-throughput-under-contention theo thread-count (khác đo cô lập này — [chưa kiểm]).

### K-116 — 2026-07-17 — Flaky `test_direct_quarantine_on_killed_owner` (kill-recovery, PID-reuse/liveness race) — CÓ SẴN, không do Wave 2
Status: 🟡 flaky pre-existing (KHÔNG chặn Wave 2 — retry PASS)
Nguồn: LOG Entry #426 · gặp lúc `vp verify` sau khi code web-production-hardening Wave 2
Nội dung (grounded, không suy đoán):
- **Hiện tượng:** `tests/test_hardening_kill_recovery.py::test_direct_quarantine_on_killed_owner` fail ngắt quãng: `ring.quarantine_poisoned_slot(1)` trả **False** (kỳ vọng True). Cô lập chạy lặp = **2 pass / 1 fail** (~1/3) → test TỰ nó flaky, KHÔNG phải full-suite contention thuần.
- **BẢN CHẤT (đọc test):** test `proc.kill()` + `proc.join()` rồi kỳ vọng owner bị phát hiện DEAD (psutil liveness) → quarantine True. Trên Windows sau kill có race: OS chưa cập nhật liveness / **PID-reuse** (PID worker chết bị process khác tái dùng) → liveness báo "còn sống" → quarantine từ chối (False). Test có capture `worker_ct` (creation-time) nhưng đường quarantine trực tiếp dường như chưa dùng creation-time để loại PID-reuse.
- **KHÔNG do Wave 2:** code Wave 2 (adapters `auth_middleware`/`wsgi_server` + wiring profiles) KHÔNG import runtime/ipc/`ShmRingBuffer`; import-linter 6 kept/0 broken. Cùng `vp verify` retry → **857/2 GREEN** (flaky biến mất) → transient, không phải regression.
- **Liên hệ K-035:** cùng họ flaky cross-process/timing (đã ghi K-035 supervisor). Đây là mảnh riêng ở tầng SHM liveness.
Đóng khi: (nếu muốn fix GỐC — spec riêng) quarantine dùng **(pid, creation_time)** thay pid trần để chống PID-reuse (liveness PID-reuse-safe). NGOÀI phạm vi web-production-hardening — KHÔNG vá speculative (tiền lệ #293/#294). Ghi để theo dõi.

> **CẬP NHẬT #430 (D-136) — K-116 ĐÓNG + ĐÍNH CHÍNH:** đọc code thật → `owner_liveness` ĐÃ pid-reuse-safe (so create_time). Suy đoán "PID-reuse chưa guard" ở trên SAI. Gốc thật: psutil báo owner chưa-DEAD 1 nhịp sau kill+join (OS reap-lag/handle Popen) → assert 1-phát race; production tự lành (quarantine retried). Fix test = `wait_until(quarantine==True)` (event-driven, #288) → 12/12 lặp PASS. K-116 Status → ✅ đóng.

### K-117 — 2026-07-17 — RTSP camera .106 không tới được = VPN chặn LAN (KHÔNG phải lỗi code/camera)
Status: ✅ (2026-07-19, #450) camera .106 NAY REACHABLE — RTSP live verified (user đã mở LAN access / VPN không còn chặn tới .106). Nếu VPN siết lại thì tái diễn (giữ ngữ cảnh chẩn đoán bên dưới).
**✅ #450 (verify):** chạy web app `--rtsp rtsp://admin:***@192.168.120.106:554/cam/realmonitor?channel=1&subtype=0` trên máy `toann` (Windows GPU) → `video=2588+` frame chảy, browser stream `<img>` naturalW=1920×1080 complete=true, 0 lỗi console, ~1097 req 200 OK. ⇒ LAN tới .106:554 THÔNG (điều kiện VPN-block #429 không còn áp). KHÔNG đụng VPN.
Nguồn: LOG Entry #429 · chẩn đoán mạng chỉ-đọc (Get-NetIPAddress/Find-NetRoute/Test-NetConnection/arp) máy `toann`
Nội dung (grounded — số đo, không suy đoán):
- Máy có IP LAN **192.168.120.104** (cùng /24 với camera .106) + adapter VPN **ProTUN** (10.2.0.2) đang Up.
- `Find-NetRoute 192.168.120.106` → source .104, interface **Ethernet**, NextHop 0.0.0.0 (on-link) → **route ĐÚNG, VPN KHÔNG hijack route LAN**.
- ARP có .106 → MAC `0c-ef-15-6c-a8-8e` (L2 từng thấy thiết bị).
- NHƯNG: ping .106=**False**, mọi TCP .106 (80/554/8000/88/37777)=**False**, **ping gateway LAN .1 cũng =False**, chỉ ping chính máy .104=True.
- **KẾT LUẬN:** máy chỉ tới được chính nó, KHÔNG tới cả gateway .1 lẫn .106 dù route on-link đúng → **VPN (ProTUN) chặn TOÀN BỘ traffic LAN** (kill-switch / block-local-network qua WFP filter, drop gói dù route local). KHÔNG phải lỗi camera/code/web app.
Đóng khi: user bật **"Allow LAN / local network access"** trong app VPN (GIỮ VPN bật — tuyệt đối KHÔNG tắt VPN theo yêu cầu user) → re-test `Test-NetConnection 192.168.120.106 -Port 554` (RTSP) / 80 (web config). Nếu VPN không cho phép LAN → không dùng được camera LAN khi VPN bật (quyết định của user). Ràng buộc tuyệt đối: **AI KHÔNG được tắt/đổi VPN của user.**
> **Addendum #442 (manh mối user):** user báo camera "hình như chỉ là **IPv6**". Lưu ý: `192.168.120.106` là **IPv4** → nếu camera IPv6-only thì `.106` KHÔNG phải nó (chỉ là thiết bị khác trong ARP), giải thích thêm vì sao ping/TCP `.106` fail (bên cạnh VPN-chặn-LAN). **Khi test sau (user chủ động, tài nguyên đủ):** (1) lấy địa chỉ IPv6 + URL RTSP thật từ trang cấu hình camera; (2) RTSP qua IPv6 dạng `rtsp://[<ipv6>]:554/...` (bọc ngoặc vuông); (3) kiểm VPN có route/allow IPv6-LAN không (nhiều VPN chỉ tunnel/allow IPv4 → IPv6 có thể rò hoặc bị chặn khác IPv4); (4) `Test-NetConnection` + `-6`. CHƯA verify được bây giờ (chưa test theo ý user).

### K-118 — 2026-07-17 — Web app THREAD-SAFE đa-client dưới waitress (static proof + empiric 2844/2844)
Status: ✅ (verify tĩnh + empiric) — đóng lo ngại multi-viewer từ #420/K-101
Nguồn: LOG Entry #432 · đọc code (`vision_web_app.py` globals + `OverlayStateStore.snapshot`) + `tools/web_concurrent_probe.py`
Nội dung (grounded):
- **Static (đọc code):** mọi shared mutable state có khoá: `_jpeg/_raw/_raw_ver/_legacy_boxes/_vframes/_dframes/_last_read_ns` truy cập dưới global `_lock` (writer `_video_loop`/`_detect_loop` + reader `/stream _mjpeg`,`/stats`,`/boxes`). `/overlay` đọc `OverlayStateStore.snapshot()` = **dưới `self._lock` trả reference immutable đã commit**; mọi mutation dưới cùng lock + `_commit`→`_build` thay snapshot immutable MỚI → mẫu **lock + immutable-snapshot-swap** = reader song song luôn thấy 1 snapshot hoàn chỉnh (không torn). `_store`/`_PROCESS_EPOCH` gán 1 lần trong main() trước serve → đọc-only.
- **Empiric (`tools/web_concurrent_probe.py`, waitress threads=8 + Basic Auth + video+detect chạy):** 12 thread song song × 5s → **2844/2844 request 200** (/overlay+/stats), 0 non-200, ~564 req/s, server không crash.
- ⇒ Wave 1 (waitress) đạt mục đích thương mại: phục vụ NHIỀU client đồng thời an toàn (werkzeug dev-server không đảm bảo điều này).
- **§3.1 — Trusted Command đề nghị (read-only, tái dùng cho load/soak):** `python -m tools.web_concurrent_probe *`.
Đóng khi: (✅) — không cần thêm. Soak nhiều-giờ / >12 client / nhiều-máy = mở rộng nếu cần (dùng lại probe).

### K-119 — 2026-07-18 — "cực nhiều lỗi" browser = console flood lúc server restart/mất-kết-nối tạm (transient, app TỰ hồi phục)
Status: ✅ (root-cause + verify code THẬT + empiric restart-recovery)
Nguồn: LOG Entry #435 · browser MCP webcam máy k.nguyen (port 8026/8027) · đọc `_PAGE` JS `vision_web_app.py`
Nội dung (chống đoán — code + số đo):
- **Hiện tượng:** khi server Python DỪNG/restart (rất thường lúc dev / đổi máy / app crash-restart) mà tab browser đang mở → console flood **`ERR_CONNECTION_REFUSED`/`ERR_CONNECTION_RESET`** tới `/overlay`,`/stats`,`/stream` (poll 80ms → mỗi lần thất bại +1 lỗi → hàng chục/hàng trăm lỗi nhanh). Đây RẤT có thể là "cực nhiều lỗi" user thấy. Đo thật: dừng server 8027 → 3s sau 17 lỗi → 6s sau 51 lỗi (tích luỹ).
- **Bản chất:** lỗi này do **trình duyệt tự log request mạng thất bại** — app JS KHÔNG chặn/ẩn được (không phải defect logic app). Là transient/cosmetic.
- **App TỰ HỒI PHỤC (verify code + empiric):** `poll()` = `try{fetch}catch{o=null}` + **`finally{setTimeout(poll,80)}`** → vòng lặp reschedule DÙ lỗi, KHÔNG bao giờ chết; `statsLoop()` y hệt; `img.addEventListener('error',()=>setTimeout(reloadStream,500))` + `visibilitychange→reloadStream`. **Empiric:** restart server 8027 → client TỰ nhận lại (probe **10/10 OK**, health LIVE, 3 box, MJPEG img phục hồi 640×480) **KHÔNG cần reload tay**.
- **Kịch bản live sạch (cùng phiên):** server chạy ổn định → **0 lỗi console**, 2516/2516 request 200, stream live, canvas căn (#418), tab-nền→visible reconnect (#419), resize realign, DOM 0-delta (không leak).
- **Khử HẲN console-noise lúc outage = cần đổi transport** (WebSocket + exponential backoff: 1 lỗi WS thay hàng trăm fetch; hoặc SSE) — thay đổi kiến trúc LỚN, hiện là **Non-Goal**. KHÔNG làm speculative: hành vi hiện tại đúng chức năng + self-heal; polling vốn dĩ flood-console-khi-outage (không tránh được ở tầng app).
Đóng khi: (không cần đóng — điều nên biết). Nếu console-noise lúc restart là đau vận hành thật (demo/dashboard) → cân WS transport (spec riêng, cùng hướng WebRTC Non-Goal #419).

### K-120 — 2026-07-18 — Năng lực CUDA của onnxruntime ≠ của torch (đừng gate đường ONNX bằng torch)
Status: ✅ (đóng bằng D-142) — bài học kiến trúc dual-use
Nguồn: LOG Entry #441 · review kiến trúc trên máy GPU toann · đo thật + đọc code
Nội dung (grounded):
- **Sự thật đo được (máy toann):** torch KHÔNG cài (`has_torch=False`) nhưng `onnxruntime 1.27` `get_available_providers()` = `['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']` → **GPU DÙNG được qua onnxruntime KHÔNG cần torch** (xác nhận K-109 bằng số).
- **Bẫy kiến trúc (bug D-139 vô tình tạo):** `MachineCapabilities.has_cuda` dò QUA torch (`torch.cuda.is_available()`). Nếu đường ONNX gate device theo `has_cuda` (torch) → trên máy GPU-không-torch: `auto`→CPU, `cuda`→CapabilityError → **GPU bất khả dụng oan** dù onnxruntime thấy CUDA.
- **Vì sao máy trước (k.nguyen no-GPU) KHÔNG bắt được:** máy đó cả torch-cuda LẪN onnxruntime-cuda đều False → 2 nguồn trùng "no CUDA" → bug VÔ HÌNH. Chỉ máy GPU-onnxruntime-gpu-không-torch mới lộ → **review dual-use PHẢI chạy trên đúng cấu hình target mới thấy**.
- **Nguyên tắc (fix D-142):** gate mỗi runtime bằng NĂNG LỰC CỦA CHÍNH NÓ — ONNX theo `has_onnx_cuda` (dò `ort.get_available_providers()`), torch theo `has_cuda` (dò `torch.cuda`). KHÔNG dùng chung 1 cờ CUDA cho 2 runtime độc lập.
- **Tổng quát hoá:** khi có N backend inference (onnxruntime/torch/tensorrt/openvino...), "máy có GPU" KHÔNG đủ — phải hỏi "backend X có dùng được GPU trên máy này không". Capability là PER-BACKEND.
Đóng khi: (✅ D-142 tách has_onnx_cuda). Mở rộng nếu thêm backend khác (openvino/tensorrt-standalone) → thêm cờ năng lực per-backend tương ứng.


### K-121 — ✅ (2026-07-19, #452) Đo capacity detector THẬT trên máy `toann`: GPU 36.16 vs CPU 17.14 infer/s (yolov8n@640)
Status: ✅ đo thật (bench_capacity, median-of-many, warmup 20 + measure 200)
Scope: `benchmarks/bench_capacity.py --mode infer --onnx models/yolov8n.onnx --yolo v8` · máy `toann` (RTX 2060, onnxruntime-cuda, KHÔNG torch)
Nguồn: LOG Entry #452 · chạy thật bench_capacity 2 lần (device cuda + cpu) cùng máy/cùng model/cùng imgsz
Evidence:
- **GPU (CUDAExecutionProvider):** throughput **36.16 infer/s** · latency p50 **25.1ms** · p95 44.8 · p99 61.9 · min 20.0 · max 68.2.
- **CPU (CPUExecutionProvider) cùng máy:** throughput **17.14 infer/s** · p50 **58.1ms** · p95 64.2 · p99 70.3.
- **Lợi ích GPU (định lượng D-142):** **2.11× throughput** · **2.31× latency-p50 thấp hơn**.
Nội dung (số thật cho sizing/SLA, KHÔNG đoán):
- 1 RTX 2060 ≈ **36 detect/s** trần cho yolov8n@640 (batch=1) → sizing fleet: ~7 cam @5fps-detect · ~12 cam @3fps · v.v. (input cho multicamera-fleet-profile ASSUMPTION A2 — nay có SỐ, không còn chỉ "nhỏ-vừa").
- Xác nhận D-142 (onnx-cuda gating) không chỉ "engaged" (log device=cuda ở #451) mà THỰC SỰ nhanh hơn CPU 2.1× → GPU đáng dùng cho detector này.
Vì sao (bản chất): yolov8n là model NHỎ → GPU chỉ ~2× CPU (không phải 10×) vì kernel launch overhead + model chưa bão hoà GPU; muốn tăng nữa = batch nhiều cam (F3.3 batch-mux) hoặc input nhỏ hơn (416)/INT8 (deploy-time, K-115). Đây là C_inf batch=1; batch-mux có thể nâng throughput/GPU.
Cross-ref: K-014 (ring-drop@fps — KHÁC scope, vẫn 🔴 chưa đo drop dưới tải sustained), D-142 (GPU fix), K-115 (deploy-time levers), F3.3 (batch-mux), multicamera-fleet-profile A2.
[chưa kiểm]: fps end-to-end (gồm decode+letterbox+NMS+overlay, không chỉ infer); soak 24/7; TensorRT provider (có thể nhanh hơn CUDA nhưng build engine lâu — chưa thử).

### K-122 — ✅ `Connection` header là hop-by-hop → CẤM trong WSGI app (PEP 3333); waitress cưỡng chế, werkzeug-dev che giấu
Scope: web serving / WSGI streaming (SSE, MJPEG)
Nguồn: LOG Entry #454 · traceback waitress `task.py::start_response` `AssertionError` · PEP 3333
CẬP NHẬT 2026-07-19 (D-150): khi thêm endpoint SSE `/events`, set `resp.headers["Connection"]="keep-alive"` →
dưới `--server dev` (werkzeug) chạy OK, nhưng dưới `--server waitress` (production WSGI) → `AssertionError:
Connection is a "hop-by-hop" header; it cannot be used by a WSGI application (see PEP 3333)` → SSE KHÔNG mở được.
**Bài học:** hop-by-hop header (`Connection`, `Keep-Alive`, `Transfer-Encoding`, `Upgrade`...) do WSGI SERVER
quản, app KHÔNG được set. Streaming (SSE/MJPEG) chỉ cần yield đều + `Cache-Control:no-cache` (+ `X-Accel-Buffering:no`
cho nginx). **Verify dưới server SẢN XUẤT (waitress), KHÔNG chỉ dev-server** — dev-server dễ dãi che giấu lỗi
PEP 3333 + buffering. (Cùng tinh thần #427 verify MJPEG dưới waitress.) Fix = bỏ header `Connection`.

### K-123 — ✅ `EventSource` KHÔNG tự reconnect khi server trả HTTP status lỗi (503) — chỉ reconnect khi đứt tầng-mạng
Scope: web client SSE (`profiles/vision_web_app.py` `_PAGE`) / thiết kế fallback
Nguồn: LOG Entry #456 · ĐO Playwright MCP (`--max-stream-conns 1`, port 8037) + console log `.playwright-mcp/console-2026-07-27T02-51-16-947Z.log`
CẬP NHẬT 2026-07-27 (D-152): khi `/events` trả **503** (đạt trần bulkhead), browser log 1 lỗi rồi **KHÔNG thử lại**:
đo được `eventsAttempts=1` tại 112ms, im suốt ~59s, `sseFails` đứng ở 1 (khác hẳn trường hợp **server chết** —
lúc đó `EventSource` tự reconnect, đo ở #454: 3 lỗi/12s cách nhau ~3.5s). Trạng thái sau đó = `readyState CLOSED(2)`.
**Hệ quả BẪY THIẾT KẾ:** fallback kiểu "sau N lỗi liên tiếp mới rơi về poll" **không bao giờ kích hoạt** với lỗi
HTTP-status → overlay CHẾT VĨNH VIỄN (0 box, canvas trắng, badge đỏ) dù server hoàn toàn sống. Chính là failure
mode "hang âm thầm" bị đẩy từ server sang client.
**LUẬT RÚT RA:** phân biệt 2 loại lỗi SSE — **vĩnh viễn** (`readyState===2`: HTTP status lỗi, MIME sai) → phải
fallback NGAY; **tạm** (`readyState===0` CONNECTING: đứt mạng, browser sẽ tự thử lại) → mới dùng ngưỡng đếm.
Verify sau fix: trần=1 → degrade sau ĐÚNG 1 lỗi → poll 220 lần/8s, box vẽ lại, badge tắt.

### K-124 — ✅ URL kiểu `http://user:pass@host/` làm CHẾT mọi `fetch()` trong trang (Fetch spec) — hỏng ÂM THẦM một phần
Scope: web client (`profiles/vision_web_app.py` `_PAGE`) / kỹ thuật verify browser có Basic Auth
Nguồn: LOG Entry #457 · ĐO Playwright MCP port 8042/8043 (`document.baseURI` vs `location.origin`)
CẬP NHẬT 2026-07-27 (D-153):
- **Hiện tượng:** mở UI bằng URL nhúng credential → `fetch('/stats')` ném `TypeError: Request cannot be constructed
  from a URL that includes credentials`. `EventSource` và `<img>` **KHÔNG** bị hạn chế này ⇒ SSE + video vẫn chạy
  ⇒ trang **trông bình thường** nhưng `/stats` trống và **đường lui poll chết** = hỏng âm thầm MỘT PHẦN.
- **Gốc (đo chính xác):** `location.href` có thể sạch nhưng **`document.URL`/`document.baseURI` GIỮ credential** →
  path tương đối resolve thành URL-có-credential. `location.replace` về URL sạch KHÔNG chữa được (chỉ sửa `location`).
- **Fix:** dựng URL từ **`location.origin`** (không bao giờ chứa credential) cho mọi request. Đối chứng: absolute → 200; tương đối → TypeError.
- **Ảnh hưởng tới CÁCH VERIFY (điểm mù đã lộ):** dùng URL-nhúng-credential để né dialog Basic Auth (kỹ thuật #428)
  làm mọi `fetch` trong trang chết ⇒ số đo `/stats`, `/overlay` bị nhiễu, dễ kết luận sai là "server lỗi".
  **Cách đúng:** tiêm header `Authorization` bằng `page.route(...)` với URL SẠCH (đã dùng ở #457, cho Property 4 ✅).

### K-125 — ✅ Slot bulkhead được thu hồi cả khi viewer ngắt BẤT THƯỜNG: <1s khi kill process · ~120–150s khi mất mạng thật [phần sau chưa đo]
Scope: web serving (bulkhead D-152 · waitress) / vận hành 24/7
Nguồn: LOG Entry #459 · ĐO `tools/web_sse_capacity_probe.py --hold-seconds` + `/stats streams` (D-154) · ĐỌC `.venv/.../waitress/adjustments.py` + `channel.py`
CẬP NHẬT 2026-07-27:
- **Kill client đột ngột (không đóng socket tử tế) — ĐO THẬT:** giữ 4 kết nối (`streams=4/6`) → kill process →
  `streams=0/6` ngay mẫu đầu (**<1s**), giữ 0/6 suốt 12s. Cơ chế: waitress ghi chunk kế → broken pipe →
  generator bị close → `finally` chạy → `release()`.
- **Mất mạng THẬT (không FIN/RST) — suy từ SOURCE đã đọc, `[chưa kiểm]` thực nghiệm:** `channel_timeout=120`,
  `cleanup_interval=30`, `connection_limit=100`; `last_activity` chỉ cập nhật khi **gửi được byte** (`if sent:`)
  hoặc nhận data ⇒ partition làm buffer gửi OS đầy → không gửi được → `last_activity` đứng → waitress đóng
  channel sau ~120s (quét mỗi 30s) → release. **Biên ~120–150s**: mất TẠM dung lượng, KHÔNG rò rỉ vĩnh viễn.
- **Hệ quả vận hành:** trần bulkhead có thể tạm bị chiếm bởi viewer đã "chết" tối đa ~2,5 phút. Muốn nhanh hơn →
  hạ `channel_timeout` của waitress (app CHƯA expose cờ; chỉ thêm khi có nhu cầu thật — YAGNI).
- **Cách đo lại:** `python -m tools.web_sse_capacity_probe --hold-conns N --hold-seconds 300` rồi kill process, đọc `/stats`.

### K-126 — 🔒 RÀNG BUỘC TỐI CAO: tường lửa/kiểm soát mạng công ty — CẤM VƯỢT, phải DỪNG + BÁO
Scope: mọi truy cập mạng của AI (fetch tài liệu · tải gói · pull image · push git · gọi API)
Nguồn: LOG Entry #460 · chỉ thị trực tiếp của user 2026-07-27 ("nếu chặn tường lửa tuyệt đối không được vượt mà
báo lại… nếu vượt sẽ gây ảnh hưởng lớn cho tôi") · cùng nhóm K-117 (AI KHÔNG tắt VPN của user) · AGENTS §8 (v18)
**LUẬT:** truy cập bị CHẶN (firewall/proxy công ty/DNS/policy/TLS-inspection/registry nội bộ) → **DỪNG NGAY +
BÁO user + đề xuất cách HỢP LỆ** (xin mở quyền · dùng mirror nội bộ đã được duyệt · làm offline · bỏ bước đó).
**TUYỆT ĐỐI KHÔNG:** đổi/tắt VPN·firewall·antivirus·proxy·DNS·`hosts`; dùng tunnel/VPN/proxy khác; `--insecure`
/`--no-check-certificate`/tắt xác thực TLS; tìm domain-mirror để lách; retry vòng vo nhằm "lọt".
**Vì sao (bản chất):** vượt kiểm soát = vi phạm chính sách bảo mật doanh nghiệp → hậu quả pháp lý/kỷ luật cho
USER, KHÔNG phải cho AI. Giá trị của một phép đo KHÔNG bao giờ lớn hơn rủi ro đó. **Chặn là KẾT QUẢ HỢP LỆ của
phép đo** → ghi nhãn `[bị chặn — chưa kiểm]` và báo, đúng tinh thần §5 ("không kiểm được + việc quan trọng → DỪNG, HỎI").
**Phân loại TRƯỚC khi gán nhãn (chống kết luận sai):** dịch vụ chưa bật / thiếu gói / sai cấu hình **≠** tường lửa.
Nêu **thông điệp lỗi NGUYÊN VĂN** rồi mới phân loại. Ví dụ thật (#460): `open //./pipe/dockerDesktopLinuxEngine:
The system cannot find the file specified` = **Docker Desktop chưa bật**, KHÔNG phải bị chặn mạng.
**Ghi nhận trạng thái phiên #460:** chưa gặp lần chặn nào; `nginx.org` fetch được; hoạt động mạng chỉ gồm `git push`
lên repo của user + đọc docs chính chủ. AI KHÔNG tự bật Docker Desktop (dịch vụ mức hệ thống → để user quyết định).

### K-127 — ✅ Công cụ đo BÁO ĐỘNG GIẢ còn tệ hơn không có công cụ — `sleep` cố định trong probe ⇒ verdict "RÒ RỈ SLOT" SAI
Scope: phương pháp đo/verify (probe, test) · `tools/web_sse_capacity_probe.py`
Nguồn: LOG Entry #462 · D-156 · tiền lệ `wait_until` #288/#430 (đóng flaky bằng chờ-theo-sự-kiện)
CẬP NHẬT 2026-07-27:
- **Sự việc:** `--churn` (D-154) đợi `sleep(0.3)` rồi đọc `streams` để kết luận rò rỉ. Với churn NHẸ (6 conns, không
  có 503) → đúng. Với churn NẶNG (12 conns, vượt trần) → `active cuối=2`, verdict **"RÒ RỈ SLOT — release thiếu!"**
  ⇒ **SAI**: đo lại `/stats` sau đó thấy `streams=0/6` **suốt 15s** ⇒ chỉ là **TRỄ release** (release xảy ra khi
  server ghi chunk kế và phát hiện broken pipe — độ trễ PHỤ THUỘC TẢI).
- **Vì sao nguy hiểm:** verdict giả làm (a) đuổi bóng — sửa thứ không hỏng; (b) tệ hơn: **mất tin vào checker** →
  lần sau có rò rỉ THẬT thì bị bỏ qua. Đúng như C1-C9 drift-check phải có `self-test` để "guard the guard".
- **Fix bản chất:** thay `sleep` cố định bằng **chờ-theo-sự-kiện có deadline** (`_wait_active(target, deadline_s)`);
  chỉ kết luận rò rỉ khi QUÁ deadline mà chưa về mốc đầu. Sleep dài hơn = chỉ **đẩy** ngưỡng báo-động-giả (fix ngọn).
- **LUẬT RÚT RA (áp cho mọi phép đo tương lai):** khi đo một trạng thái đến **SAU MỘT SỰ KIỆN có độ trễ phụ thuộc
  tải** (release, reconnect, flush, restart) → **KHÔNG dùng sleep cố định**; dùng poll-tới-điều-kiện + deadline.
- **Cách phân biệt LAG vs LEAK:** đo lại sau một khoảng — về mốc đầu = lag; đứng mãi = leak thật.

### K-128 — 🟡 BẤT ĐỐI XỨNG observability: web app (khách hàng chạy) chỉ có **stdout**; slice app mới có log-file + `/metrics`
Scope: `profiles/vision_web_app.py` vs `profiles/vision_slice_app.py` · vận hành 24/7
Nguồn: LOG Entry #463 · grep xác nhận (`--log-file`/`ProductionLogHandle`/`FileLoggingObserver`/`--metrics-port` → **0 kết quả** trong web app) · `adapters/production_log_handle.py` (#443) · trả lời `[chưa kiểm]` của #462
CẬP NHẬT 2026-07-27:
- **Sự thật:** web app ghi MỌI tín hiệu ra **stdout bằng `print()`** — KHÔNG `--log-file`, KHÔNG `ProductionLogHandle`
  (non-blocking + rotating), KHÔNG `--metrics-port`. Những thứ đó **chỉ có** ở `vision_slice_app` (headless).
  ⇒ Câu `[chưa kiểm]` của #462 ("log throttle qua RotatingFileHandler?") có đáp án xác định: **đường đó KHÔNG tồn tại**.
- **Hệ quả vận hành:** phải chạy web app dưới **supervisor bắt + xoay stdout** (docker log driver / systemd-journald).
  Chạy tay trong terminal → mất log khi đóng. **Chạy detached mà stdout không ai đọc (hoặc đĩa đầy) → `print()` BLOCK
  → chặn thread đang xử lý request** (`[chưa kiểm]` empiric — nêu như rủi ro, chưa dựng thí nghiệm pipe-không-đọc).
  Log throttle (#462) giảm tần suất nhưng KHÔNG khử rủi ro này.
- **Lỗi tài liệu đã sửa cùng entry:** checklist deploy từng ghi "bật `--metrics-port` sau proxy" cho web app — cờ đó
  KHÔNG tồn tại ⇒ hướng dẫn một việc bất khả thi. Nay §4 của `deploy/README-tls-reverse-proxy.md` nói đúng sự thật.
- **CHƯA làm (chờ user quyết, KHÔNG tự mở rộng):** `--log-file` cho web app (tái dùng `ProductionLogHandle`, ~15 dòng)
  · `/metrics` Prometheus cho web app · alerting. Lý do hoãn: stdout+supervisor là chuẩn 12-factor và khớp
  `docker-compose.cpu-demo.yml`; thêm cờ = 2 lối làm cùng việc cho nhu cầu chưa ai nêu.
