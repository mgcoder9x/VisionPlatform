"""Định danh & liveness tiến trình cho SHM crash-recovery (spec shm-production-hardening, Task 1).

Layer: runtime/ipc — đây là I/O concern (hỏi OS về tiến trình), KHÔNG phải DTO thuần.
import `psutil` CHỈ được phép ở layer này (import-linter cấm psutil ở domain/kernel).

VÌ SAO module này tồn tại (Requirement 2 / design §Process identity & liveness):
- Crash-recovery cần biết owner của một slot CÒN SỐNG hay ĐÃ CHẾT để quyết định quarantine.
- CẠM BẪY đã verify thật (Windows/Python 3.12.10): `os.kill(pid, 0)` trên Windows = `CTRL_C_EVENT`
  → gửi Ctrl+C vào console group → chính tiến trình gọi nhận `KeyboardInterrupt`. => KHÔNG dùng os.kill ở đây.
- PID reuse: OS có thể cấp lại một pid cũ cho tiến trình khác → chỉ so pid là KHÔNG đủ. Định danh bằng
  cặp `(pid, create_time_ns)`: chỉ coi "còn sống" khi pid tồn tại VÀ create_time khớp.

QUY TẮC AN TOÀN (design §pid_is_alive):
- Không xác định được trạng thái (AccessDenied / Zombie / lỗi OS) → trả UNKNOWN, KHÔNG coi là DEAD.
  Recovery chỉ quarantine khi DEAD (chắc chắn chết) — UNKNOWN/ALIVE thì skip (tránh quarantine nhầm
  tiến trình còn sống đang ghi dữ liệu).

THIẾT KẾ CHO TEST (Requirement 2.x): `owner_liveness` nhận một `query` injectable. Mặc định dùng psutil;
test bơm fake query để giả lập PID reuse / AccessDenied mà KHÔNG cần spawn process thật.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable, Tuple

import psutil


class Liveness(str, Enum):
    """Kết quả kiểm tra một tiến trình còn sống hay không."""
    ALIVE = "alive"      # pid tồn tại VÀ create_time khớp
    DEAD = "dead"        # không tồn tại, hoặc create_time lệch (pid bị tái dùng), hoặc pid <= 0
    UNKNOWN = "unknown"  # không xác định được (AccessDenied/Zombie/lỗi OS) → KHÔNG quarantine


class ProcessNotFound(Exception):
    """Provider khẳng định tiến trình KHÔNG tồn tại → DEAD."""


class ProcessAccessUnknown(Exception):
    """Provider KHÔNG xác định được trạng thái (quyền/zombie/lỗi OS) → UNKNOWN."""


# query(pid) -> (is_running, create_time_ns); raise ProcessNotFound / ProcessAccessUnknown.
ProcessQuery = Callable[[int], Tuple[bool, int]]


def _to_ns(create_time_seconds: float) -> int:
    """psutil trả create_time dạng giây (float, epoch). Chuẩn hoá sang ns nguyên (1 helper duy nhất)."""
    return int(create_time_seconds * 1_000_000_000)


def current_identity() -> Tuple[int, int]:
    """Định danh của TIẾN TRÌNH HIỆN TẠI = (pid, create_time_ns).

    Owner/reader ghi cặp này vào header slot; recovery so lại để chống PID reuse.
    """
    p = psutil.Process()
    return p.pid, _to_ns(p.create_time())


def _psutil_query(pid: int) -> Tuple[bool, int]:
    """Query mặc định: hỏi OS qua psutil. Map exception psutil → exception của module.

    - NoSuchProcess           → ProcessNotFound (DEAD)
    - AccessDenied/Zombie/OSError → ProcessAccessUnknown (UNKNOWN)
    """
    try:
        p = psutil.Process(pid)                 # raise NoSuchProcess nếu pid không tồn tại
        is_running = p.is_running()             # is_running xử lý PID reuse tốt hơn pid thô
        return is_running, _to_ns(p.create_time())
    except psutil.NoSuchProcess as exc:
        raise ProcessNotFound(str(exc)) from exc
    except (psutil.AccessDenied, psutil.ZombieProcess, OSError) as exc:
        raise ProcessAccessUnknown(str(exc)) from exc


def owner_liveness(
    pid: int,
    create_time_ns: int,
    *,
    query: ProcessQuery = _psutil_query,
) -> Liveness:
    """Tiến trình `(pid, create_time_ns)` còn sống không?

    Bảng quyết định (design §pid_is_alive, Requirement 2.3–2.6):
    - pid <= 0                                  → DEAD
    - query raise ProcessNotFound               → DEAD
    - query raise ProcessAccessUnknown          → UNKNOWN (KHÔNG quarantine)
    - is_running == False                       → DEAD
    - create_time thực tế != create_time_ns lưu → DEAD (PID đã bị OS tái dùng)
    - còn lại                                   → ALIVE
    """
    if pid <= 0:
        return Liveness.DEAD
    try:
        is_running, actual_create_time_ns = query(pid)
    except ProcessNotFound:
        return Liveness.DEAD
    except ProcessAccessUnknown:
        return Liveness.UNKNOWN

    if not is_running:
        return Liveness.DEAD
    if actual_create_time_ns != create_time_ns:
        return Liveness.DEAD   # pid trùng nhưng tiến trình KHÁC (PID reuse)
    return Liveness.ALIVE
