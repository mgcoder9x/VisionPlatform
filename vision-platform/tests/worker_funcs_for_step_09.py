"""Worker functions cho test Step 09 shutdown.

Module RIÊNG để multiprocessing spawn (mặc định trên Windows) pickle được (qua module path)
mà KHÔNG re-import test module. Không có side-effect top-level.
"""
import sys
import time


def ok_worker(work_path):
    """Heartbeat worker — ghi marker sống, chạy mãi (non-cooperative → bị force-kill lúc shutdown)."""
    while True:
        with open(work_path, "a") as f:
            f.write(f"alive_{time.time():.3f}\n")
        time.sleep(0.05)


def crash_worker(work_path, crash_after_s):
    """Chạy rồi crash (sys.exit(1)) sau N giây → supervisor restart."""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > crash_after_s:
            sys.exit(1)
        with open(work_path, "a") as f:
            f.write(f"alive_{elapsed:.3f}\n")
        time.sleep(0.05)


def short_lived_worker(work_path, run_for_s):
    """Chạy N giây rồi thoát sạch (exit 0)."""
    start = time.time()
    while time.time() - start < run_for_s:
        with open(work_path, "a") as f:
            f.write("ok\n")
        time.sleep(0.05)


def eternally_failing_worker(_):
    """Crash ngay lập tức, mọi lần → dùng test give-up-after-max-restarts."""
    sys.exit(1)


def graceful_worker(shutdown_event, work_path):
    """Cooperative worker: poll shutdown_event để tự thoát + cleanup (finally).

    Pattern graceful đúng trên CẢ Windows lẫn POSIX — KHÔNG dựa SIGTERM. `shutdown_event` là
    `mp.Event` do Supervisor truyền (arg đầu khi WorkerSpec.uses_shutdown_event=True).
    """
    try:
        while not shutdown_event.is_set():
            with open(work_path, "a") as f:
                f.write(f"alive_{time.time():.3f}\n")
            shutdown_event.wait(timeout=0.05)   # responsive: thoát <=0.05s sau khi set
    finally:
        # Cleanup chạy được vì worker tự thoát vòng lặp (không bị kill cứng).
        with open(work_path, "a") as f:
            f.write("cleanup_done\n")
