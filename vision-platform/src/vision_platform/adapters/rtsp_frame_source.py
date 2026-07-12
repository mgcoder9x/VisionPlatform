"""RtspFrameSource — nguồn frame từ camera RTSP (sub-spec real-detector, IFrameSource adapter). Layer: adapters.

Leaf: import kernel(ReadResult/ReadStatus) + numpy + cv2 (lazy). KHÔNG runtime/application/profiles.

BẢN CHẤT (vì sao thiết kế thế này): luồng RTSP KHÔNG ổn định — camera/mạng RỚT là chuyện thường (Wi-Fi,
switch, camera reboot). Nguồn NGÂY THƠ (mở 1 lần, đọc mãi) sẽ CHẾT khi rớt. Adapter này TỰ KẾT NỐI LẠI
(self-heal): read() gặp cap chưa mở/đọc lỗi → trả `ReadStatus.RECONNECTING` (KHÔNG raise, KHÔNG None) + thử
mở lại lần sau. Caller (camera_worker) coi RECONNECTING = bỏ frame + thử lại → hệ không chết vì camera chớp tắt.

DI (chống phụ thuộc + TEST được KHÔNG cần camera thật): `capture_factory(url) -> VideoCaptureLike` tiêm ngoài.
Mặc định = `cv2.VideoCapture` (lazy import). Test tiêm capture GIẢ để kiểm logic reconnect deterministic.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol

import numpy as np

from vision_platform.kernel.read_result import ReadResult, ReadStatus


class VideoCaptureLike(Protocol):
    """Giao diện tối thiểu của cv2.VideoCapture mà adapter dùng (để tiêm bản giả khi test)."""
    def isOpened(self) -> bool: ...
    def read(self): ...            # -> tuple[bool, np.ndarray | None]
    def release(self) -> None: ...


def mask_rtsp(url: str) -> str:
    """Che mật khẩu trong URL rtsp://user:PASS@host → rtsp://user:***@host (KHÔNG lộ secret ra log)."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user = creds.split(":", 1)[0]
        creds = f"{user}:***"
    return f"{scheme}://{creds}@{host}"


def _default_cv2_capture(url: str):
    """Factory mặc định: cv2.VideoCapture với timeout mở/đọc (tránh treo vô hạn khi host không tới được)."""
    import cv2

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    # Timeout mở + đọc (ms) — chống treo khi camera/mạng không phản hồi.
    with_open = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
    with_read = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if with_open is not None:
        cap.set(with_open, 5000)
    if with_read is not None:
        cap.set(with_read, 5000)
    # Buffer nhỏ nhất → giảm ĐỘ TRỄ dồn (đọc frame mới, không chồng hàng đợi khi xử lý chậm).
    bufsize = getattr(cv2, "CAP_PROP_BUFFERSIZE", None)
    if bufsize is not None:
        cap.set(bufsize, 1)
    return cap


class RtspFrameSource:
    """IFrameSource cho camera RTSP, tự kết nối lại. Stream vô hạn (is_finite=False)."""

    def __init__(
        self,
        url: str,
        *,
        capture_factory: Optional[Callable[[str], VideoCaptureLike]] = None,
        source_id: Optional[str] = None,
        reconnect_delay_ms: int = 500,
        max_reconnect: Optional[int] = None,   # None = thử lại vô hạn (stream production)
    ):
        self._url = url
        self._factory = capture_factory or _default_cv2_capture
        self._source_id = source_id or f"rtsp:{mask_rtsp(url)}"
        self._reconnect_delay_ms = reconnect_delay_ms
        self._max_reconnect = max_reconnect
        self._cap: Optional[VideoCaptureLike] = None
        self._reconnects = 0
        self._is_setup = False

    def _release_cap(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    def _open(self) -> bool:
        """Mở capture mới. Trả True nếu isOpened()."""
        self._release_cap()
        cap = self._factory(self._url)
        if cap is not None and cap.isOpened():
            self._cap = cap
            return True
        # mở hỏng → dọn
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        return False

    def setup(self) -> None:
        self._is_setup = True
        self._reconnects = 0
        self._open()          # mở lần đầu; hỏng cũng không sao — read() sẽ tự thử lại

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() phải gọi trước read()")
        # Chưa có kết nối sống → thử mở lại (self-heal). Phân biệt CÒN-hạn vs VƯỢT-hạn:
        if self._cap is None or not self._cap.isOpened():
            if self._max_reconnect is not None and self._reconnects >= self._max_reconnect:
                # Vượt ngân sách reconnect → BÁO LỖI (caller quyết định dừng/cảnh báo), không thử vô ích.
                return ReadResult(
                    status=ReadStatus.ERROR,
                    error=RuntimeError(f"RTSP mở lại thất bại, vượt max_reconnect ({self._max_reconnect})"),
                )
            self._reconnects += 1
            self._open()          # có thể vẫn hỏng → lần read sau thử tiếp (còn trong hạn)
            return ReadResult(status=ReadStatus.RECONNECTING, retry_after_ms=self._reconnect_delay_ms)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._release_cap()      # rớt giữa chừng → ép mở lại lần đọc sau (self-heal)
            return ReadResult(status=ReadStatus.RECONNECTING, retry_after_ms=self._reconnect_delay_ms)
        # D.3 (review #319): đọc THÀNH CÔNG → reset đếm rớt. `max_reconnect` = số lần rớt LIÊN TIẾP
        # (self-heal thật), KHÔNG phải ngân sách trọn-đời → camera chớp-tắt lai rai không bị ERROR oan.
        self._reconnects = 0
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._release_cap()
        self._is_setup = False

    def __enter__(self) -> "RtspFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False

    @property
    def is_finite(self) -> bool:
        return False            # RTSP là stream vô hạn

    @property
    def source_id(self) -> str:
        return self._source_id
