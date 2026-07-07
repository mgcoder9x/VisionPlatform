"""Step 09: Supervisor + shutdown protocol cascade.

6 test (multi-process spawn → chậm ~vài giây):
- spawns_and_terminates: 2 ok worker, run rồi shutdown sạch (restart 0).
- isolation (bulkhead): 1 worker crash không kéo worker ổn định.
- graceful cleanup (cooperative): worker poll shutdown_event chạy `finally` cleanup.
- restarts_crashed: worker crash → supervisor restart (restart_count >= 1).
- gives_up_after_max: worker crash liên tục → cap restart rồi bỏ.
- non_coop_terminated: worker non-cooperative bị terminate lúc shutdown, run() trả về sạch.

Windows spawn: worker ở module riêng `tests/worker_funcs_for_step_09.py` (tests là package — có __init__).
"""
from vision_platform.application.supervisor import Supervisor, WorkerSpec
from tests.worker_funcs_for_step_09 import (
    ok_worker as _ok_worker,
    crash_worker as _crash_worker,
    eternally_failing_worker as _eternally_failing_worker,
    graceful_worker as _graceful_worker,
)


def test_supervisor_spawns_and_terminates_workers(tmp_path):
    """Spawn 2 worker, chạy 0.7s, shutdown sạch (restart 0)."""
    log1 = tmp_path / "w1.log"
    log2 = tmp_path / "w2.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="w1", target=_ok_worker, args=(str(log1),)),
            WorkerSpec(worker_id="w2", target=_ok_worker, args=(str(log2),)),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    restart_counts = sup.run(duration_s=0.7)
    assert restart_counts["w1"] == 0
    assert restart_counts["w2"] == 0
    assert log1.exists() and log1.stat().st_size > 0
    assert log2.exists() and log2.stat().st_size > 0


def test_supervisor_isolation_one_worker_crash_does_not_kill_others(tmp_path):
    """Bulkhead: w1 crash không dừng w2 (w2 tiếp tục heartbeat)."""
    log1 = tmp_path / "w1.log"
    log2 = tmp_path / "w2.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="crashing", target=_crash_worker, args=(str(log1), 0.3), max_restarts=10),
            WorkerSpec(worker_id="stable", target=_ok_worker, args=(str(log2),)),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    sup.run(duration_s=1.5)
    assert log2.exists()
    w2_lines = log2.read_text().strip().split("\n")
    assert len(w2_lines) > 5   # stable chạy liên tục


def test_supervisor_graceful_worker_runs_cleanup_on_shutdown(tmp_path):
    """Worker cooperative (poll shutdown_event) chạy cleanup khi dừng (đúng trên Windows + POSIX)."""
    log = tmp_path / "graceful.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="graceful", target=_graceful_worker, uses_shutdown_event=True, args=(str(log),)),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    sup.run(duration_s=0.5)
    content = log.read_text()
    assert "alive_" in content           # đã chạy
    assert "cleanup_done" in content     # ĐÃ cleanup (không bị kill cứng)


def test_supervisor_restarts_crashed_worker(tmp_path):
    """Worker crash sau 0.2s → supervisor restart (restart_count >= 1)."""
    log = tmp_path / "c.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="crasher", target=_crash_worker, args=(str(log), 0.2), max_restarts=10),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    restart_counts = sup.run(duration_s=1.2)
    assert restart_counts["crasher"] >= 1   # đã crash + restart ít nhất 1 lần


def test_supervisor_gives_up_after_max_restarts(tmp_path):
    """Worker crash ngay mọi lần, max_restarts=2 → cap tại 3 (>max) rồi bỏ."""
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="ef", target=_eternally_failing_worker, args=(None,), max_restarts=2),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=2.0,
    )
    restart_counts = sup.run(duration_s=5.0)
    # restart_count tăng tới khi > max (=3) thì bỏ → cap đúng tại 3, không tăng nữa.
    assert restart_counts["ef"] == 3


def test_supervisor_non_cooperative_worker_terminated_cleanly(tmp_path):
    """Worker non-cooperative (ok_worker chạy mãi) bị terminate lúc shutdown; run() trả về sạch."""
    log = tmp_path / "nc.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="nc", target=_ok_worker, args=(str(log),)),
        ],
        poll_interval_s=0.05,
        shutdown_grace_s=1.0,
    )
    restart_counts = sup.run(duration_s=0.4)
    assert restart_counts["nc"] == 0
    assert log.exists() and log.stat().st_size > 0   # đã chạy trước khi bị terminate
