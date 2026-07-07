# Requirements Document

> **SHM ring epoch switchover (shm-ring-epoch-switchover)** — sub-spec của `shm-production-hardening` (Task 10.3).
> **Loại spec:** Feature · **Workflow:** Design-First. Tài liệu này **suy ra (derive) từ `design.md`**. Mỗi
> requirement trỏ ngược mục design/code nguồn để chống bịa. CHƯA viết code — đây là hợp đồng để valid trước triển khai.
>
> **Nhãn (kế thừa design):** 🟢 [GROUNDED] · 🟡 [THIẾT KẾ MỚI — CẦN DUYỆT] · 🔴 [CẦN KIỂM CHỨNG].
> **EARS:** WHEN/WHILE/IF…THEN/WHERE + "THE SYSTEM SHALL". "Hệ thống" = SHM frame bus control-plane
> (`runtime/ipc/ring_control_plane.py` + `application/ring_supervisor.py`, mới) + writer/reader hiện có.

## Introduction

Spec cha đã phát `shm_ring_rebuild_requested` (🟢 `shm_frame_ring.py` L432–433) nhưng chưa ai xử lý. Sub-spec này
định nghĩa **control-plane switchover**: khi ring mất dần capacity do QUARANTINED terminal tích lũy, một
`RingSupervisor` dựng **ring epoch mới (N+1)**, publish qua **control-plane segment tên cố định**, cho writer +
reader chuyển sang ring mới an toàn, rồi giải phóng ring cũ không leak.

Phạm vi (theo design §Overview):
- **Trong phạm vi:** control-plane publish/bootstrap (Q1), chuyển epoch writer/reader, teardown ref-count ring cũ
  (Q3, Windows-safe), authority = supervisor, chính sách mất frame best-effort (Q2).
