# Design — shm-ring-epoch-switchover (sub-spec)

> Sub-spec của `shm-production-hardening` (Task 10.3). Design-first (HLD + LLD).
> Nhãn độ chắc: 🟢 đã verify với code thật · 🟡 quyết định thiết kế (cần chốt) · 🔴 chưa verify / cần đo.
> Mọi khẳng định về code đã đọc nguyên văn `runtime/ipc/shm_frame_ring.py` + `kernel/shm_layout.py` (cite dòng).

## Overview

Spec cha đã **phát** sự kiện `shm_ring_rebuild_requested` nhưng **chưa ai xử lý** (🟢 verify: emit tại
`shm_frame_ring.py` L432–433 khi `quarantined_count >= rebuild_threshold`, và L371–373 khi writer cũ DEAD).
Khi slot bị QUARANTINED terminal tích lũy tới ngưỡng, ring mất dần capacity → cần **dựng ring mới (epoch N+1)**
và cho writer + reader **chuyển sang ring mới** an toàn, rồi **giải phóng ring cũ** không leak. Đây là
**control-plane đa-process** — phần khó và rủi ro nhất còn lại của #05.

**Nền đã có sẵn (KHÔNG làm lại — 🟢 verify với code):**

| Thành phần | Bằng chứng (dòng) |
|---|---|
| `ShmFrameRefData.ring_epoch` stamp vào mọi ref | writer L474, L553 |
| Reader từ chối ref epoch cũ (stale) → `None` | `read()` L574; `read_ref()` L641 |
| `ring_epoch` đọc từ ctrl segment @40 | property L335–337; ghi khi create L291 |
| `new_ring_name()` = `prefix_ + uuid4().hex` (NGẪU NHIÊN) | L99–108 |
| `rebuild_threshold` default `max(1,(n_slots+1)//2)` | L265 |
| Emit `shm_ring_rebuild_requested` (reason=threshold, kèm ring_epoch) | L432–433 |
| Ctrl segment 64B: magic/ver/size/max_readers(0–15) + writer registry(16–39) + ring_epoch@40 | `shm_layout.py` |

**Quyết định thiết kế (đã sửa theo phát hiện code):**

- **Q1 — Publish ring/epoch mới: well-known control-plane segment 🟡 (SỬA).** Root-cause: tên ring là
  `uuid4().hex` (🟢 L108) → **không suy diễn từ epoch**; không thể "chỉ publish số epoch". Docstring
  `new_ring_name` (🟢 L106) chỉ hướng: *"Well-known name ... chỉ trỏ control-plane nhỏ; data ring dùng tên này."*
  → dùng **1 segment tên CỐ ĐỊNH** chứa {epoch, tên-ring-hiện-tại}. Ghi **name trước, epoch cuối** (epoch 8B
  aligned = authority atomic; reader chỉ tin khi epoch tăng — cùng nguyên lý "state ghi cuối").
- **Q2 — Mất frame khi switchover: best-effort. Bound cấu trúc ≤ n_slots (2026-07-03).** Reader ref cũ → None (🟢 L574).
  Bound suy ra từ thiết kế (KHÔNG bịa số): coordinator **check-on-write** (D-008) chuyển ring TRƯỚC mỗi `write()`
  → writer KHÔNG ghi thêm frame nào vào ring cũ sau khi publish epoch mới (mis-write = 0). Frame "mất" = các frame
  READY **chưa được đọc** còn nằm trong ring cũ tại thời điểm switchover → ref epoch cũ hoá stale → reader drop.
  Số này **≤ n_slots** (dung lượng ring). Verify định tính: T-B (serialize) drop = 0. **[CẬP NHẬT 2026-07-03] Bound ≤ n_slots ĐÃ XÁC NHẬN THỰC NGHIỆM** (`test_switchover_q2_bound.py`: worst-case ring-đầy-chưa-đọc → drop = n_slots; drain trước → drop = 0). 🔴 **Số đo dưới TẢI THẬT
  (nhiều fps, đa reader) VẪN CHƯA đo** — cần perf harness riêng (K-014); không bịa.
- **Q3 — Giải phóng ring cũ: dựa OS handle ref-count (quyết định B) 🟢/🔴.** Root-cause (SỬA so với đề xuất
  ref-count tường minh ban đầu): **thực nghiệm thật trên Windows** (`_shm_lifecycle_probe`) cho thấy OS TỰ
  ref-count handle — memory ring cũ sống tới khi HANDLE CUỐI đóng, biến mất ngay sau đó (`FileNotFoundError`
  khi attach lại). → **KHÔNG cần biến đếm tường minh.** Mỗi bên `close()` handle ring cũ khi rời epoch;
  supervisor `close()` handle của nó sau switchover; OS giải phóng ở handle cuối. POSIX có thể `unlink()` tên
  ring cũ ngay sau switchover (an toàn cho handle đang mở; tên mới dùng cho ring mới). 🔴 hành vi
  `resource_tracker` trên **Linux CHƯA verify** (chỉ verify Windows) → kiểm ở T-C. Biến `attach_count` bị BỎ.
