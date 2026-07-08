"""PushFrameSource — nguồn phát frame theo NHỊP CỐ ĐỊNH (spec backpressure-cross-process, task 2.2).

Layer: adapters (LEAF). Chỉ import kernel (ReadResult/ReadStatus) + numpy — hợp lệ contract
"Adapters la leaf".

Mục đích (R7.1, R7.2): mô phỏng camera thật đẩy frame theo nhịp ĐỘC LẬP với tốc độ tiêu thụ
của consumer. Khi consumer chậm hơn nhịp phát → hàng đợi outbound quá tải → kích hoạt backpressure
(DROP_OLDEST). Bám interface `setup()/read(timeout_ms)->ReadResult/teardown()` như NoiseFrameSource.

Nhịp phát:
- `interval_s == 0.0` → phát ngay mỗi lần `read()` (không TIMEOUT), tới khi đủ `max_frames`.
- `interval_s > 0.0` → chỉ phát khi đồng hồ đã tới hạn; chưa tới → trả `ReadStatus.TIMEOUT`
  (nhịp KHÔNG phụ thuộc tốc độ gọi `read()`).

Frame DETERMINISTIC: mọi pixel = (chỉ số frame mod 256) → test kiểm được frame value tăng dần
+ kiểm recency (frame mới nhất là frame còn lại sau DROP_OLDEST).

`time_fn` tiêm được (mặc định `time.monotonic`) để test mô phỏng đồng hồ, không cần sleep thật
→ test xác định, không flaky.
"""
import time
from typing import Callable, Optional

import numpy as np

from vision_platform.kernel.read_result import ReadResult, ReadStatus


class PushFrameSource:
    def __init__(
        self,
        *,
        width: int = 320,
        height: int = 240,
        max_frames: int = 50,
        interval_s: float = 0.0,
        seed: Optional[int] = None,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.width = width
        self.height = height
        self.max_frames = max_frames
        self.interval_s = interval_s
        self.seed = seed  # giữ tương thích chữ ký; frame deterministic không cần rng
        self._time_fn = time_fn
        self._frame_count = 0
        self._next_emit = 0.0
        self._is_setup = False

    def setup(self) -> None:
        self._frame_count = 0
        # Frame đầu phát NGAY tại thời điểm setup; các frame sau giãn theo interval_s.
        self._next_emit = self._time_fn()
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")

        if self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)

        if self.interval_s > 0.0:
            now = self._time_fn()
            if now < self._next_emit:
                # Chưa tới nhịp → TIMEOUT (không có frame lần này), nhịp độc lập tốc độ gọi.
                return ReadResult(status=ReadStatus.TIMEOUT)
            # Tới hạn: dời mốc phát kế tiếp theo nhịp cố định (không theo `now` để không trôi).
            self._next_emit += self.interval_s

        value = self._frame_count % 256
        frame = np.full((self.height, self.width, 3), value, dtype=np.uint8)
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._is_setup = False

    def __enter__(self) -> "PushFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False

    @property
    def is_finite(self) -> bool:
        return True
