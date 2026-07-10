"""Helper đồng-bộ EVENT-DRIVEN cho test cross-process (spec test-stability-hardening, D-076/#287).

Thay "sleep N giây rồi assert" (race, flaky dưới tải) bằng CHỜ ĐIỀU KIỆN quan sát được tới deadline GENEROUS
→ xác định trên mọi tốc độ máy (pass sớm khi nhanh, fail RÕ nếu điều kiện không bao giờ tới).

AN-TOÀN-NGOẠI-LỆ (K-070): predicate thường quan sát side-effect CHƯA xảy ra lúc bắt đầu chờ (vd log CHƯA tạo →
FileNotFoundError). `wait_until` coi predicate NÉM = "chưa thoả" (poll tiếp), KHÔNG crash.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


def _safe(predicate: Callable[[], bool]) -> bool:
    try:
        return bool(predicate())
    except Exception:            # noqa: BLE001 — side-effect CHƯA xảy ra (file/state chưa có) = "chưa thoả"
        return False


def wait_until(predicate: Callable[[], bool], deadline_s: float = 10.0, poll_s: float = 0.02) -> bool:
    """Poll `predicate` tới khi True HOẶC hết `deadline_s`. Trả True nếu thoả, False nếu quá hạn.

    `deadline_s` GENEROUS (chỉ chặn treo, KHÔNG phải mốc kỳ vọng). Predicate ném → coi "chưa thoả".
    """
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if _safe(predicate):
            return True
        time.sleep(poll_s)
    return _safe(predicate)      # kiểm lần cuối tại deadline


def log_text(path) -> str:
    """Đọc file log an toàn: trả "" nếu CHƯA tạo/đọc lỗi (predicate khỏi tự guard)."""
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def log_line_count(path) -> int:
    """Số dòng không rỗng trong log (0 nếu chưa tạo)."""
    txt = log_text(path)
    return len([ln for ln in txt.splitlines() if ln.strip()])
