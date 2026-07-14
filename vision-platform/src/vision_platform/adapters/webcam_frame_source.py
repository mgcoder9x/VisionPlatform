"""WebcamFrameSource — nguồn frame từ webcam USB/tích-hợp (cv2.VideoCapture theo INDEX). Layer: adapters (leaf).

Leaf: import kernel(ReadResult/ReadStatus) + numpy + cv2 (lazy). KHÔNG runtime/application/profiles.

Khác `RtspFrameSource` (URL + timeout mạng + reconnect nhiều): webcam là thiết bị CỤC BỘ theo index (0,1,...),
thường ổn định. Vẫn self-heal nhẹ (read lỗi → RECONNECTING + thử mở lại) để không chết khi thiết bị chớp.
DI `capture_factory(index) -> VideoCaptureLike` (mặc định `cv2.VideoCapture`) → TEST được không cần webcam thật.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from vision_platform.kernel.read_result import ReadResult, ReadStatus
from vision_platform.adapters.rtsp_frame_source import VideoCaptureLike


def _default_cv2_capture(index: int) -> VideoCaptureLike:
    import cv2
    return cv2.VideoCapture(index)


class WebcamFrameSource:
    """IFrameSource cho webcam cục bộ theo index. Stream vô hạn (is_finite=False)."""

    def __init__(
        self,
        index: int = 0,
        *,
        capture_factory: Optional[Callable[[int], VideoCaptureLike]] = None,
        source_id: Optional[str] = None,
        reconnect_delay_ms: int = 500,
    ):
        self._index = index
        self._factory = capture_factory or _default_cv2_capture
        self._source_id = source_id or f"webcam:{index}"
        self._reconnect_delay_ms = reconnect_delay_ms
        self._cap: Optional[VideoCaptureLike] = None
        self._is_setup = False

    def _release_cap(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    def _open(self) -> bool:
        self._release_cap()
        cap = self._factory(self._index)
        if cap is not None and cap.isOpened():
            self._cap = cap
            return True
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        return False

    def setup(self) -> None:
        self._is_setup = True
        self._open()      # mở lần đầu; hỏng cũng không sao — read() tự thử lại

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() phải gọi trước read()")
        if self._cap is None or not self._cap.isOpened():
            self._open()
            return ReadResult(status=ReadStatus.RECONNECTING, retry_after_ms=self._reconnect_delay_ms)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._release_cap()   # đọc lỗi → ép mở lại lần sau (self-heal)
            return ReadResult(status=ReadStatus.RECONNECTING, retry_after_ms=self._reconnect_delay_ms)
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._release_cap()
        self._is_setup = False

    def __enter__(self) -> "WebcamFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False

    @property
    def is_finite(self) -> bool:
        return False

    @property
    def source_id(self) -> str:
        return self._source_id
