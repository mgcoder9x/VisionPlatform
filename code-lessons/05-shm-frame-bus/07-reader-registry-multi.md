# Mẩu 07 — `ShmFrameReader`: pin / copy / unpin + reader registry (đa reader)

> Bám file: `vision-platform/src/vision_platform/runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Bên "consumer": xác minh vé (slot+gen+epoch) → **pin** (ghi tên mình vào registry) →
**copy** ảnh ra → **unpin**. Cho phép NHIỀU reader cùng đọc 1 frame.

## 2. Cần biết trước
- Mẩu 06 (writer/generation), 04 (reader_registry@48, reader_count@40). `arr.copy()` = chép ra bản riêng.

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
def read(self, slot_idx, expected_gen, *, ring_epoch=None):
    if ring_epoch is not None and ring_epoch != self._ring.ring_epoch:
        return None                                          # stale-ref (P0-3)
    lock = self._ring.slot_lock(slot_idx)
    if self._ring.peek_state(slot_idx) == SlotState.QUARANTINED:
        return None
    # PIN
    if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
        self._ring._obs.emit("shm_slot_lock_timeout", ...); self._ring.quarantine_poisoned_slot(slot_idx)
        return None
    try:
        buf = self._ring._meta_shms[slot_idx].buf
        state, gen, _pid = _read_header(buf)
        if gen != expected_gen or state not in (SlotState.READY, SlotState.READING):
            return None                                      # ABA / không đọc được
        _reap_dead_readers(buf, self._ring._liveness_fn, self._ring._obs, self._ring.name, slot_idx)
        free_idx = _registry_find_free(buf)
        if free_idx is None:
            self._ring._obs.emit("shm_reader_registry_full", ...)
            raise ReaderRegistryFull(...)                    # đầy → fail-fast, KHÔNG spin
        _registry_set(buf, free_idx, self._pid, self._create_time_ns, time.monotonic_ns() + READ_LEASE_NS)
        _write_reader_count(buf, _registry_count(buf))
        struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.READING))
    finally:
        lock.release()
    # COPY ngoài lock
    arr = np.ndarray((...), dtype=np.uint8, buffer=self._ring._data_shms[slot_idx].buf)
    frame_copy = arr.copy()
    # UNPIN
    if not lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S):
        return frame_copy                                    # E-15 F-3b: đã copy xong
    try:
        ridx = _registry_find(buf, self._pid, self._create_time_ns)
        if ridx is not None: _registry_clear(buf, ridx)
        count = _registry_count(buf)
        _write_reader_count(buf, count)
        if count == 0:
            # clear owner/lease + DONE
            struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.DONE))
    finally:
        lock.release()
    return frame_copy
```
(Nguồn: `runtime/ipc/shm_frame_ring.py::ShmFrameReader.read` — excerpt; `# ...` = lược bớt.)

## 4. Giải thích từng ý nhỏ nhất
- **stale-ref check:** `ring_epoch` vé khác epoch ring hiện tại → `None` (mẩu 12).
- **peek QUARANTINED → None:** slot terminal, không đọc.
- **PIN (dưới lock):** kiểm `gen == expected_gen` (ABA) + `state ∈ {READY, READING}` (cho reader thứ N vào slot đang READING); reap reader chết; tìm ô registry trống → ghi `(pid, create_time, lease)`; cập nhật `reader_count`; set `READING`.
- **`reader_count` là DẪN XUẤT:** = số ô registry active (đếm lại sau mỗi thay đổi), KHÔNG phải biến đếm rời (tránh lệch).
- **registry đầy → `ReaderRegistryFull`:** fail-fast, KHÔNG spin chờ (P1-2).
- **COPY ngoài lock:** `arr.copy()` tạo bản riêng → nhả slot nhanh (không giữ lock khi copy 6MB).
- **UNPIN (dưới lock):** xoá ô của mình; `count == 0` (reader cuối) → clear owner/lease + `DONE`; còn reader → giữ `READING` (Req 3.5).

## 5. Là gì (1–2 câu)
Bên đọc đa-reader: ghi danh vào registry của slot, copy ảnh ra bản riêng, rồi rút danh; reader cuối cùng
trả slot về DONE.

## 6. Tại sao tồn tại / vấn đề nó giải
Nhiều consumer (inference + recorder + preview) cùng đọc 1 frame. Registry + `reader_count` cho biết CÒN
AI đang đọc để writer KHÔNG đè (Req 3.6), và để recovery biết reader nào chết mà dọn (mẩu 09).

## 7. Dùng ở đâu trong project
- `r = ShmFrameReader(ring); frame = r.read(ref.slot, ref.generation)` (hoặc `r.read_ref(ref)` tự kiểm epoch).
- Test: `test_hardening_multi_reader.py` (reader thứ N pin khi slot đang READING; registry full; count) — pass.

## 8. Không có nó thì sao
Chỉ 1 reader (demo cũ) → không phục vụ đa consumer; hoặc dùng biến đếm rời → lệch khi reader chết đột ngột.

## 9. Ví von
Slot như **cuốn sách trong thư viện**; registry = **danh sách người đang mượn đọc tại chỗ**. Còn tên trong
danh sách → thủ thư (writer) không được xếp lại kệ; người cuối trả sách → sách sẵn sàng cho lượt sau.

## 10. Liên kết bức tranh lớn
Reader + Writer (mẩu 06) khép vòng. Registry là dữ liệu để recovery cho READING (mẩu 09) quyết định
quarantine hay không (còn reader sống thì KHÔNG loại slot — R-2.2).

## 11. Cạm bẫy (+errata)
- **E-15 F-3b:** unpin acquire timeout → đã có `frame_copy` nên trả về; slot có thể kẹt READING (owner=self reader còn sống → recovery không loại; reader chết mới bị reap).
- Copy TRONG lock (sai) → giữ lock lâu → nghẽn. Phải copy NGOÀI lock.

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao cho pin cả khi state là READING (không chỉ READY)? Đa reader hoạt động thế nào?
- `reader_count` "dẫn xuất" nghĩa là gì, vì sao không dùng biến đếm rời?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py::ShmFrameReader` (excerpt). · Test: `test_hardening_multi_reader.py` + `test_step_05_shm.py` pass. · Độ chắc: cao.
