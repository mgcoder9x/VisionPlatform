"""should_detect — chính sách THUẦN "frame này có nên chạy detector không" (spec adaptive-detection-perf Task 1).

Layer: domain — THUẦN (stdlib), KHÔNG import kernel (domain là lõi trong cùng; kernel phụ thuộc domain, không
ngược lại → nhận PRIMITIVE thay vì DetectionCadenceConfig). Clock (`now_ns`) + version tiêm → test xác định.

Hai cổng độc lập, PHẢI cùng thỏa mới detect:
- **min-interval:** `now_ns - last_detect_ns >= min_interval_ns` (điều tiết theo thời gian — quan trọng nhất
  vì detect vốn là nút cổ chai; throttle để dành CPU).
- **every-N:** `frame_version - last_detect_version >= every_n` (điều tiết theo số frame-version).
Lần đầu (chưa từng detect) → luôn detect. Trả `(should, reason)`; reason ∈ {FIRST, OK, MIN_INTERVAL, EVERY_N}.
Ràng buộc chống-giật (`min_interval <= displayLease`) cưỡng chế ở kernel `assert_cadence_fits_lease` (không ở đây).
"""
from __future__ import annotations

from typing import Optional, Tuple


def should_detect(
    *,
    now_ns: int,
    last_detect_ns: Optional[int],
    frame_version: int,
    last_detect_version: Optional[int],
    min_interval_ns: int,
    every_n: int,
    max_interval_ns: int = 0,
) -> Tuple[bool, str]:
    """Quyết định có chạy detector cho frame_version này không (thuần, xác định).

    Thứ tự: FIRST → HEARTBEAT (max-interval, ÉP, override mọi cổng) → min-interval (chặn) → every-N (chặn) → OK.
    `max_interval_ns=0` = tắt heartbeat (hành vi cũ).
    """
    if last_detect_ns is None or last_detect_version is None:
        return True, "FIRST"
    elapsed = now_ns - last_detect_ns
    # HEARTBEAT: quá lâu không detect → ÉP (đảm bảo box không mất — K-103). Override min/every/motion.
    if max_interval_ns > 0 and elapsed >= max_interval_ns:
        return True, "MAX_INTERVAL"
    # min-interval kiểm TRƯỚC every-N (thời gian) → reason ưu tiên khi cả hai fail.
    if min_interval_ns > 0 and elapsed < min_interval_ns:
        return False, "MIN_INTERVAL"
    if every_n > 1 and (frame_version - last_detect_version) < every_n:
        return False, "EVERY_N"
    return True, "OK"
