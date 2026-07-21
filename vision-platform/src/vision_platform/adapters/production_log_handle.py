"""adapters/production_log_handle.py — log sink PRODUCTION: non-blocking + rotating + flush-on-shutdown.

Layer: adapters (LEAF — chạm I/O file + threading). Đóng 3 thứ `08-observability`/K-018 CỐ Ý hoãn cho bản học
(xem `runtime/observability.py` docstring): (1) **non-blocking** hot-path (BoundedQueueHandler → drop+đếm khi
đầy, KHÔNG chặn thread pipeline — đúng hợp đồng `IPipelineObserver`); (2) **RotatingFileHandler** xoay theo size
(chống đầy đĩa khi chạy 24/7); (3) **flush-on-shutdown** (`shutdown()` drain queue + flush + close — không mất
log cuối lúc cascade shutdown).

Triết lý backpressure của repo (BoundedQueue DROP_OLDEST, K-016): queue log CÓ GIỚI HẠN + drop + đếm (bounded
memory) thay vì unbounded (rủi ro OOM khi burst kéo dài). Consumer (QueueListener thread) ghi file; producer
(hot-path) chỉ enqueue non-blocking.

Dùng: `handle = ProductionLogHandle(path).start()` → `handle.emit(json_line)` (non-blocking) → `handle.shutdown()`
lúc teardown. Observer (runtime) gọi `emit` qua DI (runtime KHÔNG import adapter — contract #3).
"""
from __future__ import annotations

import logging
import logging.handlers
import queue as _queue


class _DropCountingQueueHandler(logging.handlers.QueueHandler):
    """QueueHandler non-blocking: queue đầy → DROP record (mới) + đếm, KHÔNG chặn producer (hot-path)."""

    def __init__(self, q: "_queue.Queue") -> None:
        super().__init__(q)
        self.dropped = 0

    def enqueue(self, record) -> None:
        try:
            self.queue.put_nowait(record)   # non-blocking; đầy → Full (KHÔNG block hot-path)
        except _queue.Full:
            self.dropped += 1               # drop-newest + đếm (quan-sát-được, không im lặng)


class ProductionLogHandle:
    """Sink log non-blocking + rotating + flush-on-shutdown. `emit(str)` an toàn gọi từ hot-path."""

    def __init__(self, path: str, *, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5,
                 capacity: int = 10000, logger_name: str = "vp.production") -> None:
        if max_bytes <= 0:
            raise ValueError(f"max_bytes phải > 0, got {max_bytes}")
        if backup_count < 0:
            raise ValueError(f"backup_count phải >= 0, got {backup_count}")
        if capacity <= 0:
            raise ValueError(f"capacity phải > 0, got {capacity}")
        self._path = path
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._capacity = capacity
        self._logger_name = logger_name
        self._queue: "_queue.Queue | None" = None
        self._listener: "logging.handlers.QueueListener | None" = None
        self._file_handler: "logging.handlers.RotatingFileHandler | None" = None
        self._queue_handler: "_DropCountingQueueHandler | None" = None
        self._logger: "logging.Logger | None" = None

    def start(self) -> "ProductionLogHandle":
        """Dựng chuỗi: producer→[QueueHandler bounded]→queue→[QueueListener thread]→RotatingFileHandler(file)."""
        self._queue = _queue.Queue(maxsize=self._capacity)   # BOUNDED → chống OOM
        self._file_handler = logging.handlers.RotatingFileHandler(
            self._path, maxBytes=self._max_bytes, backupCount=self._backup_count, encoding="utf-8")
        self._file_handler.setFormatter(logging.Formatter("%(message)s"))  # message = JSON line observer đã dựng
        # QueueListener chạy thread NỀN: rút record khỏi queue → ghi file (I/O nặng KHÔNG ở hot-path).
        self._listener = logging.handlers.QueueListener(self._queue, self._file_handler)
        self._queue_handler = _DropCountingQueueHandler(self._queue)
        self._logger = logging.getLogger(self._logger_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False                       # không lan ra root (tránh in kép/không mong muốn)
        self._logger.handlers = [self._queue_handler]         # thay (không cộng dồn khi start lại)
        self._listener.start()
        return self

    def emit(self, message: str) -> None:
        """Enqueue 1 dòng log (NON-BLOCKING). Queue đầy → drop + đếm (xem `dropped`)."""
        if self._logger is None:
            raise RuntimeError("ProductionLogHandle.start() phải gọi trước emit()")
        self._logger.info(message)

    @property
    def dropped(self) -> int:
        """Số record bị drop do queue đầy (backpressure log — quan-sát-được)."""
        return self._queue_handler.dropped if self._queue_handler is not None else 0

    def shutdown(self) -> None:
        """Dừng SẠCH (idempotent): drain queue còn lại + flush + close file → KHÔNG mất log cuối."""
        if self._listener is None:
            return
        self._listener.stop()          # enqueue sentinel + chờ thread xử lý HẾT record còn lại (flush)
        if self._file_handler is not None:
            self._file_handler.flush()
            self._file_handler.close()
        if self._logger is not None:
            self._logger.handlers = []
        self._listener = None
        self._file_handler = None
        self._queue = None
