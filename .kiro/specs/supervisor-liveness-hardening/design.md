# Design Document — supervisor-liveness-hardening (bền máy chậm/tải + test xác định, no-GPU)

## Overview

Đóng K-035 bằng fix 2 root-cause đã chẩn đoán (KHÔNG bump timeout bừa):
- **(B, production) Tách `startup_grace_s` khỏi `heartbeat_timeout_s`** trong Supervisor: chờ beat-ĐẦU (spawn +
  import chậm) dùng ngưỡng RỘNG riêng; khoảng-cách-giữa-beat (steady-state) giữ ngưỡng chặt. → worker khoẻ
  khởi-động-chậm KHÔNG bị restart oan (lỗ production thật trên node ~100 cam tải nặng).
- **(A, test) Chờ-sự-kiện thay ngân-sách-thời-gian-cứng:** chạy supervisor trong THREAD + `wait_until(điều kiện)`
  (cap RỘNG) → assert khi điều kiện thoả rồi mới `request_shutdown()`. Xác định trên mọi tốc độ máy.

**Nguyên tắc gốc:** thời-gian-cứng trong test = giả định tốc-độ-máy (race). Chờ-điều-kiện = kiểm ĐÚNG thứ cần
(side-effect đã xảy ra), pass sớm khi nhanh, chỉ fail nếu điều kiện KHÔNG BAO GIỜ tới trong cap. Với production:
startup ≠ steady-state → không được dùng chung 1 ngưỡng.

## Bằng chứng code đã đọc (chống bịa)
- `supervisor.py::_is_hung`: `last = hb.value if hb.value>0 else self._spawn_walltime.get(wid,now); return (now-last) > spec.heartbeat_timeout_s`.
  → beat-đầu và steady-state DÙNG CHUNG `heartbeat_timeout_s`.
- `_spawn`: `mp.Process(...,daemon=True).start(); self._spawn_walltime[wid]=time.time()`. Windows spawn = re-import.
- `run(duration_s)`: vòng `while not _shutdown_requested`, break khi `(monotonic-start)>=duration_s`, cuối gọi `_cascade_shutdown`.
  `_request_shutdown(signum,frame)` set `_shutdown_requested=True` (chỉ gắn signal ở main thread; `except ValueError: pass` khi không phải main thread).
