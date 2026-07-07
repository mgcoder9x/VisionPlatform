# Mẩu 07 — `reset_for_reuse`: cơ chế "tái dùng" 1 ring cho epoch mới (không cấp phát)

> Bám code thật `runtime/ipc/shm_frame_ring.py` (`ShmRingBuffer.reset_for_reuse`, L477+, đọc nguyên văn khi viết).

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc` (method của `ShmRingBuffer`). **CREATOR-only** (chỉ process tạo ring gọi = pool owner).
- **Vai:** biến 1 ring cũ (đã dùng ở epoch trước) thành "ring sạch cho epoch mới" — trái tim của H2.

## 2. Cần biết trước
- Mẩu 06: `pool.activate(epoch)` gọi chính hàm này.
- Từ #05: **QUARANTINED** (terminal), **reader registry** (đa reader), **writer registry** (1-writer), **ring_epoch** (stale-check).
- Gloss: **best-effort lock** = cố lấy khoá nhưng không kẹt nếu lấy không được (vì đây là recovery) ·
  **monotonic (đơn điệu)** = chỉ tăng, không giảm/lặp.

## 3. Code thật (quote nguyên văn — `runtime/ipc/shm_frame_ring.py`, `reset_for_reuse`)
```python
        if self._ctrl_shm is None:
            raise RuntimeError("reset_for_reuse: ring đã đóng / không phải creator")
        cur = self.ring_epoch
        if new_epoch <= cur:
            raise ValueError(f"ring_epoch phải đơn điệu tăng: new={new_epoch} <= cur={cur}")

        # 1) Xoá mọi slot về FREE (gồm QUARANTINED) + reader registry + count (best-effort lock).
        for i in range(self.n_slots):
            lock = self._slot_locks[i]
            acquired = lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT_S)
            try:
                buf = self._meta_shms[i].buf
                for r in range(MAX_READERS):
                    _registry_clear(buf, r)
                _write_reader_count(buf, 0)
                _write_header(buf, SlotState.FREE, 0, 0)   # state ghi CUỐI, gen=0
            finally:
                if acquired:
                    lock.release()

        # 2) Xoá writer registry (control segment) → ring "chưa có writer".
        ctrl = self._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, 0)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, 0)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_LEASE_NS, 0)

        # 3) Bump ring_epoch — GHI CUỐI (authority): bên khác thấy epoch mới = ring đã reset xong.
        struct.pack_into(U64_FMT, ctrl, OFFSET_RING_EPOCH, new_epoch)
        self._writer_registered = False
        self._obs.emit("shm_ring_reset_for_reuse", ring_name=self.name, new_epoch=new_epoch)
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `if self._ctrl_shm is None: raise ...` — chặn gọi trên ring đã đóng / không phải creator.
- `cur = self.ring_epoch` rồi `if new_epoch <= cur: raise ValueError(...)` — **ép đơn điệu**: epoch mới phải
  LỚN HƠN hiện tại (không lùi/lặp) → giữ `Property 2` (epoch đơn điệu).
- Vòng `for i in range(self.n_slots):` — duyệt từng slot:
  - `lock.acquire(timeout=...)` **best-effort**: cố lấy khoá; lấy không được vẫn tiếp (đây là recovery, không kẹt vì khoá của owner đã chết).
  - `for r in range(MAX_READERS): _registry_clear(buf, r)` + `_write_reader_count(buf, 0)` — **xoá sạch reader registry**.
  - `_write_header(buf, SlotState.FREE, 0, 0)  # state ghi CUỐI, gen=0` — đưa slot về **FREE**, gen=0. **Kể cả
    slot đang QUARANTINED cũng bị xoá về FREE** — đúng mục đích rebuild (làm sạch ring hỏng).
  - `finally: if acquired: lock.release()` — chỉ nhả khoá nếu ban nãy lấy được.
- `struct.pack_into(..., OFFSET_WRITER_PID, 0)` (+ create_time + lease = 0) — **xoá writer registry** → ring
  "chưa có writer" → writer mới `register_writer` claim lại được (mẩu 09).
- `struct.pack_into(U64_FMT, ctrl, OFFSET_RING_EPOCH, new_epoch)  # GHI CUỐI` — **bump epoch, ghi SAU CÙNG**:
  bên khác thấy epoch mới nghĩa là ring đã reset xong (authority). Ref epoch cũ → stale (mẩu 10).
- `self._writer_registered = False` — reset cờ intra-process để register lại được.
- `self._obs.emit("shm_ring_reset_for_reuse", ...)` — báo ra sự kiện (quan sát).

