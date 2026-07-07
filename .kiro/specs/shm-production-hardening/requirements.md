# Requirements Document

> **SHM frame bus PRODUCTION hardening (shm-production-hardening)**
> **Loại spec:** Feature · **Workflow:** Design-First. Tài liệu này **suy ra (derive) từ `design.md`** đã thẩm
> định (review Antigravity + validation Codex 2026-06-24, đã chốt 6 câu). Mỗi requirement trỏ ngược về mục
> design nguồn để chống bịa. Chưa viết code — đây là hợp đồng để valid trước khi triển khai.
>
> **Quy ước nhãn (kế thừa design):** 🟢 [GROUNDED] · 🟡 [THIẾT KẾ MỚI — CẦN DUYỆT] · 🔴 [CẦN KIỂM CHỨNG].
> **EARS:** WHEN/WHILE/IF…THEN/WHERE + "THE SYSTEM SHALL". "Hệ thống" = SHM frame bus (`runtime/ipc`).

## Introduction

Mục tiêu: nâng SHM frame bus (#05, `runtime/ipc/shm_frame_ring.py`) từ demo 1-writer/1-reader lên **sản phẩm
thương mại 24/7** chịu được process chết / lock poison mà KHÔNG cạn slot, quan sát được, phục vụ đa reader.

Phạm vi (theo design §Overview):
- **Trong phạm vi:** P-1 crash/poison recovery · P-2 observability hooks · P-3 multi-reader · P-4 header giàu ·
  P-5 ép invariant 1-writer · (P0-3) ring epoch/rebuild control-plane.
- **Ngoài phạm vi:** P-6 backpressure (#07) · structlog đầy đủ (#08) · seqlock (Option B) · validate ARM (task gate riêng).

Nền tảng bất biến đã GROUNDED: x86-64 store atomic chỉ khi ≤8B aligned → header đa-byte truy cập dưới lock;
trường `state` 4B @offset0 aligned → peek/ghi lock-free làm sentinel. Bản hiện tại đã đúng atomicity trong
model 1-writer/1-reader (16 test xanh + verify Windows).

## Requirements

### Requirement 1: Crash & lock-poison recovery (P-1)

**User Story:** Là người vận hành hệ thống 24/7, tôi muốn bus tiếp tục chạy khi một process owner chết hoặc
lock bị poison, để ring KHÔNG cạn slot và bus KHÔNG đứng toàn cục.

#### Acceptance Criteria
*(Nguồn design: §Error Handling · §State machine · Property 3.)*

1. WHEN một writer hoặc reader không acquire được lock của slot trong `LOCK_ACQUIRE_TIMEOUT`, THE SYSTEM SHALL
   peek lock-free trường `state` (4B @offset0) TRƯỚC khi làm bất cứ việc gì khác với slot đó.
2. IF state peek == `QUARANTINED` THEN THE SYSTEM SHALL bỏ qua slot đó NGAY mà KHÔNG acquire lock của nó.
3. WHEN `now >= lease_deadline_ns` AND `owner_liveness == DEAD`, THE SYSTEM SHALL ghi `state = QUARANTINED`
   bằng atomic 4-byte store (`struct.pack_into("<I", buf, 0, QUARANTINED)`).
4. WHILE `owner_liveness ∈ {ALIVE, UNKNOWN}` (kể cả khi lease đã quá hạn), THE SYSTEM SHALL NOT quarantine slot;
   thay vào đó skip slot + emit metric (`lease_expired_owner_alive` / `shm_owner_liveness_unknown`).
5. THE SYSTEM SHALL coi `QUARANTINED` là TERMINAL — slot bị loại vĩnh viễn, KHÔNG bao giờ reclaim về `FREE`
   và KHÔNG bao giờ acquire lại lock vật lý của slot đó (lý do: `multiprocessing.Lock` = semaphore, không robust — R-1.1).
6. WHEN một slot bị quarantine, THE SYSTEM SHALL giảm capacity khả dụng đúng 1 slot (`healthy_slots = n_slots - quarantined_count`)
   và emit `shm_ring_capacity_degraded`.
7. WHEN `quarantined_count >= REBUILD_THRESHOLD`, THE SYSTEM SHALL phát `shm_ring_rebuild_requested` cho control-plane
   (KHÔNG tự rebuild ở mức per-slot).

### Requirement 2: Process identity & liveness

**User Story:** Là kỹ sư hardening, tôi muốn xác định owner còn sống hay đã chết một cách chính xác và an toàn
trên Windows lẫn Linux, để recovery không quarantine nhầm process còn sống và không bị lừa bởi PID reuse.

#### Acceptance Criteria
*(Nguồn design: §Process identity & liveness · R-3.1/3.2/3.3 · chốt câu 1/2.)*

1. THE SYSTEM SHALL dùng `psutil` làm đường chính cho liveness và lấy `create_time`; `psutil>=5.9` là runtime dependency.
2. THE SYSTEM SHALL định danh owner/reader bằng cặp `(pid, create_time_ns)` với `create_time_ns = int(psutil.Process().create_time()*1e9)` qua một helper duy nhất.
3. WHEN `psutil.Process(pid)` ném `NoSuchProcess`, THE SYSTEM SHALL trả `Liveness.DEAD`.
4. WHEN process tồn tại nhưng `create_time` thực tế KHÁC `create_time_ns` đã lưu, THE SYSTEM SHALL trả `DEAD` (PID đã bị OS tái dùng).
5. WHEN gặp `AccessDenied` / `ZombieProcess` / `OSError`, THE SYSTEM SHALL trả `UNKNOWN` và SHALL NOT quarantine.
6. WHEN `pid <= 0`, THE SYSTEM SHALL trả `DEAD`.
7. THE SYSTEM SHALL NOT dùng `os.kill(pid, 0)` trên Windows (đã verify thật: tương đương `CTRL_C_EVENT` → gây `KeyboardInterrupt`).
8. WHERE bắt buộc cấm native wheel (không được dùng psutil), THE SYSTEM SHALL dùng fallback ctypes hardened
   (`WinDLL("kernel32", use_last_error=True)` + khai báo `argtypes/restype` HANDLE 64-bit + xử lý `WAIT_FAILED` + `ERROR_ACCESS_DENIED→UNKNOWN`),
   coi là sub-spec riêng có test đầy đủ, KHÔNG phải đường chính vòng đầu.
9. THE SYSTEM SHALL ép `import-linter` cấm import `psutil` trong layer `domain` và `kernel` (chỉ cho phép ở `runtime/ipc`).

### Requirement 3: Multi-reader (P-3)

**User Story:** Là kiến trúc sư, tôi muốn nhiều consumer (inference, recorder, preview…) cùng đọc một frame,
để hệ thống phục vụ đa luồng tiêu thụ mà không serialize về 1 reader.

#### Acceptance Criteria
*(Nguồn design: §Multi-reader · P1-2 · Property 5 · chốt câu 3.)*

1. THE SYSTEM SHALL hỗ trợ tối đa `MAX_READERS = 8` reader pin đồng thời trên một slot.
2. WHEN một reader pin, THE SYSTEM SHALL (dưới lock) đặt `state = READING`, ghi định danh `(pid, create_time, reader_lease_ns)`
   vào một ô registry trống, rồi recompute `reader_count`, và gia hạn lease.
3. THE SYSTEM SHALL giữ invariant `reader_count == số ô registry đang active` (reader_count là giá trị DẪN XUẤT, không phải biến độc lập).
4. IF registry đã đầy (`MAX_READERS` ô) khi reader xin pin THEN THE SYSTEM SHALL fail-fast + emit `shm_reader_registry_full` (KHÔNG spin chờ).
5. WHEN một reader unpin (sau khi đã `arr.copy()`), THE SYSTEM SHALL (dưới lock) xoá đúng ô của nó theo `(pid, create_time)`,
   recompute `reader_count`; IF `reader_count == 0` THEN đặt `state = DONE`.
6. THE SYSTEM SHALL chỉ cho writer tái dùng slot khi `state ∈ {FREE, DONE}` và `reader_count == 0`.
7. WHEN một reader đã đăng ký là `DEAD` AND lease của nó quá hạn, THE SYSTEM SHALL reap đúng ô đó + giảm count;
   THE SYSTEM SHALL NOT quarantine cả slot nếu vẫn còn reader sống (giải R-2.2).
8. IF một reader chết khi đang GIỮ lock (lúc pin/unpin) THEN slot đó trở thành terminal (lock có thể đã poison).

### Requirement 4: Header layout v2 (P-4)

**User Story:** Là người triển khai, tôi muốn header slot mang đủ metadata (owner, lease, reader registry, định
danh) và tự mô tả (magic/version), để recovery có dữ liệu cần và attach sai bị bắt ngay.

#### Acceptance Criteria
*(Nguồn design: §Data Models header v2 · P2-1 · chốt câu 3/6.)*

1. THE SYSTEM SHALL đặt trường `state` tại offset 0, kích thước 4B, aligned để peek/ghi lock-free atomic.
2. THE SYSTEM SHALL bố trí các trường 8-byte (`generation`@8, `owner_pid`@16, `owner_create_time_ns`@24, `lease_deadline_ns`@32)
   tại offset chia hết cho 8; `reader_count`@40 (4B) chia hết cho 4.
3. THE SYSTEM SHALL chứa mảng `reader_registry[MAX_READERS]`, mỗi ô `<QQQ` (24B) = `(reader_pid, reader_create_time_ns, reader_lease_ns)`.
4. THE SYSTEM SHALL pad header lên bội cache-line 64B → 256B/slot (với `MAX_READERS=8`).
5. THE SYSTEM SHALL nhúng `magic`, `header_version`, `header_size`, `max_readers` vào metadata.
6. WHEN attach phát hiện `magic` / `header_version` / `header_size` / `max_readers` không khớp, THE SYSTEM SHALL
   fail-fast (KHÔNG diễn dịch bytes rác thành state hợp lệ).
7. THE SYSTEM SHALL có một test kiểm `struct.calcsize` + alignment thật cho layout v2 trước khi dùng (🔴 cần chạy thật khi code).

### Requirement 5: Ép invariant single-writer (P-5)

**User Story:** Là kiến trúc sư, tôi muốn đảm bảo mỗi ring chỉ có đúng 1 writer, để counter `generation` không bị
trùng (vỡ chống ABA).

#### Acceptance Criteria
*(Nguồn design: §Ép invariant 1-writer · P1-3.)*

1. THE SYSTEM SHALL ném `RuntimeError` nếu `register_writer()` được gọi >1 lần trong cùng một process.
2. THE SYSTEM SHALL duy trì ring-level writer registry `(writer_pid, writer_create_time, writer_lease)` (segment control-plane).
3. WHEN một writer mới đăng ký while writer hiện tại `ALIVE` AND `create_time` khớp, THE SYSTEM SHALL reject writer mới.
4. WHEN writer hiện tại `DEAD`, THE SYSTEM SHALL ưu tiên rebuild/switchover ring (KHÔNG takeover im lặng ring cũ có slot terminal),
   trừ khi chứng minh được takeover an toàn.

### Requirement 6: Observability hooks (P-2)

**User Story:** Là người vận hành, tôi muốn mọi sự kiện bất thường (poison, quarantine, drop, reader chết) phát ra
ngoài thay vì bị nuốt im lặng, để phát hiện sự cố khi đang chạy thật.

#### Acceptance Criteria
*(Nguồn design: §Observability · P2-2.)*

1. THE SYSTEM SHALL thay mọi `except: pass` im lặng bằng `ObservabilityHook.emit(event, **fields)`.
2. THE SYSTEM SHALL hỗ trợ taxonomy sự kiện cố định: `shm_slot_lock_timeout` · `shm_slot_quarantined` ·
   `shm_reader_registry_full` · `shm_reader_reaped` · `shm_owner_liveness_unknown` · `shm_ring_rebuild_requested` · `shm_ring_capacity_degraded`.
3. THE SYSTEM SHALL đính kèm mỗi event các field tối thiểu: `ring_name, ring_epoch, slot, state, owner_pid,
   owner_create_time_ns, quarantined_count, healthy_slots`.
4. THE SYSTEM SHALL dùng hook mặc định no-op/stderr ở bản này (structlog đầy đủ để dành #08).

### Requirement 7: Atomicity & Correctness Properties

**User Story:** Là kỹ sư đảm bảo chất lượng, tôi muốn các thuộc tính đúng đắn (no torn read, ABA, sticky) được
phát biểu rõ thành điều kiện kiểm được, để biến thành property-based test ở pha tasks.

#### Acceptance Criteria
*(Nguồn design: §Correctness Properties · P1-1.)*

1. THE SYSTEM SHALL chỉ đọc các trường header đa-byte (>4B hoặc nhiều trường) khi đang GIỮ lock (Property 1 — no torn read).
2. THE SYSTEM SHALL chỉ cho reader trust data khi `actual_gen == expected_gen` AND `state ∈ {READY, READING}` (Property 2 — ABA).
3. THE SYSTEM SHALL giữ `QUARANTINED` sticky/terminal — không bao giờ tự revert (Property 6).
4. WHEN recovery cần đọc nhiều trường (`owner_pid/create_time/lease/registry`) sau lock-timeout, THE SYSTEM SHALL
   đọc snapshot 2 lần liên tiếp và chỉ hành động khi 2 snapshot GIỐNG nhau HOẶC `state` đã là `QUARANTINED`;
   nếu torn/không ổn định → KHÔNG quarantine, emit metric + retry sau (P1-1).
5. THE SYSTEM SHALL ghi header theo thứ tự có chủ đích: identity → lease → `state` cuối cùng; chỉ `state` là authority để skip.

### Requirement 8: Ring epoch / rebuild control-plane (P0-3)

**User Story:** Là kiến trúc sư, tôi muốn cơ chế tạo lại ring khi quá nhiều slot terminal, có handshake và quan sát
được, để reader cũ không đọc nhầm ring mới và việc rebuild không ẩn trong recovery per-slot.

#### Acceptance Criteria
*(Nguồn design: §P0-3 + P2-1.)*

1. THE SYSTEM SHALL thêm trường `ring_epoch: int` vào DTO `ShmFrameRefData` (layer kernel, vẫn thuần — không import multiprocessing).
2. WHEN một reader cầm `ShmFrameRefData` có `ring_epoch` khác epoch hiện tại, THE SYSTEM SHALL trả `None` (stale), KHÔNG đọc ring mới.
3. THE SYSTEM SHALL lưu ring-level metadata ở segment riêng `<name>_ctrl`: `magic, header_version, header_size, max_readers, ring_id/epoch, writer_registry`.
4. THE SYSTEM SHALL giao quyền rebuild cho control-plane (supervisor / composition root), KHÔNG phải per-slot recovery.
5. WHEN rebuild, THE SYSTEM SHALL tạo ring epoch mới (name theo epoch/uuid) → publish → writer/reader chuyển sang;
   unlink ring cũ CHỈ khi không còn handle attach.
6. THE SYSTEM MAY tách toàn bộ switchover/epoch thành sub-spec `shm-ring-epoch-switchover` nếu quá lớn (🔴 cần kiểm chứng).

### Requirement 9: Cold-start sanitation

**User Story:** Là người vận hành, tôi muốn khởi động lại sau crash không bị dính segment/lock rác từ phiên trước,
để không attach nhầm vào state hỏng.

#### Acceptance Criteria
*(Nguồn design: §R-5.1 + P1-4.)*

1. THE SYSTEM SHALL dùng tên ring theo epoch/uuid mỗi phiên thay vì tái dùng name cố định cho data ring.
2. THE SYSTEM SHALL bảo đảm creator (`create=True`) KHÔNG attach vào name cũ; luôn tạo segment + lock MỚI.
3. THE SYSTEM SHALL ghi nhận (documented) rằng `SharedMemory.unlink()` KHÔNG có tác dụng trên Windows
   (block mất khi mọi handle đóng) → không dựa vào unlink để dọn; dựa vào epoch naming.
4. WHERE cần well-known name, THE SYSTEM SHALL chỉ dùng nó cho control-plane nhỏ; data ring dùng name theo epoch.

### Requirement 10: Phạm vi nền tảng (platform scope)

**User Story:** Là chủ sản phẩm, tôi muốn tuyên bố "production-ready" chỉ cho nền tảng đã kiểm chứng thật, để
không hứa quá khả năng đã verify.

#### Acceptance Criteria
*(Nguồn design: §R-4.1 · chốt câu 5.)*

1. THE SYSTEM SHALL chỉ claim production correctness cho x86-64 trong vòng hardening này.
2. THE SYSTEM SHALL coi việc validate ARM64 (visibility/ordering yếu) là task gate riêng `arm-atomic-sentinel-validation`
   (stress visibility + kill-holder + jitter trên HW thật) — chưa gọi "verified" cho tới khi có bằng chứng đó.
3. WHERE chạy trên ARM, THE SYSTEM MAY giới hạn fast-path lock-free chỉ bật trên x86-64, ARM dùng lock thuần (lock có barrier ngầm).

### Requirement 11: Cấu hình lease & timeout

**User Story:** Là người vận hành realtime, tôi muốn các tham số thời gian tách bạch và chỉnh được, để đường scan
không bị chặn lâu và lease không bao trùm thời gian inference.

#### Acceptance Criteria
*(Nguồn design: §Lease · chốt câu 4.)*

1. THE SYSTEM SHALL đặt `WRITE_LEASE_NS = READ_LEASE_NS = 2s` mặc định, qua config (KHÔNG hard-code).
2. THE SYSTEM SHALL tách `LOCK_ACQUIRE_TIMEOUT = 0.05–0.10s` cho đường scan realtime (KHÔNG dùng giá trị 2s như demo).
3. THE SYSTEM SHALL bảo đảm lease chỉ bao `pin / copy / unpin`, KHÔNG bao thời gian model inference.
4. THE SYSTEM SHALL coi lease là chỉ báo kích hoạt recovery khi quá hạn (không tự kill process).

### Requirement 12: Migration an toàn & regression

**User Story:** Là người triển khai, tôi muốn nâng cấp theo từng slice nhỏ mà không phá vỡ hành vi đã đúng, để mỗi
bước đều có bằng chứng xanh.

#### Acceptance Criteria
*(Nguồn design: §Testing Strategy · chốt thứ tự triển khai.)*

1. THE SYSTEM SHALL giữ toàn bộ 16 test #05 hiện có XANH sau MỖI slice migration.
2. THE SYSTEM SHALL giữ `lint-imports` = 5 kept / 0 broken sau MỖI slice (thêm `psutil` vào forbidden của domain/kernel KHÔNG được làm gãy contract).
3. THE SYSTEM SHALL triển khai theo thứ tự đã chốt: identity → header v2 → lock-free peek + terminal quarantine →
   reader registry → observability → writer registry/ring epoch → ring rebuild (KHÔNG gộp rebuild vào per-slot).
4. THE SYSTEM SHALL chạy `pytest` + `lint-imports` thật (đọc output) làm bằng chứng cho mỗi slice — KHÔNG gọi "xong" bằng đọc-code-tĩnh.
5. WHEN một slice là `pid_is_alive`, THE SYSTEM SHALL ghi kết quả test ra FILE rồi đọc (terminal có thể nuốt output / KeyboardInterrupt).

## Glossary

- **Slot:** một ô trong ring buffer chứa 1 frame (data + header metadata).
- **Header:** vùng metadata cố định của mỗi slot (`state`, `generation`, `owner_pid`, lease, reader registry…).
- **`state` sentinel:** trường 4-byte @offset0, aligned → đọc/ghi atomic lock-free; dùng để peek/skip và đánh dấu QUARANTINED.
- **QUARANTINED (terminal):** trạng thái slot bị loại VĨNH VIỄN khi owner chết + lease quá hạn; không bao giờ reclaim về FREE (vì lock OS không robust).
- **Lease:** mốc thời gian (`lease_deadline_ns`) owner cam kết hoàn tất; quá hạn là điều kiện CẦN (không đủ) để recovery.
- **`LOCK_ACQUIRE_TIMEOUT`:** thời gian tối đa chờ acquire lock của 1 slot trên đường scan realtime (0.05–0.10s), TÁCH khỏi lease.
- **Liveness (ALIVE/DEAD/UNKNOWN):** kết quả kiểm tra process còn sống qua psutil, định danh bằng `(pid, create_time_ns)`.
- **PID reuse:** OS cấp lại một pid cũ cho process khác; chống bằng so khớp `create_time`.
- **Reader registry:** mảng `MAX_READERS` ô trong header lưu `(reader_pid, create_time, lease)` để phát hiện reader chết.
- **`generation`:** counter chống ABA — reader chỉ trust data khi gen khớp.
- **Ring epoch:** số hiệu phiên bản của ring; reader cầm ref epoch cũ → trả `None` (stale) sau switchover.
- **Control-plane:** lớp điều phối (supervisor/composition root) có quyền rebuild ring, tách khỏi recovery per-slot.
- **Observability hook:** callback `emit(event, **fields)` thay cho `except: pass` im lặng.
- **Sticky sentinel:** giá trị `state` một khi đặt QUARANTINED thì không tự revert (đảm bảo eventual-visibility trên ARM cũng an toàn).
