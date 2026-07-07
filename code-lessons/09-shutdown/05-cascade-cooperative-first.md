# Mẩu 05 — `_cascade_shutdown`: 4 bước cooperative-first (ERRATA E-10)

**(1) Thuộc về đâu:** `application/supervisor.py`, `Supervisor._cascade_shutdown`. **Trái tim** graceful shutdown + là chỗ sửa bug E-10.

**(2) Cần biết trước:** mẩu 06 (graceful_worker cooperative); `mp.Event` (cờ liên-tiến-trình);
`p.join(timeout)` (chờ process kết thúc); `terminate()` (SIGTERM/TerminateProcess) vs `kill()` (SIGKILL/cứng); `finally`.

**(3) Code thật (quote `application/supervisor.py`):**
```python
def _cascade_shutdown(self) -> None:
    deadline = time.monotonic() + self.shutdown_grace_s
    # Step 0: tín hiệu cooperative — cách DUY NHẤT graceful trên Windows.
    if self._shutdown_event is not None:
        self._shutdown_event.set()
    # Step 1: JOIN worker COOPERATIVE với grace TRƯỚC (cho finally cleanup chạy). ERRATA E-10.
    coop_ids = {s.worker_id for s in self.workers if s.uses_shutdown_event}
    for wid, p in list(self._procs.items()):
        if wid in coop_ids:
            remaining = max(0.0, deadline - time.monotonic())
            p.join(timeout=remaining)
    # Step 2: terminate() mọi worker còn sống (non-cooperative / coop bị hang).
    for wid, p in self._procs.items():
        if p.is_alive():
            logger.debug("sending_sigterm", worker_id=wid)
            p.terminate()
    # Step 3: kill() stragglers cuối cùng.
    for wid, p in list(self._procs.items()):
        p.join(timeout=1.0)
        if p.is_alive():
            logger.warning("sigkill_straggler", worker_id=wid)
            p.kill()
            p.join(timeout=1.0)
```

**(4) Giải thích 4 bước:**
- **Step 0** `shutdown_event.set()` → báo mọi worker cooperative "dừng đi".
- **Step 1** JOIN các worker cooperative (`uses_shutdown_event`) với thời gian còn lại tới `deadline` →
  cho chúng tự thoát vòng lặp + chạy `finally` cleanup. Non-coop KHÔNG chờ (khỏi phí grace).
- **Step 2** `terminate()` ai còn sống (non-coop, hoặc coop bị treo) → SIGTERM (Linux) / TerminateProcess (Windows).
- **Step 3** `kill()` kẻ ngoan cố còn sống sau terminate → giết cứng cuối cùng.

**(5) Là gì:** trình tự tắt có kiểm soát: mềm trước (cho cleanup), cứng sau (chỉ khi cần).

**(6) Tại sao thứ tự này (ERRATA E-10):** bug cũ = set event rồi `terminate()` NGAY cho MỌI worker →
trên Windows `TerminateProcess` giết cứng, `finally` cleanup **không chạy** → race → cleanup gần như
luôn mất (đo thật: **1/20** lần chạy). Fix: JOIN cooperative với grace TRƯỚC → cleanup chạy xong (đo
lại **20/20**). Đây là fix **bản chất** (đổi thứ tự cascade), không phải vá ngọn.

**(7) Dùng ở đâu trong project:** gọi ở cuối `run()`. Test `test_supervisor_graceful_worker_runs_cleanup_on_shutdown`
kiểm `cleanup_done` xuất hiện → chứng minh Step 1 hoạt động THẬT tại #09.

**(8) Không có (terminate ngay) thì sao:** cleanup worker cooperative bị mất (Windows) → mất dữ liệu/
trạng thái dở → đúng bug E-10.

**(9) Ví von:** báo cháy sơ tán: (0) hú còi; (1) cho người TỰ đi ra theo lối thoát (mang theo đồ quan
trọng) trong X phút; (2) ai còn kẹt thì đội cứu hộ kéo ra; (3) ai vẫn mắc thì phá cửa. Không phá cửa ngay từ đầu.

**(10) Liên kết bức tranh lớn:** phân biệt coop/non-coop (mẩu 02 `uses_shutdown_event`) → non-coop
không chờ grace vô ích. `graceful_worker` (mẩu 06) là bên "tự đi ra". Nối giới hạn Windows (nhịp 2 cau-chuyen).

**(11) Cạm bẫy (E-10):** ĐỪNG đảo lại terminate-trước. `deadline` chia sẻ cho mọi coop (tổng grace, không mỗi worker
full grace). `list(self._procs.items())` (copy) khi có thể `del` trong vòng — tránh "dict changed during iteration".

**(12) Tự kiểm:**
- Kể 4 bước cascade + vì sao Step 1 (join coop) phải TRƯỚC Step 2 (terminate)?
- Bug E-10 là gì? Con số 1/20 → 20/20 nói lên điều gì?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (_cascade_shutdown) · `Design/00-ERRATA.md` E-10 · LOG #40 (verify 20×) ·
test graceful cleanup. Độ chắc: cao (quote thật + test pass tại #09).
