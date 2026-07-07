"""Backpressure — BoundedQueue thread-safe với 4 policy khi hàng đợi đầy.

Layer: kernel — dữ liệu + cơ chế THUẦN Python (threading/collections/queue). KHÔNG import
cv2/torch/zmq/multiprocessing/shared_memory (contract import-linter "Kernel chi phu thuoc domain").

⚠️ RANH GIỚI QUAN TRỌNG (K-016): BoundedQueue là **THREAD-safe** (dùng threading.Lock/Condition) —
KHÔNG process-safe. Chỉ dùng cho hàng đợi TRONG MỘT tiến trình (vd: thread capture → thread submit).
Truyền frame GIỮA các tiến trình vẫn phải qua SHM ring (bài #05) — threading.Lock không đồng bộ
được cross-process. Dùng nhầm cross-process = khoá vô hiệu → hỏng dữ liệu.

4 policy (Module 02 có 6; bỏ SAMPLE/DEGRADE_QUALITY vì là quyết định source-side, không phải queue):
    DROP_OLDEST · DROP_NEWEST · BLOCK · REJECT.
Lưu ý vận hành: BLOCK KHÔNG dùng cho source RTSP (gây TCP Zero Window) — ràng buộc này enforce ở
tầng cấu hình/per-source, KHÔNG ở đây (BoundedQueue giữ policy-agnostic — SRP).
"""
from __future__ import annotations

import queue as _queue
from collections import deque
from enum import Enum
from threading import Condition, Lock
from typing import Generic, Optional, TypeVar


class BackpressurePolicy(Enum):
    """Chính sách khi hàng đợi đầy (maxsize)."""
    DROP_OLDEST = "drop_oldest"   # bỏ item cũ nhất, nhận item mới (giữ dữ liệu mới)
    DROP_NEWEST = "drop_newest"   # bỏ item mới (giữ item đang có)
    BLOCK = "block"               # chặn producer tới khi có chỗ / timeout
    REJECT = "reject"             # từ chối ngay, không chặn


T = TypeVar("T")


class BoundedQueue(Generic[T]):
    """Hàng đợi có giới hạn, thread-safe, với backpressure policy cấu hình được.

    Metrics (đọc để quan sát — #08 sẽ wire vào observability):
        - drops: số item bị bỏ (DROP_OLDEST/DROP_NEWEST).
        - rejects: số lần REJECT.
        - block_timeouts: số lần BLOCK hết giờ chờ.
    """

    def __init__(self, maxsize: int, policy: BackpressurePolicy):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._buf: deque[T] = deque()
        self._maxsize = maxsize
        self._policy = policy
        self._lock = Lock()
        self._not_empty = Condition(self._lock)
        self._not_full = Condition(self._lock)
        self.drops = 0
        self.rejects = 0
        self.block_timeouts = 0

    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """Thử đưa item vào. True = item của caller đã vào; False = drop/reject/timeout."""
        with self._lock:
            if len(self._buf) < self._maxsize:
                self._buf.append(item)
                self._not_empty.notify()
                return True

            if self._policy == BackpressurePolicy.DROP_OLDEST:
                # Net size không đổi → chỉ notify not_empty (item mới), không notify not_full.
                self._buf.popleft()
                self._buf.append(item)
                self.drops += 1
                self._not_empty.notify()
                return True

            if self._policy == BackpressurePolicy.DROP_NEWEST:
                self.drops += 1
                return False

            if self._policy == BackpressurePolicy.REJECT:
                self.rejects += 1
                return False

            if self._policy == BackpressurePolicy.BLOCK:
                # wait_for re-check predicate → chống spurious wakeup.
                if not self._not_full.wait_for(
                    lambda: len(self._buf) < self._maxsize,
                    timeout=timeout,
                ):
                    self.block_timeouts += 1
                    return False
                self._buf.append(item)
                self._not_empty.notify()
                return True

            raise ValueError(f"Unknown policy: {self._policy}")

    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """Chờ lấy item. Trả None khi timeout.

        CẢNH BÁO: nếu queue có thể chứa None hợp lệ, None-timeout trùng nghĩa → dùng get_or_raise.
        """
        with self._lock:
            if not self._not_empty.wait_for(
                lambda: len(self._buf) > 0,
                timeout=timeout,
            ):
                return None
            item = self._buf.popleft()
            self._not_full.notify()
            return item

    def get_or_raise(self, timeout: Optional[float] = None) -> T:
        """Chờ lấy item; raise queue.Empty khi timeout (không nhập nhằng None)."""
        with self._lock:
            if not self._not_empty.wait_for(
                lambda: len(self._buf) > 0,
                timeout=timeout,
            ):
                raise _queue.Empty
            item = self._buf.popleft()
            self._not_full.notify()
            return item

    def qsize(self) -> int:
        with self._lock:
            return len(self._buf)

    @property
    def policy(self) -> BackpressurePolicy:
        return self._policy

    @property
    def maxsize(self) -> int:
        return self._maxsize
