"""log_throttle — chặn LOG AMPLIFICATION: nén log lặp do CLIENT điều khiển, KHÔNG mất thông tin.

VẤN ĐỀ (tự soi ra ở #462, cùng loại với starve thread #456): endpoint từ chối (`503` khi đạt trần bulkhead) mà in
log MỖI lần thì **lượng ghi đĩa/độ ồn log do client quyết định** — client bị 503 sẽ retry (backoff `img.onerror`
#436), hoặc một client hỏng/kẻ tấn công hammer `/events`. Hậu quả: log lỗi THẬT bị chìm giữa hàng nghìn dòng
giống nhau; với `RotatingFileHandler` (#443) thì log cũ bị xoay mất sớm ⇒ mất khả năng chẩn đoán.

TRIẾT LÝ FIX (giống bulkhead D-152 · keep-latest K-014): **giới hạn tường minh + suy giảm có kiểm soát**, KHÔNG
im lặng bỏ. Trong 1 cửa sổ chỉ log 1 lần, và lần log đó **BÁO SỐ LẦN đã nén** ⇒ operator vẫn thấy được cường độ.

THUẦN: chỉ số học + `now_ns` TIÊM (không gọi clock, không I/O) → test xác định, không sleep, không flaky.
Tầng `runtime` (stdlib) — caller (profiles) tự lo việc in.
"""
from __future__ import annotations

import threading
from typing import Optional


class LogThrottle:
    """Cho phép log tối đa 1 lần mỗi `min_interval_ns`; các lần bị nén được ĐẾM và báo ở lần log kế.

    `tick(now_ns)` → `0` = log ngay (không có gì bị nén) · `n>0` = log ngay + `n` lần trước đã bị nén ·
    `None` = ĐANG trong cửa sổ, KHÔNG log.
    """

    def __init__(self, min_interval_ns: int) -> None:
        if min_interval_ns <= 0:
            raise ValueError(f"min_interval_ns phải > 0, nhận {min_interval_ns}")
        self._interval = int(min_interval_ns)
        self._last_ns: Optional[int] = None
        self._suppressed = 0
        self._lock = threading.Lock()      # waitress đa thread → nhiều request có thể tick đồng thời

    def tick(self, now_ns: int) -> Optional[int]:
        with self._lock:
            if self._last_ns is None:
                self._last_ns = now_ns
                return 0
            elapsed = now_ns - self._last_ns
            # `elapsed < 0` = đồng hồ lùi (hiếm với monotonic, nhưng KHÔNG được biến thành log-flood) → coi như
            # vẫn trong cửa sổ; mốc `_last_ns` giữ nguyên để cửa sổ tự hết theo thời gian tiến.
            if 0 <= elapsed < self._interval or elapsed < 0:
                self._suppressed += 1
                return None
            n = self._suppressed
            self._suppressed = 0
            self._last_ns = now_ns
            return n
