# Mẩu 06 — `ShmFrameWriter`: ghi frame + `generation` (chống ABA)

> Bám file: `vision-platform/src/vision_platform/runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Bên "camera": tìm 1 slot trống → ghi ảnh vào → đánh dấu READY → trả `ShmFrameRefData`.

## 2. Cần biết trước
- Mẩu 03 (SlotState), 04 (header), 05 (ring). ABA (mẩu 02: generation).
- `np.copyto(arr, frame)` = chép nội dung ảnh vào vùng SHM.

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
class ShmFrameWriter:
    def __init__(self, ring):
        self._ring = ring
        self._next_slot = 0
        self._next_generation = 1
        self._pid, self._create_time_ns = current_identity()
        self._ring_epoch = ring.ring_epoch

    def write(self, frame):
        if frame.shape != (...): raise ValueError(...)
        if frame.dtype != np.uint8: raise ValueError(...)   # F-6 fail-fast
        for attempt in range(self._ring.n_slots):
            slot_idx = (self._next_slot + attempt) % self._ring.n_slots
            if self._ring.peek_state(slot_idx) == SlotState.QUARANTINED:
                continue                                    # bỏ slot terminal (lock-free)
            lock = self._ring.slot_lock(slot_idx)
            if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
                self._ring._obs.emit("shm_slot_lock_timeout", ...)
                self._ring.quarantine_poisoned_slot(slot_idx)
                continue
            try:
                buf = self._ring._meta_shms[slot_idx].buf
                state, gen, _pid = _read_header(buf)
                if state not in (SlotState.FREE, SlotState.DONE) or _read_reader_count(buf) != 0:
                    continue                                # chỉ ghi FREE/DONE + không còn reader
                new_gen = self._next_generation
                self._next_generation += 1
                _write_header(buf, SlotState.WRITING, new_gen, self._pid,
                              self._create_time_ns, time.monotonic_ns() + WRITE_LEASE_NS)
            finally:
                lock.release()
            # ghi data NGOÀI lock (slot đang WRITING, không ai đụng)
            arr = np.ndarray((...), dtype=np.uint8, buffer=self._ring._data_shms[slot_idx].buf)
            np.copyto(arr, frame)
            if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
                return None                                 # ERRATA E-15
            try:
                _write_header(buf, SlotState.READY, new_gen, self._pid, ...)  # commit READY
            finally:
                lock.release()
            self._next_slot = (slot_idx + 1) % self._ring.n_slots
            return ShmFrameRefData(ring_name=..., slot=slot_idx, generation=new_gen,
                                   ..., ring_epoch=self._ring_epoch)
        return None                                         # hết slot → caller backpressure
```
(Nguồn: `runtime/ipc/shm_frame_ring.py` — excerpt; `# ...` = lược bớt.)

## 4. Giải thích từng ý nhỏ nhất
- **`_next_generation` bắt đầu 1, tăng mỗi lần ghi** → mỗi frame có "số đời" riêng.
- **round-robin scan:** thử slot `_next_slot`, `+1`, `+2`... (mod n) → phân tải đều.
- **peek QUARANTINED → continue:** bỏ slot terminal mà KHÔNG đụng lock (mẩu 04/09).
- **acquire timeout → quarantine + continue:** lock kẹt (owner chết?) → thử recovery, bỏ slot.
- **chỉ ghi khi `FREE/DONE` VÀ `reader_count==0`:** không đè slot đang READY (rớt frame) hay đang có reader đọc.
- **2 pha ghi:** (1) dưới lock mark `WRITING` + `new_gen`; (2) **ghi data NGOÀI lock** (an toàn vì slot đang WRITING, reader không đọc WRITING); (3) dưới lock mark `READY`. → giữ lock ngắn, không giữ khi copy ảnh nặng.
- **`_write_header` ghi `state` CUỐI CÙNG** → reader chỉ thấy READY khi mọi field đã sẵn.
- **trả `ShmFrameRefData`** kèm `generation` + `ring_epoch` để reader kiểm.
- **`dtype != uint8` → ValueError (F-6):** chặn `np.copyto` ép/cắt ÂM THẦM.

## 5. Là gì (1–2 câu)
Bên ghi: tìm ô rảnh, đặt số đời mới, chép ảnh, chốt READY, trả vé (`ShmFrameRefData`).

## 6. Tại sao tồn tại / vấn đề nó giải
`generation` giải **ABA**: reader cầm vé (slot 0, gen 5); nếu writer đã đè slot 0 bằng frame mới (gen 9),
reader so `expected_gen(5) != actual(9)` → biết vé cũ, KHÔNG đọc nhầm. Ghi data ngoài lock → không nghẽn.

## 7. Dùng ở đâu trong project
- Camera process: `w = ShmFrameWriter(ring); ref = w.write(frame)`.
- Test: `test_step_05_shm.py` (writer round-robin, recycle, ABA) — pass.

## 8. Không có nó thì sao
Không có generation → reader không phân biệt frame cũ/mới trên cùng slot → **ABA bug** (đọc data mới tưởng
cũ, hoặc ngược lại). Ghi data trong lock → giữ lock lâu (copy 6MB) → nghẽn.

## 9. Ví von
Mỗi lần thay đồ trong phòng thử (slot), dán **số lượt mới** lên cửa (generation). Khách cầm phiếu "phòng 0,
lượt 5"; nếu phòng 0 đã sang lượt 9 → phiếu cũ vô hiệu, không mở nhầm.

## 10. Liên kết bức tranh lớn
Writer + Reader (mẩu 07) là 2 đầu của bus. `generation` (writer-local) là lý do **1 writer/ring** (mẩu 10).
Ghi `state` cuối + peek lock-free là nền recovery (mẩu 09).

## 11. Cạm bẫy (+errata)
- **E-15:** nếu acquire LẦN 2 (commit READY) timeout → slot kẹt WRITING (owner=self còn sống → không quarantine); production dựa lease+recovery cho owner CHẾT (mẩu 09).
- 2 writer/ring → generation trùng → vỡ ABA (F-4) → ép single-writer (mẩu 10).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao ghi data NGOÀI lock lại an toàn? Vì sao `state` phải ghi cuối cùng?
- `generation` chống ABA như thế nào? Ví dụ vé cũ đọc slot đã bị đè.

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py::ShmFrameWriter` (excerpt). · Test: `test_step_05_shm.py` (ABA/recycle pass). · Độ chắc: cao.
