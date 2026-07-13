"""VideoFileFrameSource — đọc frame từ FILE video (IFrameSource adapter). Layer: adapters (leaf).

Khác `RtspFrameSource`: file là nguồn HỮU HẠN + ổn định → KHÔNG tự-reconnect. Thay vào đó:
- thiếu/không mở được file = LỖI CẤU HÌNH → fail-fast ở setup() (không im lặng retry như stream).
- đọc hết file → `ReadStatus.EOF` (is_finite=True). `loop=True` → tua về đầu, chạy lại (demo/test bền).

DI `capture_factory` (mặc định cv2.VideoCapture) → unit-test bằng capture GIẢ, KHÔNG cần file/codec thật.
Dùng để chạy detect trên video quay sẵn (validate model) khi chưa có camera live.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from vision_platform.kernel.read_result import ReadResult, ReadStatus
from vision_platform.adapters.rtsp_frame_source import VideoCaptureLike


def _default_cv2_capture(path: str):
    import cv2

    return cv2.VideoCapture(path)


class VideoFileFrameSource:
    """IFrameSource đọc file video. is_finite=True (trừ khi loop). EOF khi hết frame."""

    def __init__(
        self,
        path: str,
        *,
        capture_factory: Optional[Callable[[str], VideoCaptureLike]] = None,
        source_id: Optional[str] = None,
        loop: bool = False,
    ):
        self._path = path
        self._factory = capture_factory or _default_cv2_capture
        self._source_id = source_id or f"videofile:{path}"
        self._loop = loop
        self._cap: Optional[VideoCaptureLike] = None
        self._is_setup = False
        # V1 (#349): loop=True nhưng video RỖNG/không-seek-được → 1 chu kỳ loop (seek→read) KHÔNG ra frame nào
        # = KHÔNG loop được → THỰC CHẤT finite. Cờ này khiến is_finite→True → runner BREAK trên EOF (thay vì
        # `continue` mãi = LIVELOCK peg CPU + treo _run_from_config tuần tự). Chỉ set khi loop CHỨNG MINH thất bại.
        self._loop_failed = False

    def setup(self) -> None:
        cap = self._factory(self._path)
        if cap is None or not cap.isOpened():
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            # File là cấu hình → thiếu/hỏng = LỖI, fail-fast (khác stream retry).
            raise RuntimeError(f"Không mở được file video: {self._path}")
        self._cap = cap
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup or self._cap is None:
            raise RuntimeError("setup() phải gọi trước read()")
        ok, frame = self._cap.read()
        if ok and frame is not None:
            return ReadResult(status=ReadStatus.FRAME, data=frame)
        # Hết frame:
        if self._loop:
            self._seek_start()
            ok, frame = self._cap.read()
            if ok and frame is not None:
                return ReadResult(status=ReadStatus.FRAME, data=frame)
            # 1 chu kỳ loop (seek→read) KHÔNG ra frame → video bất-khả-loop (rỗng/không-seek-được) →
            # đánh dấu finite để runner BREAK trên EOF (chống LIVELOCK — V1/#349). Video hợp lệ KHÔNG bao giờ
            # tới đây (reread-sau-seek ra frame → return FRAME ở trên).
            self._loop_failed = True
        return ReadResult(status=ReadStatus.EOF)

    def _seek_start(self) -> None:
        # cv2.CAP_PROP_POS_FRAMES = 1; tua về frame 0. Bọc try để capture giả (không có set) vẫn chạy.
        try:
            self._cap.set(1, 0)   # type: ignore[attr-defined]
        except Exception:
            pass

    def teardown(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None
        self._is_setup = False

    def __enter__(self) -> "VideoFileFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False

    @property
    def is_finite(self) -> bool:
        # loop=True → non-finite; NHƯNG nếu loop CHỨNG MINH thất bại (video bất-khả-loop) → finite (chống LIVELOCK, V1/#349).
        return (not self._loop) or self._loop_failed

    @property
    def source_id(self) -> str:
        return self._source_id
