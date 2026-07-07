# Mẩu 10 — `ReaderEpochCoordinator`: reader tự chuyển ring + ref cũ hoá stale (check-on-read)

> Bám code thật `application/reader_epoch_coordinator.py` (đọc nguyên văn khi viết). Đối xứng mẩu 09 (writer),
> nhưng phía đọc — đơn giản hơn (reader không register_writer).

## 1. Thuộc về đâu
- **Tầng:** `application`. Bọc quanh 1 `ShmFrameReader` (#05) — additive.
- **Vai:** ở process consumer (inference/recorder); mỗi `read_ref`, tự kiểm control-plane để chuyển ring.

## 2. Cần biết trước
- Mẩu 09 (writer coord, cùng khuôn); từ #05: `ShmFrameReader.read_ref` **tự trả None nếu `ref.ring_epoch` khác epoch ring** (stale-check).
- Gloss: **check-on-read** = kiểm epoch NGAY TRƯỚC mỗi lần đọc · **stale-ref** = con trỏ cầm epoch cũ.

## 3. Code thật (quote nguyên văn — `application/reader_epoch_coordinator.py`)
```python
    def bootstrap(self) -> int:
        """Mở ring hiện tại từ control-plane + dựng reader. Trả epoch hiện tại."""
        ring, epoch = bootstrap_current_ring(self._cp, self._ring_opener)
        self._ring = ring
        self._epoch = epoch
        self._reader = self._reader_factory(ring)
        return epoch

    def _maybe_switch(self) -> Optional[int]:
        cur_epoch, name = self._cp.read_current()
        if cur_epoch == self._epoch:
            return None

        new_ring = self._ring_opener(name)
        old_ring = self._ring
        old_epoch = self._epoch
        self._ring = new_ring
        self._epoch = cur_epoch
        self._reader = self._reader_factory(new_ring)
        self._obs.emit("shm_reader_switched", old_epoch=old_epoch, new_epoch=cur_epoch, new_ring_name=name)

        if old_ring is not None:
            old_ring.close()                        # teardown B: đóng handle ring cũ (KHÔNG unlink/detach)
            self._obs.emit("shm_ring_teardown_pending", epoch=old_epoch)
        return cur_epoch

    def read_ref(self, ref: ShmFrameRefData):
        """Kiểm switchover TRƯỚC rồi đọc ref. ref epoch cũ → None (stale). Trả frame copy hoặc None."""
        if self._reader is None:
            raise RuntimeError("ReaderEpochCoordinator.read_ref() gọi trước bootstrap()")
        self._maybe_switch()
        return self._reader.read_ref(ref)
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `bootstrap`: mở ring hiện tại (mẩu 04) → nhớ `_ring/_epoch` → tạo reader thật qua `_reader_factory`. **KHÔNG
  `register_writer`** (reader không phải writer → không có bất biến 1-writer → đơn giản hơn mẩu 09).
- `_maybe_switch`: đọc `read_current()`; không đổi epoch → `return None`. Đổi → mở ring mới, swap `_ring/_epoch/_reader`,
  emit `shm_reader_switched`, rồi `old_ring.close()` (teardown B) + emit `shm_ring_teardown_pending`. (Không có
  `register_writer` nên không có nhánh fail-fast như writer.)
- `read_ref(ref)`: chưa bootstrap → raise; **luôn `_maybe_switch()` TRƯỚC** rồi `self._reader.read_ref(ref)`.
  Nếu `ref` cầm epoch cũ → `ShmFrameReader.read_ref` tự trả **None** (stale-check #05) → **không đọc nhầm ring cũ**.

## 5. Là gì (1–2 câu)
Lớp bọc reader: mỗi `read_ref` tự kiểm epoch; đổi thì mở ring mới + đóng ring cũ; ref epoch cũ → None. Không
register (chỉ đọc).

## 6. Tại sao tồn tại / vấn đề nó giải
Reader #05 không biết switchover. Coordinator thêm "tự chuyển ring" + tận dụng stale-check sẵn có để **không đọc
nhầm ring cũ**. Thứ tự đúng: supervisor **publish epoch mới TRƯỚC** khi có frame epoch mới → reader poll thấy kịp.

## 7. Dùng ở đâu trong project
- Process consumer: `ReaderEpochCoordinator(cp, make_pool_opener(...))` → `bootstrap()` → `read_ref(ref)` cho từng ref nhận được.
- Verify cross-process ở T-B (mẩu 11): parent đọc frame epoch mới do worker ghi.

## 8. Không có nó thì sao
Không có coordinator → reader kẹt ở ring cũ sau switchover → đói frame (writer đã sang ring mới). Không có
stale-check → reader có thể đọc frame rác từ ring đã bỏ.

## 9. Ví von
Như **người nhận hàng** trước mỗi lần lấy hàng **liếc bảng tin**: kho đổi thì sang kho mới nhận; nếu cầm **phiếu
cũ** (ref epoch cũ) tới kho mới → phiếu **vô hiệu** (None), không lấy nhầm hàng cũ.

## 10. Liên kết bức tranh lớn
supervisor publish (mẩu 08) → **reader coordinator check-on-read (mẩu 10)** + writer coordinator (mẩu 09) đối
xứng. Stale-check nối `ring_epoch` (mẩu 07 bump + #05 read_ref). Bằng chứng: T-B (mẩu 11).

## 11. Cạm bẫy (+errata)
- **Đọc trước khi kiểm epoch** → có thể đọc ring cũ. Code luôn `_maybe_switch()` TRƯỚC.
- **Tưởng reader cần register** — KHÔNG; chỉ writer register (1-writer). Reader chỉ pin/copy/unpin (#05).
- 🔴 Cross-process lock: đúng nhờ worker thừa kế khoá pool (mẩu 06). In-process test không phủ; T-B (mẩu 11) phủ.

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao reader coordinator **đơn giản hơn** writer coordinator? (nêu: không register_writer.)
- ref epoch cũ tới sau switchover → điều gì xảy ra, nhờ cơ chế nào (nối stale-check + bump epoch mẩu 07)?
- Vì sao "publish epoch trước" đảm bảo reader không đọc nhầm ring cũ?

## 13. Mốc ôn
- 1 ngày: nhắc chuỗi read_ref → _maybe_switch → reader.read_ref (stale → None).
- 1 tuần: giải thích đối xứng writer/reader + khác biệt (register) không nhìn code.
- 1 tháng: tự viết lại `_maybe_switch` reader.

## 14. Nguồn
- Code: `application/reader_epoch_coordinator.py` — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_reader_coordinator.py` (6 test: bootstrap · switch on epoch ·
  stale-ref → None · no-switch · read-before-bootstrap · observability) — **pass** (full 242 passed/1 skipped). → đã verify.
- Stale-check nền: #05 `ShmFrameReader.read` (ring_epoch mismatch → None). · Độ chắc: cao (code + test chạy thật).
