# Mẩu 01 — Vì sao cần switchover: tín hiệu `shm_ring_rebuild_requested` phát ra mà CHƯA ai xử lý

> Mẩu nhỏ nhất mở đầu #05b. Mục tiêu: thấy **nỗi đau** (ring cạn slot khỏe dần + đã có tín hiệu kêu cứu
> nhưng không ai nghe) TRƯỚC khi xem cách giải. Bám code thật `runtime/ipc/shm_frame_ring.py`.

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc` (nơi ring sống) — nhưng tín hiệu này sẽ được **`application`** xử lý ở các mẩu sau.
- **Luồng:** đây là điểm CUỐI của recovery #05 (đánh slot hỏng = `QUARANTINED`) và là điểm **BẮT ĐẦU** của #05b
  (phát tín hiệu "hãy dựng ring mới").

## 2. Cần biết trước
- Đã đọc `00-cau-chuyen.md` (#05b) — bức tranh switchover.
- Từ #05: **QUARANTINED** = slot bị loại **vĩnh viễn** (terminal) khi owner của nó chết + hết hạn lease.
  (Ôn lại mẩu #05/09 nếu quên.)
- Gloss: **threshold (ngưỡng)** = con số slot-hỏng mà vượt qua thì kêu rebuild · **rebuild (dựng lại)** = tạo
  ring mới thay ring hỏng · **emit (phát sự kiện)** = gọi hook quan sát để "báo ra ngoài" (xem #05/11).

## 3. Code thật (quote nguyên văn — `runtime/ipc/shm_frame_ring.py`, L424–435, trong `quarantine_poisoned_slot`)
```python
        struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.QUARANTINED))  # atomic 4B, terminal
        q = self._quarantined_count()
        self._obs.emit("shm_slot_quarantined", ring_name=self.name, slot=slot_idx, state=int(state),
                       quarantined_count=q, healthy_slots=self.n_slots - q)
        self._obs.emit("shm_ring_capacity_degraded", ring_name=self.name,
                       quarantined_count=q, healthy_slots=self.n_slots - q)
        if q >= self._rebuild_threshold:
            # Task 10: quá ngưỡng → yêu cầu control-plane rebuild (KHÔNG tự rebuild ở per-slot).
            self._obs.emit("shm_ring_rebuild_requested", ring_name=self.name, reason="threshold",
                           quarantined_count=q, threshold=self._rebuild_threshold, ring_epoch=self.ring_epoch)
        return True
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.QUARANTINED))` — ghi trạng thái slot thành
  **QUARANTINED** (4 byte, atomic). Từ đây slot này **bị loại vĩnh viễn**.
- `q = self._quarantined_count()` — đếm hiện có **bao nhiêu** slot đã QUARANTINED trong ring.
- `self._obs.emit("shm_slot_quarantined", ...)` — **báo ra**: vừa loại 1 slot (kèm `slot`, số đã loại `q`,
  số còn khỏe `healthy_slots`).
- `self._obs.emit("shm_ring_capacity_degraded", ...)` — **báo ra**: ring vừa **tụt capacity** (ít slot khỏe hơn).
- `if q >= self._rebuild_threshold:` — **điểm mấu chốt**: nếu số slot hỏng ĐẠT/VƯỢT ngưỡng...
- `self._obs.emit("shm_ring_rebuild_requested", ..., reason="threshold", ...)` — ...thì **kêu cứu**: "ring này
  hỏng nhiều quá, hãy dựng ring mới". Kèm `ring_epoch` hiện tại để bên nghe biết đang ở thế hệ nào.
- `# ... KHÔNG tự rebuild ở per-slot` (comment thật trong code) — ring **KHÔNG tự dựng lại chính nó**; nó chỉ
  **phát tín hiệu**, để tầng cao hơn (supervisor) quyết định. Đây chính là chỗ #05 dừng lại.

## 5. Là gì (1–2 câu)
Đây là chỗ ring **tự nhận ra mình hỏng nhiều** (số slot QUARANTINED ≥ ngưỡng) và **phát 1 tín hiệu**
`shm_ring_rebuild_requested` — chứ không tự sửa. Tín hiệu này là "đơn xin dựng ring mới".

