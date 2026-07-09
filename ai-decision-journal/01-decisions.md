# 01 — Quyết định AI tự ra (spec/yêu cầu KHÔNG nói)

> Định dạng + quy tắc: xem `README.md` §1. Mỗi entry BẮT BUỘC có `Nguồn` + `Evidence`.
> Trạng thái: ✅ verify · 🟡 làm rồi chưa kiểm đủ · 🔴 chưa verify/rủi ro · ↩️ đã bị đảo.
> Seed từ sub-spec `shm-ring-epoch-switchover` + `#05 shm-production-hardening` (đã verify từ LOG #105–#127).

---

### D-001 — 2026-07-02 — Control-plane = segment tên-cố-định chứa {epoch, ring_name}
Status: ✅
Scope: shm-ring-epoch-switchover / design.md, Task 1.1–1.2
Nguồn: LOG Entry #119, #121, #122 · `kernel/shm_control_plane_layout.py` · `runtime/ipc/ring_control_plane.py`
Evidence: pytest 8 test layout + 4 test control-plane; full 192 passed/1 skipped; lint 5 kept/0 broken (LOG #122)
Links: C-001, T-001
Nội dung: Bên đọc tìm ring hiện hành qua 1 SHM segment "well-known" tên cố định, chứa epoch + tên ring; publish ghi ring_name TRƯỚC, `current_epoch` CUỐI (authority atomic). CP_SEGMENT_BYTES=128 (magic 0x53484D43 / version / epoch@16 / ring_name[96]).
Vì sao: `new_ring_name()` = `uuid4().hex` (ngẫu nhiên, KHÔNG suy diễn được từ epoch) → không thể "publish epoch rồi suy ra tên". Phải có nơi cố định lưu tên thật.
⚠️ SẼ ĐẢO MỘT PHẦN nếu chốt H2 (K-012): switchover đổi từ "tạo ring tên mới" → "chọn pool[N%K] + reset + bump epoch" (tên pool cố định). Chờ user chốt.

### D-002 — 2026-07-02 — Authority switchover đặt ở tầng application (RingSupervisor), không per-slot
Status: ✅ (authority-ở-application GIỮ) · ↩️ phần "tạo ring mới" ĐÃ ĐẢO bởi D-013 (H2: pool.activate tái dùng)
Đảo bởi: D-013/C-006 (LOG #136) — switchover không còn tạo ring uuid mới; dùng RingPool.activate. Phần "supervisor là nơi duy nhất quyết định switchover" VẪN đúng.
Scope: shm-ring-epoch-switchover / Task 3
Nguồn: LOG Entry #124 · `application/ring_supervisor.py`
Evidence: 3 test T-A (deterministic, ring_factory tiêm); full 198 passed/1 skipped; lint 5 kept/0 broken (LOG #124)
Links: T-005
Nội dung: `RingSupervisor(control_plane, ring_factory, obs)`: `on_event` chỉ trigger khi `shm_ring_rebuild_requested`; `switchover()` = read epoch → +1 → `new_ring_name()` → `ring_factory(name, epoch)` → `cp.publish` → emit start/completed. `ring_factory` tiêm (DI).
Vì sao: quyết định chuyển ring là chính sách vòng đời (application), không phải cơ chế slot (runtime). Tách để test được không cần cấp phát SHM thật.

### D-003 — 2026-07-02 — Wave 3 làm ADDITIVE, không sửa ShmFrameWriter/ShmFrameReader
Status: ✅
Scope: shm-ring-epoch-switchover / Task 4.1
Nguồn: LOG Entry #125 · `bootstrap_current_ring(cp, ring_opener)`
Evidence: 3 test; full 201 passed/1 skipped; lint 5/0 (LOG #125)
Links: T-003
Nội dung: Thêm hàm mới `bootstrap_current_ring` (DI `ring_opener`) thay vì đụng vào Writer/Reader hiện có; epoch=0 → RuntimeError.
Vì sao: giữ ZERO regression trên 180+ baseline test; giảm blast-radius khi thêm switchover.

### D-004 — 2026-07-02 — Teardown = OS handle ref-count; BỎ hẳn attach_count/cp_lock  ⟵ fix tận gốc
Status: ✅
Scope: shm-ring-epoch-switchover / Task 2 (revert-forward sang phương án B), Task 4.2/5
Nguồn: LOG Entry #126 · thực nghiệm `_shm_lifecycle_probe` (Windows) · `ShmRingBuffer.close()` (Entry #127)
Evidence: full 198→200 passed/1 skipped; lint 5/0 (LOG #126, #127); commit `db0fc21`(refactor B), `2eb18c9`, `b812071`
Links: C-002, T-002, K-003
Nội dung: Bỏ `attach_register/detach/attach_count/cp_lock` khỏi `RingControlPlane`. Teardown = mỗi bên `close()` handle ring cũ khi rời epoch; OS tự giải phóng memory ở handle CUỐI. Byte @8 control-plane = RESERVED. `ShmRingBuffer.close()` = chỉ-đóng handle, KHÔNG unlink (creator vẫn dùng được).
Vì sao (bản chất): thực nghiệm chứng minh Windows OS đã tự ref-count handle (memory sống tới handle cuối; attach lại sau khi đóng hết → FileNotFoundError). `attach_count` thủ công vừa ĐẶT SAI CHỖ (toàn cục, không tách được ring cũ) vừa THỪA (trùng việc OS đã làm) → đây là bỏ nguyên nhân, không vá triệu chứng.

### D-005 — 2026-06-24 — Tiêm `liveness_fn` và `obs` (ObservabilityHook) vào ShmRingBuffer
Status: ✅
Scope: shm-production-hardening / Task 4.2, Task 6
Nguồn: LOG Entry #106, #109 · `runtime/ipc/shm_frame_ring.py`
Evidence: recovery 11 test + observability 6 test; full 148→162 passed/1 skipped; lint 5/0 (LOG #106, #109)
Links: T-004
Nội dung: `ShmRingBuffer(..., liveness_fn=owner_liveness, obs=NoOpHook)`. Liveness & quan sát là dependency tiêm được, mặc định an toàn (psutil thật / no-op).
Vì sao: cho phép test recovery deterministic (không cần process thật) + không ép cứng logging; mặc định no-op nên 16 test #05 gốc không đổi hành vi.

### D-006 — 2026-06-24 — `register_writer()` là API EXPLICIT, không auto trong __init__
Status: ✅
Scope: shm-production-hardening / Task 7 (single-writer invariant)
Nguồn: LOG Entry #110 · ctrl segment 64B (writer registry)
Evidence: 6 test single-writer; full 168 passed/1 skipped; lint 5/0 (LOG #110)
Links: C-003, T-003
Nội dung: Composition root gọi `register_writer()` tường minh: trống→claim · ALIVE→`SingleWriterViolation` · DEAD→emit `shm_ring_rebuild_requested`+reject (KHÔNG takeover) · UNKNOWN→reject · gọi>1→raise.
Vì sao: auto trong __init__ sẽ phá các test tạo nhiều writer + ép cứng không cần thiết; enforce invariant tại điểm đăng ký là đủ và đúng ranh giới.

### D-007 — 2026-06-24 — ring_epoch mặc định 0 + tham số read() optional (backward-compat)
Status: ✅
Scope: shm-production-hardening / Task 8
Nguồn: LOG Entry #111 · DTO `ShmFrameRefData.ring_epoch=0`
Evidence: ring_epoch 5 test; full 180 passed/1 skipped; lint 5/0 (LOG #111)
Links: —
Nội dung: DTO thêm field `ring_epoch=0` (default → không phá construct cũ); `read(..., ring_epoch=None)` mặc định → 16 test #05 không đổi; ref stale (epoch cũ) → trả None.
Vì sao: giữ tương thích ngược thay vì sửa mọi call-site.

### D-008 — 2026-07-03 — WriterEpochCoordinator: additive + check-on-write + DI writer_factory
Status: ✅
Scope: shm-ring-epoch-switchover / Task 4.2
Nguồn: LOG Entry #129 · `application/writer_epoch_coordinator.py` · test `test_switchover_writer_coordinator.py`
Evidence: 6 test coordinator; full 206 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật env mới)
Links: T-007, C-002(teardown B), K-012
Nội dung: Bọc quanh 1 ShmFrameWriter; mỗi `write()` đọc `read_current()`, epoch đổi → mở ring mới (`ring_opener` DI) → `register_writer()` TRƯỚC frame đầu → swap → `old.close()` (teardown B). Đặt ở application. Thêm DI `writer_factory=ShmFrameWriter`. Edge `SingleWriterViolation` ring mới → fail-fast (đóng handle ring mới, giữ epoch cũ).
Vì sao: additive → 0 regression trên baseline 200; check-on-write → không cần thread poll; DI → test deterministic không cấp SHM thật (đúng phạm vi Task 4.2 in-proc).

### D-009 — 2026-07-03 — ReaderEpochCoordinator: additive + check-on-read (đối xứng writer)
Status: ✅
Scope: shm-ring-epoch-switchover / Task 4.3
Nguồn: LOG Entry #130 · `application/reader_epoch_coordinator.py` · test `test_switchover_reader_coordinator.py`
Evidence: 6 test reader; full 212 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-008, K-012
Nội dung: Bọc quanh 1 ShmFrameReader; mỗi `read_ref()` đọc `read_current()`, epoch đổi → mở ring mới (`ring_opener`) → swap reader → `old.close()` (teardown B) → delegate. Reader KHÔNG register_writer. DI `reader_factory=ShmFrameReader`.
Vì sao: đối xứng D-008; check-on-read đúng thứ tự (supervisor publish N+1 trước khi có ref N+1 → reader thấy kịp, không đọc nhầm ring cũ). Dùng stale-check sẵn có của ShmFrameReader (ref epoch cũ→None) → không code lại logic.

### D-010 — 2026-07-03 — Supervisor giữ handle ring hiện tại + close ring cũ khi switchover (teardown B)
Status: ↩️ ĐÃ ĐẢO bởi D-013 (H2) — supervisor KHÔNG còn close ring cũ; POOL giữ ring suốt phiên, teardown=pool.close_all() lúc shutdown.
Đảo bởi: D-013/C-006 (LOG #136). Test D-010 (supervisor-close-prev) đã gỡ khỏi `test_switchover_teardown.py`. Primitive `ShmRingBuffer.close()` vẫn dùng (nền pool.close_all) — 2 test ring thật giữ nguyên.
Scope: shm-ring-epoch-switchover / Task 5
Nguồn: LOG Entry #131 · `RingSupervisor.switchover()` · test `test_switchover_teardown.py`
Evidence: 4 test teardown (2 real-ring guard win32); full 216 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0
Links: D-008, D-009, K-003
Nội dung: Supervisor (creator) GIỮ handle ring hiện tại (Windows: block sống khi còn ≥1 handle), sau `publish` thì `prev_ring.close()` + emit `shm_ring_teardown_pending`. Consumer (writer/reader coordinator) tự close handle khi migrate → OS giải phóng ở handle CUỐI. Test ring thật chứng minh: mọi handle đóng → attach lại → FileNotFoundError; còn 1 handle → sống.
Vì sao: teardown quyết định B dựa OS ref-count handle, KHÔNG biến đếm. Supervisor buộc phải giữ handle nếu không ring biến mất ngay khi tạo (Windows). POSIX unlink để T-C (không claim).
⚠️ SẼ ĐẢO nếu chốt H2 (K-012): pool giữ K ring suốt phiên → supervisor KHÔNG close-per-migrate mà GIỮ pool, teardown = shutdown-only (moot K-003). Chờ user chốt.

### D-011 — 2026-07-03 — CHỐT hướng H2 (ring pool) cho K-012 + cơ chế nền `reset_for_reuse()`
Status: ✅ (quyết định + cơ chế nền) · ⬜ (RingPool + supervisor variant + T-B chưa làm)
Scope: shm-ring-epoch-switchover / K-012, Task 6 (H2 variant)
Nguồn: LOG Entry #132/#133/#134 · `K-012-lock-provisioning-analysis.md` (H2 + §6) · `ShmRingBuffer.reset_for_reuse()`
Evidence: 5 test reuse; full 221 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: C-006, D-002(sẽ đảo), D-010(sẽ đảo), K-012
Nội dung: Chọn **H2 ring-pool tái dùng vòng** (user ủy quyền "theo khuyến nghị"). Giải K-012 bằng NÉ cấp-phát-động: pool ring tạo 1 lần, lock thừa kế 1 lần; switchover = `reset_for_reuse(new_epoch)` (xoá slot→FREE gồm QUARANTINED, xoá reader+writer registry, bump ring_epoch GHI CUỐI). Cơ chế nền `reset_for_reuse` đã code+test (additive, creator-only, contract drain-before-reuse do caller đảm bảo).
Vì sao: locking rủi ro thấp (dùng lại lock verified) + real-time (không alloc giữa luồng) + bộ nhớ đoán trước + moot K-003. Bằng chứng khả thi: ring_epoch live cross-process (D-... test poke ctrl).

### D-012 — 2026-07-03 — RingPool (H2 bước 1): pool K ring cố định + opener attach-by-name
Status: ✅ (component + opener) · ⬜ (supervisor variant + T-B chưa nối)
Scope: shm-ring-epoch-switchover / K-012, Task 6 (H2)
Nguồn: LOG Entry #135 · `runtime/ipc/ring_pool.py` · test `test_switchover_ring_pool.py`
Evidence: 9 test pool; full 230 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-011, C-006, K-012, K-004
Nội dung + LÝ DO CHÍNH XÁC (mỗi lựa chọn neo ràng buộc thật):
- Tên `{uuid phiên}_r{i}`: uuid mỗi phiên → cold-start safe (không đụng segment sót crash, #05 T9); hậu tố cố định → attach-by-name bằng lock thừa kế (bản chất H2).
- `pool_size` default 3, min 2: 2 = tối thiểu (old drain + new active chồng nhau); 3 = +1 thế hệ đệm cho rebuild dồn (drain chặn bởi READ_LEASE). K chính xác cần đo SLA (như K-004) — KHÔNG claim 3 tối ưu.
- `activate(epoch)` = `ring_for_epoch(epoch).reset_for_reuse(epoch)`: pool[epoch%K] lần trước ở epoch-K < epoch → reset ép đơn điệu (dùng lại cơ chế verified D-011).
- `slot_locks_map()` + `make_pool_opener(locks_map)`: mảnh ghép GIẢI K-012 — truyền toàn bộ lock pool qua spawn, worker `opener(name)` attach ring pool bằng lock thừa kế.
Vì sao: né cấp-phát-động (H2). Layer runtime/ipc (chỉ import ShmRingBuffer → lint giữ 5/0).

### D-013 — 2026-07-03 — RingSupervisor chuyển sang H2 (pool.activate) — ĐẢO D-002 (tạo ring) + D-010 (close-prev)
Status: ✅
Scope: shm-ring-epoch-switchover / K-012, Task 6 bước 2
Nguồn: LOG Entry #136 · `application/ring_supervisor.py` · test `test_switchover_supervisor.py`
Evidence: 4 test supervisor (3 FakePool + 1 RingPool thật) + 2 test teardown primitive; full 229 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-002(↩️), D-010(↩️), D-011, D-012, C-006, K-012
Nội dung + LÝ DO CHÍNH XÁC:
- Constructor `RingSupervisor(control_plane, ring_pool, obs)` — TIÊM pool (composition root sở hữu vòng đời pool → supervisor thuần điều phối, SRP + test được).
- `switchover()` = `pool.activate(N)` (reset_for_reuse + bump) + publish. **Đảo D-002** vì `mp.Lock` không cấp được cho worker đang chạy → phải TÁI DÙNG pool ring, không tạo mới.
- Bỏ close-prev + `_current_ring`. **Đảo D-010** vì pool sở hữu ring suốt phiên → supervisor close sẽ phá tái dùng; teardown = `pool.close_all()` lúc shutdown (moot K-003).
- Gỡ 2 test D-010 lỗi thời khỏi `test_switchover_teardown.py`; giữ 2 test primitive `close()` (nền pool.close_all).
Vì sao: hoàn tất chuyển authority sang mô hình pool H2 (đúng bản chất K-012), không để lại đường tạo-ring-mới song song (tránh nợ dual-path).

### D-014 — 2026-07-03 — Test tích hợp in-process toàn hệ switchover (H2 bước 3)
Status: ✅
Scope: shm-ring-epoch-switchover / K-012 bước 3
Nguồn: LOG Entry #137 · test `test_switchover_integration.py`
Evidence: 2 test tích hợp; full 231 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-011, D-012, D-013, K-012
Nội dung: Nối THẬT RingPool + RingControlPlane + RingSupervisor + Writer/ReaderEpochCoordinator + ShmFrameWriter/ShmFrameReader (qua make_pool_opener). Chứng minh: ghi→đọc frame khớp; rebuild→switchover→writer/reader chuyển ring; ref epoch cũ→None; **tái dùng pool vòng epoch 1→4 (pool_size=3) với SHM thật**; single-writer/ring giữ (writer thứ 2 raise).
Vì sao (lý do chính xác): đây là cổng verify IN-PROCESS cuối trước T-B — dùng SHM + mp.Lock THẬT (chia sẻ qua object trong 1 process), chứng minh toàn bộ wiring + cyclic reuse đúng. GIỚI HẠN đã ghi: 1 process → CHƯA chứng minh lock thừa kế cross-process (Task 6 T-B).

### D-015 — 2026-07-03 — T-B cross-process THẬT (spawn) — GIẢI K-012 + đóng K-002
Status: ✅ (Windows, 5/5 không flaky)
Scope: shm-ring-epoch-switchover / Task 6 (T-B)
Nguồn: LOG Entry #138 · test `test_switchover_cross_process.py`
Evidence: T-B 5/5 pass (spawn thật); full 232 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-011..D-014, K-012, K-002, K-013
Nội dung + LÝ DO CHÍNH XÁC:
- Worker process riêng nhận `locks_map` (dict toàn bộ lock pool) qua Process args (thừa kế) → writer coordinator bootstrap + ghi; parent (supervisor+reader) switchover epoch 2 giữa stream → worker frame kế tự sang ring 2 + KHOÁ được → parent đọc frame epoch 2 cross-process. `got_epoch2>=1` = **bằng chứng locks thừa kế phủ ring đích switchover** (crux K-012).
- Chống flaky: ack-queue serialize (worker ghi 1 → parent đọc+ack → ghi tiếp) → không lapping slot → deterministic (verify: 5/5 pass).
Vì sao đây là bằng chứng đủ: nếu locks_map KHÔNG phủ ring 2, worker sẽ lỗi/deadlock khi ghi ring 2 → got_epoch2=0 → test fail. Pass ⇒ H2 giải K-012 đúng cross-process.
GIỚI HẠN (thật): chỉ Windows (guard skip non-win32); POSIX ở T-C (K-003). Q2 frame-drop CHƯA đo (T-B serialize không tải thật) — không bịa số.

### D-016 — 2026-07-03 — Task 8 PBT (Hypothesis) Property 1-5 + thêm dep hypothesis
Status: ✅
Scope: shm-ring-epoch-switchover / Task 8
Nguồn: LOG Entry #139 · test `test_switchover_pbt.py` · pyproject `[dev]` +hypothesis>=6.0
Evidence: 5 property pass (hypothesis 6.156.1); full 237 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-011, D-013, K-004
Nội dung + LÝ DO CHÍNH XÁC:
- Thêm `hypothesis>=6.0` vào [dev] (fix gốc: khai báo dep, không cài lẻ) — Task 8 spec yêu cầu PBT.
- P2 (epoch đơn điệu) + P5 (lọc event) dùng **FakeCP in-memory** — vì logic thuần không cần SHM → tránh churn SHM trong Hypothesis (nhanh, không leak segment). P1/P2b/P3 dùng **1 ring THẬT** + reset_for_reuse để đi epoch (max_examples 15-25, deadline=None vì có I/O).
Vì sao: PBT sinh input tự động phủ ca biên các bất biến lõi (đơn điệu, stale, single-writer, lọc event); Hypothesis KHÔNG tìm được phản chứng ⇒ củng cố tính đúng. P4 (no-leak) là I/O nền tảng → để T-C, không PBT (không bịa PBT cho thứ không thuần logic).

### D-017 — 2026-07-03 — Task 9: observability taxonomy END-TO-END + catalog + regression cuối
Status: ✅
Scope: shm-ring-epoch-switchover / Task 9 (Req 6.1/6.2)
Nguồn: LOG Entry #140 · test `test_switchover_observability.py` · `observability-taxonomy.md`
Evidence: 2 test observability; full 239 passed/1 skipped; lint 5 kept/0 broken; T-B 3/3; getDiagnostics 0 (chạy thật)
Links: D-013, D-015
Nội dung + LÝ DO CHÍNH XÁC:
- Test taxonomy END-TO-END: 1 `RecordingHook` tiêm xuyên pool+supervisor+coordinator+opener → 1 vòng rebuild phải thấy đủ 6 event lifecycle (started/completed/reset_for_reuse/writer_switched/reader_switched/teardown_pending) + kiểm field. Lý do: các emit lẻ đã test rời; giá trị Task 9 = chứng minh chúng CÙNG chảy qua 1 hook (đúng nhu cầu vận hành 1 sink).
- Test default-noop: không truyền obs → hook ngoài không nhận gì (no-op không tốn, hợp real-time).
- Req 6.2 (fail-fast magic sai) KHÔNG viết lại — đã có `test_attach_wrong_magic_fail_fast` (trỏ tới, không nhân đôi).
- `observability-taxonomy.md`: catalog 13 event (tên/khi phát/fields/nguồn) neo grep thật — cho dashboard/alert sản phẩm 24/7.
Vì sao: đóng Task 9 với bằng chứng end-to-end + tài liệu vận hành, không phình test trùng.

### D-018 — 2026-07-03 — Task 7 T-C (no-leak) + trả lời Q2 (bound cấu trúc) → sub-spec switchover ĐÓNG (Windows)
Status: ✅ (Windows) · 🔴 POSIX K-003 · 🔴 Q2 số-đo-tải
Scope: shm-ring-epoch-switchover / Task 7 + Q2
Nguồn: LOG Entry #141 · test `test_switchover_leak.py` · design.md §Overview Q2
Evidence: 3 test leak; full 242 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: D-011, D-012, K-003, K-004
Nội dung + LÝ DO CHÍNH XÁC:
- No-leak cốt lõi dưới H2 = **số segment không tăng theo switchover** (pool tái dùng, không tạo mới). Test: 20 switchover → tập tên segment KHÔNG đổi (platform-independent) + bounded theo pool_size (K=2/3/5). Đây là bằng chứng no-leak-by-growth verify được không cần /dev/shm.
- close_all frees all: guard win32 (OS ref-count handle); POSIX → K-003 (không claim).
- **Q2 trả lời bằng BOUND CẤU TRÚC ≤ n_slots** (không bịa số đo): check-on-write (D-008) → writer chuyển ring TRƯỚC khi ghi → mis-write ring cũ = 0; frame mất = READY chưa đọc trong ring cũ ≤ n_slots. Số dưới tải thật vẫn 🔴 (cần kịch bản tải).
Vì sao: đóng no-leak bằng tính chất bản chất (bounded reuse) thay vì đo leak trực tiếp (không đo được trên Windows) — trung thực + verify được.
KẾT: **sub-spec switchover Task 1-9 ✅ trên Windows.** Còn treo: 🔴 K-003 (POSIX teardown) · 🔴 Q2 số-đo-tải · 🔴 K-001 (ARM).

### D-019 — 2026-07-03 — Tạo NỀN bài dạy switchover `code-lessons/05b-ring-switchover/`
Status: ✅ (nền) · ⬜ (12 mẩu chi tiết + Feynman)
Scope: dạy học (PHA 3 mở rộng cho phần switchover) — theo LESSON-RULES
Nguồn: LOG Entry #142 · `code-lessons/05b-ring-switchover/00-cau-chuyen.md` + `00-muc-luc.md` · `code-lessons/00-INDEX.md`
Evidence: 2 file nền tạo; INDEX cập nhật (đọc lại LESSON-RULES + cau-chuyen #05 để nối mạch)
Links: D-011..D-018
Nội dung + LÝ DO CHÍNH XÁC:
- Tạo folder RIÊNG `05b-ring-switchover` (không nhét vào 12 mẩu #05, không chiếm slot #06): switchover có VÒNG CUNG riêng (vấn đề K-012 → giải H2) → xứng 1 cau-chuyen riêng (LESSON-RULES §3.5). "b" = nối tiếp #05, map sub-spec.
- `00-cau-chuyen.md`: 6 nhịp (tổng quan nối #05 → vấn đề K-012 + Forces → 3 hướng H1/H2/H3 → chốt H2 + cái giá → triển khai → nên/tránh). Gloss mọi thuật ngữ (epoch/control-plane/pool/mp.Lock/stale-ref...) — không name-drop treo.
- `00-muc-luc.md`: 12 mẩu map file code THẬT (control-plane → K-012/pool → coordinator → T-B → no-leak/Q2/observability), tất cả ⬜.
Vì sao: theo LESSON-RULES §6 (nền TRƯỚC, mẩu chi tiết sau — mỗi mẩu cần đọc lại code + quote nguyên văn). Mọi khẳng định neo code + test đã chạy (242 passed/1 skipped) + journal D-011..018 (không bịa).
**Tiến độ mẩu:** ✅ **ĐỦ 12/12 mẩu 05b** (01 vì-sao · 02 control-plane layout · 03 RingControlPlane · 04 bootstrap · 05 K-012 · 06 RingPool · 07 reset_for_reuse · 08 supervisor · 09 writer-coord · 10 reader-coord · 11 T-B · 12 no-leak/Q2/observability) — log #143–149, quote nguyên văn + neo test. ⬜ Chờ Feynman (05b + 05 gốc) + sơ đồ drawio 05b (tùy chọn).

### D-020 — 2026-07-03 — Fix A cho K-015: cưỡng chế drain-before-reuse (refuse + defer+retry)
Status: ✅
Scope: shm-ring-epoch-switchover / reset_for_reuse + RingPool.activate + RingSupervisor.switchover
Nguồn: LOG Entry #153 · test `test_switchover_drain_guard.py`
Evidence: 6 test drain-guard; full 248 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 0 (chạy thật)
Links: K-015, D-011, D-013
Nội dung + LÝ DO CHÍNH XÁC:
- `reset_for_reuse -> bool`: pass 0 (drain guard) reap-dead-readers rồi nếu `_reader_protects_slot` bất kỳ slot → REFUSE (return False, chưa đụng gì) + emit `shm_reset_blocked_active_readers`. Tái dùng helper #05 có sẵn (không phát minh).
- `RingPool.activate -> Optional[str]`: None khi reset bị chặn.
- `RingSupervisor.switchover -> Optional[int]`: None + emit `shm_switchover_deferred` khi chưa drain (KHÔNG publish, KHÔNG bump epoch) → an toàn.
Vì sao chọn Fix A + caller-a (defer+retry): cưỡng chế tại CƠ CHẾ (bất biến do code đảm bảo, không dựa docstring) = fix bản chất; defer+retry đơn giản+an toàn nhất (switchover thử lại lần rebuild sau). Two-pass (check-all rồi mới clear) = refuse toàn phần, không xoá dở. TOCTOU không khai thác được: ring đang reset là pool[N%K] (epoch N-K cũ), control-plane vẫn trỏ epoch N-1 → không reader MỚI nào target ring đó.
Tương thích: không phá test cũ (mọi reset cũ ở trạng thái drained). Backward: đổi return type None→bool/Optional (test cũ không check return value → OK).

### D-021 — 2026-07-03 — Stress đa-process reader cross-process (đóng K-006)
Status: ✅ (Windows) · 🔴 POSIX chờ (cùng K-003)
Scope: #05 multi-reader / cross-process
Nguồn: LOG Entry #154 · `tests/test_multi_reader_cross_process.py`
Evidence: 2 test, chạy 5/5 không flaky; full 250 passed/1 skipped; lint 5 kept/0 broken (chạy thật)
Links: K-006
Nội dung + LÝ DO CHÍNH XÁC:
- Test (a) N reader PROCESS riêng, mỗi process 1 slot riêng, barrier đồng bộ đọc đồng thời → tất cả đọc ĐÚNG data (`np.all(frame==v)`, không torn). Deterministic (mỗi reader 1 slot → không đua same-slot).
- Test (b) N reader cùng 1 slot → mỗi reader OK(đúng)/None, KHÔNG TORN/ERROR (multi-reader registry cross-process an toàn). Assert no-corruption (không assert số OK cụ thể vì timing → tránh flaky).
Vì sao chọn K-006 (trong các món còn lại): AI-làm-được + verify Windows + ASSERTABLE (đúng/sai rõ) — khác K-014 (chỉ số quan sát, khó assert) / K-001/003 (cần OS-HW khác) / K-005 (rủi ro). Lock thừa kế qua Process args (như T-B). Chống flaky: barrier + test (a) mỗi reader slot riêng.

### D-022 — 2026-07-03 — Q2 bound frame-drop xác nhận thực nghiệm ≤ n_slots (K-014 một phần)
Status: 🟡 (bound ✅ · throughput-tải 🔴)
Scope: shm-ring-epoch-switchover / Q2
Nguồn: LOG Entry #155 · `tests/test_switchover_q2_bound.py`
Evidence: 2 test (worst-case drop=4=n_slots≤4 · drain→drop=0); full 252 passed/1 skipped; lint 5 kept/0 broken (chạy thật, in số drop)
Links: K-014, D-018, D-008
Nội dung + LÝ DO CHÍNH XÁC: dựng worst-case (ghi 12 frame không đọc → chỉ n_slots=4 thành READY do backpressure) → switchover → mọi ref epoch cũ stale → drop = 4 = số chưa đọc ≤ n_slots. Đối chứng: đọc-hết-trước-switchover → drop=0 (chứng minh mất-frame CHỈ do frame chưa đọc, không do mis-write — khớp check-on-write D-008). 
GIỚI HẠN thật (không bịa): đây đo BOUND deterministic in-process, KHÔNG phải throughput dưới tải fps thật (số đó timing-dependent → perf harness riêng, vẫn 🔴). Chỉ khẳng định bound đúng + tight (worst-case = n_slots).


### D-023 — 2026-07-04 — Vấn đề #06: dời InlineInferenceClient adapters→application; InferenceRequest nhúng ShmFrameRefData (ring_epoch)
Status: ✅ (verify thật — 9 test #06 pass, full 261/1, lint 5/0)
Scope: implement/06-inference-inline / Design step-06 (ERRATA E-06-1/E-06-2)
Nguồn: LOG Entry #157 (PHA 1), #158 (PHA 2 verify) · `pyproject.toml` contract #4/#5 · `shm_frame_ring.py` (`read_ref` dùng `ref.ring_epoch`; writer stamp `ring_epoch`) · `implement/06-inference-inline/00-brief.md`
Evidence: `pytest tests/test_step_06_inference.py` = 9 passed; full 261 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 5 file = 0
Links: C-007, D-007 (ring_epoch), K-014
Nội dung + LÝ DO CHÍNH XÁC:
- **F-1:** Design đặt `InlineInferenceClient` ở `adapters/` nhưng client import `runtime.ipc.ShmFrameReader` → vi phạm contract import-linter #5 (adapters là leaf, cấm import runtime). Bản chất: client là SERVICE ĐIỀU PHỐI (ghép runtime reader + IDetector port DI), không phải leaf-adapter → thuộc `application/` (cùng chỗ ring_supervisor/writer_epoch_coordinator). Layering domain←kernel←runtime←application cho phép application→runtime; contract #4 chỉ cấm application→adapters/profiles (client dùng *port*, không import FakeDetector cụ thể → hợp lệ). FakeDetector ở lại adapters (leaf, chỉ domain+kernel).
- **F-2:** `InferenceRequest` Design thiếu `ring_epoch`. `read()`/`read_ref()` dùng ring_epoch để stale-detect (P0-3, D-007). Không có epoch → sau switchover #05, request epoch cũ có thể đọc nhầm frame. Khuyến nghị: request mang đủ field ShmFrameRefData (gồm ring_epoch) + client dùng `read_ref(ref)`.
Vì sao: cả hai là fix BẢN CHẤT để #06 khớp kiến trúc thật + tích hợp đúng invariant switchover vừa xây (#05). Chưa code — dừng chờ duyệt (§1.7 PLAN-FIRST, deviation không tầm thường vs Design).


### D-024 — 2026-07-04 — Vấn đề #07: BoundedQueue 4 policy — giữ nguyên thiết kế Design (không deviation) + docstring K-016
Status: ✅ (verify thật — 11 test #07 pass, full 272/1, lint 5/0)
Scope: implement/07-backpressure / Design step-07
Nguồn: LOG Entry #160 · `kernel/backpressure.py` · `tests/test_step_07_backpressure.py` · `pyproject.toml` contract #2 (kernel)
Evidence: `pytest tests/test_step_07_backpressure.py` = 11 passed; full 272 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 2 file = 0
Links: K-016, D-005 (obs hook, wiring hoãn #08)
Nội dung + LÝ DO CHÍNH XÁC:
- Giữ NGUYÊN BoundedQueue của Design (khác #06 phải sửa) vì valid diện rộng (doubt-driven) thấy đã đúng: Condition+wait_for chống spurious wakeup; notify() đủ (1 get giải phóng 1 chỗ → wake 1 producer); DROP_OLDEST net-size-không-đổi chỉ notify not_empty; metrics under-lock thread-safe; get vs get_or_raise xử lý None-ambiguity. Không đổi cái đang đúng = fix bản chất.
- +4 test phụ (get None-timeout, get_or_raise raise queue.Empty, props, maxsize<1 ValueError) đủ 11 + phủ biên.
- kernel/backpressure.py hợp lệ layer: contract #2 kernel không cấm threading/collections/queue/enum/typing (chỉ cấm cv2/torch/zmq/multiprocessing/shared_memory/psutil/runtime/application).
- 4 policy (bỏ SAMPLE/DEGRADE khỏi queue — SRP: queue lo "đầy", source lo "tiết chế").


### D-025 — 2026-07-04 — Vấn đề #08: observability (structlog + log_context + InMemoryMetrics) — giữ nguyên thiết kế + style cleanup
Status: ✅ (verify thật — 12 test #08 pass, full 284/1, lint 5/0)
Scope: implement/08-observability / Design step-08
Nguồn: LOG Entry #162 · `runtime/observability.py` · `tests/test_step_08_observability.py` · `pyproject.toml` (thêm structlog)
Evidence: `pytest tests/test_step_08_observability.py` = 12 passed; full 284 passed/1 skipped; lint 5 kept/0 broken (structlog runtime KEPT); getDiagnostics 2 file = 0
Links: C-008, K-018, K-019, K-017 (sink cho backpressure metrics — wiring sau)
Nội dung + LÝ DO CHÍNH XÁC:
- Giữ NGUYÊN logic Design (contextvars thay threading.local — an toàn async/thread; token reset LIFO nested-safe; InMemoryMetrics Lock; get_histogram/snapshot copy under-lock chống "mutated during iteration"). Không đổi cái đúng.
- Style: `import logging` đầu file thay `__import__("logging")` inline (không đổi hành vi).
- Test contextvar injection: test `_add_context_vars` TRỰC TIẾP trong log_context (capture_logs bỏ qua processor chain nên không dùng để kiểm contextvar).
- Layer: observability.py ở runtime hợp lệ (contract #3 chỉ cấm application/adapters/profiles; structlog ngoài không bị cấm ở runtime).


### D-026 — 2026-07-04 — Vấn đề #09: Supervisor + shutdown cascade cooperative-first — giữ nguyên thiết kế (đã fix E-10) + verify THẬT
Status: ✅ (verify thật — 6 test #09 pass, full 290/1, lint 5/0)
Scope: implement/09-shutdown / Design step-09 (đã chứa fix E-10)
Nguồn: LOG Entry #164 (+ #40 fix E-10 gốc) · `application/supervisor.py` · `tests/worker_funcs_for_step_09.py` · `tests/test_step_09_shutdown.py` · ERRATA E-10
Evidence: `pytest tests/test_step_09_shutdown.py` = 6 passed (10s); full 290 passed/1 skipped; lint 5 kept/0 broken; getDiagnostics 3 file = 0
Links: K-020, K-021, E-10
Nội dung + LÝ DO CHÍNH XÁC:
- Giữ NGUYÊN thiết kế (bản đã fix E-10 từ #40): cascade **cooperative-first** (set event → JOIN coop grace → terminate non-coop/hang → kill straggler). Bug cũ terminate() ngay → Windows TerminateProcess không chạy finally → cleanup race (verify 20×: cũ 1/20, mới 20/20 ở #40).
- Verify E-10 THẬT tại #09: test graceful cleanup (`cleanup_done` xuất hiện) pass → cooperative worker cleanup sạch, không còn chỉ suy luận.
- Worker module riêng (tests là package) + phân biệt coop/non-coop (non-coop không chờ grace vô ích).
- restart cap `>` (max 3 = restart đúng 3 lần); give-up test assert ==3 (cap đúng).
- Layer application hợp lệ: contract #4 không cấm multiprocessing/signal/structlog.


### D-027 — 2026-07-04 — Vấn đề #10: package + ship + re-run all — dùng SỐ THẬT (290/1) không blueprint (110)
Status: ✅ (verify thật — 290/1, lint 5/0, wheel build + fresh-install 0.1.0, 2 smoke demo đúng)
Scope: implement/10-package-ship / Design step-10 (CUỐI Module 03)
Nguồn: LOG Entry #166 · `vision-platform/README.md` · `dist/vision_platform-0.1.0-*.whl/.tar.gz` · `.gitignore`
Evidence: pytest 290 passed/1 skipped (16.6s); lint 5 kept/0 broken; build → whl 59025B + tar 85855B; fresh-install `__version__`=0.1.0; demo noise→10 processed / fake→5 skipped
Links: C-009, K-022
Nội dung + LÝ DO CHÍNH XÁC:
- #10 KHÔNG code mới (verify/package/ship). README dùng số THẬT 290/1 (không copy blueprint 110) vì dự án đã production-hardening vượt vision_demo MVP — trung thực, kiểm chứng được.
- Build wheel bằng `python -m build` (cài `build` như dev tool, KHÔNG thêm [project] deps — K-022). Fresh-install venv tạm verify import + version, rồi XOÁ venv tạm (cleanup).
- README mô tả layer theo THẬT (InlineInferenceClient ở application E-06-1; observability runtime; backpressure kernel) + list trade-offs hoãn (ZMQ/handlers/hang/POSIX/ARM) trỏ journal.
- .gitignore bổ sung build/dist/egg-info/pycache/pytest_cache/hypothesis/_tmp venv (không commit artifacts).
🎯 MODULE 03 #01–#10 ✅ trên Windows.


### D-028 — 2026-07-04 — Sub-spec `zmq-inference-service` — HOÀN TẤT (đóng K-023) + port IInferenceClient
Status: ✅ (verify thật — 10 test zmq pass, full 300/1, lint 5/0, negative-test msgpack, K-023 đóng)
Scope: .kiro/specs/zmq-inference-service / production inference
Nguồn: LOG Entry #169/#170/#171 · spec {requirements,design,tasks}.md (0 diagnostic) · code (codec/port/client/server) · test cross-process + switchover
Evidence: pytest 5 (codec) + 5 (cross-process+switchover) pass; full **300 passed/1 skipped**; lint 5 kept/0 broken; negative-test msgpack BROKEN→gỡ→kept; pyzmq 27.1.0/msgpack 1.2.1
Links: K-023 (đóng), C-010, K-017, D-023 (port hoãn ở #06 nay tách)
Nội dung + LÝ DO CHÍNH XÁC:
- Sub-spec design-first (requirements EARS 9 mục → chờ valid → design → tasks → code), giống cách #05b làm tốt. Đóng K-023 (R4 switchover-aware read + R5 retryable) + tách port IInferenceClient (R1, giờ mới justify vì có bản thứ 2 = zmq) + tích hợp #07/#08/#09 (R7/R8/R9).
- Neo CODE THẬT + step-06 + K-023, KHÔNG neo `Vision_platform_architecture_design/` (đã xác nhận VẮNG trong workspace — chống bịa nguồn upstream). Ghi rõ ranh giới nguồn ở requirements §0.
- Non-goals: batching GPU / CURVE-auth / detector thật / multi-server (chống phình scope).
- **Chống bịa:** mọi ẩn số ZMQ/msgpack/spawn-Windows gắn [chưa kiểm] tới PHA build.
Ghi kèm: sửa cleanup miss #10 (`_tmp_install_venv` xoá sai đường dẫn tương đối → nay xoá đúng ở gốc repo).


### D-029 — 2026-07-04 — Sub-spec `supervisor-liveness` HOÀN TẤT (đóng K-020 heartbeat + K-021 backoff)
Status: ✅ (verify thật — 4 test liveness pass, #09 6 pass regression, full 304/1, lint 5/0)
Scope: .kiro/specs/supervisor-liveness / resilience #09 (additive)
Nguồn: LOG Entry #173/#174 · spec {requirements,design,tasks}.md (0 diagnostic) · `application/supervisor.py` (additive) · test
Evidence: pytest liveness 4 passed; #09 6 passed; full **304 passed/1 skipped**; lint 5 kept/0 broken; getDiagnostics 0
Links: K-020 (đóng), K-021 (đóng), #09
Nội dung + LÝ DO CHÍNH XÁC:
- ADDITIVE vào Supervisor: WorkerSpec thêm uses_heartbeat/heartbeat_timeout_s/restart_backoff_base_s/cap (default TẮT → 6 test #09 giữ xanh). Heartbeat `mp.Value('d')` wall-clock (K-020); backoff non-blocking `_next_spawn_ok` deadline (K-021); failure thống nhất crash+hang; startup grace (spawn_walltime khi hb=0).
- Lý do chọn heartbeat trước secrets/log-handlers: vá lỗi IM LẶNG nghiêm trọng nhất (hang→camera chết thầm) + verify được Windows. secrets premature (chưa RTSP source).
- Test: hang→restart (chứng minh is_alive KHÔNG bắt được, heartbeat bắt) + no-false-positive + backoff-logic + give-up thống nhất.


### D-030 — 2026-07-04 — Mở sub-spec `full-stack-integration-profile` (design-first) — capstone wire end-to-end
Status: ✅ (PHA 2 XONG — code + test THẬT: 307 passed/1 skipped · lint 5/0 · full-stack infer_ok≥1 cross-process, shutdown sạch. Q1–Q3 chốt. LOG #180. Điều chỉnh worker-placement → C-011. Timing chống-flaky → K-027.)
Scope: .kiro/specs/full-stack-integration-profile / composition-root end-to-end
Nguồn: LOG Entry #179 · spec {requirements,design}.md · các component đã có (đọc lại WriterEpochCoordinator/InferenceServer/Supervisor/RingPool)
Evidence: 2 file spec 0 diagnostic. Baseline 306/1 không đổi. Ghép full-stack [chưa kiểm] tới PHA build.
Links: đóng gap "chưa có full-stack test"; K-017 (Q3), #05b/#06b/#09b
Nội dung + LÝ DO CHÍNH XÁC:
- Capstone: composition-root spawn camera-worker + inference-server (bulkhead) dưới Supervisor, chia sẻ RingPool+control-plane+ZMQ endpoint. Chứng minh frame chảy camera→SHM→(ZMQ)inference→detections cross-process + shutdown sạch.
- QĐ-1 v1 1 camera+1 server (single-writer/ring → 1 pool); QĐ-4 verify artifact-file (cross-process metrics aggregation Non-goal); tái dùng component (không viết lại) → test cũ giữ xanh.
- Design-first vì hướng lớn nhiều process (rủi ro flaky) — valid thiết kế trước khi code (nguyên tắc user).
- Q1 (1 camera) / Q2 (artifact-file) / Q3 (BoundedQueue ngay-hay-sau, đề xuất sau) — CHỜ user.

### D-031 — 2026-07-04 — Mở sub-spec `real-detector-integration` (design-first) — đóng gap coordinate-transform
Status: 🔵 (PHA 1 requirements+design, 0 diagnostic — chờ user chốt Q1–Q3; chưa code)
Scope: .kiro/specs/real-detector-integration / detector thật production-shaped
Nguồn: LOG Entry #182 · spec {requirements,design}.md · code đã đọc (IDetector/FakeDetector/BBox+CoordinateSpace/Detection) · grep verify gap
Evidence: 2 file spec 0 diagnostic. Grep toàn `src` xác nhận CHƯA có hàm transform/letterbox/resize (chỉ enum CoordinateSpace). Baseline 307/1 không đổi.
Links: tiền đề cho detector thật; nối #06 inference + Step 02 CoordinateSpace
Nội dung + LÝ DO CHÍNH XÁC (tinh chỉnh khuyến nghị "#1 detector thật"):
- Bản chất "detector thật" = 2 phần theo tính KIỂM-CHỨNG-ĐƯỢC. **Phần A (verify NGAY):** `LetterboxTransform`
  (domain thuần toán) + `DetectorPipeline` (adapters Decorator, resize tiêm DI) — đóng BUG PRODUCTION #1 (box
  sai toạ độ sau resize) mà `CoordinateSpace` sinh ra để chống nhưng CHƯA ai làm. **Phần B (GATED):** `OnnxDetector`
  cần onnxruntime + model → chỉ làm khi verify được môi trường (luật user: không triển khai cái chưa kiểm chứng).
- QĐ-1 LetterboxTransform ở domain (toán toạ độ = nơi hay sai nhất → thuần, property-test tuyệt đối, tái dùng mọi detector).
- QĐ-2 DetectorPipeline ở adapters (Decorator over IDetector, chỉ domain+kernel, inner qua DI port — không chạm runtime).
- QĐ-3 OnnxDetector adapters leaf, onnxruntime cấm ở domain+kernel (import-linter như zmq/msgpack).
- Q1 (làm A trước, B sau) / Q2 (NMS vào A luôn?) / Q3 (cho cài onnxruntime verify B?) — CHỜ user.

### D-032 — 2026-07-05 — App demo trực quan (xem luồng + vẽ box) + BrightBlobDetector + cài opencv
Status: ✅ (verify — 6 test + chạy app tạo 12 PNG có box + full 345/1 · lint 5/0)
Scope: `profiles/vision_demo_app.py` + `adapters/blob_detector.py` + cài opencv-python 5.0.0.93
Nguồn: LOG Entry #188 · user "app đơn giản xem luồng + nhận diện"
Links: D-031 (real-detector), C-013 (camera user lắp)
Nội dung + LÝ DO CHÍNH XÁC:
- App `vision_demo_app`: nguồn (ô vuông sáng di chuyển / --camera / --rtsp) → DetectorPipeline → vẽ box cv2 →
  --save PNG (headless verify) / --show live. SWAP-READY YOLO: --onnx --labels → OnnxDetector+yolov8_decode.
- `BrightBlobDetector` (ngưỡng sáng → bbox, thuần numpy) để demo "nhận diện" bám vật THẬT mà không cần weight.
- opencv-python: công cụ đúng cho video/camera/vẽ (đã khai báo optional [cv2]); cài + verify chạy thật.
- Vì sao dùng blob thay Fake cho demo: box BÁM vật sáng di chuyển → trực quan thuyết phục "nhận diện", vẫn verify được.
- Vì sao synthetic source: chạy được NGAY (chưa có camera); --camera/--rtsp sẵn cho khi user cắm thiết bị.

### D-033 — 2026-07-05 — RtspFrameSource (IFrameSource tự reconnect) + copy weight YOLO vào repo
Status: ✅ adapter (7 test) · ⏳ kết nối camera thật chặn bởi ffmpeg-Windows 401 (K-030) · ⏳ weight chờ export .onnx
Scope: `adapters/rtsp_frame_source.py` + `profiles/vision_demo_app.py` (--rtsp) + `models/*.pt`
Nguồn: LOG Entry #189 · port IFrameSource (đã đọc) · user cung cấp URL + weight
Links: D-031/D-032 (detector/app), K-030 (RTSP 401), K-031 (secret)
Nội dung + LÝ DO:
- RtspFrameSource: bản chất RTSP hay rớt → adapter tự reconnect (RECONNECTING/ERROR qua ReadResult, không raise).
  DI capture_factory → unit-test không cần camera. mask_rtsp che mật khẩu trong log/source_id.
- Weight: 3 file `.pt` (Ultralytics YOLO, imgsz 640, cpu, vehicle {0:car,1:moto,2:truck}) copy vào models/ (gitignore).
  CẦN export `.pt`→`.onnx` (ultralytics+torch) mới dùng OnnxDetector — khuyến nghị user export ở env syn (version-compat).

### D-034 — 2026-07-05 — VideoFileFrameSource (IFrameSource file video) + wire --video + yolov5_decode
Status: ✅ (verify — 6 test video-source + 4 test yolov5_decode; full 362/1, lint 5/0)
Scope: `adapters/video_file_frame_source.py` + `adapters/yolo_postprocess.py::yolov5_decode` + `profiles/vision_demo_app.py` (--video)
Nguồn: LOG Entry #192/#193 · port IFrameSource · weight là YOLOv5 (xác nhận code syn)
Links: D-031/D-033, K-030
Nội dung + LÝ DO:
- `yolov5_decode`: weight user = YOLOv5 (code syn có repo yolov5) → decode [1,N,5+nc] có objectness, conf=obj×class (khác v8). Verify tensor tổng hợp + ONNX-stub. Sẵn cho khi có .onnx.
- `VideoFileFrameSource`: chạy detect trên VIDEO QUAY SẴN (validate model không cần camera live — camera vướng ffmpeg-Windows K-030). File hữu hạn → fail-fast nếu thiếu (khác RTSP retry) + EOF + loop tùy chọn. DI capture → test không cần file/codec.
- Vì sao: hoàn thiện bộ nguồn (synthetic/camera/rtsp/video-file) + đường validate model trên footage — bước tự nhiên hướng sản phẩm, verify được ngay trong lúc chờ .onnx.

### D-035 — 2026-07-05 — Web UI (Flask MJPEG) + artifact Docker (Linux) + cờ --yolo v5/v8
Status: ✅ web UI (verify chạy thật máy dev) · ⏳ Docker (chưa verify — không có docker ở dev, K-032)
Scope: `profiles/vision_web_app.py` + `deploy/{Dockerfile,docker-compose.yml,README.md}` + `--yolo` (demo+web) + dep flask (optional `web`)
Nguồn: LOG Entry #196 · user chỉ đạo "web + docker cho stream"
Links: D-034, K-030 (RTSP Windows), K-031 (secret), K-032 (docker chưa verify)
Nội dung + LÝ DO:
- Web UI (MJPEG lên browser) thay cv2.imshow: xem đúng res + resize + **headless** (chạy được trong Docker/Linux server nơi RTSP OK). Verify: `/` 200, `/stats` frames tăng + có box.
- Docker (Linux): giải RTSP-401 (ffmpeg Linux xử lý digest như VLC) + inference bằng onnxruntime (sạch, không torch/GPL runtime). CHƯA build được ở dev (không docker) → tài liệu + để user chạy.
- `--yolo v5` mặc định (weight user = YOLOv5, xác nhận code syn) → chọn yolov5_decode.

### D-036 — 2026-07-05 — Yolov5PtDetector: chạy THẲNG weight `.pt` YOLOv5 (không cần export ONNX)
Status: ✅ (verify chạy THẬT trong WSL: load model + names car/moto/truck + detect chạy; Windows 364/1 · lint 5/0)
Scope: `adapters/yolov5_pt_detector.py` + cờ `--pt` (demo/web) + optional dep `pt` (`yolov5>=7.0`) + contract forbidden torch/yolov5 ở domain+kernel
Nguồn: LOG Entry #198 · user "chạy thẳng .pt"
Evidence: WSL ~/vpvenv (yolov5 7.0.14 + torch): load OK, `model.names = {0:car, 1:motorcycle, 2:truck}` (đọc thật), detect chạy (0 det ảnh nhiễu — đúng); Windows `pytest` 364 passed/1 skipped · lint 5 kept/0 broken (+2 test)
Links: D-034 (yolov5_decode ONNX path), K-030/K-033 (RTSP), K-029 (AGPL license YOLO)
Nội dung + LÝ DO CHÍNH XÁC:
- Nguyên nhân gốc `.pt` không load được = **torch ≥ 2.6 mặc định `weights_only=True`** (KHÔNG phải version kiến trúc model) → patch `torch.load(weights_only=False)` khi nạp. Đây là fix GỐC (tìm đúng cơ chế torch), không phải đổi model.
- `Yolov5PtDetector` lazy-import `yolov5`/`torch` (giữ base install gọn + không kéo dep nặng khi không dùng `--pt`); box trả về hệ **ORIGINAL_FRAME** (không bọc pipeline letterbox — yolov5 pkg tự lo tiền/hậu xử lý).
- Contract import-linter cấm `torch`/`yolov5` ở domain+kernel (giữ lõi thuần) — detector nặng chỉ ở adapters (leaf).
Vì sao: cho phép chạy weight `.pt` user có sẵn NGAY (không buộc export `.onnx`) để nghiệm thu nhanh trên máy có GPU/WSL; đường ONNX (D-034) vẫn giữ cho deployment không-torch.

### D-037 — 2026-07-05 — Web UI TÁCH LUỒNG: video ⊥ detect, browser vẽ bbox overlay (đề xuất user)
Status: ✅ (verify chạy WSL GPU: video~15fps ⊥ detect~15fps, /boxes JSON person thật)
Scope: `profiles/vision_web_app.py` (viết lại 2 thread + /boxes JSON + canvas overlay)
Nguồn: LOG Entry #201 · đề xuất kiến trúc của user
Links: D-035 (web cũ server-vẽ), K-034
Nội dung + LÝ DO:
- Trước: 1 vòng đọc→detect→VẼ→encode→stream (detect chặn video). Sau: video thread (đọc→encode→MJPEG, full fps)
  + detect thread async (frame mới nhất→bbox chuẩn hoá 0–1→/boxes JSON) + browser canvas vẽ overlay.
- Vì sao đúng: pattern chuẩn VMS/analytics — TÁCH transport khỏi analytics → video mượt độc lập tốc detect.
- Đánh đổi: server vẫn phải transcode RTSP→MJPEG (browser không phát RTSP); box trễ nhẹ = độ trễ detect;
  toạ độ chuẩn hoá 0–1 để browser scale. Chấp nhận — mượt hơn hẳn.

### D-038 — 2026-07-06 — Mở sub-spec `media-ref-port` (PHA 1 design-first): trừu tượng media_ref → port IMediaRef
Status: ✅ HOÀN TẤT (PHA1 design 0-diag + PHA2 code verify THẬT 369/1 · lint 5/0). User "duyệt theo khuyến nghị" → code.
Scope: `.kiro/specs/media-ref-port/{requirements,design}.md`
Nguồn: audit K-038 (seam World-A/B) · grep verify consumers · đọc pyproject contracts + kernel/media_ref khả thi
Links: K-038 (điểm gãy), K-037 (5 gap base), D-037
Nội dung + LÝ DO:
- Quyết định: rút port `IMediaRef` (Protocol kernel, tối thiểu `array: np.ndarray`) + nới type hint
  `MediaPacket.media_ref: InMemoryArrayRef → IMediaRef`. InMemoryArrayRef KHÔNG sửa (thoả structural typing).
- Vì sao ĐÚNG GỐC (bám yêu cầu "fix bản chất"): điểm gãy không phải "thiếu impl SHM" mà là packet phụ thuộc
  CHIỀU SAI (data-model cấp cao trỏ thẳng impl concrete). Đảo phụ thuộc về port là sửa đúng chỗ. Thêm
  ShmMediaRef sau chỉ là +1 impl, không phải sửa lại packet/Stage.
- Vì sao ADDITIVE an toàn: grep xác nhận consumers CHỈ dùng `.array` (brightness_stage, demo_pipeline) →
  bề mặt port tối thiểu = 1 thuộc tính. numpy đã được phép ở kernel (media_packet đã import) → không phá
  contract import-linter. Backward-compat 100% (InMemoryArrayRef đã có `.array`).
- Vì sao ShmMediaRef là Non-Goal PHA này: kernel CẤM shared_memory (contract) → ShmMediaRef phải ở
  runtime/ipc + cần reader coordinator → bước riêng. Giữ bước nhỏ, chống phình.
- Đánh đổi: nới type hint làm mypy "lỏng" hơn 1 chút (media_ref giờ là Protocol thay concrete) — chấp nhận
  vì đó chính là mục tiêu (mở cho đa impl). Xem T-tiếp trong 03-tradeoffs.


### D-039 — 2026-07-06 — Mở sub-spec `pipeline-runner` (PHA 1 design-first): engine source→executor→sink + port ISink
Status: ⏸️ HOÃN (design 0-diag, CHƯA code) — user phản biện phạm vi "đang đưa hơi nhiều" → AI khuyến nghị DỪNG ở
mốc media-ref-port; giữ spec này dạng design-only "sẵn sàng dùng khi có nghiệp vụ thật" (tránh suy đoán kiến trúc).
Scope: `.kiro/specs/pipeline-runner/{requirements,design}.md`
Nguồn: audit K-037 Gap-1 · grep verify 4 profile trùng vòng lặp · đọc IFrameSource/SyncLinearExecutor/demo_pipeline thật
Links: K-037 (Gap-1), D-038 (IMediaRef — nối qua media_ref_factory)
Nội dung + LÝ DO:
- Quyết định: thêm `PipelineRunner` (runtime) + outbound port `ISink` (kernel/ports) + `RunStats`. Runner
  chạy vòng read→dựng-packet→execute→sink.handle với lifecycle + thống kê + điều kiện dừng.
- Vì sao ĐÚNG GỐC: không phải "profile dài dòng" mà là KHÔNG có nơi DUY NHẤT định nghĩa "cách chạy pipeline"
  → 4 profile (grep verify: demo_pipeline/web_app/fullstack/demo_app) mỗi cái tự xử EOF/ERROR/teardown →
  phân kỳ hành vi = bug im lặng cho sản phẩm. Rút engine = một-cách-đúng, kiểm một lần.
- Vì sao ISink là port (không callback): nhất quán codebase (mọi ranh giới = Protocol); sink có lifecycle
  (mở DB/file); là chỗ nghiệp vụ sau (IEventSink/DBSink) cắm vào. Đối xứng IFrameSource/IDetector.
- Vì sao KHÔNG tạo IExecutor: chỉ 1 executor → chưa biến thiên → YAGNI (what varies? executor KHÔNG). Nhận
  SyncLinearExecutor concrete v1; đổi sau rẻ (nới type như đã làm media_ref).
- Vì sao ADDITIVE: PHA này CHỈ thêm runner+sink+test, KHÔNG đụng 4 profile → 369 test bất biến. Migrate
  profile = bước SAU (opt-in, regression riêng). media_ref_factory DI (mặc định InMemoryArrayRef.from_copy)
  nối port IMediaRef (D-038) → SHM sau cắm không sửa runner.
- Đánh đổi: xem T-009 (ISink port vs callback) + T-010 (concrete executor vs IExecutor) trong 03-tradeoffs.


### D-040 — 2026-07-06 — Mở spec `scale-architecture` (PHA 1 design ĐỊNH HƯỚNG cụm ~100 camera)
Status: 🔵 PHA 1 (requirements+design 0-diagnostic) — CHỜ user đọc-lại-valid. CHƯA code.
Scope: `.kiro/specs/scale-architecture/{requirements,design}.md`
Nguồn: C-014 (~100 cam) + C-015 (phần cứng tương lai) + K-040 (lỗ hổng) + K-041 (công suất) + đọc base thật.
Links: K-037, K-040, K-041, D-038 (IMediaRef), D-039 (pipeline-runner)
Nội dung + LÝ DO:
- Quyết định: viết tài liệu ĐỊNH HƯỚNG đặt **capacity model per-node (tham số đo)** làm gốc → topology 3 mặt
  phẳng (data/control/observability) → bản đồ TÁI DÙNG (base=1 node) vs THÊM MỚI (batch-mux/config/scheduler/
  metrics/motion-gate/fan-out) → 5 trụ (motion-gate/sub-stream/batch/budget/shed) → lộ trình 1→10→N + benchmark trước.
- Vì sao ĐÚNG GỐC: 100 cam = bài toán PHÂN BỔ TÀI NGUYÊN HỮU HẠN, không phải "chạy nhanh hơn" → đặt ngân sách+
  shed+config làm hạng-nhất TỪ ĐẦU (không vá khi nghẽn). Capacity model đặt trước để mọi con số suy ra được + đo được.
- Vì sao KHÔNG rebuild: bản đồ tái dùng chỉ rõ base = "1 node" giữ nguyên; cụm = THÊM tầng bao quanh.
- Vì sao để-ngỏ công nghệ (transport/config-format/metrics-backend/Triton): tránh chốt sớm khi chưa có số + chưa
  tới bước — nêu tiêu chí, chốt ở sub-spec. (tránh over-engineer, bám nguyên tắc user.)
- Lộ trình đặt **vertical slice TRƯỚC scale-out** (giá trị nghiệp vụ thật trước, tránh xây hạ tầng rỗng) — xem T-011.


### D-041 — 2026-07-06 — Mở spec `vision-vertical-slice` (PHA 1 design): lát cắt dọc đầu tiên chạy thật
Status: 🔵 PHA 1 (requirements+design 0-diagnostic) — CHỜ user đọc-lại-valid. CHƯA code.
Scope: `.kiro/specs/vision-vertical-slice/{requirements,design}.md`
Nguồn: roadmap scale-architecture (T-011 slice-trước) · design pipeline-runner (D-039) · đọc code base thật.
Links: D-039 (pipeline-runner — slice là consumer đầu tiên), D-040 (scale roadmap), K-042 (Lỗ 3 → v1 stateless)
Nội dung + LÝ DO:
- Quyết định: slice = source→DetectStage→CountStage→sink, chạy qua PipelineRunner. Hiện thực nền ISink+
  PipelineRunner+RunStats (D-039) + Stage-hoá detector (DetectStage, đóng Gap-2 K-037) + analytics đếm STATELESS
  (CountStage) + sink (CollectingSink test + JsonlEventSink optional-storage) + profile + test CI xác định.
- Vì sao ĐÚNG (T-011): giá trị thương mại từ luồng nghiệp vụ chạy được, không từ hạ tầng scale rỗng. Slice cũng
  là BẰNG CHỨNG cho pipeline-runner + detector-as-Stage trước khi nhân bản lên scale.
- Vì sao v1 STATELESS (QĐ-1): né Lỗ 3 (K-042 — đếm-không-trùng cần tracking stateful + camera-affinity = bài toán
  riêng lớn). Giữ slice nhỏ + chạy XÁC ĐỊNH trong CI (Fake/Noise + FakeDetector, không cần camera → tránh flaky K-035).
- Vì sao tách DetectStage/CountStage (QĐ-2): SRP + tái dùng detections cho analytics khác.
- Vì sao JsonlEventSink@adapters (QĐ-3): chạm I/O file = leaf adapter; storage optional = gắn/không-gắn ở
  composition root, không đổi lõi (C-013 lưu-trữ-optional).
- Hệ quả: **D-039 pipeline-runner từ ⏸️HOÃN → 🔵 KÍCH HOẠT** (giờ có consumer thật = slice) — hết "suy đoán".


### D-042 — 2026-07-06 — Spec `config-declarative` HOÀN TẤT (đóng K-040 **C2** no-config): schema + loader + factory
Status: ✅ (verify thật #221–#223 = 406/1; **RE-VERIFY máy `endgame` #228 = full 421/1 · lint 5/0**, K-047 đóng)
Scope: `.kiro/specs/config-declarative/{requirements,design,tasks}.md` (0-diag) → `kernel/config.py` · `application/config_loader.py` · `profiles/pipeline_factory.py`
Nguồn: LOG Entry #219 (design) · #220 (req+tasks) · #221 (Task 1 schema) · #222 (Task 2 loader) · #223 (Task 3+4 factory+PBT)
Evidence: `pytest` 406 passed/1 skipped (LOG #223) — config_schema 7 + config_loader 12 + pipeline_factory 6 + config_pbt 2 = 25 test mới; lint verify qua `importlinter.api` (K-044) = 5 kept/0 broken; getDiagnostics 0
Links: K-040 (C2), C-014 (multi-cam → config bắt buộc), T-013 (tomllib vs external), D-039/D-041 (dựng lại PipelineRunner/CompositeSink)
Nội dung + LÝ DO CHÍNH XÁC (đóng lỗ C2 trong sổ K-040):
- **`kernel/config.py`** — schema THUẦN stdlib: `SourceConfig/StageConfig/SinkConfig/DetectorConfig(type,params)` + `PipelineConfig(id,source,stages,sinks,detector?,max_frames?)` + `AppConfig(pipelines)`. Tất cả `@dataclass(frozen=True)`; `params`→`MappingProxyType` (read-only) qua `__post_init__`+`object.__setattr__`; list→`tuple`. KHÔNG I/O/adapter (giữ kernel thuần theo AGENTS §4).
- **`application/config_loader.py`** — `ConfigError` + `parse_app_config(dict)->AppConfig` (validate CẤU TRÚC fail-fast: pipelines là list · id str-không-rỗng + DUY NHẤT · source/stage/sink/detector = {type,params} · max_frames int|None) + `load_app_config(path)` dùng **`tomllib` (stdlib)** mở `'rb'`.
- **`profiles/pipeline_factory.py`** — `DEFAULT_REGISTRY` (sources fake/noise/video/rtsp · detectors fake/pt · stages detect/count · sinks jsonl) + `build_runner(pcfg, registry)` → source + SyncLinearExecutor([stages]) + CompositeSink([sinks]) + PipelineRunner. **Lazy-import mỗi builder** (không kéo torch/cv2 lúc load module). Type lạ → `ConfigError` liệt kê type hợp lệ.
- Vì sao ĐÚNG GỐC: multi-camera ~100 con (C-014) KHÔNG thể hard-code trong profile → "cấu hình khai báo" là TRỤC BẮT BUỘC (K-040 C2). Tách 3 tầng theo đúng layer (schema@kernel / parse@application / build@profiles) để KHÔNG vi phạm import-linter: type∈registry check phải ở factory@profiles (không để loader@application import profiles).
- Vì sao `tomllib` (không thêm dep): xem T-013 (đánh đổi TOML-only + py≥3.11 đổi lấy zero-dependency, giữ base lean).
- ADDITIVE tuyệt đối: 25 test mới, KHÔNG sửa base → baseline cũ giữ xanh.


### D-043 — 2026-07-06 — Config end-to-end dùng được: wire `--config` + configs GPU-ready + `validate_config`/`--validate`
Status: ✅ parse+validate+wire verify thật (#224–#226 + **RE-VERIFY máy `endgame` #228 = full 421/1 · lint 5/0**) · 🔴 **end-to-end GPU (pt/cuda/rtsp) VẪN CHƯA chạy** (máy dev no-GPU/no-torch — nghiệm thu máy GPU)
Scope: `profiles/vision_slice_app.py` (`--config`, `--validate`, `_run_from_config`) · `profiles/pipeline_factory.py` (`validate_config`) · `vision-platform/configs/` (3 file .toml + README)
Nguồn: LOG Entry #224 (wire --config) · #225 (configs GPU-ready + test) · #226 (validate_config + --validate, đóng lỗ review #1)
Evidence: full 421 passed/1 skipped (LOG #226) — thêm vision_slice_config 3 + example_configs 4 + config_validate 8 test; lint 5/0 (qua importlinter.api); getDiagnostics 0
Links: D-042 (nền config), D-036/K-034 (Yolov5PtDetector đã proven WSL — glue tái dùng), K-045/K-046 (2 lỗ review CÒN mở), K-041 (capacity)
Nội dung + LÝ DO CHÍNH XÁC:
- **`--config <file.toml>`** (#224): `_run_from_config(path)` = `load_app_config` → mỗi pipeline `build_runner` + `run(max_frames)` + in summary/stderr. KHÔNG có --config → đường argparse cũ NGUYÊN VẸN (additive, base xanh). v1 chạy đa-pipeline **TUẦN TỰ** (song song thuộc scale-architecture — xem T-015).
- **`configs/`** (#225): `example_fake.toml` (no-GPU smoke) · `example_video_gpu.toml` · `example_rtsp_gpu.toml` (placeholder secret, K-031) + README. Test: mọi .toml PARSE hợp lệ; fake BUILD+RUN thật (no-GPU); gpu configs kiểm khai báo pt/cuda/rtsp. Config→pt TÁI DÙNG `Yolov5PtDetector` (đã chứng minh WSL D-036/K-034).
- **`validate_config(app, registry)` + `--validate`** (#226, đóng lỗ review #1): kiểm mọi `type`∈registry (dùng `_lookup`, **KHÔNG gọi builder** → không import torch/cv2) + detect-phải-có-detector → raise `ConfigError` kèm pipeline id. `--validate` → exit 0 (OK) / 2 (sai). Cho phép **validate config GPU NGAY trên máy dev no-GPU** trước khi mang lên máy GPU — xem T-014.
- Vì sao ĐÚNG NGUYÊN TẮC USER ("valid thiết kế trước khi triển khai"): `--validate` chính là cổng "kiểm trước khi chạy" đưa vào runtime — bắt lỗi cấu hình sớm trên máy rẻ (no-GPU), không phải chờ mang lên GPU mới vỡ.
- ⚠️ TRUNG THỰC: chuỗi **parse→validate→build(fake)→run(fake)** đã verify; nhưng **YOLO thật + RTSP thật (pt/cuda) CHƯA chạy end-to-end** trong bất kỳ phiên nào từ config (máy dev không torch/GPU) → nghiệm thu ở máy GPU/WSL (end.md §3). KHÔNG được claim "config chạy YOLO thật".
- CÒN NỢ (2 lỗ review doubt-driven CHƯA vá): **K-045** bulkhead per-pipeline · **K-046** params typo nuốt im lặng.


### D-044 — 2026-07-06 — Bulkhead per-pipeline trong `_run_from_config` (đóng K-045): cô lập lỗi từng pipeline
Status: ✅ (TDD RED→GREEN, verify THẬT máy `endgame` — full **423 passed/1 skipped** · lint 5 kept/0 broken; LOG #229)
Scope: `profiles/vision_slice_app.py::_run_from_config` · test `tests/test_vision_slice_config.py`
Nguồn: K-045 (lỗ review #2 doubt-driven, #226) · đọc code thật `_run_from_config` + `PipelineRunner.run` + `build_runner` + constructor `VideoFileFrameSource`/`JsonlEventSink`
Evidence: `pytest tests/test_vision_slice_config.py` = 5 passed (3 cũ + 2 bulkhead mới); full `pytest -q` = **423 passed/1 skipped** (39.58s, EXIT 0); lint qua `importlinter.api` = 5 kept/0 broken (LINT_OK True)
Links: K-045 (đóng), C-016 (đổi return code), T-016 (except Exception), D-043 (config wire), C-014 (~100 cam)
Nội dung + LÝ DO CHÍNH XÁC (fix TẬN GỐC, không vá ngọn):
- **Gốc của K-045 (từ đọc code):** `PipelineRunner.run` ĐÃ cô lập lỗi PER-FRAME (ReadStatus.ERROR→source_errors+continue; StageStatus.ERROR→stage_errors, vẫn sink). NHƯNG lỗi PER-PIPELINE thì không ai bắt: (a) `build(pcfg)` — constructor ném (thiếu weights/file, type lạ→ConfigError); (b) `runner.run()` — `source.setup()`/`sink.setup()`/`sink.handle()` I/O/`read()` ném bất ngờ (KHÔNG nằm trong try/except của run(), chỉ `finally` lo teardown). Vòng `for pcfg` gọi cả 2 TRẦN → 1 pipeline ném = cả loop chết.
- **Vách ngăn đặt ĐÚNG RANH GIỚI = mỗi vòng lặp pipeline** (không trong runner — per-frame đã lo; không trong build_runner — đó là dựng object). Đây là nơi "1 camera = 1 khoang" cần cô lập.
- **Bắt `except Exception` (KHÔNG `BaseException`):** vách ngăn phải bắt rộng vì kiểu lỗi đa dạng (ConfigError/FileNotFoundError/ImportError/CUDA RuntimeError/cv2/disk). Chừa `KeyboardInterrupt`/`SystemExit` để Ctrl+C dừng được TOÀN hệ (xem T-016). Log rõ `type(e).__name__: e` — KHÔNG nuốt im lặng.
- **DI seam `build=None`→`build_runner`:** thêm tham số keyword để test bulkhead XÁC ĐỊNH (inject build ném lỗi + build ok), không cần dựng adapter thật lỗi. `main()` gọi `_run_from_config(path)` KHÔNG đổi. Kiểu DI codebase đã dùng (media_ref_factory/ring_factory).
- **KHÔNG leak khi build-dở (verify):** đọc `VideoFileFrameSource.__init__`/`JsonlEventSink.__init__` = THUẦN (chỉ lưu ref); tài nguyên OS mở trong `setup()` (trong run(), `finally` release). ⇒ build ném giữa chừng → object đã dựng KHÔNG giữ handle OS → không leak. Claim này ĐÃ kiểm tận nơi, không suy đoán.
- **Kỷ luật phạm vi:** KHÔNG đụng PipelineRunner/adapter/stage; KHÔNG làm song song (T-015); KHÔNG gộp K-046 (params typo — lỗ khác, làm riêng). Additive → 421 test cũ giữ xanh, +2 test → 423.
- Test: (1) pipeline 'a' ném lúc BUILD + 'b' ném lúc RUN → 'c' VẪN chạy (assert ran==['c-ok']) + rc==1; (2) all-ok → rc==0.


### D-045 — 2026-07-06 — Strict-key validation cho config params (đóng K-046): typo không còn nuốt im lặng
Status: ✅ (TDD RED→GREEN, verify THẬT máy `endgame` — full **427 passed/1 skipped** · lint 5 kept/0 broken; LOG #230)
Scope: `profiles/pipeline_factory.py` (`_check_params` + `allowed_params` mỗi builder + `validate_config` + `build_runner`) · test `tests/test_config_validate.py`
Nguồn: K-046 (lỗ review #3 doubt-driven, #226) · đọc code thật builders + configs/*.toml + test hiện có (enumerate key hợp lệ)
Evidence: `pytest tests/test_config_validate.py` = 12 passed (8 cũ + 4 mới); full `pytest -q` = **427 passed/1 skipped** (36.20s, EXIT 0); lint qua `importlinter.api` = 5 kept/0 broken (LINT_OK True)
Links: K-046 (đóng), C-017 (contract build_runner siết), T-017 (fail-fast vs lenient), D-042/D-043 (config), T-014 (validate no-GPU)
Nội dung + LÝ DO CHÍNH XÁC (fix TẬN GỐC):
- **Gốc của K-046:** builder đọc `params.get("key", default)` → key gõ sai (vd `wieghts`/`max_frame`/`devcie`) bị BỎ QUA im lặng, dùng default → sai cấu hình không báo (chạy CPU thay GPU, sai đường weight). `_need` chỉ bắt key THIẾU, không bắt key LẠ. Gốc sâu hơn: **không builder nào khai báo tập key nó chấp nhận** → không kiểm được.
- **Khai báo `allowed_params` (frozenset) gắn VÀO từng builder** (function attribute): builder là nơi ĐỌC params → là authority về key hợp lệ; đặt tập key ngay đó, KHÔNG đẻ bảng song song dễ lệch pha. 9 builder mặc định khai báo đủ (đọc code enumerate: fake/noise=`{max_frames}`, video=`{path}`, rtsp=`{url,max_reconnect}`, det-fake=`{model_size}`, det-pt=`{weights,device}`, detect/count=`{}`, jsonl=`{path}`).
- **Cổng `_check_params(builder, where, params)` dùng ở CẢ `validate_config` VÀ `build_runner`** (dùng chung, không lặp). Lý do chính xác (từ đọc code): `_run_from_config` gọi `build_runner` KHÔNG qua `validate_config` → nếu chỉ đặt ở validate thì đường chạy thật (`--config`) vẫn nuốt typo. Đặt cả hai → bắt ở dry-run (`--validate`, máy dev — T-014) LẪN run thật.
- **`_check_params` chạy TRƯỚC khi gọi builder** trong build_runner → detector `pt` typo bị bắt TRƯỚC lazy-import torch → validate được trên máy no-GPU (test `test_build_runner_rejects_unknown_detector_param_before_torch` chứng minh).
- **Key lạ → `ConfigError` fail-fast** (không cảnh báo suông) — sai config chạy sai là nguy hiểm 24/7; đồng bộ fail-fast của config_loader. Builder chưa khai báo `allowed_params` → BỎ QUA (lenient, không siết registry bên thứ 3) — xem T-017.
- **Không phá baseline:** mọi config mẫu (configs/*.toml) + test hiện có chỉ dùng key ∈ allowed (đã đọc xác nhận TRƯỚC khi siết) → 423 test cũ giữ xanh, +4 test → 427.
- Test: (1) validate typo `max_frame`→ConfigError kèm pipeline id + key lạ; (2) key đúng→không raise; (3) build_runner typo `wieghts` detector pt→ConfigError trước torch; (4) CLI `--validate` typo→return 2.


### D-046 — 2026-07-06 — Mở sub-spec `node-capacity-benchmark` (PHA 1 design phương pháp đo, design-only)
Status: 🔵 PHA 1 (requirements+design **0-diagnostic**) — CHỜ user valid. CHƯA code. KHÔNG đổi baseline (chỉ thêm 2 .md).
Scope: `.kiro/specs/node-capacity-benchmark/{requirements,design}.md`
Nguồn: `scale-architecture` Roadmap bước 2 + R6.1 + Capacity Model · K-041 (công suất phải benchmark) · K-047 (máy dev no-GPU) · đọc code thật `IDetector`/`Yolov5PtDetector`/`RunStats`/`VideoFileFrameSource`
Links: K-041, D-040 (scale-architecture), K-047, T-014
Nội dung + LÝ DO CHÍNH XÁC:
- Quyết định: viết PHƯƠNG PHÁP ĐO capacity per-node (C_inf theo batch 1/8/16 · C_dec + combined decode+infer · VRAM · latency p50/p95/p99) để điền vào capacity model `scale-architecture` bằng SỐ THẬT — trước khi thiết kế bất kỳ mảnh scale nào.
- Vì sao ĐÚNG NGUYÊN TẮC USER + K-041: "chính xác kiểm chứng được rồi mới triển khai" → capacity là tham-số-ĐO, không được bịa; benchmark là bước 0 của mọi thiết kế scale. Đây là thứ DUY NHẤT về scale làm được trên máy no-GPU mà KHÔNG bịa (viết methodology, không phải số liệu).
- **Trung thực (K-047):** spec ghi rõ máy `endgame` no-GPU → chỉ verify LOGIC harness (fake/CPU) ở đây; SỐ THẬT chỉ chạy ở máy GPU. Bảng kết quả để RỖNG `[chưa đo]`, cấm điền số phỏng đoán (Property 5).
- **Bám code THẬT (chống bịa API):** `IDetector.detect(frame)` theo-TỪNG-frame (đọc `kernel/ports/detector.py`) → đo batch phải gọi `Yolov5PtDetector._model([frames])` DƯỚI port → spec ghi rõ đây là bằng chứng lỗ A1 (batch chưa expose qua port), không giả vờ port batch. `RunStats` (đọc `pipeline_runner.py`) KHÔNG có field thời gian → harness tự đóng dấu `perf_counter_ns` (Property 2: sau `cuda.synchronize`).
- **3 điểm dễ sai đã chốt phương pháp:** (1) CUDA async → phải synchronize trước khi chốt mốc (P2); (2) decode/infer tranh GPU → đo COMBINED, không `min` riêng lẻ (P3); (3) số vô nghĩa nếu thiếu môi trường → header bắt buộc (P4).
- **Ranh giới:** harness đặt `benchmarks/` NGOÀI `src/` (công cụ dev, ranh giới K-022) → KHÔNG thêm runtime dep, KHÔNG sửa src → baseline 427/1 giữ. KHÔNG xây batch-mux/scheduler (sub-spec sau khi có số).
- Verify: 2 artifact **0 diagnostic** (getDiagnostics). PHA 2 (code harness + verify logic máy dev + chạy số máy GPU) chờ user valid.


### D-047 — 2026-07-06 — PHA2 code harness benchmark (`benchmarks/`) + verify LOGIC (đóng phần dev-máy của D-046)
Status: ✅ logic verify (TDD, full **436 passed/1 skipped** · lint 5 kept/0 broken; LOG #232) · 🔴 số capacity thật CHƯA đo (cần torch — xem K-048)
Scope: `benchmarks/{__init__.py,_stats.py,_env.py,bench_capacity.py,README.md}` (NGOÀI src) · test `tests/test_bench_stats.py`
Nguồn: LOG Entry #232 · spec `node-capacity-benchmark` (D-046) · đọc API thật FakeDetector/FakeFrameSource/IDetector/ReadResult + pyproject (testpaths/import-linter root_package)
Evidence: `pytest tests/test_bench_stats.py` = 9 passed; full `pytest -q` = **436 passed/1 skipped** (48.70s, EXIT 0); lint qua `importlinter.api` = 5 kept/0 broken; CLI smoke `--mode infer --device cpu` chạy + in cảnh báo "logic-verify không phải capacity"; `--device cuda` khi thiếu torch → dừng (exit 3, không số giả)
Links: D-046 (spec), K-048 (GPU máy endgame), K-022 (ranh giới tool ngoài src), K-040 (A1 batch)
Nội dung + LÝ DO CHÍNH XÁC:
- **Hàm đo DI-friendly** (`measure_infer`/`measure_infer_batch`/`measure_decode`/`measure_latency`): nhận detector/source/`infer_batch_fn`/`sync_fn` TIÊM VÀO → verify LOGIC được với `FakeDetector`/`FakeFrameSource` trên CPU (không cần GPU). `sync_fn` tiêm = `torch.cuda.synchronize` CHỈ khi cuda (Property 2 — không import torch ở hàm thuần).
- **`_stats.py` thuần** (percentile/throughput/drop-warmup) tách riêng → test giá trị đã biết ([1..100]ms → p50=50.5/p95=95.05, throughput=100/5.05). `_env.py` stamp môi trường, không nổ khi thiếu torch.
- **Ranh giới (K-022):** `benchmarks/` NGOÀI `src/` → import-linter `root_package=vision_platform` KHÔNG quét → 5 contract không đổi. `testpaths=["tests"]` → test đặt `tests/test_bench_stats.py`, import benchmarks qua sys.path (thêm gốc vision-platform) → chạy trong baseline (436/1).
- **Bám code THẬT:** batch>1 gọi `infer_batch_fn` (model nền) vì `IDetector.detect` theo-frame = lỗ A1 (không giả vờ port batch). `measure_latency` đo t0-khi-có-frame→detect (đúng M4). Dừng sớm khi source EOF (test `stops_early`).
- **TRUNG THỰC (Property 5):** CPU/fake mode in cảnh báo LỚN "KHÔNG phải capacity"; cuda-thiếu-torch → exit 3 không số giả. Số capacity thật chờ chạy `--device cuda` (K-048).
- Additive: chỉ thêm `benchmarks/` + 1 test file, KHÔNG sửa src → baseline 427→436 (+9 test bench).


### D-048 — 2026-07-07 — Spec `backpressure-cross-process`: chốt Mô hình A (bound-before-send) — design + tasks (design-only, CHƯA code)
Status: 🔵 (design/tasks PHA — 3 file spec 0-diagnostic; CHƯA code → hành vi runtime chưa verify)
Scope: `.kiro/specs/backpressure-cross-process/{requirements,design,tasks}.md` · đóng lỗ hổng A2 (no-backpressure-cross-proc) + A3 (no-HWM) của K-040
Nguồn: LOG Entry #237 (requirements), #238 (design + Mô hình A), #239 (tasks + đóng diagnostics) · đọc THẬT 8 file code (`zmq_inference_client.py`/`backpressure.py`/`inference_server.py`/`inference_protocol.py`/`fake_detector.py`/`noise_frame_source.py`/`read_result.py`/`vision_fullstack_profile.py` + `test_zmq_inference_cross_process.py`)
Evidence: 3 file spec = 0 diagnostics (get_diagnostics, phiên #239); 12 ref `Validates: Requirements` đọc-khớp AC thật trong requirements.md (không bịa). CHƯA code → baseline **436/1 · lint 5/0 theo LOG #234 (máy `k.nguyen.manh.toan`)**; trên máy `toann` hiện tại **[chưa kiểm]** (chưa chạy pytest, repo máy này không có `.git`).
Links: C-018, T-018, T-019, K-050, K-051, K-052, K-040 (A2/A3), K-016 (BoundedQueue thread-safe)
Nội dung (các quyết định AI tự ra, spec ban đầu #237 KHÔNG chốt cơ chế):
- **Chốt Mô hình A — backpressure BOUND TRƯỚC KHI GỬI:** hệ chỉ `send()` khi `In_Flight_Count < window_size` (flow-control); frame vượt cửa sổ nằm ở **hàng đợi outbound có giới hạn**, bị `Backpressure_Policy` xử lý TRƯỚC khi chạm socket. Bác Mô hình B (bound in-flight đã gửi) — xem T-018.
- **Tái dùng `kernel/backpressure.py::BoundedQueue`** (đã có 4 policy + đếm drops/rejects) làm van outbound — hợp lệ vì client là 1 process (thread capture ⊥ thread io), KHÔNG cross-process (K-016). Xem T-019.
- **Metric_DTO ở kernel:** `kernel/backpressure_metrics.py::BackpressureMetrics` (frozen, thuần Python, property `conserved`) — không import zmq/torch.
- **Giữ `infer()` sync cũ** (5 test cross-process cũ không đổi) + THÊM đường async `submit()`/`poll_responses()`/`in_flight`/`metrics_snapshot()` (cùng 1 io thread sở hữu socket → không tranh chấp).
- **Additive khác:** `FakeDetector.delay_s=0.0` (mặc định không đổi hành vi) · `PushFrameSource` (nhịp cố định, bám interface `ReadResult`) · set `SNDHWM/RCVHWM` TRƯỚC `connect()` (đóng A3) · cấm BLOCK+RTSP ở tầng config (không ở BoundedQueue, giữ nó policy-agnostic).
- **tasks.md:** 5 wave TDD atomic (1 kernel DTO → 2 adapters → 3 profiles/config → 4 cross-process spawn → 5 nghiệm thu), map Requirement + Property, chống flaky bằng assert BẤT BIẾN + `dropped>0` tất yếu (không assert số drop cố định).
Vì sao (bản chất): `inference_server.py` là ROUTER single-thread, KHÔNG hủy được request đã nhận → bound sau khi gửi chỉ ngừng tracking mà server vẫn tốn inference = fix NGỌN. Bound trước khi gửi = frame bị bỏ không tới server = GIẢM TẢI THẬT = fix GỐC đúng mục tiêu A2. Đây là điểm dễ chọn sai nếu bám câu chữ requirement gốc thay vì bản chất.


### D-049 — 2026-07-08 — Wave 3.1 `camera_worker` async submit + drain + hạch toán backpressure 2-tầng
Status: ✅ (verify thật — fullstack pass + full 456/1 + lint 5/0)
Scope: `profiles/vision_fullstack_profile.py::camera_worker` + `_write_result` + `ZmqInferenceClient.outbound_size` · spec backpressure-cross-process Wave 3.1
Nguồn: LOG Entry #244 · design.md §4.5 · requirements R1.2/R4.1/R4.2/R4.3/R5.1 · đọc code camera_worker (nhánh `ref is None`) + `metrics_snapshot()`
Evidence: máy `toann` (venv py3.13.12) — `pytest tests/test_fullstack_integration.py` = **1 passed (4.09s)** (camera async chạy end-to-end, frames_ok/infer_ok≥1, drain hoàn tất); full `pytest -q` = **456 passed/1 skipped (39.83s)** (không hồi quy); lint `importlinter.api` = **5 kept/0 broken**
Links: C-019, T-020, K-053, D-048, K-051
Nội dung: Chuyển `camera_worker` từ `client.infer()` SYNC blocking → `client.submit()` async (Mô hình A): `frames_captured += 1` mỗi frame `has_data` (R4.1); `wcoord.write()` trả None (SHM ring đầy) → `frames_dropped_shm += 1` (KHÔNG submit); có ref → `client.submit(InferenceRequest(...))` non-blocking; mỗi vòng gọi `client.poll_responses()` để drain + đếm `dets_total` + log sample. Sau vòng lặp: **drain** — poll tới khi `client.in_flight == 0` AND `client.outbound_size == 0` (thêm property `outbound_size` vào client, additive), có deadline an toàn `timeout_s+1`. Ghi artifact 6 field `BackpressureMetrics` (`frames_captured/frames_submitted/frames_dropped_backpressure/infer_ok/infer_err/infer_timeout`) từ `metrics_snapshot(frames_captured)` + `frames_dropped_shm` riêng + `dets_total`; GIỮ key cũ `frames_ok`(=frames_submitted)/`infer_ok`/`infer_err` để test fullstack cũ không vỡ (additive). `frames_dropped_backpressure` ghi ra artifact = client-window drops + `frames_dropped_shm` (gộp 2 tầng, xem C-019/T-020).
Vì sao (bản chất): bỏ `infer()` blocking = camera không bị chặn bởi inference chậm (đóng A2/R1). Đếm submitted TẠI LÚC GỬI do client (K-051). Drain sau vòng lặp đảm bảo mọi frame chưa gửi được gửi nốt → bất biến đúng SAU vòng lặp (R4.3). Thêm `outbound_size` vì drain cần biết van outbound đã rỗng chưa (chỉ `in_flight==0` chưa đủ: có thể còn frame trong queue chưa kịp gửi giữa 2 vòng io).

### D-050 — 2026-07-08 — Wave 3.2: R3 (cấm BLOCK+RTSP) làm HÀM GUARD THUẦN, KHÔNG bơm field `policy` vào schema
Status: ✅ (verify thật — 8 test guard pass + full 464/1 + lint 5/0)
Scope: `application/config_loader.py::assert_policy_allowed_for_source` + `tests/test_backpressure_policy_guard.py` · spec backpressure-cross-process Wave 3.2
Nguồn: LOG Entry #245 · ĐỌC `kernel/config.py` (SourceConfig chỉ type+params, KHÔNG có policy) + `pipeline_factory` (path config-declarative dựng PipelineRunner, KHÔNG dựng ZmqInferenceClient)
Evidence: máy `toann` — `pytest tests/test_backpressure_policy_guard.py` = **8 passed (0.42s)**; full **464 passed/1 skipped (39.67s)**; lint **5 kept/0 broken**
Links: D-049, T-021, C-018, K-053
Nội dung: Xác minh: KHÔNG đường config nào gắn `Backpressure_Policy` vào nguồn RTSP (schema không có policy + config path không dựng ZMQ client). → Implement R3 dạng hàm THUẦN `assert_policy_allowed_for_source(source_type, policy)` (application/config_loader): `rtsp+BLOCK → ConfigError` (thông điệp nêu TCP Zero Window + mất frame im lặng); tổ hợp khác OK. Đặt ở tầng config per-source (R3.2), KHÔNG ở BoundedQueue (giữ policy-agnostic). 8 test (rtsp+BLOCK raise · rtsp+{DROP_OLDEST/DROP_NEWEST/REJECT} ok · non-rtsp+BLOCK ok).
Vì sao (bản chất): schema hiện KHÔNG mang policy → bơm field vào TOML + parse + wire lúc này = xây cho nhu-cầu-chưa-tồn-tại (over-engineer, trái nguyên tắc user + T-015). Guard thuần thỏa R3 (nền tảng TỪ CHỐI được rtsp+BLOCK, có test = P7) + "sẵn-sàng-wire" khi config sau này có policy per-source. Fix bản chất (R3 = ngăn tổ hợp nguy hiểm), không phình schema thừa.


### D-051 — 2026-07-08 — Wave 4: test overload cross-process (assert bất biến 2-tầng) + Wave 5 nghiệm thu — spec backpressure-cross-process HOÀN TẤT
Status: ✅ (verify thật — overload 4x không flaky + full 465/1 (3 lần sạch) + lint 5/0)
Scope: `tests/test_zmq_inference_cross_process.py` (+test overload, +harness n_slots/client_kwargs) + `tests/zmq_server_worker.py` (detector_kind="slow") · Wave 4+5
Nguồn: LOG Entry #246, #247 · design §8.2 · R8.1/8.2/8.4/8.5 · P1/P5
Evidence: máy `toann` — `test_zmq_backpressure_overload_conserves` PASS 4 lần (1.47/1.56/1.26s isolation + trong full) không flaky; cross-process file 6 passed (5.76s); full `pytest -q` = **465 passed/1 skipped** (3 lần liên tiếp sạch); lint **5 kept/0 broken**. 1 flake tạm 1 lần = K-035 shutdown (test_step_09_shutdown 6 passed cô lập → không hồi quy).
Links: C-019, T-020, K-053, D-048, D-049, K-035
Nội dung (quyết định AI tự ra cho test):
- `detector_kind="slow"` = `FakeDetector(delay_s=0.05)` (~20 infer/s) — hằng số `SLOW_DETECTOR_DELAY_S`; chậm hơn submit → quá tải TẤT YẾU (deterministic, không xác suất).
- Mở rộng `_harness` thêm `n_slots`/`client_kwargs` (additive, call cũ không đổi) → dùng **SHM ring lớn (n_slots=64 > M=50)** để CÔ LẬP backpressure tầng client-window (thứ spec thêm) khỏi tầng SHM → test tập trung đúng cơ chế mới, ít ghép.
- Test kế toán **2 tầng** giống camera_worker (shm_dropped + client-window) → assert bất biến CHÍNH XÁC `submitted + client_dropped + shm_dropped == M` (airtight: submit_calls = _sent + queue.drops sau drain) + `dropped_total>0` (quá tải tất yếu) + `in_flight==0` (P5). KHÔNG assert số drop cố định (chống flaky). Guard win32.
Vì sao (bản chất): đây là bằng chứng cross-process cho bất biến bảo toàn dưới quá tải THẬT — nâng C-019/T-020/K-053 từ 🟡 (by-construction) lên ✅ (test-asserted). window=1/queue=1 làm quá tải cực đại → drop chắc chắn. Lặp 4x xác nhận deterministic (không dựa may rủi timing).


### D-052 — 2026-07-08 — Cơ chế chống-drift "cực mạnh" = LINTER NHẤT QUÁN BỘ NHỚ (kiểm bằng máy, không thêm luật văn xuôi)
Status: ✅ (chạy thật PASS + đã BẮT drift tồn đọng thật khi dogfood)
Scope: `tests/test_memory_consistency.py` (mới) + wire vào AGENTS §0/§2 (RULES_VERSION 14→15) + hook userTriggered
Nguồn: LOG Entry #248 · user yêu cầu "1 cách cực mạnh để tránh drift" · pattern có sẵn `tests/test_rules_sync.py`
Evidence: `py tests/test_memory_consistency.py` = PASS (6 nhóm check); khi CHẠY LẦN ĐẦU đã BẮT drift thật: LOG dup #90/91/95/96 + thiếu detail D-036 → đã xử lý (allowlist legacy + khôi phục D-036 từ LOG #198)
Links: C-020, K-054, K-050/K-052 (drift đa-máy)
Nội dung: Biến các BẤT BIẾN "bản ghi khớp thực tế" thành TEST khách quan (giống test_rules_sync). 6 check nhắm đúng loại drift đã xảy ra: C1 LOG entries liên tục/không dup · C2 INDEX "Log canonical tới #N" == max LOG (bắt INDEX cũ) · C3 journal D/C/T/K liên tục · C4 header total == đếm thật (bắt tự-đếm-sai 133-vs-137) · C5 ID journal ⇄ dòng INDEX (bắt orphan/thiếu) · C6 activeContext có mốc + nhắc #maxEntry (bắt con trỏ cũ). Pure stdlib, exit 0/1 + pytest fn.
Vì sao (bản chất): drift ở repo này = cập-nhật-tay nhiều mirror → luật văn xuôi TỰ NÓ drift. Cách mạnh nhất theo đúng triết lý user ("code validate khách quan bằng test") = MÁY kiểm bản ghi, chạy đầu mỗi phiên = cổng khách quan. Không phải thêm chữ (ngọn) mà là công cụ kiểm chứng (gốc).



### D-053 — 2026-07-08 — Củng cố chống-drift: ENFORCEMENT tự động (hook agentStop) + PORT cơ chế vào kit (RULES_VERSION 15)
Status: ✅ (2 linter PASS đầu phiên; kit template tạo + bump; hook tạo)
Scope: hook `auto-drift-check` (agentStop) + `ai-learning-os-kit/tests/test_memory_consistency.template.py` (mới) + `ai-learning-os-kit/AGENTS.template.md` (§2 + bump 15)
Nguồn: LOG Entry #249 · user re-nhấn "cách CỰC MẠNH chống drift" · nợ §2.5 (đồng bộ kit) từ #248
Evidence: đầu phiên chạy `test_memory_consistency.py` + `test_rules_sync.py` = PASS (dogfood §0 mới); kit AGENTS.template RULES_VERSION=15 + có luật anti-drift §2; hook agentStop tạo thành công
Links: D-052, K-054
Nội dung:
- **Mắt xích yếu = "phải nhớ chạy" linter** (phụ thuộc kỷ luật AI). Đóng bằng hook **agentStop runCommand** `auto-drift-check`: tự chạy 2 linter SAU MỖI lượt agent → drift lộ NGAY trong terminal, không cần nhớ. Chọn `runCommand` (KHÔNG `askAgent`) để KHÔNG loop (agentStop+askAgent = nguy cơ vòng lặp theo doc hook). Giữ hook userTriggered `kiem-drift` (thủ công) song song.
- **Port cơ chế vào kit** (giá trị lâu dài, sản phẩm thương mại): thêm `test_memory_consistency.template.py` (generic, allowlist rỗng cho dự án mới) + luật §2 anti-drift-linter + bump AGENTS.template 14→15 → dự án SAU copy kit có sẵn chống-drift bằng máy.
Vì sao (bản chất): "cực mạnh" = KHÔNG dựa kỷ luật con người/AI (thứ drift được) mà là (a) MÁY kiểm (linter D-052) + (b) TỰ ĐỘNG chạy (hook) + (c) tái dùng được (kit). 3 tầng: rule §0 (agent chạy) + hook agentStop (tự chạy) + hook userTriggered (thủ công). Không chỉ bump số kit (ngọn) mà port cả cơ chế (gốc) → số 15 của kit là THẬT (rule + reference impl đều có).



### D-054 — 2026-07-08 — Review đối kháng (doubt-driven) code backpressure + FIX GỐC F1 (đua drain io_loop)
Status: ✅ (verify thật — 14 test đích + overload 3/3 không flaky + full 465/1 + lint 5/0)
Scope: `adapters/zmq_inference_client.py::_io_loop` (reorder step 1b) · review toàn client + camera_worker drain
Nguồn: LOG Entry #252 · đọc THẬT io_loop/submit/metrics_snapshot/camera_worker drain · user "validate nhiều lần, nhìn sâu rộng, fix bản chất"
Evidence: máy `toann` — `pytest` 4 file đích (async/hwm/fullstack/cross-process) = **14 passed (15.72s)**; overload lặp **3/3 pass (1.24/1.18/1.18s)** không flaky; full **465/1**; lint **5/0**
Links: K-056, K-051, K-053, D-048
Nội dung: Review đối kháng phát hiện **F1 (đua drain, benign nhưng thật):** io_loop step 1b thứ tự `send()→pending→_in_flight+=1` → giữa `get_or_raise` (pop, outbound_size↓) và `_in_flight+=1` có cửa sổ (outbound=0 & in_flight=0) ở frame CUỐI → vòng drain `camera_worker` (`while outbound_size>0 or in_flight>0`) có thể thoát sớm (bất biến VẪN đúng vì frame vẫn đếm submitted; chỉ sót `dets_total` 1 frame trong µs hiếm). **FIX GỐC (sửa thứ tự nhân-quả, không patch drain):** set `_pending_async`/`_in_flight`/`_sent` NGAY sau pop, TRƯỚC `send()` → cửa sổ biến mất + chính xác hơn cho flow-control. An toàn: send() DEALER fire-and-forget, `window_size ≪ SNDHWM` nên không block/raise.
Vì sao: fix ở THỨ TỰ (gốc) thay vì thêm settle-check ở drain (ngọn). Đã VERIFY KHÔNG bug ở: timeout-scan (không double-decrement, single-thread, `expired` build sau recv-pop); response về sau timeout (pending_async đã pop → bỏ an toàn, in_flight không âm); mỗi request giảm in_flight đúng 1 lần.



### D-055 — 2026-07-08 — Bất biến bảo toàn ĐÚNG VÔ ĐIỀU KIỆN: đếm shutdown-leftover + snapshot-sau-quiesce (camera_worker)
Status: ✅ (verify thật — fullstack pass + full 465/1 + lint 5/0)
Scope: `profiles/vision_fullstack_profile.py` (`camera_worker.finally` + `_write_result` thêm `frames_dropped_shutdown`)
Nguồn: LOG Entry #253 · review đối kháng tiếp D-054 · design §4.5 ghi rõ "drain deadline-cut → bất biến lệch (biên hiếm)"
Evidence: máy `toann` — `test_fullstack_integration` 1 passed; full **465/1**; lint **5/0** (parse_result đọc field mới generic, không phá test cũ)
Links: D-054, C-019, T-020, K-053, K-056 (F2 đóng)
Nội dung: Review phát hiện biên THẬT: drain deadline = `timeout_s+1`; nếu server CHẾT + van còn Q frame lúc shutdown → window đầy, io chỉ gửi tiếp sau mỗi timeout-scan (`timeout_s`) → flush Q cần ~`ceil(Q/window)*timeout_s` ≫ deadline → drain thoát khi `outbound_size>0` → frame còn trong van: captured NHƯNG không submit/không evict → **bất biến VỠ đúng bằng leftover**. **FIX GỐC (hoàn thiện kế toán, không nới deadline vô hạn = ngọn):** `finally` teardown TRƯỚC (dừng io thread → counters+van ỔN ĐỊNH) → đếm `frames_dropped_shutdown = client.outbound_size` (leftover) → `_write_result` GỘP 3 tầng drop (client-window + SHM + shutdown) → bất biến `submitted+dropped==captured` đúng **VÔ ĐIỀU KIỆN**. Kèm: snapshot đọc SAU teardown = sau quiesce → đóng luôn F2 (K-056).
Vì sao: bất biến bảo toàn là LINH HỒN của fix A2 (không mất frame im lặng); "đúng nếu drain hoàn tất" là guarantee YẾU. Hoàn thiện kế toán 3 tầng (mỗi captured frame → đúng 1 trong {submitted, client-drop, shm-drop, shutdown-leftover}) = guarantee MẠNH vô điều kiện = đúng bản chất cho sản phẩm 24/7.



### D-056 — 2026-07-09 — Hook drift-check dùng LAUNCHER capability-test interpreter (fix gốc portable), không hardcode `python`
Status: ✅ (verify thật — launcher EXIT 0 dùng `py -3`; drift_check PASS)
Scope: `tests/drift_check.cmd` (mới) + 2 hook (`auto-drift-check`, `kiem-drift-bo-nho`) + docstring `tests/drift_check.py` + kit `ai-learning-os-kit/tests/drift_check.template.cmd`
Nguồn: LOG Entry #254 · lỗi thật user dán (hook EXIT 9009 "Python was not found") · kiểm 2 máy (k.nguyen: `py` OK/`python` Store-alias hỏng; toann: `python` OK/`py` chưa kiểm)
Evidence: `cmd /c tests\drift_check.cmd` từ repo root = PASS + EXIT 0 (dùng py -3); `py tests/drift_check.py` = EXIT 0
Links: K-055 (điểm-vào-1-script #250), K-057 (interpreter portability), T-022
Nội dung: Launcher `.cmd` dò Python theo KHẢ NĂNG (`--version` exit 0), thứ tự tin cậy `py -3` → venv dự án → `python`; dùng cái ĐẦU TIÊN chạy được. Hook trỏ `cmd /c tests\drift_check.cmd`. Đóng LỖ anti-drift: hook "tự chạy" (#251) âm thầm hỏng trên máy có `python` là Store-alias.
Vì sao: nguyên nhân GỐC = hook phụ thuộc 1 tên interpreter cố định (không portable). Đổi `python`→`py` là fix NGỌN (dời lỗi sang máy scoop thiếu `py`). Capability-test (không presence-test) loại đúng Store-alias tồn-tại-mà-hỏng. Launcher đúng trên MỌI máy → không dựa suy đoán máy nào có gì.


### D-057 — 2026-07-09 — Lớp trừu tượng môi trường = dev-env launcher `scripts/vp.cmd` (auto-detect + env-var override), cross-machine
Status: ✅ (verify thật — env/setup/verify EXIT 0, 465/1·5/0·drift PASS)
Scope: `scripts/vp.cmd` (mới) + `scripts/env.local.cmd.example` + `scripts/README.md` + `.gitignore` (env.local.cmd, .venv_broken)
Nguồn: LOG Entry #256 · yêu cầu user "lớp môi trường cho nhiều máy" · gốc K-013/K-044/K-047/K-048/K-049/K-052/K-057
Evidence: `vp env` EXIT 0 (BASEPY=py -3, GPU=khong); `vp verify` = 465/1 + lint 5/0 + drift PASS (test=0 lint=0 check=0) EXIT 0; `vp setup` reinstall EXIT 0
Links: D-056 (launcher pattern), K-058, T-023, K-044/K-049
Nội dung: Dispatcher `.cmd` subcommand `env/setup/test/lint/check/verify` — 1 giao diện chạy giống nhau mọi máy. Auto-detect interpreter theo KHẢ NĂNG (py→venv→python) + GPU qua nvidia-smi (chỉ inform). Ghi đè per-máy bằng `VP_PYTHON`/`VP_EXTRAS` nạp từ `scripts/env.local.cmd` (gitignored) — mỗi máy 1 profile, file chung vẫn chạy nhờ auto-detect. `lint` bake `importlinter.api` (K-044), `check` ủy quyền drift_check.cmd.
Vì sao: đổi máy = ma sát tay lặp lại (đã ghi ≥5 K-entry) → gom thành lớp ổn định = fix GỐC ma sát môi trường, không phải vá từng lần. KHÔNG auto-cài torch dù thấy GPU (tôn trọng K-049) → an toàn, để env-var quyết.


### D-058 — 2026-07-09 — CI server-side (GitHub Actions `verify.yml`) chạy cổng pytest+lint+drift sau mỗi push
Status: 🔵 (tạo xong · CHƯA verify chạy CI — verify khi push kích hoạt)
Scope: `.github/workflows/verify.yml`
Nguồn: LOG Entry #257 · khuyến nghị #256 (anti-drift server-side)
Evidence: file tạo (jobs.verify, windows-latest, 5 step: checkout/setup-python/install/pytest/lint(importlinter.api)/drift_check). CHƯA chạy CI (không chạy Actions cục bộ được)
Links: D-057 (vp verify — cùng cổng), D-056, K-059, T-024, K-044
Nội dung: CI chạy lại ĐÚNG cổng của `vp verify` trên server sau mỗi push/PR → không phụ thuộc dev chạy Kiro cục bộ. windows-latest giữ parity test `win32`. Dùng `python` trực tiếp (setup-python, không Store-alias) nên không cần launcher.
Vì sao: hook Kiro + linter là anti-drift PHÍA-DEV (bỏ qua được nếu push từ máy/tool khác). CI = anti-drift PHÍA-SERVER, vô điều kiện → mạnh nhất + chuẩn thương mại. Tái dùng cổng đã có = rủi ro thấp, không logic mới.


### D-059 — 2026-07-09 — Spec + code `object-tracking-count` — analytics stateful đầu tiên, đóng Lỗ 3/K-042
Status: ✅ (PHA1 design 0-diag + PHA2 code TDD HOÀN TẤT — verify **479/1 · lint 5/0** máy `k.nguyen.manh.toan`)
Scope: `.kiro/specs/object-tracking-count/{requirements,design}.md` (2 file, 0 code)
Nguồn: LOG Entry #258 · yêu cầu user "quay lại dự án cho xong" · `vision-vertical-slice/design.md` (sub-spec kế) · roadmap `scale-architecture` R3.3 · K-042
Evidence: `get_diagnostics` 2 file = 0 diagnostic; API bám code thật (`domain.iou`, `BaseStage._do_process→MediaPacket`, `with_artifact`, `Detection/BBox`, `ISink` — đã đọc)
Links: K-042 (stateful+camera-affinity), D-041 (slice stateless), T-011 (slice-trước), D-039 (pipeline-runner)
Nội dung: Thiết kế analytics STATEFUL đầu tiên (tracking + đếm-không-trùng) — 3 lớp: `domain/tracking.py::greedy_associate` (thuần, index-based, tái dùng iou) + `kernel` `Track` DTO/`ITracker` port + `runtime` `IouTracker`(giữ state)/`TrackingStage`(BaseStage, camera-affinity fail-fast). Additive: KHÔNG sửa CountStage (fan-out chung `detections`). 6 Correctness Property + testing no-GPU (chuỗi Detection dựng tay). IoU-greedy (không ML/GPU) → xác định.
Vì sao: bước nghiệp vụ kế của sản phẩm + là nền cho mọi analytics (không trùng đếm). Nhánh scale (A1) bị chặn GPU (R6.1) → chọn nghiệp vụ làm+test được không-GPU. Design-first (user preference): valid design rồi mới code.


### D-060 — 2026-07-09 — Spec + code `line-crossing-count` — đếm vật qua vạch, analytics tầng-2 trên tracking
Status: ✅ (PHA1 design 0-diag + PHA2 code TDD + wire `--line` HOÀN TẤT — verify **494/1 · lint 5/0**)
Scope: `.kiro/specs/line-crossing-count/{requirements,design}.md` (2 file, 0 code)
Nguồn: LOG Entry #261 · user "cực sâu tiếp tục" · xây trên D-059 (tracking) · roadmap R3.3
Evidence: `get_diagnostics` 2 file = 0 diagnostic; API bám thật (`Track.box`, `BaseStage._do_process`, `with_artifact`)
Links: D-059 (tracking — cung cấp track_id), K-042 (camera-affinity), K-060 (giới hạn tracking)
Nội dung: Thiết kế đếm vật băng qua vạch `[A,B]` theo hướng (in/out/total) — geometry thuần `domain/geometry.py` (orientation/cross-product + segments_intersect) + `LineCrossingStage`@runtime (stateful, đọc artifacts["tracks"], camera-affinity fail-fast, prune-bounded-memory). Additive (không sửa TrackingStage/lõi). 6 Property + test no-GPU (Track dựng tay).
Vì sao: "đếm qua cửa" = nghiệp vụ phổ biến + là bước kế tự nhiên trên tracking (cần track_id để biết cùng vật). Design-first: valid geometry/quy-ước-hướng trước khi code (subsystem có hình học dễ sai). Nhánh scale (A1) vẫn chặn GPU.
