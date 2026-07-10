# Design Document — test-stability-hardening (ổn định test cross-process, no-GPU)

## Overview

Đóng K-035 (flaky supervisor/liveness/step_09) bằng fix ĐÚNG BẢN CHẤT ở TẦNG TEST — **KHÔNG đổi hành vi
Supervisor production** (nó đang đúng; đã xác nhận git-stash #284: baseline sạch cũng fail → pre-existing, không
do feature). 3 chế độ hỏng đã chẩn đoán từ code thật, mỗi cái có fix nguyên tắc:
- **rate-coupling** (`assert len(lines) > 5`) → assert PROPERTY bất biến (có output MỚI sau mốc), không đếm-tuyệt-đối.
- **window-race** (`run(0.5s)` rồi assert `alive_`) → CHỜ-SỰ-KIỆN (event-driven) tới deadline generous rồi mới assert/stop.
- **tight-timeout-false-positive** (`heartbeat_timeout_s=0.5`) → dùng timeout TEST phản ánh cấu hình thực tế (margin >> jitter).

**Nguyên tắc gốc:** test kiểm PROPERTY (bất biến hành vi), KHÔNG kiểm RATE/timing tuyệt đối; đồng bộ trên TIẾN ĐỘ
QUAN SÁT ĐƯỢC (event-driven) thay vì "ngủ N giây rồi hy vọng". Bump-timeout-bừa / retry-che-lỗi = fix ngọn (BÁC).

## Bằng chứng code đã đọc (chống bịa)
- `application/supervisor.py::Supervisor.run(duration_s)`: vòng `while not self._shutdown_requested`, break khi
  `(monotonic-start)>=duration_s`, cuối `_cascade_shutdown()`. **BLOCK** luồng gọi tới hết duration. `_request_shutdown`
  (signal handler) set `_shutdown_requested=True`; signal chỉ gắn ở main thread (`except ValueError: pass` khi không).
  → CHƯA có API public dừng từ luồng khác.
- `_is_hung`: đã-beat → `(now-hb.value)>heartbeat_timeout_s`; chưa-beat → mốc spawn. (Production default
  `heartbeat_timeout_s=2.0s` — đủ hấp thụ startup; test dùng 0.5s là phi-thực-tế → nguồn false-positive).
- `tests/worker_funcs_for_step_09.py`: `ok_worker` ghi `alive_{i}` mỗi ~0.05s; `graceful_worker` ghi `alive_` rồi
  `cleanup_done` trong `finally` khi shutdown_event set. `tests/liveness_workers.py::heartbeat_ok_worker` beat mỗi ~0.05s.
- Test flaky: `test_step_09_shutdown.py` (`run(0.4..1.5)` + assert `alive_`/`len>5`/`counts==N`), `test_supervisor_liveness.py::test_heartbeat_ok...` (`heartbeat_timeout_s=0.5`, assert `counts==0`).
- git-stash #284: baseline sạch fail 4/6 → flaky pre-existing (KHÔNG do thay đổi feature).

## Architecture

Thay đổi TỐI THIỂU: +1 API public additive @Supervisor (dừng từ luồng khác) + 1 helper test + viết-lại assertion
~9 test (rate→property, window→event-driven, timeout thực tế) + marker `slow`. KHÔNG đổi liveness/backoff/cascade.

```
application/supervisor.py
  • request_stop(): public → set _shutdown_requested=True (additive; không gọi = hành vi cũ). Cho test dừng
    theo SỰ KIỆN từ luồng nền (không đợi duration cố định). KHÔNG đổi semantics liveness/heartbeat/cascade.

tests/_wait_helpers.py (mới)
  • wait_until(predicate, deadline_s, poll_s) -> bool   (poll điều kiện tới deadline generous; THUẦN)

tests/conftest.py (đã có gpu-gate) — THÊM marker `slow` (đăng ký pyproject; KHÔNG autoskip mặc định → giữ phủ)

tests/test_step_09_shutdown.py + test_supervisor_liveness.py (viết lại assertion)
  • chạy sup.run() trong THREAD → wait_until(<tiến độ quan sát được>) → sup.request_stop() → thread.join()
  • assert PROPERTY (đã chờ tới) — KHÔNG phụ thuộc duration/rate/timeout chặt
```

