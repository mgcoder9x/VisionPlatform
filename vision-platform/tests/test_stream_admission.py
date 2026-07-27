"""Test `StreamAdmission` (spec overlay-sse-transport Wave 2 — bulkhead cho kết nối streaming).

BỐI CẢNH ĐO THẬT (LOG #456): waitress WSGI **sync** cấp 1 thread/kết nối; `/stream` (MJPEG) và `/events` (SSE)
KHÔNG bao giờ kết thúc → với `--threads 8`, mở 8 kết nối dài là **MỌI request ngắn treo vô hạn** (`/stats`
timeout). Fix GỐC = bulkhead: trần tường minh + CHỪA reserve thread cho request ngắn + vượt trần trả 503 NGAY
(graceful degradation) thay vì hang âm thầm.

Lớp này THUẦN (chỉ đếm + khoá, stdlib) → test xác định, không cần server. Property P9/P10 phần logic.
"""
from __future__ import annotations

import threading

import pytest

from vision_platform.runtime.stream_admission import StreamAdmission, capacity_from_threads


# --- capacity_from_threads: dẫn trần từ thread-pool, CHỪA reserve cho request ngắn (P8 phần tính) ---
def test_capacity_reserves_threads_for_short_requests():
    assert capacity_from_threads(8, reserve=2) == 6      # 8 thread − 2 chừa = 6 kết nối dài
    assert capacity_from_threads(32, reserve=4) == 28


def test_capacity_never_below_one_even_with_tiny_pool():
    """Pool nhỏ hơn reserve → vẫn cho 1 stream (thà chậm còn hơn KHÔNG phục vụ được video)."""
    assert capacity_from_threads(2, reserve=2) == 1
    assert capacity_from_threads(1, reserve=8) == 1


@pytest.mark.parametrize("threads,reserve", [(0, 2), (-1, 2), (8, -1)])
def test_capacity_fail_fast_on_invalid(threads, reserve):
    with pytest.raises(ValueError):
        capacity_from_threads(threads, reserve=reserve)


def test_admission_fail_fast_on_invalid_max():
    with pytest.raises(ValueError):
        StreamAdmission(0)


# --- P9: vượt trần → try_acquire False (route sẽ trả 503, KHÔNG treo) ---
def test_acquire_until_limit_then_refuse():
    a = StreamAdmission(2)
    assert a.try_acquire() is True and a.active == 1
    assert a.try_acquire() is True and a.active == 2
    assert a.try_acquire() is False and a.active == 2      # vượt trần → TỪ CHỐI, không chiếm thêm thread
    assert a.max_streams == 2


# --- P10: release trả slot; over-release KHÔNG làm âm (double-release trong finally không phá trần) ---
def test_release_returns_slot():
    a = StreamAdmission(1)
    assert a.try_acquire() is True
    assert a.try_acquire() is False
    a.release()
    assert a.active == 0
    assert a.try_acquire() is True                          # slot dùng lại được


def test_over_release_clamped_at_zero():
    a = StreamAdmission(2)
    a.release()
    a.release()
    assert a.active == 0                                    # không âm → trần không bị nới sai
    assert a.try_acquire() is True and a.try_acquire() is True
    assert a.try_acquire() is False


# --- Thread-safety: nhiều thread đua acquire → KHÔNG vượt trần (waitress đa thread) ---
def test_concurrent_acquire_never_exceeds_limit():
    a = StreamAdmission(5)
    granted: list[bool] = []
    lock = threading.Lock()
    start = threading.Event()

    def worker():
        start.wait()
        ok = a.try_acquire()
        with lock:
            granted.append(ok)

    ts = [threading.Thread(target=worker) for _ in range(50)]
    for t in ts:
        t.start()
    start.set()
    for t in ts:
        t.join()

    assert sum(1 for g in granted if g) == 5                # đúng trần, không hơn
    assert a.active == 5
