# Bài #05 — Mục lục các mẩu (đọc tuần tự)

> Đọc `00-cau-chuyen.md` TRƯỚC (vòng cung vấn đề→giải pháp). Rồi tới các mẩu nhỏ nhất dưới.
> Trạng thái: ⬜ chưa viết · 🔵 đang viết · ✅ đã viết + tự giải thích lại được.
> Bám code thật: `kernel/shm_frame_ref.py`, `kernel/shm_layout.py`, `runtime/ipc/_process_identity.py`,
> `runtime/ipc/shm_frame_ring.py` (trạng thái sau spec `shm-production-hardening`, 12/12 task).

| Mẩu | File | Nội dung | Code thật | Trạng thái |
|-----|------|----------|-----------|-----------|
| 01 | `01-vi-sao-shm.md` | Vì sao SHM/zero-copy giữa process (vs copy/queue) — nỗi đau + bức tranh | (khái niệm + `runtime/ipc/`) | ✅ |
| 02 | `02-shmframeref-dto.md` | `ShmFrameRefData` — con trỏ nhẹ (ring_name/slot/generation/h/w/c) + `ring_epoch` | `kernel/shm_frame_ref.py` | ✅ |
| 03 | `03-slotstate-vong-doi.md` | `SlotState` FREE→WRITING→READY→READING→DONE + QUARANTINED (terminal) | `kernel/shm_layout.py` | ✅ |
| 04 | `04-header-layout-atomic.md` | Header v2: offsets, `state`@0 4-byte aligned → atomic; vì sao pad 256B | `kernel/shm_layout.py` | ✅ |
| 05 | `05-shmringbuffer.md` | `ShmRingBuffer` — cấp phát N slot (meta+data) + per-slot lock + ctrl segment fail-fast | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 06 | `06-writer-generation-aba.md` | `ShmFrameWriter` — WRITING→copy data→READY + `generation` chống ABA + lease | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 07 | `07-reader-registry-multi.md` | `ShmFrameReader` — pin/copy/unpin + reader registry (đa reader) + reader_count dẫn xuất | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 08 | `08-process-identity-liveness.md` | `(pid, create_time)` + `owner_liveness` (psutil); cạm bẫy `os.kill` Windows | `runtime/ipc/_process_identity.py` | ✅ |
| 09 | `09-lease-recovery-quarantine.md` | Lease + lock-free peek + `quarantine_poisoned_slot` (double-snapshot, terminal) — đóng F-3/F-3b | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 10 | `10-single-writer.md` | `register_writer` — 1 writer/ring (intra + cross-process qua ctrl writer registry) | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 11 | `11-observability.md` | `ObservabilityHook.emit` + taxonomy — thay `except: pass` nuốt lỗi | `runtime/ipc/shm_frame_ring.py` | ✅ |
| 12 | `12-ring-epoch-coldstart-rebuild.md` | `ring_epoch` + stale-ref + `new_ring_name` (cold-start) + rebuild-request (nền → sub-spec) | `shm_frame_ring.py` + `shm_frame_ref.py` | ✅ |

> ✅ **#05 ĐÃ VIẾT ĐỦ 12/12 MẨU** (2026-06-24): `00-cau-chuyen.md` (vòng cung 6 nhịp) + mục lục này + 12 mẩu chi tiết (01–12). Chờ **cổng Feynman** (người học tự giải thích lại — AI không tự đánh "đã hiểu").
> Baseline code lúc lập kế hoạch (chạy thật): full **180 passed/1 skipped** · `lint-imports` 5 kept/0 broken · kill-recovery stress 5/5.
> Quy trình mỗi mẩu (LESSON-RULES §1/§4/§6): đọc lại file code → quote NGUYÊN VĂN + cite path → template 14 mục → không dán lesson vào chat.
> Sơ đồ (drawio-first) — **ĐÃ TẠO 3 file** (2026-07-02) trong `diagrams/`, well-formed XML + không cạnh gãy
> (validate bằng `xml.etree`): `ring-nslot-dataflow.drawio` (writer→ring→reader) · `slotstate-machine.drawio`
> (SlotState + QUARANTINED, nhãn cạnh cite dòng code thật) · `recovery-flow.drawio` (kill→quarantine terminal).
> ⏳ **Chờ user Export SVG** (máy không có drawio CLI/app — không tự export/verify render được).
> Ghi chú: #05 = 12 mẩu (bài phức tạp/production nhất — SHM atomicity + crash-recovery + multi-reader + single-writer + observability + epoch).