- **Q4 — REBUILD_THRESHOLD: giữ default `max(1,(n+1)//2)` 🟡** (🟢 L265) + task benchmark tune sau, không hard-code SLA.

## Architecture

```
[ShmRingBuffer emit shm_ring_rebuild_requested]  --event-->  [RingSupervisor (application layer)]
                                                                     |
             1. tao ring epoch N+1 (new_ring_name uuid moi)          |
             2. ghi {name, epoch=N+1} vao CONTROL-PLANE (name co dinh)|
                                                                     v
     [Writer] poll control-plane --thay epoch doi--> dung ghi ring N, register_writer tren ring N+1
     [Reader] poll control-plane --thay epoch doi--> attach ring N+1; ref epoch N cu -> None (da co)
                                                                     |
             3. moi ben close() handle ring N khi roi epoch (khong dem tuong minh)
             4. OS ref-count handle -> giai phong ring N o HANDLE CUOI (POSIX co the unlink som)
```

- **Authority = `RingSupervisor`** ở tầng application (KHÔNG per-slot). 🟢 khớp HANDOFF mục 1 + code cấm
  per-slot tự rebuild (L432 chỉ *emit*, không tự dựng).
- Layer: supervisor thuộc `application` (phụ thuộc kernel + runtime — 🟢 khớp AGENTS §4). `RingControlPlane`
  thuộc `runtime/ipc`.
- **Bootstrap:** writer/reader attach control-plane (tên cố định biết trước) → đọc `current_ring_name` +
  `current_epoch` → attach data ring tương ứng. Đây là điểm hội tụ duy nhất để hai bên đồng bộ ring hiện tại.

## Components and Interfaces

- **`runtime/ipc/ring_control_plane.py` (mới): `RingControlPlane`** — quản control-plane segment tên cố định.
  - `publish(epoch: int, ring_name: str) -> None` — ghi name trước, epoch cuối (authority).
  - `read_current() -> tuple[int, str]` — trả (epoch, ring_name) hiện tại.
  - `close()` / `unlink()` — quản vòng đời handle segment.
  - **KHÔNG có `attach_register/detach/attach_count`** (quyết định B): teardown ring cũ dựa OS handle ref-count
    (mỗi bên `close()` handle ring cũ khi rời; OS giải phóng ở handle cuối) — không đếm tường minh.
  - `bootstrap_current_ring(cp, ring_opener)` (module-level, additive): `read_current()` → `ring_opener(name)` →
    trả `(ring, epoch)`; epoch=0 → RuntimeError. KHÔNG sửa `ShmFrameWriter/Reader` hiện có.
- **`application/ring_supervisor.py` (mới): `RingSupervisor`** — nhận event qua obs hook, quyết định switchover:
  - `on_event(event: str, **fields)` — lọc `shm_ring_rebuild_requested`.
  - `switchover() -> int` — tạo ring epoch N+1 (`new_ring_name()`), `publish`, điều phối teardown ring cũ, trả epoch mới.
- **Sửa nhẹ `ShmFrameWriter`/`ShmFrameReader`** (🟡 tối thiểu để KHÔNG phá 12/12 task xanh của spec cha):
  bootstrap qua control-plane; poll epoch đổi → chuyển ring (writer `register_writer` lại trên ring mới; reader attach ring mới).

## Data Models

- **Control-plane segment (tên cố định, ví dụ `f"{app}_cp"`)** — layout đề xuất (🟡, kích thước 🔴 cần chốt ≥128B):
  | Field | Kiểu | Offset | Ghi chú |
  |---|---|---|---|
  | magic | u32 | 0 | phát hiện attach nhầm (fail-fast, cùng pattern `check_ring_control`) |
  | version | u32 | 4 | version control-plane |
  | (reserved) | u32 | 8 | RESERVED — quyết định B bỏ `attach_count` (teardown dựa OS handle ref-count) |
  | current_epoch | u64 | 16 | **ghi CUỐI** = authority (8B aligned atomic) |
  | current_ring_name | bytes[96] | 24 | tên ring uuid (`vp_ring_<32hex>` ~40B), pad cố định |
- 🔴 Vì sao KHÔNG nhét vào ctrl 64B per-ring: ctrl per-ring đã dùng tới offset 48/64 (writer registry + ring_epoch),
  và có vấn đề chicken-and-egg (phải biết tên ring mới tìm được `<ring>_ctrl`). Control-plane phải là segment RIÊNG, tên cố định.
- **Không đổi** `ShmFrameRefData` (đã có `ring_epoch` — 🟢) và layout slot (giữ nguyên spec cha).

## Correctness Properties

🟡 **[THIẾT KẾ MỚI — CẦN DUYỆT]** (sẽ thành PBT ở phase tasks). Số Requirement điền khi tạo `requirements.md`.

