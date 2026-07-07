"""supervisor-liveness: heartbeat (đóng K-020) + backoff (đóng K-021).

Property 1 hang→restart · Property 2 beat-đều-không-restart · Property 4 backoff-logic · Property 5 give-up.
Cross-process spawn guard win32 (như #09). Backoff logic test in-process (deterministic).
"""
from __future__ import annotations

import sys

import pytest

from vision_platform.application.supervisor import Supervisor, WorkerSpec
from tests.liveness_workers import heartbeat_ok_worker, heartbeat_then_hang_worker


# ---- Backoff logic (in-process, deterministic) ----

def test_backoff_for_logic():
    sup = Supervisor(workers=[])
    spec = WorkerSpec(worker_id="x", target=heartbeat_ok_worker,
                      restart_backoff_base_s=0.1, restart_backoff_cap_s=1.0)
    assert sup._backoff_for(spec, 1) == pytest.approx(0.1)   # base·2^0
    assert sup._backoff_for(spec, 2) == pytest.approx(0.2)   # base·2^1
    assert sup._backoff_for(spec, 3) == pytest.approx(0.4)
    assert sup._backoff_for(spec, 10) == pytest.approx(1.0)  # cap
    # base=0 → KHÔNG backoff (giữ hành vi #09)
    spec0 = WorkerSpec(worker_id="y", target=heartbeat_ok_worker, restart_backoff_base_s=0.0)
    assert sup._backoff_for(spec0, 5) == 0.0


# ---- Cross-process (spawn) ----
pytestmark_cross = pytest.mark.skipif(sys.platform != "win32", reason="verify Windows; POSIX chưa verify")


@pytestmark_cross
def test_heartbeat_ok_worker_not_restarted():
    """Property 2: worker beat đều → KHÔNG bị restart nhầm (không false-positive)."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="ok", target=heartbeat_ok_worker,
                            uses_heartbeat=True, heartbeat_timeout_s=0.5)],
        poll_interval_s=0.05,
    )
    counts = sup.run(duration_s=1.2)
    assert counts["ok"] == 0


@pytestmark_cross
def test_hang_detected_and_restarted():
    """Property 1 (đóng K-020): worker beat rồi NGỪNG (vẫn alive) → supervisor phát hiện hang → restart."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="hang", target=heartbeat_then_hang_worker,
                            args=(2,), uses_heartbeat=True, heartbeat_timeout_s=0.4, max_restarts=10)],
        poll_interval_s=0.05,
    )
    counts = sup.run(duration_s=2.5)
    assert counts["hang"] >= 1   # đã phát hiện hang + restart ít nhất 1 lần


@pytestmark_cross
def test_hang_give_up_after_max_restarts():
    """Property 5: hang lặp lại + max_restarts=1 → cap tại 2 (>max) rồi bỏ (thống nhất với crash)."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="hg", target=heartbeat_then_hang_worker,
                            args=(2,), uses_heartbeat=True, heartbeat_timeout_s=0.4, max_restarts=1)],
        poll_interval_s=0.05,
    )
    counts = sup.run(duration_s=5.0)
    assert counts["hg"] == 2   # fail1→count1(≤1 restart), fail2→count2(>1 give up) → dừng ở 2
