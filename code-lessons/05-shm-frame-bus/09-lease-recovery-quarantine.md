# Mẩu 09 — Lease + lock-free peek + `quarantine_poisoned_slot`: đóng F-3/F-3b

> Bám file: `runtime/ipc/shm_frame_ring.py` (đọc nguyên văn khi viết). Đây là lõi crash-recovery.

## 1. Thuộc về đâu
Tầng **runtime/ipc**. Cơ chế để bus KHÔNG "đứng" khi 1 process chết đang giữ khoá slot.

## 2. Cần biết trước
- Mẩu 04 (state@0 atomic → peek lock-free) · 08 (owner_liveness). F-3/F-3b: slot kẹt WRITING/READING vĩnh viễn (ERRATA E-15).
- **lease** = "hạn cam kết": owner ghi `lease_deadline = now + 2s`; quá hạn = nghi treo.

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
WRITE_LEASE_NS = 2_000_000_000   # 2s
LOCK_ACQUIRE_TIMEOUT_S = 0.1     # TÁCH khỏi lease

def peek_state(self, slot_idx):                              # lock-free, atomic 4B @0
    return struct.unpack_from(STATE_FMT, self._meta_shms[slot_idx].buf, OFFSET_STATE)[0]

def quarantine_poisoned_slot(self, slot_idx):
    buf = self._meta_shms[slot_idx].buf
    if struct.unpack_from(STATE_FMT, buf, OFFSET_STATE)[0] == SlotState.QUARANTINED:
        return False
    snap1 = _full_snapshot(buf); snap2 = _full_snapshot(buf)  # double-snapshot (P1-1)
    if snap1 != snap2:
        return False                                         # torn → chưa hành động
    state = struct.unpack_from(STATE_FMT, buf, OFFSET_STATE)[0]
    now = time.monotonic_ns()
    if state in (SlotState.WRITING, SlotState.READY):
        owner_pid, owner_create_time_ns = _read_owner(buf)
        if now < _read_lease(buf):
            return False                                     # còn lease → owner có thể bận hợp lệ
        liveness = self._liveness_fn(owner_pid, owner_create_time_ns)
        if liveness is Liveness.UNKNOWN:
            self._obs.emit("shm_owner_liveness_unknown", ...); return False
        if liveness is not Liveness.DEAD:
            return False                                     # ALIVE → KHÔNG quarantine
    elif state == SlotState.READING:
        if _reader_protects_slot(buf, self._liveness_fn):
            return False                                     # còn reader sống → KHÔNG loại (R-2.2)
    else:
        return False
    struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(SlotState.QUARANTINED))  # atomic, TERMINAL
    # ... emit shm_slot_quarantined + shm_ring_capacity_degraded (+ rebuild_requested nếu quá ngưỡng)
    return True
```
(Nguồn: `runtime/ipc/shm_frame_ring.py` — excerpt; `# ...` = lược.)

## 4. Giải thích từng ý nhỏ nhất
- **`LOCK_ACQUIRE_TIMEOUT_S = 0.1` tách khỏi `lease = 2s`:** đường scan chờ khoá tối đa 0.1s (real-time); lease dài hơn (bao pin/copy/unpin, KHÔNG bao inference).
- **`peek_state` lock-free:** đọc `state` 4B atomic → biết slot QUARANTINED để BỎ QUA mà không đụng khoá chết.
- **Điều kiện quarantine (2 lớp):** owner **DEAD** VÀ **lease quá hạn**. Chỉ 1 lớp không đủ: lease-một-mình → loại nhầm process chậm-mà-sống; pid-chết-một-mình → OS tái dùng pid gây nhầm. Hai lớp = an toàn.
- **double-snapshot (P1-1):** đọc multi-field (owner/lease) KHÔNG có lock (lock đang kẹt) → chụp 2 lần, chỉ hành động nếu 2 lần GIỐNG (bytes); torn → khoan.
- **WRITING/READY** dùng `owner@16` (writer); **READING** quét registry (`_reader_protects_slot`) — còn ≥1 reader sống/còn-lease thì KHÔNG loại cả slot (R-2.2).
- **QUARANTINED = TERMINAL:** ghi bằng 1 lệnh atomic 4B; KHÔNG bao giờ về FREE (khoá OS không robust → tái dùng = chờ khoá chết mãi).
- **`monotonic_ns` cross-process:** CLOCK_MONOTONIC/GetTickCount64 system-wide theo boot → so được giữa process; cộng điều kiện DEAD nên robust.

## 5. Là gì (1–2 câu)
Cơ chế phát hiện slot có owner chết (DEAD + lease quá hạn) → đánh dấu QUARANTINED (loại vĩnh viễn) bằng thao
tác atomic không cần khoá → ring degrade dần thay vì đứng.

## 6. Tại sao tồn tại / vấn đề nó giải
F-3/F-3b: process chết khi giữ khoá slot → khoá kẹt → slot vô dụng → dần cạn → **đứng bus**. Recovery loại
slot đó (terminal) qua peek lock-free (không chạm khoá chết) → bus tiếp tục với slot khỏe.

## 7. Dùng ở đâu trong project
- Writer scan / Reader pin: acquire timeout → gọi `quarantine_poisoned_slot` (mẩu 06/07).
- Test THẬT: `test_hardening_kill_recovery.py` (kill process giữ lock → writer recover, slot QUARANTINED) — pass, stress 5/5.

## 8. Không có nó thì sao
Đúng bug F-3/F-3b của demo: slot kẹt vĩnh viễn → ring cạn → bus đứng (không phục hồi được vì khoá poison).

## 9. Ví von
Phòng thử đồ mà khách **ngất xỉu bên trong còn cầm chìa** (process chết giữ khoá). Nhân viên KHÔNG cạy khoá
(sẽ kẹt), mà dán "NIÊM PHONG — HỎNG" (QUARANTINED) rồi hướng khách sang phòng khác. Chỉ niêm phong khi CHẮC
khách đã xỉu (DEAD) VÀ quá giờ (lease hết) — không niêm nhầm khách đang thay đồ bình thường.

## 10. Liên kết bức tranh lớn
Đây là thứ biến demo #05 thành sản phẩm 24/7. Dựa hoàn toàn vào: `state`@0 atomic (mẩu 04) + liveness (mẩu 08)
+ registry (mẩu 07). Quá ngưỡng quarantine → phát rebuild-request (mẩu 12).

## 11. Cạm bẫy (+errata)
- Quarantine mà ĐỤNG lock (acquire) → kẹt (khoá chết). Phải chỉ ghi `state` atomic lock-free.
- Bỏ double-snapshot → đọc torn (owner ghi dở) → quyết sai. 
- 🔴 ARM: peek lock-free dựa atomicity aligned + sticky; ARM ordering yếu → chỉ claim x86-64 (mẩu 12).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao quarantine cần CẢ "owner DEAD" VÀ "lease quá hạn"? Ví dụ mỗi điều kiện thiếu thì sai gì.
- Vì sao QUARANTINED phải terminal (không về FREE)? Vì sao KHÔNG đụng lock khi quarantine?
- double-snapshot giải quyết vấn đề gì?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `runtime/ipc/shm_frame_ring.py::quarantine_poisoned_slot` (excerpt). · Test: `test_hardening_recovery.py` + `test_hardening_kill_recovery.py` (kill thật) pass, stress 5/5. · Spec: R-1.1/P1-1/R-2.2. · Độ chắc: cao.
