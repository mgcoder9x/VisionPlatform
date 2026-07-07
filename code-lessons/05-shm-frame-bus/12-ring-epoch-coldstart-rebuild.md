# Mẩu 12 — `ring_epoch` + cold-start (`new_ring_name`) + rebuild-request (nền switchover)

> Bám file: `runtime/ipc/shm_frame_ring.py` + `kernel/shm_frame_ref.py` (đọc nguyên văn khi viết).

## 1. Thuộc về đâu
Tầng **kernel** (`ring_epoch` trong DTO) + **runtime/ipc** (epoch trong ctrl, `new_ring_name`, rebuild-request).
Là NỀN cho "dựng lại ring" (switchover) — phần đầy đủ tách sub-spec `shm-ring-epoch-switchover`.

## 2. Cần biết trước
- Mẩu 02 (`ShmFrameRefData.ring_epoch`) · 09 (quá ngưỡng quarantine → rebuild) · 10 (writer chết → rebuild).
- switchover = dựng ring mới (epoch+1) khi ring cũ hỏng nhiều, chuyển writer/reader sang.

## 3. Code thật (quote — excerpt có đánh dấu `# ...`)
```python
# kernel/shm_frame_ref.py
ring_epoch: int = 0   # P0-3: phiên bản ring; reader cầm ref epoch cũ sau switchover → trả None (stale).

# runtime/ipc/shm_frame_ring.py
def new_ring_name(prefix="vp_ring"):
    return f"{prefix}_{uuid.uuid4().hex}"           # tên duy nhất mỗi phiên (cold-start)

@property
def ring_epoch(self):
    return struct.unpack_from(U64_FMT, self._ctrl_shm.buf, OFFSET_RING_EPOCH)[0]

# ShmFrameReader.read(...):
if ring_epoch is not None and ring_epoch != self._ring.ring_epoch:
    return None                                     # stale-ref → không đọc ring mới

# quarantine_poisoned_slot(...): khi q >= self._rebuild_threshold:
self._obs.emit("shm_ring_rebuild_requested", ring_name=self.name, reason="threshold",
               quarantined_count=q, threshold=self._rebuild_threshold, ring_epoch=self.ring_epoch)
```
(Nguồn: `kernel/shm_frame_ref.py` + `runtime/ipc/shm_frame_ring.py` — excerpt.)

## 4. Giải thích từng ý nhỏ nhất
- **`ring_epoch` (DTO, default 0):** "phiên bản ring". Writer stamp epoch hiện tại vào mọi `ShmFrameRefData` (mẩu 06).
- **`reader.read(..., ring_epoch=...)` / `read_ref(ref)`:** nếu epoch của vé KHÁC epoch ring hiện tại → `None` (stale) → không đọc nhầm ring đã bị dựng lại.
- **`new_ring_name` (cold-start):** tên ring theo `uuid` mỗi phiên → creator KHÔNG bao giờ attach segment cũ còn sót từ phiên crash trước. (Lưu ý: `SharedMemory.unlink()` vô hiệu trên Windows → dựa tên uuid chứ không dựa unlink.)
- **`REBUILD_THRESHOLD` (default `ceil(n_slots/2)`):** khi số slot QUARANTINED ≥ ngưỡng → emit `shm_ring_rebuild_requested` cho control-plane. 🔴 default thận trọng, CHƯA tuning theo SLA thật.
- **Phân quyền:** per-slot recovery CHỈ phát yêu cầu; **ai dựng lại ring là control-plane (supervisor/composition root)** — KHÔNG tự rebuild ở mức slot.

## 5. Là gì (1–2 câu)
Bộ "nền switchover": đánh số phiên bản ring (epoch) để chống đọc nhầm ring cũ; đặt tên ring theo phiên để
cold-start sạch; phát tín hiệu đòi rebuild khi hỏng quá ngưỡng.

## 6. Tại sao tồn tại / vấn đề nó giải
QUARANTINED là terminal → ring degrade dần (mẩu 09). Cần đường "hồi sinh": dựng ring mới. `ring_epoch` giải
nỗi đau **reader cầm vé ring cũ đọc nhầm ring mới**. Cold-start giải **segment rác từ phiên crash trước**.

## 7. Dùng ở đâu trong project
- Writer stamp epoch (mẩu 06); reader kiểm epoch (mẩu 07).
- Rebuild-request phát từ quarantine (mẩu 09) + writer-death (mẩu 10).
- Bàn giao: `.kiro/specs/shm-ring-epoch-switchover/00-HANDOFF.md` (switchover ĐẦY ĐỦ — chưa triển khai).

## 8. Không có nó thì sao
Không epoch → sau khi dựng ring mới, reader cầm vé cũ đọc nhầm → data sai. Không cold-start → dính segment
rác phiên trước → attach lỗi/không nhất quán.

## 9. Ví von
`ring_epoch` như **"phiên bản/đợt in" trên vé**: đổi bãi (dựng ring mới) thì in đợt mới; vé đợt cũ vào cổng
→ máy báo "vé hết hiệu lực" (stale), không cho vào nhầm bãi mới.

## 10. Liên kết bức tranh lớn
Khép vòng an toàn 24/7: degrade (quarantine) → phát rebuild-request → control-plane dựng ring epoch mới →
vé cũ tự vô hiệu. Đây là RANH GIỚI #05 dừng lại; switchover đầy đủ là sub-spec riêng (việc lớn).

## 11. Cạm bẫy (+errata)
- 🔴 **Switchover đầy đủ CHƯA làm** (sub-spec): hiện chỉ có nền (epoch + stale + rebuild-request). Ai xử lý `shm_ring_rebuild_requested` là control-plane — chưa hiện thực.
- 🔴 **REBUILD_THRESHOLD chưa tuning SLA** (default `ceil(n/2)`). 
- Windows unlink vô hiệu → BẮT BUỘC dùng tên uuid mỗi phiên.

## 12. Tự kiểm (retrieval + Feynman)
- `ring_epoch` chống loại "đọc nhầm" nào (khác với `generation` mẩu 06 ra sao)?
- Vì sao đặt tên ring theo uuid mỗi phiên? `SharedMemory.unlink` trên Windows có giúp không?
- Ai được quyền dựng lại ring — per-slot recovery hay control-plane? Vì sao?

## 13. Mốc ôn
1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
- Code thật: `kernel/shm_frame_ref.py` (ring_epoch) + `runtime/ipc/shm_frame_ring.py` (new_ring_name/ring_epoch/rebuild-request) (excerpt). · Test: `test_hardening_ring_epoch.py`, `test_hardening_cold_start.py`, `test_hardening_rebuild_threshold.py` pass. · Handoff: `.kiro/specs/shm-ring-epoch-switchover/00-HANDOFF.md`. · Độ chắc: cao (nền); 🔴 switchover đầy đủ chưa làm.
