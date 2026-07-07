# Mẩu 12 — No-leak (bounded reuse) + Q2 (bound frame-drop) + observability taxonomy

> Mẩu tổng kết #05b. Bám code thật `tests/test_switchover_leak.py` + `design.md §Q2` +
> `observability-taxonomy.md` (đọc nguyên văn khi viết). Trả 3 câu hỏi vận hành cuối: **rò rỉ? mất frame? quan sát?**

## 1. Thuộc về đâu
- **Loại:** test leak (`tests/`) + tài liệu vận hành (spec). Tầng liên quan: runtime (pool) + design (Q2) + observability hook.
- **Vai:** chứng minh switchover **không rò rỉ**, giới hạn **mất frame**, và **quan sát được** — 3 tiêu chí sản phẩm 24/7.

## 2. Cần biết trước
- Mẩu 06 (pool tái dùng vòng), 07 (reset), 09/10 (check-on-write/read), #05/11 (observability hook).
- Gloss: **leak (rò rỉ)** = ô nhớ mất mà không dọn · **bound (chặn trên)** = số tối đa · **taxonomy** = bảng phân loại sự kiện.

## 3. Code thật (quote nguyên văn — `tests/test_switchover_leak.py`)
```python
def test_no_segment_accumulation_across_many_switchovers():
    """H2 no-leak (platform-independent): 20 switchover → tập segment KHÔNG đổi (bounded = K ring)."""
    from vision_platform.application.ring_supervisor import RingSupervisor
    cp = _cp()
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"leak_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    names_before = set(pool.names())
    try:
        for _ in range(20):
            sup.switchover()                         # activate = reset+bump (TÁI DÙNG, không tạo segment mới)
        names_after = set(pool.names())
        assert names_after == names_before           # KHÔNG segment mới sau 20 switchover → bounded, no leak-by-growth
        assert len(names_after) == 3                 # đúng K ring
```

## 4. Giải thích từng-dòng-nhỏ-nhất (no-leak)
- `names_before = set(pool.names())` — chụp tập tên segment TRƯỚC.
- `for _ in range(20): sup.switchover()` — switchover **20 lần** (nhiều thế hệ epoch).
- `assert names_after == names_before` — sau 20 lần, **tập segment KHÔNG đổi** → switchover **không sinh segment
  mới** (vì tái dùng pool, mẩu 06/07). Đây là **no-leak-by-growth**, đúng bản chất H2 — verify **không cần soi /dev/shm**.
- `assert len(names_after) == 3` — vẫn đúng K=3 ring → bộ nhớ **đoán trước**, không phình.

## 5. Q2 — mất frame khi switchover (bound cấu trúc, KHÔNG bịa số)
Từ `design.md §Q2` (điền 2026-07-03): coordinator **check-on-write** (mẩu 09) chuyển ring TRƯỚC mỗi `write` →
writer **KHÔNG ghi thêm frame nào vào ring cũ sau publish** ⇒ **mis-write ring cũ = 0**. Frame "mất" = các frame
READY **chưa được đọc** còn nằm trong ring cũ lúc switchover → ref cũ hoá stale → reader drop. Số này **≤ n_slots**
(dung lượng ring). 🔴 **Số đo dưới TẢI THẬT (nhiều fps/đa reader) CHƯA đo** (K-014) — bound này là **suy ra từ
thiết kế**, không phải số đo; không bịa.

## 6. Observability taxonomy (quan sát được — Req 6.1)
Mọi bước switchover phát sự kiện qua `ObservabilityHook.emit` (mặc định no-op). Catalog đầy đủ ở
`.kiro/specs/shm-ring-epoch-switchover/observability-taxonomy.md`. Chuỗi điển hình 1 switchover:
1. `shm_slot_quarantined` × n → `shm_ring_capacity_degraded` (slot chết dần).
2. `shm_ring_rebuild_requested` (threshold) → 3. supervisor `shm_switchover_started` → `shm_ring_reset_for_reuse`
   → `shm_switchover_completed` → 4. `shm_writer_switched` + `shm_ring_teardown_pending` → 5. `shm_reader_switched` + teardown.
Fail-fast (Req 6.2): attach control-plane sai magic → `ValueError` (mẩu 02/03).

## 7. Là gì (1–2 câu)
Ba câu trả lời vận hành: **không rò rỉ** (số segment = K, bất biến qua 20 switchover), **mất frame ≤ n_slots**
(bound cấu trúc), **quan sát được** (taxonomy sự kiện + fail-fast).

## 8. Tại sao tồn tại / vấn đề nó giải
Sản phẩm 24/7 phải trả lời được: chạy lâu có phình RAM không? switchover mất bao nhiêu frame? sự cố có thấy
không? Mẩu này chốt cả ba bằng bằng chứng (test) + bound suy-ra + catalog — thay vì hứa suông.

## 9. Không có nó thì sao
Không kiểm no-leak → có thể phình segment âm thầm → hết RAM sau nhiều giờ. Không bound Q2 → không biết mất bao
nhiêu frame (SLA mù). Không taxonomy → sự cố switchover diễn ra mà ops không thấy.

## 10. Ví von
Như **báo cáo bàn giao ca**: (a) kho vẫn đúng K phòng, không mọc thêm phòng ma (no-leak); (b) mỗi lần đổi phòng
mất tối đa "1 phòng hàng chưa lấy" (Q2 ≤ n_slots); (c) mọi thao tác đổi phòng đều **ghi sổ** (taxonomy) để ca sau đọc.

## 11. Liên kết bức tranh lớn
Đây là mẩu **tổng kết** #05b: no-leak nối pool tái dùng (mẩu 06/07); Q2 nối check-on-write (mẩu 09); taxonomy
nối supervisor/coordinator (mẩu 08–10) + observability #05. Khép vòng cung: vấn đề (01/05) → giải (06/07) →
điều phối (08–10) → bằng chứng (11) → vận hành (12).

## 12. Tự kiểm (retrieval + Feynman)
- Vì sao "20 switchover, tập segment không đổi" chứng minh no-leak mà **không cần** soi /dev/shm?
- Q2 bound ≤ n_slots suy ra thế nào? Vì sao mis-write ring cũ = 0? (nối check-on-write.)
- Kể chuỗi sự kiện observability của 1 switchover. Fail-fast bảo vệ gì?

## 13. Mốc ôn
- 1 ngày: nhắc 3 tiêu chí (no-leak/Q2/observability) + bằng chứng mỗi cái.
- 1 tuần: giải thích no-leck-by-growth + Q2 bound (không nhìn code).
- 1 tháng: tự vẽ lại toàn vòng cung #05b (01→12).

## 14. Nguồn
- Code: `tests/test_switchover_leak.py` (no-accumulation + bounded-by-pool-size + close_all frees) — **đọc nguyên văn** (quote khớp).
- Q2: `.kiro/specs/shm-ring-epoch-switchover/design.md §Overview Q2` (bound cấu trúc ≤ n_slots; số-đo tải 🔴 K-014).
- Observability: `.kiro/specs/shm-ring-epoch-switchover/observability-taxonomy.md` (13 event) + `test_switchover_observability.py`.
- Kết quả: full **242 passed/1 skipped** · lint **5 kept/0 broken** (LOG #141). · 🔴 K-003 (POSIX leak thật) · K-014 (Q2 tải). Độ chắc: cao trên Windows.
