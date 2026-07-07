"""Adapter: generate frames giả - cho test và dev offline."""
import itertools
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from vision_platform.kernel.read_result import ReadResult, ReadStatus

# Bộ đếm để source_id mặc định DUY NHẤT trong 1 process (ERRATA E-13, Risk 3).
# Port contract yêu cầu source_id unique; default cố định sẽ trùng khi tạo nhiều instance.
_fake_source_counter = itertools.count()


@dataclass
class FakeFrameSource:
    """In-memory frame generator. Implements IFrameSource."""
    width: int = 640
    height: int = 480
    max_frames: Optional[int] = 100
    inject_error_at: Optional[int] = None
    _source_id: str = field(default_factory=lambda: f"fake_{next(_fake_source_counter)}")
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)

    def setup(self) -> None:
        self._frame_count = 0
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")

        if self.inject_error_at is not None and self._frame_count == self.inject_error_at:
            self.inject_error_at = None
            return ReadResult(
                status=ReadStatus.ERROR,
                error=RuntimeError("Injected fake error"),
                retry_after_ms=100,
            )

        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)

        frame = np.full(
            (self.height, self.width, 3),
            fill_value=self._frame_count % 256,
            dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._is_setup = False

    def __enter__(self) -> "FakeFrameSource":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False  # KHÔNG nuốt exception của thân `with`

    @property
    def is_finite(self) -> bool:
        return self.max_frames is not None

    @property
    def source_id(self) -> str:
        return self._source_id
