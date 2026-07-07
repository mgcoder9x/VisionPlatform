# Mẩu 11 — `ObservabilityHook`: thấy được sự cố (thay `except: pass`)

> Bám file: `runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Lớp mỏng để mọi sự cố SHM **phát ra ngoài** (log/metric) thay vì bị nuốt im lặng.

## 2. Cần biết trước
- Các sự kiện đến từ recovery (mẩu 09), registry (mẩu 07), single-writer (mẩu 10).
- "nuốt lỗi im lặng" = `except: pass` → sự cố xảy ra mà không ai biết.

## 3. Code thật (quote nguyên văn)
```python
class ObservabilityHook:
    """Hook quan sát sự kiện SHM (Task 6 / P-2). Mặc định NO-OP — thay cho `except: pass` im lặng."""
    def emit(self, event: str, **fields) -> None:  # no-op mặc định
        pass

class StderrObservabilityHook(ObservabilityHook):
    def emit(self, event: str, **fields) -> None:
        print(f"[shm-obs] {event} {fields}", file=sys.stderr)
```
Taxonomy sự kiện (phát ở các đường): `shm_slot_lock_timeout` · `shm_slot_quarantined` ·
`shm_ring_capacity_degraded` · `shm_owner_liveness_unknown` · `shm_reader_registry_full` ·
`shm_reader_reaped` · `shm_ring_rebuild_requested`.
(Nguồn: `runtime/ipc/shm_frame_ring.py` — quote nguyên văn phần class; taxonomy trích từ các lời `emit`.)

## 4. Giải thích từng ý nhỏ nhất
- **`emit(event, **fields)`** = 1 hàm chung nhận tên sự kiện + các trường (ring_name/slot/state/owner_pid/quarantined_count/healthy_slots...).
- **Mặc định NO-OP:** ring không truyền `obs` → `ObservabilityHook()` (không làm gì) → **không tốn gì**, hành vi cũ không đổi (16 test #05 vẫn xanh).
- **`StderrObservabilityHook`:** bản in stderr để debug/vận hành nhẹ.
- **Tiêm vào ring:** `ShmRingBuffer(..., obs=my_hook)` → writer/reader/recovery gọi `self._ring._obs.emit(...)`.
- **structlog đầy đủ** để dành #08 (ngoài phạm vi #05) — ở đây chỉ là callback.

## 5. Là gì (1–2 câu)
Điểm móc quan sát: mỗi sự cố (lock timeout, quarantine, registry full, reader reaped, liveness unknown,
capacity degraded, rebuild requested) đều `emit` ra ngoài với đủ ngữ cảnh.

## 6. Tại sao tồn tại / vấn đề nó giải
Sản phẩm 24/7: nếu nuốt lỗi (`except: pass`), khi bus degrade/quarantine/rebuild mà không ai biết → mù vận
hành. Hook cho phép nối log/metric/alert thật mà KHÔNG ràng buộc SHM vào 1 hệ log cụ thể (đảo phụ thuộc).

## 7. Dùng ở đâu trong project
- Quarantine → `shm_slot_quarantined` + `shm_ring_capacity_degraded` (mẩu 09).
- Registry full → `shm_reader_registry_full` (mẩu 07); reap → `shm_reader_reaped`.
- Writer chết / quá ngưỡng → `shm_ring_rebuild_requested` (mẩu 10/12).
- Test: `test_hardening_observability.py` (recording hook kiểm từng event + field) — pass.

## 8. Không có nó thì sao
Sự cố xảy ra âm thầm → không phát hiện poison/drop/degrade khi vận hành → sản phẩm không đủ "quan sát được".

## 9. Ví von
Như **hộp đen máy bay + đèn báo buồng lái**: mọi sự kiện bất thường được ghi lại + báo ra, thay vì im lặng
cho tới khi hỏng nặng.

## 10. Liên kết bức tranh lớn
Hook là "dây thần kinh cảm giác" của bus. Mặc định no-op giữ demo nhẹ; production cắm hook thật (→ structlog #08).

## 11. Cạm bẫy (+errata)
- Emit trong đường nóng phải RẺ (no-op mặc định); hook thật nặng nên đẩy async/log riêng (để #08).
- `ring_epoch` trong event: có ở rebuild_requested; các event khác thêm dần khi cần.

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao mặc định NO-OP mà vẫn "wire sẵn" emit khắp nơi? Lợi gì?
- Kể vài sự kiện taxonomy + khi nào phát.

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py::ObservabilityHook` (quote nguyên văn) + các lời `emit`. · Test: `test_hardening_observability.py` pass. · Spec: Task 6 / P2-2. · Độ chắc: cao.
