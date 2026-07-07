"""IFrameSource — driven port cho nguồn cung cấp frame."""
from typing import Protocol
import numpy as np
from vision_platform.kernel.read_result import ReadResult


class IFrameSource(Protocol):
    """Inbound source of frames (np.ndarray).

    Contract:
        - setup() MUST be called before first read(). Idempotent.
        - read(timeout_ms) returns ReadResult — KHÔNG return None.
        - teardown() releases resources. Idempotent.
        - is_finite True for batch (file ends → EOF), False for stream.
        - source_id unique cho logging/metrics.
        - Context manager: `with source as s:` → setup() lúc vào, teardown() lúc ra
          (kể cả khi raise). `__exit__` trả False (KHÔNG nuốt exception). (R2#04 / ERRATA E-16)
    """
    def setup(self) -> None: ...

    def read(self, timeout_ms: int = 100) -> ReadResult[np.ndarray]: ...

    def teardown(self) -> None: ...

    def __enter__(self) -> "IFrameSource": ...

    def __exit__(self, exc_type, exc, tb) -> bool: ...

    @property
    def is_finite(self) -> bool: ...

    @property
    def source_id(self) -> str: ...
