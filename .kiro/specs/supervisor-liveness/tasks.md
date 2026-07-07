# Implementation Plan

> Neo: requirements.md (R1–R6) + design.md (QĐ-1..4, Property 1..5). TDD, ADDITIVE (giữ 6 test #09). User duyệt Q1 (mp.Value) + Q2 (backoff non-blocking).

## Overview

Thêm heartbeat liveness (đóng K-020) + restart backoff (đóng K-021) vào `Supervisor` (#09) — ADDITIVE,
default TẮT. Verify cross-process thật trên Windows (worker treo → restart; beat đều → không restart).

## Tasks

- [x] 1. WorkerSpec + Supervisor state (additive fields) — uses_heartbeat/heartbeat_timeout_s/restart_backoff_base_s/cap + _heartbeats/_spawn_walltime/_pending_respawn/_next_spawn_ok.
- [x] 2. `_spawn` prepend heartbeat + reset hb + ghi spawn_walltime (QĐ-2).
- [x] 3. `_is_hung` + failure thống nhất (crash+hang) + backoff non-blocking (`_backoff_for`/`_next_spawn_ok`); giữ #09 khi tắt.
- [x] 4. `tests/liveness_workers.py` + `tests/test_supervisor_liveness.py` (4 test: hang→restart · beat-đều-không-restart · backoff-logic · give-up).
- [x] 5. Regression: #09 6 passed · full **304 passed/1 skipped** · lint 5 kept/0 broken.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2"], "note": "WorkerSpec/state + _spawn prepend heartbeat" },
    { "wave": 2, "tasks": ["3"], "note": "hang-detection + failure thống nhất + backoff (cần state+spawn)" },
    { "wave": 3, "tasks": ["4", "5"], "note": "worker mẫu + test cross-process + regression #09" }
  ]
}
```

## Notes

- ADDITIVE: heartbeat TẮT + backoff=0 → hành vi y #09 (Property 3). Verify bằng 6 test #09 giữ xanh.
- `hb.value = time.time()` (wall-clock, so cross-process được); backoff dùng monotonic (trong 1 process supervisor).
- Không claim xong khi chưa chạy test thật (§5). mp.Value spawn Windows [chưa kiểm] tới khi test pass.
