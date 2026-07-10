"""Step 09: Supervisor + shutdown protocol cascade — EVENT-DRIVEN (spec test-stability-hardening, D-076/#287).

Viết lại chống-flaky (K-035): chạy `sup.run()` trong THREAD → CHỜ tiến-độ-quan-sát-được (`wait_until`) →
`sup.request_stop()` → join. Assert PROPERTY (bất biến hành vi), KHÔNG assert rate/timing tuyệt đối. Xác định
trên mọi tốc độ máy (pass sớm khi nhanh, fail RÕ nếu điều kiện không bao giờ tới).

6 property giữ nguyên: spawn+terminate sạch (restart 0) · isolation (w2 sống khi w1 crash) · graceful cleanup ·
restart-on-crash · give-up-after-max · non-cooperative terminate sạch.

Windows spawn: worker ở module riêng `tests/worker_funcs_for_step_09.py` (picklable).
"""
import threading

import pytest

from vision_platform.application.supervisor import Supervisor, WorkerSpec
from tests._wait_helpers import wait_until, log_text, log_line_count
from tests.worker_funcs_for_step_09 import (
    ok_worker as _ok_worker,
    crash_worker as _crash_worker,
    eternally_failing_worker as _eternally_failing_worker,
    graceful_worker as _graceful_worker,
)

_DEADLINE = 20.0   # cap GENEROUS cho spawn chậm/tải (chỉ chặn treo, KHÔNG phải mốc kỳ vọng)


def _run_in_thread(sup: Supervisor) -> threading.Thread:
    t = threading.Thread(target=sup.run, name="supervisor-under-test", daemon=True)
    t.start()
    return t


def _stop_and_join(sup: Supervisor, t: threading.Thread) -> None:
    sup.request_stop()
    t.join(timeout=10.0)
    assert not t.is_alive(), "supervisor thread không dừng sau request_stop"


@pytest.mark.slow
def test_supervisor_spawns_and_terminates_workers(tmp_path):
    """PROPERTY: 2 worker khởi động (ghi log) rồi shutdown sạch với restart 0."""
    log1, log2 = tmp_path / "w1.log", tmp_path / "w2.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="w1", target=_ok_worker, args=(str(log1),)),
            WorkerSpec(worker_id="w2", target=_ok_worker, args=(str(log2),)),
        ],
        poll_interval_s=0.05, shutdown_grace_s=2.0,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: log_line_count(log1) > 0 and log_line_count(log2) > 0, _DEADLINE), \
            "2 worker chưa kịp ghi log (khởi động)"
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["w1"] == 0 and sup._restart_counts["w2"] == 0
    assert log1.stat().st_size > 0 and log2.stat().st_size > 0


@pytest.mark.slow
def test_supervisor_isolation_one_worker_crash_does_not_kill_others(tmp_path):
    """PROPERTY (bulkhead): w2 TIẾP TỤC tiến triển SAU khi w1 đã crash (không kéo w2 chết) — không đếm-tuyệt-đối."""
    log1, log2 = tmp_path / "w1.log", tmp_path / "w2.log"
    sup = Supervisor(
        workers=[
            WorkerSpec(worker_id="crashing", target=_crash_worker, args=(str(log1), 0.3), max_restarts=10),
            WorkerSpec(worker_id="stable", target=_ok_worker, args=(str(log2),)),
        ],
        poll_interval_s=0.05, shutdown_grace_s=2.0,
    )
    t = _run_in_thread(sup)
    try:
        # w1 đã crash+restart ÍT NHẤT 1 lần VÀ w2 đã ghi được
        assert wait_until(lambda: sup._restart_counts.get("crashing", 0) >= 1 and log_line_count(log2) > 0,
                          _DEADLINE), "crasher chưa crash/restart hoặc stable chưa ghi"
        n0 = log_line_count(log2)
        # w2 tiếp tục ghi dòng MỚI (tiến triển) SAU khi w1 crash → chứng minh sống sót (property, không rate)
        assert wait_until(lambda: log_line_count(log2) > n0, _DEADLINE), "stable KHÔNG tiến triển sau crash w1"
    finally:
        _stop_and_join(sup, t)


@pytest.mark.slow
def test_supervisor_graceful_worker_runs_cleanup_on_shutdown(tmp_path):
    """PROPERTY: worker cooperative đã CHẠY (alive_) rồi CLEANUP (cleanup_done) — chờ đã-chạy trước khi stop."""
    log = tmp_path / "graceful.log"
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="graceful", target=_graceful_worker,
                            uses_shutdown_event=True, args=(str(log),))],
        poll_interval_s=0.05, shutdown_grace_s=2.0,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: "alive_" in log_text(log), _DEADLINE), "worker chưa chạy (alive_)"
    finally:
        _stop_and_join(sup, t)
    content = log_text(log)
    assert "alive_" in content            # đã chạy
    assert "cleanup_done" in content      # ĐÃ cleanup (không bị kill cứng — finally chạy)


@pytest.mark.slow
def test_supervisor_restarts_crashed_worker(tmp_path):
    """PROPERTY: worker crash → supervisor restart (eventually restart_count >= 1)."""
    log = tmp_path / "c.log"
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="crasher", target=_crash_worker, args=(str(log), 0.2), max_restarts=10)],
        poll_interval_s=0.05, shutdown_grace_s=2.0,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: sup._restart_counts.get("crasher", 0) >= 1, _DEADLINE), \
            "worker crash chưa được restart"
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["crasher"] >= 1


@pytest.mark.slow
def test_supervisor_gives_up_after_max_restarts(tmp_path):
    """PROPERTY: crash mọi lần, max_restarts=2 → cap tại 3 (>max) rồi bỏ (terminal, không tăng nữa)."""
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="ef", target=_eternally_failing_worker, args=(None,), max_restarts=2)],
        poll_interval_s=0.05, shutdown_grace_s=2.0,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: sup._restart_counts.get("ef", 0) >= 3, _DEADLINE), \
            "chưa đạt cap give-up (3)"
    finally:
        _stop_and_join(sup, t)
    assert sup._restart_counts["ef"] == 3   # cap chính xác tại max+1, terminal


@pytest.mark.slow
def test_supervisor_non_cooperative_worker_terminated_cleanly(tmp_path):
    """PROPERTY: worker non-cooperative (ok_worker) đã chạy → bị terminate lúc shutdown, run() trả về SẠCH."""
    log = tmp_path / "nc.log"
    sup = Supervisor(
        workers=[WorkerSpec(worker_id="nc", target=_ok_worker, args=(str(log),))],
        poll_interval_s=0.05, shutdown_grace_s=1.0,
    )
    t = _run_in_thread(sup)
    try:
        assert wait_until(lambda: log_line_count(log) > 0, _DEADLINE), "worker chưa chạy"
    finally:
        _stop_and_join(sup, t)   # assert thread dừng sạch nằm trong đây
    assert sup._restart_counts["nc"] == 0
    assert log.stat().st_size > 0