### Property 1: Không đọc ring cũ sau switchover
Sau switchover N→N+1, KHÔNG reader nào trả frame epoch N (ref epoch cũ → `None`). (🟢 nền có ở L574.)
**Validates: Requirements 1.1**

### Property 2: Epoch đơn điệu tăng
Epoch chỉ chuyển N→N+1, không bao giờ giảm hoặc tái dùng giá trị cũ.
**Validates: Requirements 2.1**

### Property 3: Single-writer xuyên switchover
Không bao giờ có 2 writer cùng ghi 1 epoch; writer `register_writer` lại trên ring mới TRƯỚC khi ghi.
(🟢 nền `register_writer` L350–374.)
**Validates: Requirements 3.1**

### Property 4: Không leak ring cũ
Sau khi mọi handle ring cũ `close()`, OS giải phóng memory ring cũ (verify Windows: handle cuối đóng → segment biến mất). 🔴 Linux verify ở T-C.
**Validates: Requirements 4.1**

### Property 5: Tiến triển (liveness)
Khi `quarantined_count >= threshold`, hệ CUỐI CÙNG chuyển sang epoch mới đầy capacity — không kẹt vĩnh viễn.
**Validates: Requirements 5.1**

## Error Handling

- **Publish thất bại giữa chừng** (ghi name xong, chưa ghi epoch): reader/writer thấy epoch CHƯA đổi → tiếp tục dùng
  ring cũ (không đọc name nửa vời). Epoch ghi cuối là rào an toàn.
- **Writer cũ DEAD lúc switchover:** đã có path emit `shm_ring_rebuild_requested` (🟢 L371–373); supervisor coi như trigger switchover.
- **Bên chưa đóng handle ring cũ** (treo/chậm): với quyết định B, ring cũ chỉ giải phóng khi HANDLE CUỐI đóng
  — bên treo giữ handle của CHÍNH NÓ, KHÔNG chặn các bên khác (họ đã sang ring mới). Ring cũ tồn tại thêm cho tới
  khi bên treo đóng/chết (handle đóng theo process exit). Supervisor emit `shm_ring_teardown_pending` để quan sát;
  KHÔNG có "handle cuối do supervisor giữ" nữa. 🟡 Có thể thêm cảnh báo sau `TEARDOWN_OBSERVE_WINDOW` (mặc định ~6s) — tùy chọn.
- **liveness UNKNOWN:** không coi là DEAD (giữ nguyên tinh thần recovery spec cha — không hành động khi không chắc).
- **Attach control-plane sai magic/version:** fail-fast `ValueError` (cùng pattern `check_ring_control` 🟢).

## Testing Strategy

- **T-A (unit, deterministic):** tiêm event `shm_ring_rebuild_requested` → `RingSupervisor` tạo epoch N+1 +
  `RingControlPlane.publish`. Assert `read_current()` = (N+1, tên mới). Không cần đa-process.
- **T-B (cross-process, cốt lõi — reuse harness kill Task 4.3):** spawn writer+reader epoch N → ép quarantine
  ≥ threshold bằng kill THẬT → assert supervisor switchover; writer re-register epoch N+1; reader ref N cũ → None,
  rồi bắt được frame epoch N+1; **assert không đọc nhầm ring cũ** (qua epoch). Đo frame-drop (điền bound Q2).
- **T-C (tài nguyên/leak):** sau switchover + mọi handle đóng → assert ring cũ giải phóng. Linux `/dev/shm`;
  🔴 Windows: xác nhận handle đóng (ghi rõ nếu không đo được leak trực tiếp).
- **PBT (hypothesis):** Property 1..5 cho phần logic supervisor/control-plane thuần (không I/O đa-process).

## Giới hạn / rủi ro (🔴 nói thật)

- Toàn bộ switchover CẦN test cross-process THẬT trên môi trường đích (Windows + Linux) — 🔴 chưa chạy.
- Windows không quan sát leak SHM trực tiếp dễ dàng — có thể chỉ verify được "handle đã đóng".
- Poll control-plane có độ trễ (interval) → khoảng transient hai ring cùng tồn tại; bound theo interval.
  🟡 **Default khuyến nghị:** `CP_POLL_INTERVAL = 0.1s` (cùng bậc `LOCK_ACQUIRE_TIMEOUT` 0.05–0.1s spec cha);
  ở 30fps ≈ 3 frame transient (chấp nhận với best-effort Q2). Cần user xác nhận.
- REBUILD_THRESHOLD chưa tune SLA (🔴).

## Nguồn
- `.kiro/specs/shm-ring-epoch-switchover/00-HANDOFF.md` (phạm vi).
- Code: `runtime/ipc/shm_frame_ring.py` (L99–108, L265, L291, L335–337, L371–374, L432–433, L474, L553, L574, L641),
  `kernel/shm_layout.py` (`CTRL_SEGMENT_BYTES`, `OFFSET_RING_EPOCH`). Đã đọc nguyên văn.
- `shm-production-hardening/design.md` §P0-3 + P2-1.