## 6. Tại sao tồn tại / vấn đề nó giải
Slot QUARANTINED là **terminal** (không tái dùng được — vì khoá OS của owner đã chết không "cứu" được). Nên
theo thời gian ring **cạn dần slot khỏe**. Nếu cứ để vậy → tới lúc **không còn slot nào ghi được → đứng bus**.
Tín hiệu này là cách ring **báo sớm** để hệ kịp dựng ring mới TRƯỚC khi cạn hẳn.

## 7. Dùng ở đâu trong project
- **Phát** ở `quarantine_poisoned_slot` (`shm_frame_ring.py`, L432–434) — khi recovery loại 1 slot làm `q` chạm ngưỡng.
- **Nghe** (ở #05b): `RingSupervisor.on_event` (`application/ring_supervisor.py`) lọc đúng event này → gọi
  `switchover()`. (Xem mẩu 08.)
- Cũng phát khi **writer cũ chết** (`register_writer`, `reason="writer_dead"`) — cùng loại "đơn xin rebuild".

## 8. Không có nó thì sao
Không có tín hiệu này → ring hỏng dần **âm thầm**, không ai biết, tới khi cạn slot thì **cả frame bus đứng**
(camera ghi không được, inference đói frame) — đúng nỗi đau production 24/7 mà #05b phải chặn.

## 9. Ví von
Như **thang máy** có cảm biến: mỗi lần 1 tầng hỏng (khoá kẹt), nó **dán biển "tầng này đóng"** (QUARANTINED)
và **đếm**. Khi số tầng đóng quá nửa, nó **bấm chuông gọi kỹ thuật** (`rebuild_requested`) — nhưng **không tự
sửa**; người điều phối (supervisor) mới quyết định đưa thang mới vào.

## 10. Liên kết bức tranh lớn
`quarantine_poisoned_slot` (recovery #05) ── phát `shm_ring_rebuild_requested` ──► `RingSupervisor` (application, #05b)
── `switchover()` ──► dựng ring epoch mới + publish qua **control-plane** ──► writer/reader **coordinator** chuyển ring.
→ Mẩu 01 là **mắt xích nối #05 sang #05b**.

## 11. Cạm bẫy (+errata)
- **Nhầm "phát tín hiệu" = "đã rebuild".** KHÔNG — ring chỉ phát; nếu **không ai nghe** (như tình trạng cuối #05)
  thì tín hiệu **rơi vào hư không**, ring vẫn cạn. Đó là lý do #05b tồn tại.
- **Ngưỡng `rebuild_threshold`**: mặc định `max(1, (n_slots+1)//2)` (nửa số slot) — **chưa tuning theo SLA thật**
  (🔴 K-004). Đừng tin đây là con số tối ưu.

## 12. Tự kiểm (retrieval + Feynman)
- Tự nói lại: khi 1 slot bị QUARANTINED làm `q` chạm ngưỡng, ring làm **chính xác** những gì? (kể đủ 3 emit.)
- Vì sao ring **không tự** dựng lại chính nó mà phải phát tín hiệu cho tầng khác? (nối "authority ở đâu".)
- Nếu không ai nghe `shm_ring_rebuild_requested` thì điều gì xảy ra theo thời gian?

## 13. Mốc ôn
- Sau 1 ngày: nhắc lại 3 event phát ra + điều kiện `q >= threshold`.
- Sau 1 tuần: nối mắt xích ring → supervisor → switchover (không nhìn sơ đồ).
- Sau 1 tháng: tự vẽ lại luồng từ "slot chết" tới "ring mới".

## 14. Nguồn
- Code: `runtime/ipc/shm_frame_ring.py` L424–435 (`quarantine_poisoned_slot`) — **đọc nguyên văn khi viết mẩu này**.
- Hành vi "q ≥ threshold → phát rebuild": **đã có test** (spec cha #05 Task 10 `test_hardening_rebuild_threshold`,
  2 test pass; #05 full 180→ nay 242 passed/1 skipped). → **đã verify** (không phải suy đoán).
- Ngưỡng default `max(1,(n_slots+1)//2)`: `shm_frame_ring.py __init__` (🟢). Tuning SLA = 🔴 (K-004).
- Độ chắc: cao (code + test chạy thật). Bối cảnh switchover: `.kiro/specs/shm-ring-epoch-switchover/`.
