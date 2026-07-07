# Mẩu 10 — `register_writer`: ép bất biến 1-writer/ring (intra + cross-process)

> Bám file: `runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Ép luật "mỗi ring chỉ 1 writer" — qua control segment (ctrl) mức ring.

## 2. Cần biết trước
- Mẩu 06: `generation` là WRITER-LOCAL → 2 writer → trùng generation → vỡ ABA (F-4).
- Mẩu 08 (liveness). ctrl segment (mẩu 05) chứa writer registry (pid/create_time/lease @16..39).

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
def register_writer(self, pid=None, create_time_ns=None):
    if pid is None or create_time_ns is None:
        pid, create_time_ns = current_identity()
    if self._writer_registered:
        raise SingleWriterViolation("register_writer() gọi >1 lần trong process này (Req 5.1)")
    cur_pid, cur_ct = self._read_writer()
    if cur_pid != 0:
        liveness = self._liveness_fn(cur_pid, cur_ct)
        if liveness is Liveness.ALIVE:
            raise SingleWriterViolation(f"ring đã có writer còn sống pid={cur_pid} (Req 5.3)")
        if liveness is Liveness.UNKNOWN:
            raise SingleWriterViolation(...)                 # không claim khi không chắc
        self._obs.emit("shm_ring_rebuild_requested", ring_name=self.name, reason="writer_dead", ...)
        raise SingleWriterViolation("writer cũ ... đã chết — cần rebuild ring, KHÔNG takeover")
    # trống → claim
    struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, pid)
    struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, create_time_ns)
    struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_LEASE_NS, time.monotonic_ns() + WRITE_LEASE_NS)
    self._writer_registered = True
```
(Nguồn: `runtime/ipc/shm_frame_ring.py::ShmRingBuffer.register_writer` — excerpt.)

## 4. Giải thích từng ý nhỏ nhất
- **Intra-process:** cờ `_writer_registered` → gọi 2 lần trong 1 process → `SingleWriterViolation` (Req 5.1).
- **Cross-process (ctrl writer registry):** đọc writer hiện tại; `ALIVE` → reject; `UNKNOWN` → reject (không claim khi mơ hồ); **`DEAD` → KHÔNG takeover im lặng** mà emit `shm_ring_rebuild_requested` + reject (Req 5.4) — vì ring của writer chết có thể có slot terminal, phải dựng lại (mẩu 12).
- **Trống (`cur_pid==0`) → claim:** ghi `(pid, create_time, lease)` vào ctrl.
- **API explicit:** KHÔNG auto gọi trong `ShmFrameWriter.__init__` (để không phá test/hành vi cũ) — composition root gọi lúc setup.

## 5. Là gì (1–2 câu)
Cổng đăng ký writer: đảm bảo tối đa 1 writer sống/ring; writer cũ chết thì đòi rebuild chứ không tiếp quản ẩu.

## 6. Tại sao tồn tại / vấn đề nó giải
`generation` writer-local → 2 writer → trùng số đời → reader đọc nhầm (vỡ ABA). register_writer chặn tận gốc.

## 7. Dùng ở đâu trong project
- Composition root: `ring.register_writer()` trước khi spawn worker ghi.
- Test: `test_hardening_single_writer.py` (claim/2-lần/ALIVE/DEAD-rebuild/UNKNOWN) — pass.

## 8. Không có nó thì sao
Lỡ tạo 2 writer/ring → generation trùng → chống-ABA vỡ → reader đọc data sai đời mà không biết.

## 9. Ví von
Như **đăng ký chủ sạp ở chợ**: 1 sạp (ring) chỉ 1 chủ (writer). Chủ cũ còn buôn → không cho ai chiếm; chủ cũ
bỏ đi (chết) → KHÔNG cho người lạ nhảy vào bán tiếp trên sạp cũ (có thể còn hàng hỏng) → phải dựng sạp mới.

## 10. Liên kết bức tranh lớn
Bảo vệ tính đúng của `generation` (mẩu 06). Writer-death → rebuild-request nối sang cơ chế ring epoch (mẩu 12).

## 11. Cạm bẫy (+errata)
- Registration KHÔNG khoá nội bộ → giả định gọi ở startup (composition root điều phối), KHÔNG 2 process đăng ký ĐỒNG THỜI cùng micro-giây (documented). Tái-đăng-ký worker-mới được liveness bảo vệ.

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao 1 ring chỉ được 1 writer? Điều gì vỡ nếu 2 writer?
- Writer cũ DEAD → vì sao KHÔNG cho writer mới "takeover" ngay mà đòi rebuild?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py::register_writer` (excerpt). · Test: `test_hardening_single_writer.py` pass. · Spec: Req 5 / P1-3. · Độ chắc: cao.
