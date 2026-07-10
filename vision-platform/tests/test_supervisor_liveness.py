"""supervisor-liveness: heartbeat (đóng K-020) + backoff (đóng K-021) — EVENT-DRIVEN (D-076/#287).

Viết lại chống-flaky (K-035): (1) test heartbeat-ok dùng `heartbeat_timeout_s` THỰC TẾ (margin >> nhịp beat)
→ jitter lịch/spawn chậm KHÔNG bị coi hang oan; (2) chạy `run()` trong THREAD + `wait_until` chờ tiến-độ (nhịp
heartbeat / restart_count) + `request_stop()`. Backoff logic = in-process xác định (giữ nguyên).
"""
from __future__ import annotations

import sys
import threading

import pytest

from vision_platform.application.supervisor import Supervisor, WorkerSpec
from tests._wait_helpers import wait_until
from tests.liveness_workers import heartbeat_ok_worker, heartbeat_then_hang_worker

_DEADLINE = 20.0


def _run_in_thread(sup: Supervisor) -> threading.Thread:
    t = threading.Thread(target=sup.run, name="supervisor-liveness-test", daemon=True)
    t.start()
    return t


def _stop_and_join(sup: Supervisor, t: threading.Thread) -> None:
    sup.request_stop()
    t.join(timeout=10.0)
    assert not t.is_alive(), "supervisor thread không dừng sau request_stop"


# ---- Backoff logic (in-process, deterministic — KHÔNG spawn) ----

def test_backoff_for_logic():
    sup = Supervisor(workers=[])
    spec = WorkerSpec(worker_id="x", target=heartbeat_ok_worker,
                      restart_backoff_base_s=0.1, restart_backoff_cap_s=1.0)
    assert sup._backoff_for(spec, 1) == pytest.approx(0.1)   # base·2^0
    assert sup._backoff_for(spec, 2) == pytest.approx(0.2)   # base·2^1
    assert sup._backoff_for(spec, 3) == pytest.approx(0.4)
    assert sup._backoff_for(spec, 10) == pytest.approx(1.0)  # cap
    spec0 = WorkerSpec(worker_id="y", target=heartbeat_ok_worker, restart_backoff_base_s=0.0)
    assert sup._backoff_for(spec0, 5) == 0.0                 # base=0 → không backoff


# ---- Cross-process (spawn) ----
pytestmark_cross = pytest.mark.skipif(sys.platform != "win32", reason="verify Windows; POSIX chưa verify")


@pytest.mark.slow
@pytestmark_cross
def test_heartbeat_ok_worker_not_restarted():
    """Property 2: worker beat ĐỀU → KHÔNG bị restart oan. `heartbeat_timeout_s` THỰC TẾ (2.0s, margin ~40× nhịp
    0.05s) → spawn chậm/jitter lịch KHÔNG false-positive (fix root #287 test-timeout thực tế)."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="ok", target=heartbeat_ok_worker,
                            uses_heartbeat=True, heartbeat_timeout_s=2.0)],
        poll_interval_s=0.05,
    )
    t = _run_in_thread(sup)
    try:
        # beat ĐẦU (sống sót startup)
        assert wait_until(lambda: "ok" in sup._heartbeats and sup._heartbeats["ok"].value > 0, _DEADLINE), \
            "worker chưa beat lần đầu"
        v0 = sup._heartbeats["ok"].value
        assert wait_until(lambda: sup._heartbeats["ok"].value > v0, 5.0), "beat không tiến (worker không chạy?)"
        v1 = sup._heartbeats["ok"].value
        assert wait_until(lambda: sup._heartbeats["ok"].value > v1, 5.0), "beat không tiếp tục"
        # beat ĐỀU liên tục + timeout rộng → không hang oan
        assert sup._restart_counts.get("ok", 0) == 0
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["ok"] == 0


@pytest.mark.slow
@pytestmark_cross
def test_hang_detected_and_restarted():
    """Property 1 (K-020): worker beat rồi NGỪNG (vẫn alive) → eventually phát hiện hang → restart >= 1."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="hang", target=heartbeat_then_hang_worker,
                            args=(2,), uses_heartbeat=True, heartbeat_timeout_s=0.4, max_restarts=10)],
        poll_interval_s=0.05,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: sup._restart_counts.get("hang", 0) >= 1, _DEADLINE), \
            "hang chưa được phát hiện+restart"
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["hang"] >= 1


@pytest.mark.slow
@pytestmark_cross
def test_hang_give_up_after_max_restarts():
    """Property 5: hang lặp + max_restarts=1 → cap tại 2 (>max) rồi bỏ (terminal)."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="hg", target=heartbeat_then_hang_worker,
                            args=(2,), uses_heartbeat=True, heartbeat_timeout_s=0.4, max_restarts=1)],
        poll_interval_s=0.05,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: sup._restart_counts.get("hg", 0) >= 2, _DEADLINE), "chưa đạt cap give-up (2)"
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["hg"] == 2   # cap terminal tại max+1
