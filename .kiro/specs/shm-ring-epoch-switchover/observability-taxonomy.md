# Observability taxonomy — SHM frame bus + switchover (Req 6.1)

> Catalog MỌI sự kiện phát qua `ObservabilityHook.emit(event, **fields)`. Dùng cho vận hành 24/7
> (dashboard/alert). Neo THẬT vào điểm emit trong code (grep `.emit(` 2026-07-03) — KHÔNG bịa.
> Mặc định hook = NO-OP (không tốn); truyền hook thật (vd `StderrObservabilityHook` / structlog #08) để thu.

## Nguồn phát
- `runtime/ipc/shm_frame_ring.py` — ring/slot/recovery/single-writer/reset (kế thừa spec cha #05 + reset H2).
- `application/ring_supervisor.py` — vòng đời switchover.
- `application/writer_epoch_coordinator.py` / `reader_epoch_coordinator.py` — chuyển epoch + teardown.

## Bảng sự kiện

| Event | Phát khi | Fields | Nguồn |
|-------|----------|--------|-------|
| `shm_switchover_started` | supervisor bắt đầu switchover | `new_epoch` | ring_supervisor `switchover()` |
| `shm_switchover_completed` | đã publish ring epoch mới | `new_epoch`, `new_ring_name` | ring_supervisor `switchover()` |
| `shm_ring_reset_for_reuse` | pool ring bị reset+bump để tái dùng (H2) | `ring_name`, `new_epoch` | shm_frame_ring `reset_for_reuse()` |
| `shm_writer_switched` | writer coordinator chuyển sang ring epoch mới | `old_epoch`, `new_epoch`, `new_ring_name` | writer_epoch_coordinator `_maybe_switch()` |
| `shm_reader_switched` | reader coordinator chuyển sang ring epoch mới | `old_epoch`, `new_epoch`, `new_ring_name` | reader_epoch_coordinator `_maybe_switch()` |
| `shm_ring_teardown_pending` | coordinator đã `close()` handle ring cũ (teardown B) | `epoch` (ring cũ) | writer/reader coordinator |
| `shm_ring_rebuild_requested` | quarantined_count ≥ threshold, HOẶC writer cũ DEAD | `ring_name`, `reason`(`threshold`\|`writer_dead`), `quarantined_count`/`threshold`/`ring_epoch` \| `dead_writer_pid` | shm_frame_ring `quarantine_poisoned_slot()` / `register_writer()` |
| `shm_slot_quarantined` | slot chuyển QUARANTINED (terminal) | `ring_name`, `slot`, `state`, `quarantined_count`, `healthy_slots` | shm_frame_ring `quarantine_poisoned_slot()` |
| `shm_ring_capacity_degraded` | sau quarantine — ring mất bớt slot khỏe | `ring_name`, `quarantined_count`, `healthy_slots` | shm_frame_ring `quarantine_poisoned_slot()` |
| `shm_owner_liveness_unknown` | không xác định được owner sống/chết (không quarantine) | `ring_name`, `slot`, `state`, `owner_pid`, `owner_create_time_ns` | shm_frame_ring `quarantine_poisoned_slot()` |
| `shm_slot_lock_timeout` | acquire lock slot timeout (nghi poison) | `ring_name`, `slot` | shm_frame_ring writer/reader |
| `shm_reader_registry_full` | registry reader đầy (MAX_READERS) | `ring_name`, `slot`, `reader_count` | shm_frame_ring `read()` |
| `shm_reader_reaped` | reap 1 ô reader chết (lease hết + DEAD) | `ring_name`, `slot`, `owner_pid`, `owner_create_time_ns` | shm_frame_ring `_reap_dead_readers()` |

## Chuỗi sự kiện điển hình 1 lần switchover (do rebuild)
1. `shm_slot_quarantined` × n → `shm_ring_capacity_degraded` (khi slot chết dần).
2. `shm_ring_rebuild_requested` (reason=threshold) khi `quarantined_count ≥ threshold`.
3. supervisor: `shm_switchover_started` → `shm_ring_reset_for_reuse` (pool ring mới) → `shm_switchover_completed`.
4. writer: `shm_writer_switched` → `shm_ring_teardown_pending` (ring cũ).
5. reader: `shm_reader_switched` → `shm_ring_teardown_pending` (ring cũ).

## Gợi ý alert vận hành (không bắt buộc — tham khảo)
- `shm_ring_rebuild_requested` bất thường dày → điều tra nguồn crash writer/tải.
- `shm_reader_registry_full` → thiếu slot registry / reader rò rỉ không unpin.
- `shm_owner_liveness_unknown` lặp → quyền/psutil trên host cần xem (K-005).

## Fail-fast (Req 6.2)
- Attach control-plane / ring ctrl segment sai `magic`/`version` → `ValueError` NGAY (không diễn dịch byte rác).
  Verify: `test_switchover_control_plane.py::test_attach_wrong_magic_fail_fast` + `check_cp_header`/`check_ring_control`.

## Giới hạn (🔴 thật)
- structlog/JSON logging đầy đủ = spec #08 (ngoài phạm vi). Ở đây chỉ hook thô (no-op mặc định / Stderr).
- Chưa gắn `ring_epoch` vào MỌI event (một số chỉ có `ring_name`); đủ để truy vết, chưa chuẩn hoá toàn bộ.
