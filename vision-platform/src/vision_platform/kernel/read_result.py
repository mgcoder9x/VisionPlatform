"""ReadResult — explicit-status return từ IDataSource.read()."""
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Optional, TypeVar


class ReadStatus(Enum):
    FRAME = "frame"
    EOF = "eof"
    TIMEOUT = "timeout"
    RECONNECTING = "reconnecting"
    DROPPED = "dropped"
    ERROR = "error"


T = TypeVar("T")


@dataclass(frozen=True)
class ReadResult(Generic[T]):
    """Explicit status. Caller MUST handle each status."""
    status: ReadStatus
    data: Optional[T] = None
    error: Optional[Exception] = None
    retry_after_ms: Optional[int] = None

    @property
    def has_data(self) -> bool:
        return self.status == ReadStatus.FRAME and self.data is not None
