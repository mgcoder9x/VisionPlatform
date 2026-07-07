# Mẩu 04 — `_is_hung` + startup grace: phát hiện treo mà không báo oan

**(1) Thuộc về đâu:** `application/supervisor.py`, `_is_hung`.

**(2) Cần biết trước:** mẩu 03 (hb.value, spawn_walltime); startup grace (khoảng ân hạn lúc mới spawn); false-positive (báo nhầm).

**(3) Code thật (quote `application/supervisor.py`):**
```python
def _is_hung(self, spec: WorkerSpec) -> bool:
    """True nếu worker (bật heartbeat) alive nhưng nhịp quá hạn. Startup grace: chưa beat → mốc = spawn time."""
    hb = self._heartbeats.get(spec.worker_id)
    if hb is None:
        return False
    last = hb.value if hb.value > 0 else self._spawn_walltime.get(spec.worker_id, time.time())
    return (time.time() - last) > spec.heartbeat_timeout_s
```

**(4) Giải thích từng ý nhỏ:**
- `hb is None` → worker không bật heartbeat → KHÔNG bao giờ coi treo (return False). An toàn cho worker #09 cũ.
- `last = hb.value if hb.value > 0 else spawn_walltime` → **mốc tham chiếu**: nếu đã đập nhịp (hb>0) dùng
  nhịp cuối; nếu CHƯA kịp đập (hb=0, vừa spawn) dùng **thời điểm spawn** → **startup grace**.
- `(time.time() - last) > timeout` → im lặng quá ngưỡng → treo.

**(5) Là gì:** hàm quyết định worker có đang treo không, có tính đến "worker mới chưa kịp đập nhịp lần đầu".

**(6) Tại sao cần startup grace (bản chất):** worker vừa spawn cần thời gian khởi động (nạp model...) trước
khi đập nhịp lần đầu → `hb.value` còn 0. Nếu so `time.time() - 0` = con số khổng lồ → **báo treo NGAY lập
tức** (false-positive) → restart loop vô nghĩa. Dùng `spawn_walltime` làm mốc → worker có đúng `timeout`
giây kể từ spawn để đập nhịp đầu. Đây là fix bản chất chống false-positive.

**(7) Dùng ở đâu trong project:** gọi trong `run` loop: `elif spec.uses_heartbeat and self._is_hung(spec):`
→ treo → terminate + failure (mẩu 05). Test `test_heartbeat_ok_worker_not_restarted` chứng minh không false-positive.

**(8) Không có startup grace (dùng hb=0 trực tiếp) thì sao:** mọi worker vừa spawn bị coi treo ngay (hb=0 →
now-0 rất lớn) → restart vô hạn → hệ tê liệt. Grace là bắt buộc.

**(9) Ví von:** nhân viên mới vào chưa kịp ký sổ điểm danh lần đầu — quản lý cho họ X phút kể từ lúc vào
(spawn) rồi mới tính "vắng mặt", chứ không kết luận vắng ngay giây đầu.

**(10) Liên kết bức tranh lớn:** `_is_hung` là "cảm biến" treo; `run` loop là "bộ điều khiển" xử lý (mẩu 05).
`hb is None → False` giữ tính additive (worker không heartbeat miễn nhiễm).

**(11) Cạm bẫy:** `heartbeat_timeout_s` phải đủ lớn cho worker khởi động + lớn hơn chu kỳ đập nhịp (nếu
timeout < chu kỳ đập → treo oan giữa 2 nhịp). Dùng `time.time()` (khớp hb.value wall-clock — mẩu 03).

**(12) Tự kiểm:**
- Vì sao cần startup grace? Chuyện gì xảy ra nếu bỏ (dùng hb=0 trực tiếp)?
- `_is_hung` trả False khi nào (an toàn cho worker cũ)?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (_is_hung) · design QĐ-4 · test no-false-positive. Độ chắc: cao (quote thật + test pass).