- **Ngoài phạm vi:** tuning `REBUILD_THRESHOLD` theo SLA (task benchmark riêng, Q4); backpressure (#07); structlog đầy đủ (#08); ARM (gate riêng).

Nền GROUNDED (KHÔNG làm lại): `ShmFrameRefData.ring_epoch` + reader stale-check trả `None` (🟢 L574/L641);
`ring_epoch` @ ctrl segment (🟢 L335–337); `new_ring_name()`=uuid4 ngẫu nhiên (🟢 L108); threshold default
`max(1,(n+1)//2)` (🟢 L265).

## Requirements

### Requirement 1: Switchover isolation — không đọc ring cũ

**User Story:** Là người vận hành 24/7, tôi muốn sau khi hệ chuyển sang ring epoch mới, không consumer nào còn
đọc nhầm dữ liệu ring cũ, để không xảy ra đọc frame rác/stale sau switchover.

#### Acceptance Criteria
*(Nguồn design: §Overview Q2 · §Data Models · Property 1. Code nền: L574/L641.)*

1. WHEN một reader gọi `read_ref(ref)` với `ref.ring_epoch` KHÁC epoch hiện tại của ring, THE SYSTEM SHALL trả
   `None` và KHÔNG đọc dữ liệu ring nào. (🟢 nền có ở L574.)
2. WHEN switchover từ epoch N sang N+1 hoàn tất publish, THE SYSTEM SHALL đảm bảo mọi ref stamp epoch N trở thành stale (đọc ra `None`).
3. THE SYSTEM SHALL NOT migrate frame đang nằm trong ring cũ sang ring mới (best-effort — Q2); frame in-flight ring cũ được coi là drop.

### Requirement 2: Epoch monotonic & publish authority

**User Story:** Là kỹ sư hệ thống, tôi muốn epoch tăng đơn điệu và việc công bố ring hiện tại là atomic, để hai
bên (writer/reader) không bao giờ đọc trạng thái control-plane "nửa vời".

#### Acceptance Criteria
*(Nguồn design: §Overview Q1 · §Data Models control-plane · Property 2.)*

1. THE SYSTEM SHALL chỉ tăng epoch theo chiều N → N+1 và KHÔNG bao giờ tái dùng một giá trị epoch đã dùng.
2. WHERE control-plane segment có tên CỐ ĐỊNH (well-known), THE SYSTEM SHALL lưu `{current_epoch, current_ring_name}` ở đó (KHÔNG suy tên từ epoch vì `new_ring_name`=uuid4 — 🟢 L108).
3. WHEN `RingSupervisor.publish(epoch, ring_name)` ghi control-plane, THE SYSTEM SHALL ghi `current_ring_name` TRƯỚC rồi ghi `current_epoch` (8B aligned) CUỐI CÙNG như authority atomic.
4. WHEN một bên đọc control-plane thấy `current_epoch` CHƯA đổi, THE SYSTEM SHALL tiếp tục dùng ring hiện tại (không đọc name nửa vời).

### Requirement 3: Single-writer xuyên switchover

**User Story:** Là kỹ sư hardening, tôi muốn bất biến 1-writer/ring được giữ qua switchover, để `generation`
không trùng và không vỡ chống-ABA.

#### Acceptance Criteria
*(Nguồn design: §Architecture · Property 3. Code nền: `register_writer` L350–374.)*

1. WHEN writer phát hiện epoch đổi, THE SYSTEM SHALL dừng ghi ring cũ và gọi `register_writer()` trên ring mới TRƯỚC khi ghi frame đầu tiên vào ring mới.
2. THE SYSTEM SHALL NOT cho phép 2 writer cùng ghi trên cùng một epoch (giữ `SingleWriterViolation` như spec cha).
3. WHEN writer cũ DEAD tại thời điểm switchover, THE SYSTEM SHALL coi sự kiện `shm_ring_rebuild_requested` (🟢 L371–373) là trigger switchover.

### Requirement 4: Giải phóng ring cũ không leak (Windows-safe)

**User Story:** Là người vận hành, tôi muốn ring cũ được giải phóng hoàn toàn sau switchover mà không leak SHM,
kể cả trên Windows nơi `unlink()` không có tác dụng.

#### Acceptance Criteria
*(Nguồn design: §Overview Q3 (quyết định B) · Property 4. Bằng chứng: thực nghiệm `_shm_lifecycle_probe` trên Windows + docstring L104–106.)*

1. WHEN một writer/reader chuyển khỏi ring epoch cũ, THE SYSTEM SHALL `close()` handle ring cũ của process đó (không giữ lại).
2. THE SYSTEM SHALL dựa cơ chế OS ref-count handle để giải phóng ring cũ — memory ring cũ được giải phóng khi HANDLE CUỐI đóng (verify Windows: attach lại sau đó → `FileNotFoundError`). THE SYSTEM SHALL NOT dùng biến đếm tường minh trên control-plane.
3. THE SYSTEM SHALL NOT cưỡng bức `unlink()` trên Windows; WHERE nền tảng là POSIX, THE SYSTEM MAY `unlink()` tên ring cũ ngay sau switchover (an toàn cho handle đang mở; tên mới dùng cho ring mới).
4. WHERE nền tảng là Linux, THE SYSTEM SHALL được verify hành vi `resource_tracker`/giải phóng ở Task T-C (🔴 chưa verify ngoài Windows).
4. IF một bên chưa `detach()` quá một timeout cấu hình, THEN THE SYSTEM SHALL emit cảnh báo qua observability hook và KHÔNG nhả handle cuối (ưu tiên không đọc-nhầm hơn là dọn sớm). 🟡 hành vi sau timeout cần chốt.

### Requirement 5: Tiến triển (liveness) — threshold kích hoạt switchover

**User Story:** Là người vận hành, tôi muốn khi ring hỏng tới ngưỡng thì hệ chắc chắn chuyển sang ring mới đầy
capacity, để bus không kẹt ở trạng thái suy giảm vĩnh viễn.

#### Acceptance Criteria
*(Nguồn design: §Architecture · Property 5. Code nền: threshold L265, emit L432–433.)*

1. WHEN `quarantined_count >= rebuild_threshold`, THE SYSTEM SHALL để `RingSupervisor` (authority, tầng application) nhận `shm_ring_rebuild_requested` và thực hiện switchover — KHÔNG rebuild ở mức per-slot.
2. WHEN switchover hoàn tất, THE SYSTEM SHALL cung cấp một ring epoch N+1 có đủ capacity (không slot QUARANTINED kế thừa từ ring cũ).
3. WHERE `rebuild_threshold` không được cấu hình, THE SYSTEM SHALL dùng default `max(1, (n_slots+1)//2)` (🟢 L265); tuning theo SLA là task benchmark riêng (Q4).

### Requirement 6: Observability & fail-fast control-plane

**User Story:** Là kỹ sư vận hành, tôi muốn mọi bước switchover quan sát được và control-plane từ chối segment
sai định dạng, để chẩn đoán sự cố và tránh đọc bytes rác.

#### Acceptance Criteria
*(Nguồn design: §Error Handling. Code nền: `check_ring_control` fail-fast pattern.)*

1. WHEN switchover bắt đầu/hoàn tất và khi teardown ring cũ, THE SYSTEM SHALL emit sự kiện qua `ObservabilityHook` (taxonomy nối tiếp spec cha).
2. WHEN attach control-plane segment có `magic`/`version` sai, THE SYSTEM SHALL raise `ValueError` fail-fast (KHÔNG diễn dịch bytes rác thành trạng thái hợp lệ).
3. WHERE nền tảng không phải x86-64, THE SYSTEM SHALL tuân theo platform gate của spec cha (ARM là task riêng, ngoài phạm vi).

## Glossary

- **Epoch:** số phiên bản của ring (u64). Switchover tăng N → N+1. Reader dùng để phát hiện ref cũ (stale).
- **Switchover:** quá trình chuyển từ ring epoch N sang ring epoch N+1 (tạo ring mới → publish → hai bên chuyển → dọn ring cũ).
- **Control-plane segment:** một SHM segment **tên cố định (well-known)** chứa `{current_epoch, current_ring_name}` — điểm hội tụ để writer/reader biết ring hiện tại (vì `new_ring_name` là uuid ngẫu nhiên, không suy diễn được).
- **Ring cũ / ring mới:** ring epoch N (đang bị suy giảm capacity) và ring epoch N+1 (mới dựng, đầy capacity).
- **OS handle ref-count (quyết định B):** cơ chế của HĐH — segment SHM sống tới khi handle CUỐI đóng, rồi tự giải phóng. Teardown ring cũ dựa vào đây (mỗi bên `close()` handle ring cũ khi rời), KHÔNG dùng biến đếm tường minh.
- **stale-ref:** một `ShmFrameRefData` mang `ring_epoch` cũ hơn epoch hiện tại → reader trả `None`.
- **QUARANTINED (terminal):** trạng thái slot bị loại vĩnh viễn (kế thừa spec cha) — nguyên nhân ring mất capacity dẫn tới switchover.
- **RingSupervisor:** thành phần tầng application, authority duy nhất quyết định và điều phối switchover.
- **RingControlPlane:** thành phần `runtime/ipc` quản control-plane segment (publish/read/attach-register/detach).
