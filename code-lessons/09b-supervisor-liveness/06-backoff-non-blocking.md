# Mẩu 06 — Backoff non-blocking: `_backoff_for` + `_next_spawn_ok` deadline

**(1) Thuộc về đâu:** `application/supervisor.py`, `_backoff_for` + nhánh respawn trong `run`.

**(2) Cần biết trước:** exponential backoff (chờ tăng dần); `time.monotonic()` (đo khoảng, không giật lùi); non-blocking (không `sleep` chặn).

**(3) Code thật (quote `application/supervisor.py`):**
```python
def _backoff_for(self, spec: WorkerSpec, restart_count: int) -> float:
    if spec.restart_backoff_base_s <= 0:
        return 0.0
    return min(spec.restart_backoff_base_s * (2 ** (restart_count - 1)), spec.restart_backoff_cap_s)
```
Trong `run` (sau khi quyết định restart):
```python
backoff = self._backoff_for(spec, self._restart_counts[wid])
if backoff <= 0:
    self._procs[wid] = self._spawn(spec)   # respawn NGAY (hành vi #09)
else:
    self._procs.pop(wid, None)
    self._pending_respawn[wid] = True
    self._next_spawn_ok[wid] = time.monotonic() + backoff
```
Đầu vòng, khi `p is None`:
```python
if self._pending_respawn.get(wid, False) and time.monotonic() >= self._next_spawn_ok.get(wid, 0.0):
    self._pending_respawn[wid] = False
    self._procs[wid] = self._spawn(spec)
```

**(4) Giải thích từng ý nhỏ:**
- `_backoff_for`: base<=0 → 0 (không backoff, #09). base>0 → `base·2^(n-1)` (n=lần restart), chặn trần `cap`.
- `backoff <= 0` → respawn NGAY (giữ hành vi #09).
- `backoff > 0` → **KHÔNG sleep**; gỡ proc, ghi `_pending_respawn=True` + `_next_spawn_ok = monotonic + backoff`.
- Đầu vòng: nếu tới hạn (`monotonic >= _next_spawn_ok`) → mới respawn. Vòng vẫn chạy kiểm worker KHÁC trong lúc chờ.

**(5) Là gì:** giãn nhịp restart tăng theo cấp số nhân (có trần), thực hiện **không chặn** vòng giám sát.

**(6) Tại sao NON-BLOCKING (bản chất):** nếu `time.sleep(backoff)` trong vòng → đang ngủ chờ worker A thì
worker B treo/chết **không ai giám sát** (supervisor "đơ"). Dùng deadline (`_next_spawn_ok`) → vòng tiếp tục
kiểm mọi worker mỗi `poll_interval`, chỉ trì hoãn RESPAWN của worker đang backoff. Đây là fix đúng bản chất
(một supervisor phải luôn "mắt mở" với TẤT CẢ worker).

**(7) Tại sao backoff:** worker crash liên tục (config hỏng) + respawn ngay → spawn/exit dồn dập → CPU spike +
log ngập (K-021). Giãn `base·2^(n-1)` cho hệ/tài nguyên hồi + giảm nhiễu. Trần `cap` để không chờ vô hạn.

**(8) Dùng ở đâu / bằng chứng:** `test_backoff_for_logic` (in-process, deterministic): base=0.1,cap=1.0 →
n=1→0.1, n=2→0.2, n=3→0.4, n=10→1.0 (cap); base=0 → 0.0. (Test logic thay đo timing cross-process → không flaky.)

**(9) Không có (sleep chặn) thì sao:** supervisor mù với worker khác trong lúc chờ backoff → mất tính giám sát toàn cục (worst khi nhiều camera).

**(10) Ví von:** thợ sửa máy hỏng liên tục — thay vì đứng chờ đúng máy đó (bỏ mặc máy khác), thợ ghi "9h15
quay lại máy A" rồi đi tuần máy B, C; tới 9h15 mới quay lại A. Chờ tăng dần để khỏi sửa-hỏng-sửa vô ích.

**(11) Cạm bẫy:** `_backoff_for` dùng `restart_count` (n) — công thức `2^(n-1)` để n=1 ra base (không 2·base).
Backoff dùng **monotonic** (đo khoảng trong 1 process supervisor — khác heartbeat wall-clock). base=0 phải giữ
"respawn ngay" (đừng vô tình thêm delay).

**(12) Tự kiểm:**
- Vì sao backoff non-blocking (deadline) thay vì `sleep`? Rủi ro của sleep là gì?
- `_backoff_for(base=0.1, n=3)` = ? Vì sao `2^(n-1)`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (_backoff_for + run) · test `test_backoff_for_logic` · design QĐ-3. Độ chắc: cao (quote thật + test logic pass).
