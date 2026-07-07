# Mẩu 09 — `WriterEpochCoordinator`: writer tự chuyển ring khi epoch đổi (check-on-write)

> Bám code thật `application/writer_epoch_coordinator.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
- **Tầng:** `application`. Bọc quanh 1 `ShmFrameWriter` (#05) — **additive**, KHÔNG sửa writer cũ.
- **Vai:** ở process camera; mỗi lần ghi frame, tự kiểm control-plane để chuyển sang ring mới khi có switchover.

## 2. Cần biết trước
- Mẩu 03 (`read_current`), 04 (`bootstrap_current_ring`), 06 (`make_pool_opener`), 07 (epoch bump).
- Từ #05: `register_writer` (1-writer/ring), `SingleWriterViolation`, `ShmRingBuffer.close` (teardown B).
- Gloss: **check-on-write** = kiểm epoch NGAY TRƯỚC mỗi lần ghi · **fail-fast** = lỗi thì nổ ngay (không nuốt).

## 3. Code thật (quote nguyên văn — `application/writer_epoch_coordinator.py`)
```python
    def bootstrap(self) -> int:
        """Mở ring hiện tại từ control-plane + register_writer TRƯỚC frame đầu. Trả epoch hiện tại."""
        ring, epoch = bootstrap_current_ring(self._cp, self._ring_opener)
        ring.register_writer()                      # 1-writer/ring (Req 5) — trước khi ghi
        self._ring = ring
        self._epoch = epoch
        self._writer = self._writer_factory(ring)
        return epoch

    def _maybe_switch(self) -> Optional[int]:
        cur_epoch, name = self._cp.read_current()
        if cur_epoch == self._epoch:
            return None

        new_ring = self._ring_opener(name)
        try:
            new_ring.register_writer()              # register ring MỚI trước frame đầu (Req 3.2)
        except Exception:
            new_ring.close()                        # fail-fast vẫn dọn handle ring mới (không leak)
            raise                                   # single-writer/epoch giữ nguyên — caller xử lý

        old_ring = self._ring
        old_epoch = self._epoch
        self._ring = new_ring
        self._epoch = cur_epoch
        self._writer = self._writer_factory(new_ring)
        self._obs.emit("shm_writer_switched", old_epoch=old_epoch, new_epoch=cur_epoch, new_ring_name=name)

        if old_ring is not None:
            old_ring.close()                        # teardown B: đóng handle ring cũ (KHÔNG unlink/detach)
            self._obs.emit("shm_ring_teardown_pending", epoch=old_epoch)
        return cur_epoch

    def write(self, frame):
        if self._writer is None:
            raise RuntimeError("WriterEpochCoordinator.write() gọi trước bootstrap()")
        self._maybe_switch()
        return self._writer.write(frame)
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `bootstrap`: mở ring hiện tại (mẩu 04) → `ring.register_writer()` **TRƯỚC khi ghi** (giữ 1-writer/ring) →
  nhớ `_ring/_epoch` + tạo writer thật qua `_writer_factory`.
- `_maybe_switch`: đọc `read_current()`; nếu `cur_epoch == self._epoch` (không đổi) → `return None` (không làm gì).
- `new_ring = self._ring_opener(name)` — mở ring mới (pool ring, mẩu 06).
- `new_ring.register_writer()` trong `try` — **register ring mới TRƯỚC frame đầu** (Req 3.2). Nếu raise
  (`SingleWriterViolation`): `new_ring.close()` (dọn handle, **không leak**) rồi `raise` → **fail-fast**, epoch cũ giữ nguyên.
- Sau register OK: đổi con trỏ `_ring/_epoch/_writer` sang ring mới; emit `shm_writer_switched`.
- `if old_ring is not None: old_ring.close()` — **teardown B**: đóng handle ring cũ (không unlink; pool giữ segment). emit `shm_ring_teardown_pending`.
- `write(frame)`: nếu chưa bootstrap → raise; **luôn `_maybe_switch()` TRƯỚC** rồi mới ghi → **không bao giờ ghi
  vào ring lạc epoch** (mis-write ring cũ = 0 → nền của bound Q2 ≤ n_slots).

## 5. Là gì (1–2 câu)
Lớp bọc writer: mỗi `write()` tự kiểm epoch; nếu đổi thì mở ring mới → register (trước frame đầu) → đóng ring cũ
→ ghi ring mới. Vi phạm 1-writer → fail-fast.

## 6. Tại sao tồn tại / vấn đề nó giải
Writer #05 không biết switchover. Coordinator thêm khả năng "tự chuyển ring" mà **không sửa writer cũ** (additive
→ giữ baseline #05 xanh). Check-on-write đảm bảo **không ghi nhầm ring cũ** sau khi supervisor publish.

## 7. Dùng ở đâu trong project
- Process camera: `WriterEpochCoordinator(cp, make_pool_opener(locks_map,...))` → `bootstrap()` → vòng lặp `write(frame)`.
- Verify cross-process ở T-B (mẩu 11).

## 8. Không có nó thì sao
Không có coordinator → writer cứ ghi ring cũ sau switchover → frame đổ vào ring đã bỏ → reader không thấy (đọc
ring mới) → mất frame + có thể vi phạm 1-writer khi ai đó dựng writer trên ring mới.

## 9. Ví von
Như **tài xế giao hàng** trước mỗi chuyến **liếc bảng tin** (control-plane): nếu kho đổi (epoch mới) thì **đăng
ký ở kho mới trước** (register_writer) rồi mới chở hàng tới đó, và **trả chìa kho cũ** (close). Không bao giờ chở
hàng tới kho đã đóng.

## 10. Liên kết bức tranh lớn
supervisor publish (mẩu 08) → **writer coordinator check-on-write (mẩu 09)** phát hiện → chuyển ring (mở qua
pool opener mẩu 06). Đối xứng: reader coordinator (mẩu 10). Bằng chứng cross-process: T-B (mẩu 11).

## 11. Cạm bẫy (+errata)
- **Ghi trước khi kiểm epoch** → ghi nhầm ring cũ. Code luôn `_maybe_switch()` TRƯỚC `write`.
- **Không dọn handle ring mới khi register fail** → leak. Code `new_ring.close()` trong `except` rồi `raise`.
- **Quên register ring mới trước frame đầu** → vỡ 1-writer. Code register ngay trong `_maybe_switch`.
- 🔴 **Cross-process lock**: chỉ đúng vì worker đã thừa kế **toàn bộ** khoá pool (mẩu 06/05). In-process test không phủ điều này — T-B (mẩu 11) mới phủ.

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao kiểm epoch phải **trước** khi ghi, không phải sau?
- Khi register ring mới raise `SingleWriterViolation`, coordinator làm gì (2 việc)? Vì sao fail-fast?
- `old_ring.close()` (không unlink) — vì sao không unlink? (nối pool giữ segment, mẩu 06/07.)

## 13. Mốc ôn
- 1 ngày: nhắc chuỗi bootstrap (register trước) + _maybe_switch (register mới → swap → close cũ).
- 1 tuần: giải thích check-on-write chống mis-write ring cũ (không nhìn code).
- 1 tháng: tự viết lại `_maybe_switch`.

## 14. Nguồn
- Code: `application/writer_epoch_coordinator.py` — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_writer_coordinator.py` (6 test: register on bootstrap · switch on
  epoch change · single-writer fail-fast · no-switch same epoch · write-before-bootstrap · observability) — **pass**. → đã verify.
- Q2 bound (mis-write=0 nhờ check-on-write): `design.md §Q2`. · Độ chắc: cao (code + test chạy thật).
