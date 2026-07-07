# Bài #05b — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung vấn đề K-012 → giải pháp H2). Rồi tới các mẩu nhỏ nhất dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + code verify ‖ Feynman = cột riêng ("chờ Feynman").
> Bám code thật (trạng thái sau sub-spec `shm-ring-epoch-switchover`, Task 1–9 ✅ trên Windows;
> full **242 passed/1 skipped** · lint **5 kept/0 broken** · T-B 5/5).

| Mẩu | File dự kiến | Nội dung (mẩu nhỏ nhất) | Code thật | Trạng thái |
|-----|--------------|-------------------------|-----------|-----------|
| 01 | `01-vi-sao-switchover.md` | Nối #05: `shm_ring_rebuild_requested` phát ra mà chưa ai xử lý → cần switchover | `shm_frame_ring.py` L424–435 (điểm emit) | ✅ (chờ Feynman) |
| 02 | `02-control-plane-layout.md` | Layout control-plane segment: magic/version/epoch@16/ring_name[96] → 128B; vì sao "name trước, epoch cuối" | `kernel/shm_control_plane_layout.py` | ✅ (chờ Feynman) |
| 03 | `03-ring-control-plane.md` | `RingControlPlane.publish/read_current` (authority atomic) + fail-fast attach (magic sai → ValueError) | `runtime/ipc/ring_control_plane.py` | ✅ (chờ Feynman) |
| 04 | `04-bootstrap-current-ring.md` | `bootstrap_current_ring` — đọc control-plane → mở data ring qua `ring_opener` (DI); epoch=0 → lỗi | `runtime/ipc/ring_control_plane.py` | ✅ (chờ Feynman) |
| 05 | `05-k012-loi-cap-khoa.md` | **K-012**: `ShmRingBuffer(create=False)` bắt buộc `slot_locks`; `mp.Lock` không mở theo tên → ring lúc chạy không cấp khoá được | `shm_frame_ring.py __init__` + `test_step_05_shm.py` | ✅ (chờ Feynman) |
| 06 | `06-ring-pool.md` | `RingPool` — K ring cố định (tên `{uuid}_r{i}`), `slot_locks_map()`, `activate`, `make_pool_opener` (giải K-012) | `runtime/ipc/ring_pool.py` | ✅ (chờ Feynman) |
| 07 | `07-reset-for-reuse.md` | `ShmRingBuffer.reset_for_reuse` — clear slot (gồm QUARANTINED) + clear registry + bump epoch (đơn điệu, ghi cuối) | `runtime/ipc/shm_frame_ring.py` | ✅ (chờ Feynman) |
| 08 | `08-ring-supervisor.md` | `RingSupervisor` — nhận `shm_ring_rebuild_requested` → `pool.activate` + publish (đảo D-002/D-010: pool giữ ring) | `application/ring_supervisor.py` | ✅ (chờ Feynman) |
| 09 | `09-writer-coordinator.md` | `WriterEpochCoordinator` — check-on-write; register ring mới TRƯỚC frame đầu; `old.close()` (teardown B); fail-fast SingleWriterViolation | `application/writer_epoch_coordinator.py` | ✅ (chờ Feynman) |
| 10 | `10-reader-coordinator.md` | `ReaderEpochCoordinator` — check-on-read; stale-ref cũ → None; thứ tự "publish trước" đảm bảo không đọc nhầm | `application/reader_epoch_coordinator.py` | ✅ (chờ Feynman) |
| 11 | `11-tb-cross-process.md` | **T-B** — spawn writer THẬT + `locks_map` thừa kế + switchover giữa chừng → đọc frame epoch mới cross-process (bằng chứng K-012 giải) | `tests/test_switchover_cross_process.py` | ✅ (chờ Feynman) |
| 12 | `12-no-leak-q2-observability.md` | No-leak = số segment không tăng theo switchover (bounded reuse); Q2 bound ≤ n_slots; taxonomy sự kiện | `tests/test_switchover_leak.py` + `observability-taxonomy.md` | ✅ (chờ Feynman) |

> ✅ **ĐỦ 12/12 MẨU** (2026-07-03) — quote nguyên văn code + neo test đã pass (full 242 passed/1 skipped). Chờ **cổng Feynman** (người học tự giải thích lại). Mỗi mẩu khi viết:
> đọc lại file code → quote NGUYÊN VĂN + cite path → template 14 mục (LESSON-RULES §4) → không dán vào chat.
> Sơ đồ (drawio-first) — **ĐÃ TẠO 2 file** trong `diagrams/` (validate `xml.etree`: well-formed, 0 cạnh gãy):
> `switchover-flow.drawio` (9 node/9 cạnh — rebuild→supervisor→activate→publish→coordinator, control-plane + pool) ·
> `k012-h2.drawio` (10 node/3 cạnh — vấn đề K-012 vs giải pháp H2). ⏳ **Chờ user Export SVG** (máy không có drawio CLI).
> Chờ **cổng Feynman** (người học tự giải thích lại).
> Bám thứ tự: control-plane (02–04) → K-012 & pool (05–07) → điều phối (08–10) → bằng chứng & vận hành (11–12).
