"""Adapter: generate random noise frames - alternative test source."""
import itertools
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from vision_platform.kernel.read_result import ReadResult, ReadStatus

# source_id mặc định DUY NHẤT trong 1 process (ERRATA E-13, Risk 3).
_noise_source_counter = itertools.count()


@dataclass
class NoiseFrameSource:
    """Random noise generator. Useful cho test detector against random input."""
    width: int = 320
    height: int = 240
    max_frames: Optional[int] = 50
    seed: Optional[int] = 42
    _source_id: str = field(default_factory=lambda: f"noise_{next(_noise_source_counter)}")
    _rng: np.random.Generator = field(default=None, init=False)
    _frame_count: int = field(default=0, init=False)
    _is_setup: bool = field(default=False, init=False)

    def setup(self) -> None:
        self._frame_count = 0
        self._rng = np.random.default_rng(self.seed)
        self._is_setup = True

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]:
        if not self._is_setup:
            raise RuntimeError("setup() must be called before read()")

        if self.max_frames is not None and self._frame_count >= self.max_frames:
            return ReadResult(status=ReadStatus.EOF)

        frame = self._rng.integers(
            0, 256, size=(self.height, self.width, 3), dtype=np.uint8,
        )
        self._frame_count += 1
        return ReadResult(status=ReadStatus.FRAME, data=frame)

    def teardown(self) -> None:
        self._is_setup = False
        self._rng = None

    def __enter__(self) -> "NoiseFrameSource":
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
