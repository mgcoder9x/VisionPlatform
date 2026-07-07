# Mẩu 05 — `ShmRingBuffer`: cấp phát N slot + per-slot lock + control segment

> Bám file: `vision-platform/src/vision_platform/runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc** (transport). Là "kho" quản lý vùng SHM: cấp phát N slot (mỗi slot = 1 vùng meta +
1 vùng data), 1 lock/slot, và 1 control segment mô tả ring.

## 2. Cần biết trước
- Mẩu 03 (SlotState) · 04 (header layout 256B). [lock](../../knowledge-base/00-GLOSSARY.md) (mẩu 01).
- `multiprocessing.SharedMemory` = API Python tạo/gắn vùng RAM chia sẻ theo TÊN.

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
class ShmRingBuffer:
    def __init__(self, name, n_slots, height, width, channels=3, *, create,
                 slot_locks=None, liveness_fn=owner_liveness, obs=None,
                 ring_epoch=1, rebuild_threshold=None):
        # ...
        if slot_locks is not None:
            if len(slot_locks) != n_slots:
                raise ValueError(...)
            self._slot_locks = slot_locks
        elif create:
            self._slot_locks = [mp.Lock() for _ in range(n_slots)]
        else:
            raise RuntimeError("create=False requires slot_locks from parent process.")

        ctrl_name = f"{name}_ctrl"
        if create:
            ctrl = shared_memory.SharedMemory(name=ctrl_name, create=True, size=CTRL_SEGMENT_BYTES)
            ctrl.buf[:RING_CONTROL_BYTES] = pack_ring_control()
            struct.pack_into(U64_FMT, ctrl.buf, OFFSET_RING_EPOCH, ring_epoch)
        else:
            ctrl = shared_memory.SharedMemory(name=ctrl_name)
            check_ring_control(bytes(ctrl.buf[:RING_CONTROL_BYTES]))   # fail-fast nếu mismatch
        self._ctrl_shm = ctrl

        for i in range(n_slots):
            meta_name = f"{name}_meta_{i}"
            data_name = f"{name}_data_{i}"
            if create:
                meta = shared_memory.SharedMemory(name=meta_name, create=True, size=SLOT_HEADER_BYTES)
                data = shared_memory.SharedMemory(name=data_name, create=True, size=self._frame_bytes)
                _write_header(meta.buf, SlotState.FREE, 0, 0)
            else:
                meta = shared_memory.SharedMemory(name=meta_name)
                data = shared_memory.SharedMemory(name=data_name)
            self._meta_shms.append(meta); self._data_shms.append(data)
```
(Nguồn: `runtime/ipc/shm_frame_ring.py` — excerpt; `# ...` là lược bớt, không phải bịa.)

## 4. Giải thích từng ý nhỏ nhất
- **2 vai:** `create=True` (parent/creator TẠO các segment) vs `create=False` (child ATTACH vào segment đã có, phải nhận `slot_locks` từ parent).
- **`slot_locks`**: parent tạo `mp.Lock()` cho mỗi slot; truyền sang child qua `Process(args=...)` (lock không đi qua tên SHM được).
- **`create=False` mà thiếu `slot_locks`** → `RuntimeError` (child không tự tạo lock local hợp lệ).
- **`len(slot_locks) != n_slots`** → `ValueError` (phòng cấu hình lệch).
- **Control segment `<name>_ctrl`**: tạo TRƯỚC slot; creator ghi magic/version/size/max_readers + ring_epoch; attacher gọi `check_ring_control` → sai thì **fail-fast** ngay (không đụng slot rác).
- **Mỗi slot 2 segment:** `<name>_meta_<i>` (256B header) + `<name>_data_<i>` (`height*width*channels` byte ảnh). Creator init header về `FREE`.

## 5. Là gì (1–2 câu)
Lớp quản lý ring: tạo/gắn N cặp (meta, data) + lock/slot + ctrl segment; là nơi writer/reader dựa vào để
đọc-ghi đúng vùng nhớ chia sẻ.

## 6. Tại sao tồn tại / vấn đề nó giải
Gom mọi chi tiết cấp phát SHM + đồng bộ (lock/slot) + tự-mô-tả (ctrl) vào 1 chỗ, để writer/reader chỉ lo
logic ghi/đọc. Ctrl segment giải nỗi đau **attach nhầm ring / sai version** (fail-fast thay vì đọc bytes rác).

## 7. Dùng ở đâu trong project
- Parent: `ShmRingBuffer(name, ..., create=True)`; truyền `ring.slot_locks_for_children` cho subprocess.
- Child: `ShmRingBuffer(name, ..., create=False, slot_locks=...)`.
- `cleanup_all()` (creator) đóng + unlink mọi segment (gồm ctrl).

## 8. Không có nó thì sao
Writer/reader phải tự lo cấp phát + đặt tên + đồng bộ + kiểm version → lặp code, dễ lệch giữa các process.

## 9. Ví von
Như **ban quản lý bãi giữ xe**: kẻ ô (slot), phát chìa khoá từng ô (lock), treo bảng thông tin bãi ở cổng
(ctrl segment: "bãi số mấy, quy cách nào"). Ai vào sai quy cách → chặn ngay ở cổng.

## 10. Liên kết bức tranh lớn
`ShmRingBuffer` = nền vật lý; `ShmFrameWriter`/`ShmFrameReader` (mẩu 06/07) là logic đặt lên trên. Ctrl
segment cũng chứa writer registry + ring_epoch (mẩu 10/12).

## 11. Cạm bẫy (+errata)
- Trên Windows, `SharedMemory.unlink()` không hiệu quả như POSIX → dùng **tên theo uuid mỗi phiên** để creator không dính segment cũ (mẩu 12 / cold-start).
- Chỉ creator được `cleanup_all()` (child close thôi) — tránh unlink khi bên kia còn dùng.

## 12. Tự kiểm (retrieval + Feynman)
- Phân biệt `create=True` vs `create=False`. Vì sao child phải nhận `slot_locks` từ parent?
- Control segment giải quyết nỗi đau gì? "fail-fast" ở đây nghĩa là gì?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py` (excerpt có đánh dấu). · Test: `test_step_05_shm.py` (lifecycle) + `test_hardening_ring_v2.py` (ctrl fail-fast) — pass. · Độ chắc: cao.
