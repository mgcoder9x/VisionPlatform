"""Worker heartbeat mẫu cho test supervisor-liveness (module-level, spawn-safe).

`uses_heartbeat=True` → supervisor prepend `heartbeat: mp.Value('d')` làm arg đầu (không dùng shutdown_event
trong các test này). Worker gọi `heartbeat.value = time.time()` để báo nhịp.
"""
import time


def heartbeat_ok_worker(heartbeat):
    """Beat đều mãi (khoẻ) → KHÔNG bao giờ bị coi hang."""
    while True:
        heartbeat.value = time.time()
        time.sleep(0.05)


def heartbeat_then_hang_worker(heartbeat, beats=2):
    """Beat `beats` lần rồi NGỪNG beat nhưng vẫn ALIVE (sleep dài) → mô phỏng HANG/deadlock.

    is_alive()=True suốt → chỉ heartbeat mới phát hiện được (đóng K-020).
    """
    for _ in range(beats):
        heartbeat.value = time.time()
        time.sleep(0.05)
    time.sleep(3600)   # hang: sống nhưng không beat nữa
