# Mẩu 08 — `RingSupervisor`: authority DUY NHẤT quyết định switchover

> Bám code thật `application/ring_supervisor.py` (đọc nguyên văn khi viết). Đây là "bộ não" nối tín hiệu
> rebuild (mẩu 01) với hành động tái dùng pool (mẩu 06/07).

## 1. Thuộc về đâu
- **Tầng:** `application` (được phụ thuộc kernel + runtime). Là NƠI DUY NHẤT quyết định switchover — KHÔNG per-slot.
- **Vai:** nghe `shm_ring_rebuild_requested` → chọn pool ring kế + reset + publish qua control-plane.

## 2. Cần biết trước
- Mẩu 01 (tín hiệu rebuild), 03 (`RingControlPlane.publish`), 06 (`RingPool.activate`), 07 (`reset_for_reuse`).
- Gloss: **authority** = nơi duy nhất có quyền quyết định (tránh nhiều bên tranh) · **on_event** = hàm nhận sự kiện + lọc.

## 3. Code thật (quote nguyên văn — `application/ring_supervisor.py`)
```python
    def switchover(self) -> int:
        """Chuyển sang epoch N+1: TÁI DÙNG pool ring (activate = reset+bump) + publish. Trả epoch mới (đơn điệu).

        H2: KHÔNG tạo ring mới (đảo D-002), KHÔNG close ring cũ (đảo D-010 — pool giữ ring). Contract
        drain-before-reuse do pool/deployment đảm bảo (pool[N%K] đã drain khi tái dùng cho epoch N).
        """
        cur_epoch, _ = self._cp.read_current()
        new_epoch = cur_epoch + 1
        self._obs.emit("shm_switchover_started", new_epoch=new_epoch)
        name = self._pool.activate(new_epoch)        # reset_for_reuse + bump epoch trên pool[N%K]
        self._cp.publish(new_epoch, name)            # publish CUỐI (hai bên poll thấy đổi)
        self._obs.emit("shm_switchover_completed", new_epoch=new_epoch, new_ring_name=name)
        return new_epoch
```
(Và `on_event` — lọc đúng sự kiện, quote nguyên văn phần điều kiện:)
```python
            return self.switchover()
        return None
```

## 4. Giải thích từng-dòng-nhỏ-nhất
- `on_event`: chỉ khi event là `shm_ring_rebuild_requested` → gọi `self.switchover()`; sự kiện khác → `return None` (bỏ qua).
- `cur_epoch, _ = self._cp.read_current()` — hỏi control-plane epoch hiện tại (bỏ tên, chỉ cần epoch).
- `new_epoch = cur_epoch + 1` — epoch kế (tăng 1).
- `self._obs.emit("shm_switchover_started", ...)` — báo bắt đầu switchover.
- `name = self._pool.activate(new_epoch)` — **tái dùng** pool ring cho epoch mới (mẩu 06 → gọi `reset_for_reuse` mẩu 07); trả tên ring.
- `self._cp.publish(new_epoch, name)` — công bố "ring hiện tại = (new_epoch, name)". Nhờ `publish` ghi tên trước
  epoch cuối (mẩu 03) → hai bên poll thấy epoch đổi = tín hiệu chuyển.
- `self._obs.emit("shm_switchover_completed", ...)` — báo xong.
- `return new_epoch`.

## 5. Là gì (1–2 câu)
Supervisor là bộ điều phối tầng application: nhận đúng tín hiệu rebuild → tái dùng pool ring epoch N+1 → publish.
Nó KHÔNG tạo/đóng ring (pool giữ) — chỉ ra lệnh.

## 6. Tại sao tồn tại / vấn đề nó giải
Cần **1 nơi duy nhất** quyết định switchover (nếu nhiều bên cùng đổi ring → hỗn loạn epoch). Đặt ở application
(tách khỏi cơ chế slot ở runtime) → đúng "authority tập trung". `on_event` lọc để chỉ rebuild mới kích hoạt.

## 7. Dùng ở đâu trong project
- Composition root: `RingSupervisor(cp, pool)`; đăng ký `on_event` nhận `shm_ring_rebuild_requested` từ ring.
- Gọi `pool.activate` (mẩu 06) → `reset_for_reuse` (mẩu 07) → `cp.publish` (mẩu 03).

## 8. Không có nó thì sao
Không có supervisor → tín hiệu rebuild rơi vào hư không (như cuối #05) → ring cạn → đứng bus. Hoặc nhiều bên tự
đổi ring → epoch loạn → đọc nhầm.

## 9. Ví von
Như **lễ tân duy nhất** của khách sạn: chỉ lễ tân được "đổi phòng đón khách" (switchover). Khi nghe chuông báo
phòng hỏng (rebuild), lễ tân **dọn 1 phòng trong bể** (activate) rồi **cập nhật bảng tin** (publish). Nhân viên
khác không tự đổi phòng.

## 10. Liên kết bức tranh lớn
ring phát `shm_ring_rebuild_requested` (mẩu 01) → **RingSupervisor.on_event → switchover (mẩu 08)** →
`pool.activate` (06) → `reset_for_reuse` (07) → `cp.publish` (03) → coordinator poll thấy đổi (mẩu 09/10).

## 11. Cạm bẫy (+errata)
- **Nhiều process cùng làm supervisor** → tranh publish. Thiết kế: 1 authority. (Composition root chỉ dựng 1.)
- **Đảo D-002/D-010:** supervisor H2 KHÔNG tạo ring mới / KHÔNG close ring cũ (pool lo). Đừng nhầm mô hình cũ (journal C-006/D-013).
- **Contract drain-before-reuse**: supervisor phải chắc pool[N%K] đã drain trước khi `activate` (bất biến ở tầng deploy/pool).

## 12. Tự kiểm (retrieval + Feynman)
- `switchover()` làm mấy bước, thứ tự nào? Vì sao `publish` phải sau `activate`?
- Vì sao switchover là **authority ở application**, không phải mỗi slot tự quyết?
- `on_event` lọc gì? Nếu không lọc (trigger mọi event) thì hỏng ra sao?

## 13. Mốc ôn
- 1 ngày: nhắc chuỗi read_current → +1 → activate → publish.
- 1 tuần: giải thích "1 authority" + đảo D-002/D-010 (không nhìn code).
- 1 tháng: tự viết lại `switchover` + `on_event`.

## 14. Nguồn
- Code: `application/ring_supervisor.py` — **đọc nguyên văn khi viết** (quote khớp).
- Hành vi: **đã có test** `tests/test_switchover_supervisor.py` (activate+publish monotonic · on_event lọc ·
  observability · tích hợp RingPool thật) — **4 test pass** (full 242 passed/1 skipped). → đã verify.
- Đảo quyết định: `ai-decision-journal/` D-013/C-006. · Độ chắc: cao (code + test chạy thật).
