# Mẩu 06 — `RingPool`: giải K-012 bằng "né" — cấp sẵn K ring + phát hết khoá lúc spawn (H2)

> Bám code thật `runtime/ipc/ring_pool.py` (đọc nguyên văn khi viết). Đây là **giải pháp** trực tiếp cho
> nỗi đau K-012 (mẩu 05).

## 1. Thuộc về đâu
- **Tầng:** `runtime/ipc` (chỉ import `ShmRingBuffer` → import-linter giữ 5 kept/0 broken).
- **Vai:** sở hữu **K ring cố định** suốt phiên; cấp `slot_locks_map` cho worker + cho supervisor `activate` (tái dùng).

## 2. Cần biết trước
- Mẩu 05 (K-012): `mp.Lock` chỉ thừa kế lúc spawn, không mở theo tên → **không cấp khoá được cho ring sinh lúc chạy**.
- Gloss: **pool (bể)** = tập K ring dựng sẵn · **locks_map** = `{tên ring → danh sách khoá slot}` · **drain (rút cạn)**
  = chờ hết reader đang đọc ring cũ trước khi tái dùng · **cyclic reuse** = xoay vòng `pool[epoch % K]`.

## 3. Code thật (quote nguyên văn — `runtime/ipc/ring_pool.py`)

**(a) Dựng K ring cố định (tên `{uuid phiên}_r{i}`):**
```python
        if pool_size < 2:
            raise ValueError(f"pool_size phải >=2 (old+new overlap khi switchover), got {pool_size}")
        ...
        self._prefix = session_prefix if session_prefix is not None else f"vp_pool_{uuid.uuid4().hex}"
        self._rings: list[ShmRingBuffer] = [
            ShmRingBuffer(
                name=f"{self._prefix}_r{i}", n_slots=n_slots, height=height, width=width,
                channels=channels, create=True, ring_epoch=0, obs=obs,
            )
            for i in range(pool_size)
        ]
```

**(b) Chọn ring theo epoch (vòng) + tái dùng:**
```python
    def ring_for_epoch(self, epoch: int) -> ShmRingBuffer:
        """Ring vật lý dùng cho epoch (vòng): pool[epoch % K]."""
        return self._rings[epoch % self.size]

    def activate(self, epoch: int) -> str:
        ...
        ring = self.ring_for_epoch(epoch)
        ring.reset_for_reuse(epoch)   # tự ép epoch > epoch hiện tại của ring (ValueError nếu vi phạm)
        return ring.name
```