- Test `test_step_09_shutdown.py`: `sup.run(duration_s=0.4..1.5)` RỒI assert (`'alive_' in log`, `len(lines)>5`, `restart_counts==N`).
- Test `test_supervisor_liveness.py::test_heartbeat_ok...`: `heartbeat_timeout_s=0.5`, `sup.run(1.2)`, assert `counts==0`.
- Khớp failure quan sát (#284): `'alive_' in 'cleanup_done\n'` (chưa kịp beat), `4>5` (thiếu dòng), `counts!=0` (restart oan). git-stash: baseline sạch fail 4/6 → pre-existing.

## Architecture

Thay đổi TỐI THIỂU, additive: 1 trường `WorkerSpec` + sửa `_is_hung` + 1 method public `request_shutdown()` +
1 helper test + viết lại test theo chờ-sự-kiện. KHÔNG layer mới, KHÔNG đụng cascade/backoff/bulkhead.

```
application/supervisor.py
  • WorkerSpec.startup_grace_s: float | None = None   (None → = heartbeat_timeout_s: backward-compat)
  • _is_hung: chưa-beat → dùng startup_grace_s (từ spawn) ; đã-beat → heartbeat_timeout_s (từ beat cuối)
  • request_shutdown(): public → set _shutdown_requested=True (cho test dừng theo SỰ KIỆN, không đợi duration)

tests/_wait_helpers.py (mới)
  • wait_until(predicate, timeout_s, interval_s) -> bool   (poll điều kiện; THUẦN, no I/O ngoài sleep)

tests/test_step_09_shutdown.py + test_supervisor_liveness.py (viết lại)
  • chạy sup.run(...) trong THREAD → wait_until(<side-effect>) → sup.request_shutdown() → thread.join()
  • assert side-effect (đã chờ tới) — KHÔNG phụ thuộc duration cố định
```

- **Hướng phụ thuộc:** không đổi (chỉ sửa application + test). import-linter giữ 5/0.
- **Vì sao `request_shutdown()` public:** test cần DỪNG supervisor NGAY khi side-effect xảy ra (không đợi hết
  duration). Hiện chỉ có signal handler (main-thread-only) + set private. Public method = API sạch, additive,
  cũng hữu ích production (dừng có kiểm soát ngoài signal).

## Components and Interfaces

### 1. WorkerSpec.startup_grace_s + _is_hung (Supervisor)
```
@dataclass
class WorkerSpec:
    ...
    startup_grace_s: float | None = None
    """Ngưỡng RỘNG cho spawn+import+beat-đầu. None → = heartbeat_timeout_s (backward-compat).
       Đặt > heartbeat_timeout_s để chịu spawn chậm mà vẫn phát hiện hang steady-state chặt."""

def _is_hung(self, spec) -> bool:
    hb = self._heartbeats.get(spec.worker_id)
    if hb is None:
        return False
    if hb.value > 0:                                   # ĐÃ beat → steady-state (chặt)
        return (time.time() - hb.value) > spec.heartbeat_timeout_s
    grace = spec.startup_grace_s if spec.startup_grace_s is not None else spec.heartbeat_timeout_s
    spawn_at = self._spawn_walltime.get(spec.worker_id, time.time())
    return (time.time() - spawn_at) > grace            # CHƯA beat → startup grace (rộng)
```
- Additive: `startup_grace_s=None` → `grace = heartbeat_timeout_s` → hành vi Y HỆT hiện tại (R1.4).
- Đã-beat nhánh KHÔNG đổi → phát hiện hang steady-state giữ nguyên (R1.3, R3.1).

### 2. request_shutdown() (Supervisor, public additive)
```
def request_shutdown(self) -> None:
    """Yêu cầu dừng vòng giám sát (thread-safe: chỉ set cờ bool). Dùng ngoài signal (test / orchestration)."""
    self._shutdown_requested = True
```
- Chỉ set cờ bool (đọc trong vòng `while not _shutdown_requested`) — an toàn gọi từ thread khác (GIL + bool đơn).

### 3. tests/_wait_helpers.py — wait_until (chờ-sự-kiện)
```
def wait_until(predicate, timeout_s: float = 10.0, interval_s: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()          # kiểm lần cuối tại deadline
```
- Cap `timeout_s` RỘNG (chặn treo, KHÔNG phải mốc kỳ vọng); trả sớm khi điều kiện thoả.

### 4. Viết lại test theo chờ-sự-kiện (map từng test flaky)
Mẫu chung (chạy supervisor trong thread, dừng theo sự kiện):
```
import threading
sup = Supervisor(workers=[...], poll_interval_s=0.05, shutdown_grace_s=2.0)
t = threading.Thread(target=sup.run, kwargs={"duration_s": None})   # chạy tới khi request_shutdown
t.start()
assert wait_until(lambda: <side-effect đã xảy ra>, timeout_s=15.0)   # chờ SỰ KIỆN
sup.request_shutdown()
t.join(timeout=10.0)
# assert kết quả cuối (log/counts) — đã chắc side-effect xảy ra
```
- `graceful cleanup`: wait_until(log chứa "alive_") → shutdown → join → assert "cleanup_done" in log (worker dùng startup_grace rộng).
- `isolation (line>5)`: wait_until(count_lines(log2) > 5) → shutdown → assert.
- `spawns_and_terminates` / `non_cooperative`: wait_until(log tồn tại + >0) → shutdown → assert restart==0.
- `restarts_crashed` / `gives_up_after_max`: wait_until(restart_counts[wid] >= N) → shutdown → assert cap.
- `heartbeat_ok_not_restarted`: dùng `startup_grace_s` RỘNG (vd 5s) + `heartbeat_timeout_s` vừa (0.5s) → wait_until(≥3 beat qua hb.value / log) → assert counts==0 (không false-hang lúc spawn).
- `hang_detected` / `hang_give_up`: wait_until(restart_counts[wid] >= N) (beat rồi ngừng → steady-state timeout vẫn bắt) → assert.

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `WorkerSpec.startup_grace_s` | float\|None | None→=heartbeat_timeout_s; >0 nếu set | application | _is_hung |
| `Supervisor.request_shutdown` | method | set cờ bool (thread-safe) | application | test/orchestration |
| `wait_until` | hàm | (predicate, timeout_s, interval_s)→bool; poll | tests | mọi test process |

- KHÔNG đổi `run()` return (dict restart_counts), cascade, backoff, `_heartbeats`, `_spawn` prepend order.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| spawn chậm > heartbeat_timeout nhưng < startup_grace | KHÔNG coi hang (chờ beat-đầu trong startup_grace) → không restart oan | R1.2, P1 |
| worker beat rồi NGỪNG (hang thật) | đã-beat nhánh: (now-beat_cuối)>heartbeat_timeout → hang → restart (giữ nguyên) | R1.3, P2 |
| startup_grace_s = None (không set) | grace = heartbeat_timeout_s → hành vi cũ (backward-compat) | R1.4, P5 |
| side-effect không bao giờ xảy ra trong cap | wait_until trả False → assert False (fail RÕ, không treo vô hạn) | R2.2 |
| request_shutdown gọi từ thread test | chỉ set bool → vòng while thoát → cascade shutdown bình thường | R2.1 |
| thread supervisor không join kịp | t.join(timeout) + kiểm t.is_alive() (test tự fail nếu treo) | R2.4 |

## Correctness Properties

### Property 1: Startup grace ngăn false-hang (in-process, tiêm)
Với hb.value==0 (chưa beat), spawn cách đây `t`: `_is_hung` False khi `t < startup_grace_s` (kể cả `t > heartbeat_timeout_s`); True khi `t > startup_grace_s`. Tiêm hb + `_spawn_walltime` → xác định, không spawn thật.
**Validates: Requirements 1.1, 1.2**

### Property 2: Steady-state hang vẫn bắt (in-process, tiêm)
Với hb.value = (now − Δ), Δ > heartbeat_timeout_s → `_is_hung` True (đã-beat nhánh, không phụ thuộc startup_grace).
**Validates: Requirements 1.3, 3.1**

### Property 3: Test xác định qua chờ-sự-kiện (cross-process, no-GPU)
Test viết lại: side-effect được CHỜ (wait_until, cap rộng) trước khi assert/shutdown → pass bất kể tốc độ spawn.
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 4: Ổn định chống-flaky (bằng chứng)
Chạy LẶP bộ test process đã sửa ≥5 lần trên máy này → KHÔNG fail ngẫu nhiên (ổn định) = đóng K-035.
**Validates: Requirements 2.4, 4.3**

### Property 5: Backward-compat + layer + không giảm phủ
startup_grace_s=None → hành vi cũ; số test KHÔNG giảm (chỉ viết lại, không xoá/skip); import-linter 5 kept/0 broken.
**Validates: Requirements 1.4, 3.2, 3.3, 3.4**

## Testing Strategy

- **In-process `_is_hung` (P1,P2):** dựng Supervisor + WorkerSpec, set `_heartbeats[wid]=mp.Value('d', ...)` +
  `_spawn_walltime[wid]=now-Δ` tay → assert `_is_hung` cho các Δ quanh startup_grace_s / heartbeat_timeout_s.
  Xác định, KHÔNG spawn (nhanh, no-GPU).
- **Cross-process viết lại (P3):** mỗi test flaky → mẫu thread + wait_until (map ở §Components 4). Worker dùng
  startup_grace_s rộng để không false-hang.
- **Chống-flaky (P4):** chạy `pytest tests/test_step_09_shutdown.py tests/test_supervisor_liveness.py --count=5`
  (hoặc lặp thủ công 5 lần) → tất cả pass, không flaky. Ghi bằng chứng vào LOG.
- **Backward-compat (P5):** test `_is_hung` với startup_grace_s=None == hành vi heartbeat_timeout_s; full suite
  không giảm số test; `vp lint` 5/0.
- **Đối chiếu:** so trước/sau bằng git (test cũ vs mới cùng phủ property gốc — hang/crash/give-up/cleanup/isolation).

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** CI-tin-cậy (xác định) ⟂ vẫn-bắt-hang-thật (steady-state chặt) ⟂ không-restart-oan (startup rộng) ⟂
  backward-compat (default None) ⟂ không-giảm-phủ (viết lại, không skip). Cân được: tách 2 ngưỡng + chờ-sự-kiện.
- **What varies?** TỐC ĐỘ máy/độ-trễ-spawn → trừu tượng = CHỜ ĐIỀU KIỆN (không giả định thời gian) + ngưỡng
  startup RIÊNG (tham số, không hằng số ẩn). Không rải sleep khắp test.
- **Which way deps point?** không đổi (application + tests). helper wait_until ở tests (không vào src).
- **Cái GIÁ:** +1 trường WorkerSpec + 1 method + 1 helper + viết lại ~9 test (công vừa). Đổi lấy: CI đáng tin +
  đóng lỗ production restart-oan. Chấp nhận.
- **Vì sao KHÔNG bump timeout (fix ngọn):** bump chỉ dời ngưỡng — máy chậm hơn vẫn flaky + làm chậm suite. Chờ-sự-kiện
  diệt RACE tận gốc (pass sớm/ fail rõ). Đây là khác biệt bản chất.
- **Vì sao KHÔNG retry-tự-động test:** retry CHE flaky (vẫn còn race) — chỉ hợp lý nếu bất-khả xác-định-hoá; ở đây
  xác-định-hoá ĐƯỢC (chờ-sự-kiện) nên retry là né tránh gốc.
- **Rủi ro:** chạy supervisor trong thread + signal — supervisor đã `except ValueError` khi set signal ngoài main
  thread (đọc code) → an toàn. request_shutdown chỉ set bool → không race nguy hiểm.
- **Khi nào KHÔNG dùng:** test đơn-process thuần logic (không spawn) → không cần thread/wait_until (giữ trực tiếp).
- **Recognize:** test "sleep rồi assert side-effect của process khác" = mùi race → chuyển chờ-sự-kiện.

## Non-Goals (nhắc lại)
Bump timeout bừa (fix ngọn) · xoá/skip vĩnh viễn test · retry-tự-động che flaky · đổi cascade E-10/backoff/bulkhead ·
POSIX-specific liveness (giữ win32 verify) · đổi ngữ nghĩa restart-count/give-up cap.
