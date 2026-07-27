"""Test `LogThrottle` — chặn LOG AMPLIFICATION do client điều khiển (defect tự soi ra ở #462).

BỐI CẢNH: `_admit_or_503` (bulkhead D-152) in 1 dòng log MỖI lần từ chối. Client bị 503 sẽ retry (img.onerror
backoff #436) hoặc ai đó hammer `/events` ⇒ **lượng ghi đĩa của server do CLIENT điều khiển** và log lỗi THẬT bị
chìm. Cùng loại lỗi vừa fix cho thread (tài nguyên không có trần) — nên fix cùng triết lý: **giới hạn tường minh
+ KHÔNG mất thông tin** (nén lại và báo số lần đã nén, thay vì im lặng bỏ).

Thuần + xác định (tiêm `now_ns`) → không cần sleep, không flaky.
"""
from __future__ import annotations

import pytest

from vision_platform.runtime.log_throttle import LogThrottle

MS = 1_000_000
S = 1_000_000_000


def test_first_event_always_logs_with_zero_suppressed():
    t = LogThrottle(min_interval_ns=5 * S)
    assert t.tick(now_ns=0) == 0          # 0 = log ngay, chưa nén gì


def test_events_within_interval_are_suppressed_then_reported():
    t = LogThrottle(min_interval_ns=5 * S)
    assert t.tick(0) == 0
    assert t.tick(1 * S) is None          # trong cửa sổ → nén
    assert t.tick(2 * S) is None
    assert t.tick(3 * S) is None
    assert t.tick(5 * S) == 3             # hết cửa sổ → log + BÁO 3 lần đã nén (không mất thông tin)


def test_counter_resets_after_report():
    t = LogThrottle(min_interval_ns=5 * S)
    t.tick(0)
    t.tick(1 * S)
    assert t.tick(5 * S) == 1
    assert t.tick(6 * S) is None
    assert t.tick(10 * S) == 1            # đếm lại từ đầu sau mỗi lần báo


def test_sparse_events_never_suppressed():
    """Sự kiện thưa (bình thường) KHÔNG bị nén → không mất tín hiệu vận hành."""
    t = LogThrottle(min_interval_ns=5 * S)
    for i in range(5):
        assert t.tick(i * 10 * S) == 0


def test_monotonic_guard_clock_going_backwards():
    """Đồng hồ lùi (đo bằng monotonic thì hiếm, nhưng không được biến thành log-flood)."""
    t = LogThrottle(min_interval_ns=5 * S)
    assert t.tick(100 * S) == 0
    assert t.tick(90 * S) is None         # lùi → coi như trong cửa sổ, KHÔNG log
    assert t.tick(105 * S) == 1


@pytest.mark.parametrize("bad", [0, -1])
def test_fail_fast_on_invalid_interval(bad):
    with pytest.raises(ValueError):
        LogThrottle(min_interval_ns=bad)
