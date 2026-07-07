# Sub-spec handoff — shm-ring-epoch-switchover

> **Trạng thái:** ⬜ CHƯA triển khai. Đây là **con trỏ bàn giao** từ spec `shm-production-hardening` Task 10.3.
> Switchover/rebuild ĐẦY ĐỦ là việc lớn (control-plane, đa-process handshake) → tách spec riêng để làm sau.

## Đã có sẵn (nền do shm-production-hardening đặt — KHÔNG làm lại)
- DTO `ShmFrameRefData.ring_epoch` (kernel) + reader `read_ref()` trả `None` khi epoch stale (Task 8).
- Control segment `<name>_ctrl` (64B): magic/version/header_size/max_readers + writer registry + `ring_epoch`@40 (Task 7/8).
- `ShmRingBuffer.ring_epoch` (đọc), `new_ring_name()` (tên epoch/uuid mỗi phiên — Task 9).
- Sự kiện `shm_ring_rebuild_requested` đã được phát khi `quarantined_count >= REBUILD_THRESHOLD` (Task 10.1) — nhưng CHƯA ai xử lý nó.

## Phạm vi sub-spec này (cần làm)
1. **Authority rebuild = supervisor/composition root** (KHÔNG per-slot). Nhận `shm_ring_rebuild_requested` → quyết định switchover.
2. **Tạo ring epoch mới** (name theo `new_ring_name()` / epoch+1) → publish cho writer + reader → 2 bên chuyển sang ring mới.
3. **Reader/writer chuyển epoch** an toàn: reader cầm ref epoch cũ tự `None` (đã có); writer dừng ghi ring cũ, đăng ký lại trên ring mới.
4. **Unlink ring cũ CHỈ khi không còn handle attach** (đếm tham chiếu / handshake). Lưu ý Windows: block mất khi mọi handle đóng (không unlink chủ động được) → cần protocol đóng handle có thứ tự.
5. **REBUILD_THRESHOLD** đo thực nghiệm theo SLA (Task 10.2 để default thận trọng `ceil(n_slots/2)`, 🔴 chưa tuning thật).

## Acceptance (gợi ý cho sub-spec)
- Switchover end-to-end cross-process: writer+reader chuyển từ epoch N→N+1, không mất frame quá X, không đọc nhầm ring cũ.
- Ring cũ được giải phóng hoàn toàn (không leak SHM) sau khi mọi handle đóng — verify trên Windows + Linux.
- 🔴 Toàn bộ CẦN test cross-process thật + đo trên môi trường đích.

## Nguồn
- `shm-production-hardening/design.md` §P0-3 + P2-1 (ring epoch / rebuild protocol).
- Tasks 8/9/10 của spec đó (đã đặt nền).