**(c) Cấp khoá cho worker (mảnh giải K-012) + opener:**
```python
    def slot_locks_map(self) -> dict[str, list]:
        """{tên ring → slot_locks} — truyền cho worker qua Process(args=) lúc spawn (giải K-012)."""
        return {r.name: r.slot_locks_for_children for r in self._rings}
```
```python
    def opener(name: str) -> ShmRingBuffer:
        if name not in locks_map:
            raise KeyError(f"ring '{name}' không có trong locks_map pool (worker chưa nhận lock qua spawn?)")
        return ShmRingBuffer(
            name=name, n_slots=n_slots, height=height, width=width, channels=channels,
            create=False, slot_locks=locks_map[name], obs=obs,
        )
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `if pool_size < 2: raise ...` — **tối thiểu 2 ring**: lúc switchover có 2 thế hệ sống chồng (cũ đang drain + mới active).
- `self._prefix = ... f"vp_pool_{uuid.uuid4().hex}"` — tiền tố **uuid mỗi phiên** → không đụng segment sót của
  phiên crash trước (cold-start).
- `name=f"{self._prefix}_r{i}"` — hậu tố **cố định** `_r0.._r{K-1}` → tên **ổn định trong phiên** để worker
  attach-by-name bằng khoá thừa kế.
- `create=True, ring_epoch=0` — pool **tự tạo** K ring (nên nó có quyền sinh `mp.Lock`), epoch khởi đầu 0.
- `ring_for_epoch(epoch) = self._rings[epoch % self.size]` — epoch N dùng ring vật lý thứ `N mod K` (xoay vòng).
- `activate(epoch)` = `ring.reset_for_reuse(epoch)` rồi trả tên — **TÁI DÙNG** ring cũ (reset + bump epoch), KHÔNG tạo ring mới.
- `slot_locks_map()` = `{tên: slot_locks_for_children}` — **toàn bộ** khoá của **mọi** ring pool, để truyền 1 lần
  cho worker lúc spawn. **Đây chính là chỗ né K-012.**
- `opener(name)`: attach ring pool theo tên với đúng khoá từ `locks_map` (đã thừa kế) → worker khoá được ring đó.
  Tên lạ → `KeyError` (worker chưa nhận khoá).

## 5. Là gì (1–2 câu)
`RingPool` dựng sẵn K ring lúc khởi động (nên có khoá), phát **toàn bộ** khoá cho worker qua `slot_locks_map`,
và cho supervisor `activate(epoch)` = tái dùng 1 ring trong bể. `make_pool_opener` là hàm để worker mở ring pool.

## 6. Tại sao tồn tại / vấn đề nó giải (H2 thắng K-012 thế nào)
K-012: không cấp được khoá cho ring **sinh lúc chạy**. H2 **né**: không sinh ring lúc chạy nữa — mọi ring + khoá
làm sẵn lúc khởi động, worker thừa kế **hết** khoá 1 lần. Switchover chỉ **tái dùng** (mẩu 07). Nhờ đó **không
đụng cơ chế khoá** (dùng lại đồ #05 đã kiểm), hợp real-time (không cấp phát giữa luồng), RAM đoán trước.

## 7. Dùng ở đâu trong project
- Composition root tạo `RingPool` + truyền `slot_locks_map()` cho worker (spawn).
- `RingSupervisor(cp, pool)` gọi `pool.activate(N)` khi switchover (mẩu 08).
- Coordinator dùng `make_pool_opener(locks_map, ...)` làm `ring_opener` (mẩu 09/10).

## 8. Không có nó thì sao
Không có pool → phải sinh ring lúc chạy → vấp K-012 (worker không khoá được ring mới) → recovery vỡ cross-process.
Hoặc phải đổi sang khoá-có-tên (H1) — thêm phụ thuộc + rủi ro (xem cau-chuyen nhịp 3).

## 9. Ví von
Như **khách sạn làm sẵn K phòng + phát hết chìa cho nhân viên lúc nhận việc**. Khi 1 phòng "hỏng" (ring cạn slot),
lễ tân (supervisor) **dọn lại 1 phòng trong số K phòng** (reset) và đổi biển số phòng (epoch) — KHÔNG xây phòng
mới (vì không kịp đưa chìa phòng mới cho nhân viên đang trực). Đổi lại: luôn giữ K phòng (tốn chỗ), phòng cũ phải
trả khách hết (drain) mới dọn lại.

## 10. Liên kết bức tranh lớn
K-012 (mẩu 05, nỗi đau) → **RingPool (mẩu 06, giải pháp H2)** → `reset_for_reuse` (mẩu 07, cơ chế tái dùng) →
supervisor `activate` (mẩu 08) → coordinator dùng opener (mẩu 09/10) → bằng chứng cross-process T-B (mẩu 11).

## 11. Cạm bẫy (+errata)
- **`pool_size` quá nhỏ (1)** → không có ring dự phòng lúc switchover → chặn bằng `raise ValueError`. Mặc định 3
  (2 tối thiểu + 1 đệm); **chưa tuning SLA** (🔴 K-004/K liên quan).
- **Tái dùng ring CHƯA drain** (còn reader đọc) → hỏng dữ liệu đang đọc. Bất biến **drain-before-reuse** do
  supervisor giữ (contract ghi trong `activate`).
- **Đảo D-002/D-010:** trước đây định "tạo ring mới + supervisor close ring cũ"; H2 đảo thành "pool giữ ring +
  tái dùng" (xem journal C-006/D-013). Đừng lẫn với mô hình cũ.

## 12. Tự kiểm (retrieval + Feynman)
- H2 "né" K-012 bằng cách nào (kể 2 ý: cấp sẵn K ring + phát hết khoá lúc spawn)?
- `slot_locks_map()` phục vụ điều gì? Vì sao worker cần **toàn bộ** khoá pool, không chỉ ring hiện tại?
- Cái giá của H2 là gì (RAM + drain-before-reuse)? Vì sao `pool_size >= 2`?

## 13. Mốc ôn
- 1 ngày: nhắc lại "cấp sẵn K ring + phát hết khoá lúc spawn + tái dùng vòng".
- 1 tuần: giải thích H2 thắng K-012 (không nhìn code) + cái giá.
- 1 tháng: tự viết lại chữ ký `RingPool` (activate/slot_locks_map/make_pool_opener).

## 14. Nguồn
- Code: `runtime/ipc/ring_pool.py` — **đọc nguyên văn khi viết** (quote khớp từng ký tự).
- Hành vi: **đã có test** `tests/test_switchover_ring_pool.py` (9 test: K ring · cyclic name · activate reset+bump ·
  monotonic reject · slot_locks_map · opener attach · unknown-name KeyError · close_all frees) — **pass** (full 242 passed/1 skipped). → đã verify.
- Phân tích chọn H2: `.kiro/specs/shm-ring-epoch-switchover/K-012-lock-provisioning-analysis.md`. · Độ chắc: cao.
