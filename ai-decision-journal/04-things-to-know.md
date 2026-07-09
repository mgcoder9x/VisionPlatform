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

### K-014 — 🟡 Q2 frame-drop: BOUND xác nhận thực nghiệm ≤ n_slots; throughput dưới tải fps thật CHƯA đo
Scope: shm-ring-epoch-switchover / Q2
Nguồn: LOG Entry #155 · `tests/test_switchover_q2_bound.py` · design.md §Q2
CẬP NHẬT 2026-07-03 (D-022): **bound ≤ n_slots đã chứng minh THỰC NGHIỆM** — worst-case (ring đầy frame chưa đọc) drop = 4 = n_slots; đối chứng drain trước switchover → drop = 0. 2 test deterministic pass.
CÒN 🔴: số throughput/drop dưới **tải fps thật + đa reader** (timing-dependent, cần perf harness riêng) — chưa đo, KHÔNG bịa. Đóng khi: có perf harness đo drop@30fps thật (gắn tuning K-004).

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

### K-030 — 🟡 (2026-07-05) RTSP ffmpeg/opencv Windows bị 401 với Dahua dù creds đúng
Scope: `adapters/rtsp_frame_source.py` · kết nối camera thật
Nguồn: LOG Entry #189 · chạy thật (401 từ camera) · VLC xác nhận creds đúng
Nội dung:
- Máy Windows TỚI được camera (nhận `method OPTIONS failed: 401 Unauthorized` = camera phản hồi → reachable).
- ffmpeg bundled trong opencv-python (Windows) bắt tay DIGEST auth với Dahua thất bại (cả khi `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`), DÙ admin/<pass> chạy trên VLC.
- KHÔNG phải lỗi adapter (RtspFrameSource 7 test pass). Là vấn đề ffmpeg(bundled opencv) vs auth Dahua.
- **ĐÍNH CHÍNH (Entry #197, verify WSL):** giả thuyết "chạy Linux sẽ ổn" = **SAI**. Test thật trên WSL2 Ubuntu (opencv-python-headless, ffmpeg bundled) → **401 Y HỆT**. Vậy KHÔNG phụ thuộc OS; là ffmpeg-của-opencv vs Dahua này. VLC dùng live555 (stack khác) nên được. Docker/Linux KHÔNG tự giải.
Hướng CÓ THỂ giải (chưa verify): (a) SYSTEM ffmpeg (apt, cần sudo) khác bundled? (b) opencv build GStreamer (như VLC); (c) HTTP snapshot Dahua `cgi-bin/snapshot.cgi` (HTTP digest robust, né RTSP); (d) record clip VLC → video file (chạy ngay). Cho "xem detect": (d)+.onnx nhanh nhất.
Đóng khi: 1 trong các hướng trên chạy lấy được frame thật.

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
