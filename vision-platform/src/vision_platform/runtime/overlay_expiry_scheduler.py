"""OverlayExpiryScheduler — phát TimerTick tới OverlayStateStore đúng lúc (spec Task 5, Property 13).

Layer: runtime. Bản chất: lease hết hạn là sự-kiện-theo-thời-gian; endpoint KHÔNG được tự lazy-expire
(design §6). Scheduler là "đồng hồ" đẩy `store.apply_tick(now)` tại/ sau deadline SỚM NHẤT → box hết hạn
đúng giờ mà KHÔNG busy-poll. Exactly-once là do STORE bảo đảm (`apply_tick` chỉ commit khi state đổi);
scheduler chỉ lo "khi nào gõ". Clock + sleep TIÊM → test fake-clock, xác định; serve() dừng qua stop_event.

KHÔNG bao lock quanh sleep (design §low-latency): scheduler đọc `next_expiry_ns()` (snapshot nhanh) rồi ngủ
NGOÀI lock, sau đó gọi apply_tick (tự lock). Không giữ lock trong lúc chờ.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from vision_platform.kernel.overlay_view import OverlayViewSnapshot
from vision_platform.runtime.overlay_state_store import OverlayStateStore


class OverlayExpiryScheduler:
    def __init__(self, store: OverlayStateStore, *,
                 clock: Callable[[], int] = time.monotonic_ns,
                 sleep_ns: Optional[Callable[[int], None]] = None,
                 idle_poll_ns: int = 250_000_000,   # 250ms khi không có gì hết hạn
                 max_wait_ns: int = 1_000_000_000    # cap 1s (chống ngủ quá lâu nếu deadline xa)
                 ) -> None:
        if idle_poll_ns <= 0 or max_wait_ns <= 0:
            raise ValueError("idle_poll_ns/max_wait_ns phải dương")
        self._store = store
        self._clock = clock
        self._sleep_ns = sleep_ns or (lambda ns: time.sleep(ns / 1_000_000_000))
        self._idle = idle_poll_ns
        self._max = max_wait_ns

    def wait_plan_ns(self, now_ns: int) -> int:
        """Số ns nên ngủ trước lần tick kế: tới deadline sớm nhất (cap max_wait); không có gì → idle_poll."""
        d = self._store.next_expiry_ns()
        if d is None:
            return self._idle
        return max(0, min(d - now_ns, self._max))

    def step(self) -> OverlayViewSnapshot:
        """Gõ 1 tick NGAY theo clock hiện tại (exactly-once do store đảm bảo)."""
        return self._store.apply_tick(self._clock())

    def serve(self, stop_event: threading.Event) -> None:
        """Vòng lặp: chờ tới deadline sớm nhất (ngủ ngoài lock) → tick. Dừng khi stop_event set."""
        while not stop_event.is_set():
            wait = self.wait_plan_ns(self._clock())
            if wait > 0:
                self._sleep_ns(wait)
            if stop_event.is_set():
                break
            self._store.apply_tick(self._clock())
