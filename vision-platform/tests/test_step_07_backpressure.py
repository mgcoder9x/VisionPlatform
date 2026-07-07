"""Step 07: Backpressure — BoundedQueue thread-safe với 4 policy.

11 test theo Design step-07:
- Policy basic (4): DROP_OLDEST, DROP_NEWEST, REJECT, put-thành-công-khi-còn-chỗ.
- BLOCK (2): trả True khi consumer lấy chỗ · timeout khi không consumer.
- Concurrent stress (1): producer/consumer 100 item, FIFO giữ nguyên, không mất/deadlock.
- Phụ (4): get None-timeout · get_or_raise raise queue.Empty · qsize/maxsize/policy props · maxsize<1 ValueError.
"""
import queue
import threading
import time

import pytest

from vision_platform.kernel.backpressure import BackpressurePolicy, BoundedQueue


# ============ Policy basic (4) ============

def test_put_succeeds_when_space_available():
    q = BoundedQueue[int](maxsize=3, policy=BackpressurePolicy.REJECT)
    assert q.put(1) is True
    assert q.put(2) is True
    assert q.qsize() == 2
    assert q.drops == 0 and q.rejects == 0


def test_drop_oldest_basic():
    q = BoundedQueue[int](maxsize=3, policy=BackpressurePolicy.DROP_OLDEST)
    for i in range(5):
        assert q.put(i) is True   # luôn nhận (bỏ cũ nhất)
    assert q.qsize() == 3
    assert q.drops == 2
    assert q.get() == 2   # 0,1 đã bị bỏ → còn [2,3,4], FIFO
    assert q.get() == 3
    assert q.get() == 4


def test_drop_newest_basic():
    q = BoundedQueue[int](maxsize=2, policy=BackpressurePolicy.DROP_NEWEST)
    assert q.put(1) is True
    assert q.put(2) is True
    assert q.put(3) is False   # đầy → bỏ item mới
    assert q.qsize() == 2
    assert q.drops == 1
    assert q.get() == 1        # [1,2] giữ nguyên
    assert q.get() == 2


def test_reject_basic():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.REJECT)
    assert q.put(1) is True
    assert q.put(2) is False   # đầy → từ chối
    assert q.rejects == 1
    assert q.qsize() == 1


# ============ BLOCK (2) ============

def test_block_returns_when_consumer_takes():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.BLOCK)
    q.put(1)   # đầy

    def consumer():
        time.sleep(0.1)
        q.get()

    t = threading.Thread(target=consumer)
    t.start()
    start = time.monotonic()
    result = q.put(2, timeout=1.0)
    elapsed = time.monotonic() - start
    t.join()

    assert result is True
    assert 0.05 < elapsed < 0.5   # có chặn, nhưng không hết timeout


def test_block_timeout_when_no_consumer():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.BLOCK)
    q.put(1)
    start = time.monotonic()
    result = q.put(2, timeout=0.2)
    elapsed = time.monotonic() - start

    assert result is False
    assert q.block_timeouts == 1
    assert 0.18 < elapsed < 0.6


# ============ Concurrent stress (1) ============

def test_concurrent_producer_consumer():
    q = BoundedQueue[int](maxsize=10, policy=BackpressurePolicy.BLOCK)
    n = 100
    received = []

    def producer():
        for i in range(n):
            q.put(i, timeout=2.0)

    def consumer():
        for _ in range(n):
            item = q.get(timeout=2.0)
            if item is not None:
                received.append(item)

    p = threading.Thread(target=producer)
    c = threading.Thread(target=consumer)
    p.start()
    c.start()
    p.join(timeout=5)
    c.join(timeout=5)

    assert len(received) == n
    assert received == list(range(n))   # FIFO giữ nguyên


# ============ Phụ (4) ============

def test_get_returns_none_on_timeout():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.REJECT)
    start = time.monotonic()
    assert q.get(timeout=0.1) is None
    assert (time.monotonic() - start) >= 0.09


def test_get_or_raise_raises_on_timeout():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.REJECT)
    with pytest.raises(queue.Empty):
        q.get_or_raise(timeout=0.1)


def test_props_qsize_maxsize_policy():
    q = BoundedQueue[int](maxsize=5, policy=BackpressurePolicy.DROP_OLDEST)
    assert q.maxsize == 5
    assert q.policy == BackpressurePolicy.DROP_OLDEST
    q.put(1)
    assert q.qsize() == 1


def test_maxsize_must_be_positive():
    with pytest.raises(ValueError):
        BoundedQueue[int](maxsize=0, policy=BackpressurePolicy.REJECT)


def test_concurrent_multi_producer_multi_consumer_no_loss():
    """Audit hardening: N producer + N consumer contend (nhiều waiter trên CẢ 2 Condition).
    Bắt lost-wakeup/deadlock nếu notify sai. Assert: mọi item giao đúng 1 lần (không mất/không trùng)."""
    q = BoundedQueue[int](maxsize=5, policy=BackpressurePolicy.BLOCK)
    n_prod = n_cons = 4
    per = 50                          # mỗi producer đẩy `per` item duy nhất; mỗi consumer lấy `per` item
    total = n_prod * per

    def producer(base: int):
        for k in range(per):
            assert q.put(base + k, timeout=5.0) is True

    consumed: list[list[int]] = [[] for _ in range(n_cons)]

    def consumer(idx: int):
        for _ in range(per):
            item = q.get(timeout=5.0)
            assert item is not None    # không được timeout (không deadlock/lost-wakeup)
            consumed[idx].append(item)

    prods = [threading.Thread(target=producer, args=(i * 1000,)) for i in range(n_prod)]
    cons = [threading.Thread(target=consumer, args=(i,)) for i in range(n_cons)]
    for t in prods + cons:
        t.start()
    for t in prods + cons:
        t.join(timeout=10)

    got = [x for lst in consumed for x in lst]
    expected = {i * 1000 + k for i in range(n_prod) for k in range(per)}
    assert len(got) == total                 # đủ số (không mất, không deadlock)
    assert set(got) == expected              # đúng tập (không trùng, không lạc)
    assert q.qsize() == 0                     # hết sạch
