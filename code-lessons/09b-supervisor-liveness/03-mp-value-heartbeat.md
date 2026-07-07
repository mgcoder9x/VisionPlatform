# Mẩu 03 — `mp.Value('d')` + prepend trong `_spawn`: kênh nhịp cross-process

**(1) Thuộc về đâu:** `application/supervisor.py`, `_spawn` (phần heartbeat).

**(2) Cần biết trước:** `mp.Value` (ô nhớ ctypes chia sẻ liên-tiến-trình); `time.time()` (wall-clock) vs
`time.monotonic()` (đồng hồ khoảng, mỗi process gốc riêng); truyền qua `Process(args=)` (thừa kế — #05b/#09).

**(3) Code thật (quote `application/supervisor.py`):**
```python
def _spawn(self, spec: WorkerSpec) -> mp.Process:
    prepend: list = []
    if spec.uses_shutdown_event:
        prepend.append(self._shutdown_event)
    if spec.uses_heartbeat:
        hb = self._heartbeats.get(spec.worker_id)
        if hb is None:
            hb = mp.Value("d", 0.0)
            self._heartbeats[spec.worker_id] = hb
        else:
            hb.value = 0.0   # reset → re-arm startup grace cho instance mới
        prepend.append(hb)
    p = mp.Process(target=spec.target, args=(*prepend, *spec.args), name=..., daemon=True)
    p.start()
    self._spawn_walltime[spec.worker_id] = time.time()
    return p
```

**(4) Giải thích từng ý nhỏ:**
- `mp.Value("d", 0.0)` → ô nhớ chia sẻ kiểu **double** (float), khởi tạo 0.0. Cả cha lẫn con thấy CÙNG ô.
- `prepend` theo thứ tự CỐ ĐỊNH `[shutdown_event?, heartbeat?]` → worker signature khớp (mẩu này + convention).
- `hb.value = 0.0` khi respawn → **reset** để startup grace tính lại cho instance mới (không dùng nhịp cũ).
- `self._spawn_walltime[wid] = time.time()` → ghi mốc spawn (wall-clock) cho startup grace (mẩu 04).
- Worker (bên kia) gọi `heartbeat.value = time.time()` định kỳ (xem `tests/liveness_workers.py`).

**(5) Là gì:** cấp cho mỗi worker-bật-heartbeat một ô nhớ chia sẻ để "đập nhịp"; supervisor đọc ô đó.

**(6) Tại sao WALL-CLOCK (`time.time()`) không MONOTONIC:** heartbeat phải **so được GIỮA 2 process** (con
ghi, cha đọc). `time.monotonic()` mỗi process có **gốc riêng** (không so được cross-process). `time.time()`
là đồng hồ hệ thống chung → con ghi `time.time()`, cha so `time.time() - hb.value` → đúng. (Backoff thì
dùng monotonic vì đo khoảng TRONG 1 process supervisor — mẩu 06.)

**(7) Dùng ở đâu trong project:** `_spawn` cấp hb; `_is_hung` đọc `hb.value` (mẩu 04). Worker `heartbeat_ok_worker`/
`heartbeat_then_hang_worker` ghi `heartbeat.value = time.time()`.

**(8) Không có (hoặc dùng monotonic) thì sao:** không có kênh → không phát hiện hang. Dùng monotonic cross-process
→ so sai (gốc khác nhau) → báo treo loạn / không phát hiện.

**(9) Ví von:** cha đưa con một **đồng hồ treo tường chung** (wall-clock) + một bảng con ghi "lần cuối tôi
làm việc". Cha nhìn bảng + đồng hồ chung → biết con im bao lâu. Nếu mỗi người xài đồng hồ bấm giờ riêng
(monotonic) thì không so được với nhau.

**(10) Liên kết bức tranh lớn:** lock/Value/Event thừa kế qua `Process(args=)` là pattern cross-process xuyên
suốt (#05b T-B, #09 shutdown_event, giờ heartbeat). Thứ tự prepend nối #09 (shutdown_event) — giờ có 2 kênh.

**(11) Cạm bẫy:** phải reset `hb.value=0.0` khi respawn (không thì nhịp cũ làm grace sai). Thứ tự prepend
phải khớp signature worker (cả 2 kênh → `target(shutdown_event, heartbeat, *args)`). mp.Value đọc/ghi atomic
dưới lock sẵn — không cần lock thêm cho 1 double.

**(12) Tự kiểm:**
- Vì sao heartbeat dùng `time.time()` (wall-clock) mà không `monotonic`?
- Vì sao reset `hb.value=0.0` khi respawn?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (_spawn) · `tests/liveness_workers.py` · design QĐ-1/QĐ-2. Độ chắc: cao (quote thật + test cross-process pass Windows).
