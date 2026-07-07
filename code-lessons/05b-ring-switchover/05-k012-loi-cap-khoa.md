# Mẩu 05 — K-012: vì sao KHÔNG thể cấp khoá cho ring sinh lúc đang chạy (gốc rễ vấn đề switchover)

> Mẩu **bản lề** của #05b. Bám code thật `runtime/ipc/shm_frame_ring.py` (`ShmRingBuffer.__init__`) +
> test `tests/test_step_05_shm.py`. Hiểu mẩu này mới hiểu **tại sao chọn H2 (pool)** ở mẩu 06.

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc` (`ShmRingBuffer.__init__`) — chỗ ring nhận khoá cho từng slot.
- **Vai:** đây KHÔNG phải 1 tính năng — đây là **ràng buộc/bức tường** khiến switchover khó. Ký hiệu **K-012**
  (mã theo dõi trong `ai-decision-journal/`).

## 2. Cần biết trước
- Từ #05: mỗi slot có 1 **`mp.Lock`** (khoá `multiprocessing`) để 2 process không giẫm chân.
- Gloss: **spawn** = cách Python tạo process con (Windows luôn dùng spawn) · **inherit/thừa kế** = process con
  nhận đối tượng từ cha **lúc được sinh ra** (qua `Process(args=...)`) · **create=False** = attach vào ring đã tồn tại.

## 3. Code thật (quote nguyên văn — `runtime/ipc/shm_frame_ring.py`, `ShmRingBuffer.__init__`)
```python
        # Locks: parent creates, children receive via args.
        if slot_locks is not None:
            if len(slot_locks) != n_slots:
                raise ValueError(
                    f"slot_locks length {len(slot_locks)} != n_slots {n_slots}"
                )
            self._slot_locks = slot_locks
        elif create:
            self._slot_locks = [mp.Lock() for _ in range(n_slots)]
        else:
            raise RuntimeError(
                "create=False requires slot_locks from parent process."
            )
```

Và test chứng minh ràng buộc (quote nguyên văn — `tests/test_step_05_shm.py`):
```python
def test_attach_without_locks_raises():
    """create=False mà KHÔNG truyền slot_locks → RuntimeError (child không tự tạo lock local được)."""
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `# Locks: parent creates, children receive via args.` — **luật vàng**: chỉ process **cha tạo** khoá; con
  **nhận qua args** (lúc spawn).
- `if slot_locks is not None:` — nếu được truyền khoá từ ngoài (con nhận từ cha) → dùng chúng.
- `elif create:` → `self._slot_locks = [mp.Lock() for _ in range(n_slots)]` — chỉ khi **tạo mới** ring
  (`create=True`, tức process cha) mới **tự sinh** khoá.
- `else: raise RuntimeError("create=False requires slot_locks from parent process.")` — **attach (create=False)
  mà KHÔNG có khoá → BÁO LỖI**. Con **không được** tự tạo khoá local (vì sẽ là khoá KHÁC → không loại trừ nhau
  giữa các process → mất tác dụng đồng bộ).

## 5. Là gì (1–2 câu)
`mp.Lock` chỉ đến tay process con **qua thừa kế lúc spawn**; nó **không mở lại được theo tên**. Vậy 1 ring
attach từ process khác **bắt buộc** nhận `slot_locks` do cha truyền — không thì raise.

## 6. Tại sao tồn tại / vấn đề nó giải (đây là NỖI ĐAU)
Switchover cần **ring MỚI sinh lúc hệ đang chạy**. Nhưng writer/reader là các process **đã spawn từ trước** →
chúng **không có cách nào nhận `mp.Lock` mới** cho ring mới đó (thừa kế chỉ xảy ra 1 lần lúc spawn; `mp.Lock`
không có "mở theo tên"). ⇒ Nếu dựng ring mới lúc chạy, worker **không khoá được slot của nó** → recovery/
đồng bộ trên ring mới **vỡ cross-process**. Đây chính là **bức tường K-012**.

**Lực giằng nhau:** *đổi ring linh hoạt lúc chạy* ↔ *khoá cross-process chỉ cấp được lúc spawn*.

## 7. Dùng ở đâu trong project
- Ràng buộc thể hiện ở MỌI test cross-process (`test_step_05_shm.py`, `test_hardening_kill_recovery.py`):
  truyền `ring.slot_locks_for_children` qua `Process(args=...)` — ring luôn **tạo TRƯỚC khi spawn**.
- Chính ràng buộc này loại phương án "switchover = tạo ring uuid mới lúc chạy" → dẫn tới H2 (mẩu 06).

## 8. Không có ràng buộc này thì sao (giả định)
Nếu `mp.Lock` mở được theo tên (như named mutex) thì switchover tạo-ring-mới sẽ đơn giản — đó chính là hướng
**H1** (mẩu 06 điểm qua). Nhưng thực tế `mp.Lock` KHÔNG có tính năng đó → phải né (H2) hoặc đổi cơ chế khoá (H1).

## 9. Ví von
`mp.Lock` như **chìa khoá vật lý** cha **dúi tận tay** con lúc con ra khỏi nhà (spawn). Sau đó con đã đi làm xa;
nếu nhà mở thêm **phòng mới** (ring mới), **không có cách nào** đưa chìa phòng mới cho đứa con đang ở xa —
trừ khi (H1) đổi sang **khoá mã số mở-theo-tên**, hoặc (H2) **làm sẵn tất cả phòng + phát hết chìa lúc con còn ở nhà**.

## 10. Liên kết bức tranh lớn
Đây là **nút thắt** giữa "muốn switchover" (mẩu 01–04) và "cách hiện thực" (mẩu 06 trở đi). H2 (RingPool) sinh
ra CHÍNH để né nút thắt này: cấp sẵn K ring + phát **toàn bộ** khoá lúc spawn.

## 11. Cạm bẫy (+errata)
- **Tưởng con tự `mp.Lock()` là xong** — SAI: sẽ là khoá riêng của con, KHÔNG loại trừ với cha/con khác → race.
  Code chặn thẳng bằng `raise RuntimeError`.
- **Định "tạo ring uuid mới lúc chạy" cho switchover** — vấp K-012 ngay. (Xem journal K-012 + C-006.)

## 12. Tự kiểm (retrieval + Feynman)
- Nói lại bằng lời mình: vì sao process con **không thể** tự tạo `mp.Lock` cho ring mới lúc đang chạy?
- `create=False` mà không truyền `slot_locks` thì điều gì xảy ra, và **tại sao** phải như vậy?
- K-012 loại bỏ phương án switchover nào? Dẫn tới hướng nào (kể tên H1/H2)?

## 13. Mốc ôn
- 1 ngày: nhắc lại "cha tạo khoá, con nhận qua args lúc spawn".
- 1 tuần: giải thích K-012 (lực giằng) không nhìn code.
- 1 tháng: tự lập luận vì sao H2 né được K-012.

## 14. Nguồn
- Code: `runtime/ipc/shm_frame_ring.py` (`__init__`, khối `slot_locks`) — **đọc nguyên văn khi viết** (quote khớp).
- Ràng buộc: **đã có test** `tests/test_step_05_shm.py::test_attach_without_locks_raises` (+ `test_slot_locks_length_mismatch_raises`) — **pass**. → đã verify.
- Phân tích đầy đủ: `.kiro/specs/shm-ring-epoch-switchover/K-012-lock-provisioning-analysis.md` + `ai-decision-journal/` (K-012, D-011..015).
- Độ chắc: cao (code + test chạy thật).
