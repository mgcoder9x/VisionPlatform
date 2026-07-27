"""stream_admission — BULKHEAD cho kết nối streaming dài (MJPEG `/stream`, SSE `/events`).

VẤN ĐỀ (ĐO THẬT, LOG #456 · `tools/web_sse_capacity_probe.py`, waitress `--threads 8`):
WSGI **sync** cấp **1 thread cho mỗi kết nối**, và 2 endpoint streaming KHÔNG bao giờ kết thúc
(`_mjpeg()` + `_sse_overlay_stream()` là vòng lặp vô hạn) ⇒ mở đủ 8 kết nối dài là **MỌI request ngắn
treo VÔ HẠN** (`/stats` timeout 4s; cả trang `/` của viewer mới). Trần viewer = threads / (kết nối dài mỗi
viewer) → 8 viewer trước SSE, **4 viewer** sau SSE (mỗi viewer giữ `/stream` + `/events`).

FIX GỐC (không phải "tăng threads" — cái đó chỉ dịch bức tường): **giới hạn tường minh + suy giảm có kiểm soát**
— cùng triết lý bulkhead io-thread ZMQ (D-091) và keep-latest drop (K-014):
  - Trần `max_streams` = `capacity_from_threads(threads, reserve)` → **CHỪA `reserve` thread** cho request ngắn
    ⇒ `/stats`, `/overlay`, `/` KHÔNG bao giờ bị starve (Property P8).
  - Vượt trần → caller trả **HTTP 503 + Retry-After NGAY** (P9), client rơi về `poll()` / retry ảnh — thay vì
    treo âm thầm (failure mode tệ nhất: client không có tín hiệu nào để phản ứng).

THUẦN: chỉ đếm + `threading.Lock` (stdlib). Tầng `runtime` (không import adapter/framework) → test xác định
không cần server. Web framework chỉ gọi `try_acquire()/release()`.
"""
from __future__ import annotations

import threading


def capacity_from_threads(threads: int, reserve: int = 2) -> int:
    """Trần kết nối streaming suy ra từ thread-pool WSGI, CHỪA `reserve` thread cho request NGẮN.

    `max(1, ...)`: pool bé hơn reserve thì vẫn cho 1 stream — thà video chậm còn hơn KHÔNG phục vụ được.
    Fail-fast tham số vô nghĩa (giống kỷ luật fail-fast của kernel config).
    """
    if threads < 1:
        raise ValueError(f"threads phải >= 1, nhận {threads}")
    if reserve < 0:
        raise ValueError(f"reserve phải >= 0, nhận {reserve}")
    return max(1, threads - reserve)


class StreamAdmission:
    """Bộ đếm có khoá giới hạn số kết nối streaming ĐỒNG THỜI (bulkhead).

    Bất biến: `0 <= active <= max_streams` ở mọi thời điểm, kể cả khi nhiều thread waitress đua nhau.
    """

    def __init__(self, max_streams: int) -> None:
        if max_streams < 1:
            raise ValueError(f"max_streams phải >= 1, nhận {max_streams}")
        self._max = int(max_streams)
        self._active = 0
        self._lock = threading.Lock()

    @property
    def max_streams(self) -> int:
        return self._max

    @property
    def active(self) -> int:
        with self._lock:
            return self._active

    def try_acquire(self) -> bool:
        """Xin 1 slot. False = ĐÃ đủ trần → caller PHẢI từ chối nhanh (503), KHÔNG được stream tiếp."""
        with self._lock:
            if self._active >= self._max:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        """Trả slot (gọi trong `finally` của generator). Clamp tại 0: double-release do đường lỗi KHÔNG được
        làm `active` âm — âm sẽ NỚI trần âm thầm (tệ hơn cả defect gốc)."""
        with self._lock:
            if self._active > 0:
                self._active -= 1