- **Hướng phụ thuộc:** không đổi (application + tests). `wait_until` ở tests (không vào src). import-linter giữ 5/0.
- **Vì sao `request_stop()` public (additive, KHÔNG phải "đổi production"):** hiện chỉ dừng qua signal
  (main-thread-only) hoặc set private. Test cần dừng NGAY khi tiến-độ đạt (từ luồng nền). Public method set cờ bool
  = additive thuần (không gọi → hành vi #09 y hệt), cũng hữu ích orchestration production (dừng ngoài signal).
- **Vì sao KHÔNG thêm `startup_grace_s`/đổi `_is_hung` (đã cân nhắc + BÁC — YAGNI):** production default
  `heartbeat_timeout_s=2.0s` đã hấp thụ startup latency; flakiness thật do TEST dùng 0.5s phi-thực-tế. Đổi semantics
  supervisor cho vấn đề chủ-yếu-thuộc-test = over-engineer + thêm bề mặt production đang đúng. Fix test-timeout thực-tế
  (R3) + event-driven (R2) đủ diệt gốc. (Nếu SAU này có nhu cầu production thật: hang-detection chặt + startup chậm →
  mở spec riêng cho startup_grace; giờ chưa cần.)

## Components and Interfaces

### 1. Supervisor.request_stop() (public, additive)
```
def request_stop(self) -> None:
    """Yêu cầu dừng vòng giám sát từ luồng khác (thread-safe: chỉ set cờ bool đọc trong vòng run()).
    Additive: không gọi → hành vi cũ. KHÔNG đổi liveness/heartbeat/backoff/cascade."""
    self._shutdown_requested = True
```
- Chỉ set bool (đọc trong `while not self._shutdown_requested`) → an toàn gọi từ thread nền (GIL + gán bool đơn).

### 2. tests/_wait_helpers.py — wait_until (event-driven)
```
def wait_until(predicate, deadline_s: float = 10.0, poll_s: float = 0.02) -> bool:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(poll_s)
    return predicate()          # kiểm lần cuối tại deadline
```
- `deadline_s` GENEROUS (chỉ chặn treo, KHÔNG phải mốc kỳ vọng); trả sớm khi điều kiện thoả → nhanh khi máy nhanh.

### 3. Viết lại test (map 3 chế độ hỏng → fix)
Mẫu chung (chạy nền, dừng theo sự kiện):
```
import threading
sup = Supervisor(workers=[...], poll_interval_s=0.05, shutdown_grace_s=2.0)
t = threading.Thread(target=sup.run)          # run() không duration → tới khi request_stop
t.start()
try:
    assert wait_until(lambda: <tiến độ quan sát được>, deadline_s=15.0), "quá hạn: điều kiện chưa xảy ra thật"
    # (tuỳ test) chờ thêm điều kiện thứ 2 nếu cần
finally:
    sup.request_stop()
    t.join(timeout=10.0)
    assert not t.is_alive(), "supervisor thread không dừng"
# assert PROPERTY cuối (log/counts) — đã chắc tiến-độ xảy ra
```
- **isolation (rate-coupling→property):** wait_until(w1 đã crash+respawn ÍT NHẤT 1 lần VÀ w2 có dòng mốc T) → ghi lại số dòng w2 = `n0` → wait_until(w2 có dòng MỚI > n0) → assert w2 vẫn tiến triển (property "sống sót", không `>5`).
- **graceful (window-race→event):** wait_until(log chứa "alive_") → request_stop → join → assert "cleanup_done" in log.
- **spawns/non_cooperative:** wait_until(log tồn tại + size>0) → stop → assert restart_counts==0.
- **restarts_crashed/gives_up:** wait_until(restart_counts[wid] >= N, deadline rộng) → stop → assert cap.
- **heartbeat_ok (tight-timeout→thực tế):** `heartbeat_timeout_s` THỰC TẾ (vd 2.0s = default production, margin ~40× nhịp 0.05s) → wait_until(≥3 beat qua hb.value hoặc log) → assert counts==0 (jitter lịch không false-hang).
- **hang_detected/hang_give_up:** worker NGỪNG beat hẳn → wait_until(restart_counts[wid] >= N, deadline rộng) → assert (property "eventually detected", không mốc chặt).

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `Supervisor.request_stop` | method | set cờ bool (thread-safe) | application | test/orchestration |
| `wait_until` | hàm | (predicate, deadline_s, poll_s)→bool; poll | tests | test cross-process |
| marker `slow` | pytest marker | phân loại test spawn/timing (KHÔNG autoskip) | tests/pyproject | conftest |

- KHÔNG đổi `run()` return, `_is_hung`, `_heartbeats`, cascade, backoff, prepend order — production giữ nguyên.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| tiến độ không xảy ra trong deadline | wait_until→False → assert False message RÕ ("chưa xảy ra thật" vs máy chậm) | R2.2 |
| supervisor thread không dừng | `t.join(timeout)` + `assert not t.is_alive()` → test fail rõ, không treo | R2.3 |
| request_stop từ thread nền | chỉ set bool → vòng while thoát → cascade shutdown bình thường | R2.1, R4.1 |
| máy quá chậm/tải cực đại | deadline generous hấp thụ; nếu vẫn quá → fail RÕ (không flaky ngầm) — [giới hạn thống kê] | R5.2 |
| heartbeat jitter lịch dưới tải | timeout test thực-tế (margin lớn) → không false-positive | R3.1 |

## Correctness Properties

### Property 1: isolation kiểm PROPERTY sống-sót (không rate)
w1 crash → w2 TIẾP TỤC tiến triển (có dòng MỚI sau mốc), khẳng định bằng "tăng so với n0" — KHÔNG `len>5`. Pass bất kể tốc độ ghi.
**Validates: Requirements 1.1**

### Property 2: graceful kiểm đã-chạy-rồi-cleanup qua event
Chờ "alive_" xuất hiện (đã chạy) TRƯỚC khi stop → sau join assert "cleanup_done". Không phụ thuộc cửa sổ 0.5s.
**Validates: Requirements 1.2, 2.3**

### Property 3: heartbeat-ok không false-positive với timeout thực tế
`heartbeat_timeout_s` margin >> nhịp beat → worker beat đều → counts==0 ổn định (jitter không bị coi hang).
**Validates: Requirements 3.1**

### Property 4: hang thật vẫn phát hiện (eventually)
Worker NGỪNG beat hẳn → wait_until(restart_count≥N, deadline rộng) → phát hiện + restart (property, không mốc chặt).
**Validates: Requirements 3.2**

### Property 5: event-driven loại race (không cửa sổ cứng)
Mọi assert side-effect được CHỜ tới khi thoả (wait_until) rồi mới hành động → không "sleep rồi hy vọng".
**Validates: Requirements 2.1, 2.2**

### Property 6: ổn định chống-flaky (bằng chứng thống kê)
Chạy LẶP nhóm test cross-process ≥5 lần trên máy này → pass mọi lần (bằng chứng đóng K-035). [Giới hạn: không chứng minh 0-flake trên máy tải vô hạn.]
**Validates: Requirements 5.1, 5.2**

### Property 7: production không đổi + không giảm phủ + layer
`request_stop` additive (không gọi = hành vi cũ); `_is_hung`/cascade/backoff giữ nguyên; số test không giảm; import-linter 5 kept/0 broken.
**Validates: Requirements 4.1, 4.3, 5.3**

## Testing Strategy

- **Viết lại (P1–P5):** mỗi test flaky → mẫu thread + wait_until (map §Components 3). Assertion đổi rate→property,
  window→event, timeout→thực-tế.
- **Chống-flaky (P6):** chạy `pytest tests/test_step_09_shutdown.py tests/test_supervisor_liveness.py` LẶP 5 lần
  (thủ công hoặc `--count=5` nếu có pytest-repeat) → tất cả pass. Ghi bằng chứng (số lần + kết quả) vào LOG. Nêu RÕ
  giới hạn thống kê (R5.2).
- **Backward-compat/production (P7):** `request_stop` không gọi → so hành vi run(duration_s) cũ; full suite không
  giảm số test (573+); `vp lint` 5/0.
- **Marker:** đăng ký `slow` trong pyproject `[tool.pytest.ini_options] markers` (cạnh `gpu`); test spawn/timing gắn
  `@pytest.mark.slow` — MẶC ĐỊNH vẫn chạy (giữ phủ), chỉ để lọc/định vị.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** CI-tin-cậy (xác định) ⟂ vẫn-bắt-hang/crash-thật (property eventually) ⟂ không-đổi-production (chỉ +API
  additive) ⟂ không-giảm-phủ (viết lại, không skip). Cân được: property + event-driven + timeout thực tế.
- **What varies?** TỐC ĐỘ máy/độ-trễ-spawn/jitter-lịch → trừu tượng = CHỜ ĐIỀU KIỆN + timeout-margin-thực-tế (không
  hằng-số-thời-gian ẩn). Không rải sleep.
- **Vì sao KHÔNG đổi supervisor (startup_grace)?** Đã cân nhắc + BÁC: production default 2.0s đã hấp thụ startup;
  flakiness do test-timeout 0.5s phi-thực-tế. Đổi semantics production cho vấn-đề-thuộc-test = over-engineer + rủi ro
  (production đang đúng). YAGNI: mở spec riêng nếu sau này có nhu cầu hang-detection-chặt + startup-chậm thật.
- **Vì sao KHÔNG retry-che-lỗi (pytest-rerunfailures)?** Retry CHE flaky (race còn đó, hồi-quy thật cũng bị "rerun qua").
  Ở đây xác-định-hoá ĐƯỢC (event-driven) → retry là né gốc. BÁC.
- **Cái GIÁ:** +1 method + 1 helper + viết lại ~9 test + marker. Đổi lấy CI đáng tin (nền tảng verify của cả dự án).
- **Rủi ro:** chạy run() trong thread + set signal ngoài main-thread → supervisor đã `except ValueError` (đọc code) →
  an toàn. request_stop chỉ set bool → không race nguy hiểm. join(timeout)+is_alive chặn treo test.
- **Giới hạn trung thực:** event-driven xoá RACE thiết kế (nguyên tắc) nhưng KHÔNG chứng minh 0-flake trên máy tải
  vô hạn (deadline hữu hạn) — nêu rõ, không over-claim (R5.2).
- **Recognize:** test "sleep rồi assert side-effect process khác" / "đếm sự kiện trong cửa sổ cố định" = mùi race.

## Non-Goals (nhắc lại)
Đổi hành vi/semantics Supervisor production (heartbeat/backoff/cascade/`_is_hung`/startup_grace) · retry-che-lỗi ·
xoá/skip vĩnh viễn test (giảm phủ) · bảo đảm 0-flake máy tải vô hạn · POSIX-specific (giữ win32 verify) · đụng unit
test không-timing.