## 5. Là gì (1–2 câu)
Hàm "làm mới" 1 ring: xoá mọi slot về FREE (kể cả QUARANTINED) + xoá reader/writer registry + bump epoch (ghi
cuối). Sau đó ring như mới, dùng cho epoch mới — **không cấp phát SHM/lock mới**.

## 6. Tại sao tồn tại / vấn đề nó giải
Đây là cách H2 "đổi ring" mà không sinh ring mới: **tái chế** ring cũ. Xoá QUARANTINED = phục hồi capacity đã
mất; bump epoch (ghi cuối) = làm ref cũ stale + báo "ring sẵn sàng". Nhờ đó né hoàn toàn K-012 (không cần khoá mới).

## 7. Dùng ở đâu trong project
- `RingPool.activate(epoch)` gọi (mẩu 06).
- Qua đó, `RingSupervisor.switchover()` (mẩu 08) kích hoạt khi có `shm_ring_rebuild_requested`.

## 8. Không có nó thì sao
Không có `reset_for_reuse` → muốn ring sạch phải **tạo ring mới** → vấp K-012. Không bump epoch **ghi cuối** →
bên đọc có thể thấy ring "nửa reset". Không ép đơn điệu → epoch lùi → stale-check sai → đọc nhầm.

## 9. Ví von
Như **dọn phòng khách sạn để đón khách mới**: gom hết đồ khách cũ (xoá slot + registry), **kể cả phòng từng bị
niêm phong** (QUARANTINED) nay mở lại lau sạch, rồi **thay số phòng mới trên cửa CUỐI CÙNG** (bump epoch) —
khách cũ cầm thẻ số cũ vào sẽ bị từ chối (stale).

## 10. Liên kết bức tranh lớn
RingPool.activate (mẩu 06) → **reset_for_reuse (mẩu 07)** → epoch mới nhìn thấy live cross-process → coordinator
writer register lại (mẩu 09) + reader thấy ref cũ stale (mẩu 10). "Ghi epoch cuối" nối đúng nguyên lý control-plane (mẩu 03).

## 11. Cạm bẫy (+errata)
- **Reset khi ring CHƯA drain** (còn reader đọc) → xưa có thể xoá slot đang bị đọc (torn frame). **[CẬP NHẬT 2026-07-03 — Fix A, K-015/D-020]:** `reset_for_reuse` nay **CƯỠNG CHẾ drain**: reap reader chết → nếu còn reader hiệu lực (`_reader_protects_slot`) ở bất kỳ slot → **REFUSE (return False, chưa đụng gì)** + emit `shm_reset_blocked_active_readers`; `pool.activate` trả None; `supervisor.switchover` HOÃN (defer+retry). Không còn dựa contract ngầm. → **Mẩu này [CẦN CẬP NHẬT nhẹ]: chữ ký giờ `reset_for_reuse(new_epoch) -> bool`** (True=reset, False=chưa drain). Xem §3 khối drain-guard trong code hiện tại.
- **Bump epoch KHÔNG ghi cuối** → ring "nửa reset" bị nhìn thấy. Giữ thứ tự: slot→registry→epoch (cuối).
- **Best-effort lock**: nếu 1 slot có khoá chết, hàm vẫn ghi FREE (không kẹt) — đúng tinh thần recovery.

## 12. Tự kiểm (retrieval + Feynman)
- `reset_for_reuse` làm mấy việc, theo thứ tự nào? Vì sao **bump epoch phải ghi CUỐI**?
- Vì sao xoá **cả** slot QUARANTINED? (nối mục đích rebuild.)
- Vì sao dùng **best-effort lock** thay vì bắt buộc acquire?

## 13. Mốc ôn
- 1 ngày: nhắc 3 bước (clear slot → clear writer registry → bump epoch cuối).
- 1 tuần: giải thích "ghi epoch cuối = authority" + xoá QUARANTINED (không nhìn code).
- 1 tháng: tự viết lại khung `reset_for_reuse`.

## 14. Nguồn
- Code: `runtime/ipc/shm_frame_ring.py` (`reset_for_reuse`, L477+) — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_ring_reuse.py` (5 test: bump+clear slot · clear QUARANTINED ·
  monotonic guard · re-register writer · stale-ref sau reset) — **pass** (full 242 passed/1 skipped). → đã verify.
- Quyết định H2/đảo D-002-D-010: `ai-decision-journal/` (D-011, C-006). · Độ chắc: cao (code + test chạy thật).
