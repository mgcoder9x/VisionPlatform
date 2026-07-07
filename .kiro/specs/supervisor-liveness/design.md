# Design Document

> **Trạng thái:** PHA 1 (design) — CHỜ user valid + chốt Q1–Q2 trước tasks/code.
> **Neo:** requirements.md (R1–R6) + `application/supervisor.py` (đã đọc lại) + K-020/K-021. ADDITIVE.
> **Cập nhật lúc:** 2026-07-04.

## Overview

Thêm 2 cơ chế vào `Supervisor` (#09), ADDITIVE (mặc định TẮT → #09 không đổi):
1. **Heartbeat liveness** (đóng K-020): worker cập nhật `mp.Value('d')` (wall-clock time) định kỳ; supervisor
   coi HANG nếu alive nhưng nhịp quá hạn → terminate + restart.
2. **Restart backoff** (đóng K-021): non-blocking — mỗi worker có "thời điểm được respawn"; crash liên tục → giãn dần.

## Architecture

Layer: `application/supervisor.py` (đã có). Thêm field WorkerSpec + state Supervisor + logic trong `run` loop.
KHÔNG file mới trong src (sửa supervisor.py additive) + worker heartbeat mẫu ở test module (spawn-safe).

### QĐ-1 — Heartbeat qua `mp.Value('d')` (không dùng file)
Mỗi worker bật heartbeat → supervisor tạo `hb = mp.Value('d', 0.0)`, truyền cho worker qua `Process(args=)`
(thừa kế, như shutdown_event). Worker gọi `hb.value = time.time()` định kỳ (wall-clock — so sánh cross-process
được; monotonic KHÔNG so được giữa process). Supervisor đọc `hb.value`. *Vì sao Value không file:* không I/O
đĩa, không rác file, atomic dưới lock sẵn của mp.Value. *[chưa kiểm]* hành vi mp.Value spawn Windows → verify PHA build.

### QĐ-2 — Thứ tự args prepend (convention rõ)
`_spawn` prepend theo thứ tự CỐ ĐỊNH: `[shutdown_event?, heartbeat?] + spec.args`.
- chỉ shutdown_event: `target(shutdown_event, *args)`.
- chỉ heartbeat: `target(heartbeat, *args)`.
- cả hai: `target(shutdown_event, heartbeat, *args)`.
Document trong WorkerSpec. (Đây là điểm dễ sai → ghi rõ + test.)

### QĐ-3 — Backoff NON-BLOCKING (không sleep trong loop)
KHÔNG `time.sleep(backoff)` trong run loop (sẽ chặn giám sát worker khác — R3.3). Thay bằng
`_next_spawn_ok[worker_id] = monotonic_deadline`; khi worker chết/hang, set deadline = now + `min(base·2^(n−1), cap)`;
chỉ respawn khi `time.monotonic() >= deadline`. Loop tiếp tục kiểm worker khác trong lúc chờ.

### QĐ-4 — Startup grace (R1.3)
Track `_spawn_time[worker_id]`. "Nhịp tham chiếu" = `hb.value` nếu >0, ngược lại `_spawn_time`. HANG khi
`now − nhịp-tham-chiếu > heartbeat_timeout_s`. → worker chưa kịp beat lần đầu vẫn có grace = timeout kể từ spawn.

## Components and Interfaces

**WorkerSpec (thêm field, default TẮT — R2.2):**
```python
uses_heartbeat: bool = False
heartbeat_timeout_s: float = 2.0
restart_backoff_base_s: float = 0.0     # 0 = KHÔNG backoff (giữ #09)
restart_backoff_cap_s: float = 30.0
```

**Supervisor state (thêm):**
```python
_heartbeats: dict[str, "mp.Value"]      # worker_id → hb Value (chỉ worker bật)
_spawn_time: dict[str, float]           # worker_id → monotonic lúc spawn (grace + hang calc dùng time.time cho hb)
_next_spawn_ok: dict[str, float]        # worker_id → monotonic deadline được respawn (backoff)
```

**`_spawn` (sửa additive):** nếu `uses_heartbeat` → tạo/hoặc tái dùng `hb`, reset `hb.value=0.0`, prepend theo QĐ-2, ghi `_spawn_time[wid]=time.monotonic()`.

**`run` loop (sửa additive):** với mỗi worker còn `_procs`:
```
p = _procs[wid]
if not p.is_alive():                       # CRASH (như #09)
    _on_failure(spec, reason="crash", exit_code=p.exitcode)
elif spec.uses_heartbeat:                  # kiểm HANG (mới)
    hb = _heartbeats[wid]
    last = hb.value if hb.value > 0 else _spawn_time_walltime[wid]
    if time.time() - last > spec.heartbeat_timeout_s:
        obs/log "worker_heartbeat_timeout"
        p.terminate(); p.join(1.0); p.kill()? 
        _on_failure(spec, reason="hang", exit_code=None)
# respawn chỉ khi qua backoff deadline:
if wid not in _procs and được-phép-respawn(wid): _procs[wid] = _spawn(spec)
```
`_on_failure(spec, reason, exit_code)`: `restart_counts[wid]+=1`; nếu `> max_restarts` → give up (del); else set
`_next_spawn_ok[wid] = now + backoff(n)`; **không spawn ngay** (spawn ở nhánh "được-phép-respawn" khi tới deadline).

> Lưu ý: cần refactor nhỏ nhánh restart #09 thành `_on_failure` + tách "quyết định respawn" ra để dùng chung crash+hang + backoff. Giữ hành vi cũ khi heartbeat TẮT + backoff=0 (respawn ngay như #09).

## Data Models
`mp.Value('d', 0.0)` — double wall-clock giây (time.time()). 0.0 = chưa beat. Không DTO mới.

## Correctness Properties

### Property 1: Phát hiện hang
Worker alive nhưng ngừng beat > timeout → bị coi failure → restart (đóng K-020). **Validates: Requirements 1**

### Property 2: Không false-positive
Worker beat đều (< timeout) → KHÔNG bị restart. **Validates: Requirements 1, 2**

### Property 3: Additive
Worker không heartbeat + backoff=0 → hành vi y #09 (6 test xanh). **Validates: Requirements 2**

### Property 4: Backoff giãn + non-blocking
Crash liên tục base>0 → khoảng cách respawn tăng `base·2^(n-1)` (cap); worker khác vẫn được giám sát. **Validates: Requirements 3**

### Property 5: Give-up thống nhất
Hang lẫn crash đều tuân max_restarts (`>` → give up). **Validates: Requirements 4**

## Error Handling
Hang → `terminate()` (+ `kill()` nếu còn sống sau grace ngắn) → coi failure. mp.Value đọc lỗi (hiếm) → coi như chưa beat (an toàn: không false-positive vội, dựa grace).

## Testing Strategy
Test THẬT cross-process spawn (guard win32, như #09):
- `test_supervisor_heartbeat_detects_hang.py`: worker beat vài lần rồi NGỪNG beat (vẫn alive, sleep dài) → supervisor restart (Property 1); worker beat đều → không restart (Property 2).
- backoff: worker crash ngay + base>0 → đo `_next_spawn_ok` giãn dần (Property 4) — có thể test logic backoff in-process (thuần) + 1 test spawn.
- regression: chạy lại 6 test #09 (Property 3) + full + lint 5/0.

## Open Questions (CHỜ USER CHỐT)
- **Q1:** Heartbeat qua `mp.Value('d')` (QĐ-1) OK, hay muốn heartbeat-file (mtime)? (đề xuất mp.Value — không I/O đĩa)
- **Q2:** Backoff non-blocking bằng `_next_spawn_ok` deadline (QĐ-3) OK? (đề xuất — không chặn worker khác)
