"""StageResult + StageStatus + base stage contract."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol
from vision_platform.kernel.media_packet import MediaPacket


class StageStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StageResult:
    """Outcome of stage processing 1 packet."""
    status: StageStatus
    packet: Optional[MediaPacket] = None
    skip_reason: Optional[str] = None
    error_type: Optional[str] = None        # type name only — no Exception ref
    error_message: Optional[str] = None     # str(exc) — no traceback ref
    error_traceback: Optional[str] = None   # format_exc() STRING — debug info, KHONG giu frame (E-16)
    stage: str = ""

    @classmethod
    def success(cls, packet: MediaPacket, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SUCCESS, packet=packet, stage=stage)

    @classmethod
    def skipped(cls, reason: str, stage: str = "") -> "StageResult":
        return cls(status=StageStatus.SKIPPED, skip_reason=reason, stage=stage)

    @classmethod
    def error(cls, error: Exception, stage: str = "",
              traceback_str: Optional[str] = None) -> "StageResult":
        """Build ERROR result without retaining exception reference (no traceback frames).

        `traceback_str` = traceback.format_exc() (CHUỖI thuần — giữ thông tin debug nhưng
        KHÔNG giữ tham chiếu frame/biến local → không rò RAM). Xem ERRATA E-16.
        """
        return cls(
            status=StageStatus.ERROR,
            error_type=type(error).__qualname__,
            error_message=str(error),
            error_traceback=traceback_str,
            stage=stage,
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome của TOÀN BỘ pipeline cho 1 packet (executor trả về cái này).

    Giữ ĐẦY ĐỦ trạng thái — KHÔNG bóp về Optional:
        - SUCCESS   → packet chạy hết chuỗi, `packet` là kết quả cuối.
        - SKIPPED   → 1 stage skip (filter chặn), `failed_stage` + `reason`.
        - ERROR     → 1 stage lỗi, `failed_stage` + error_type/message.
        - CANCELLED → pipeline bị huỷ giữa chừng.

    Vì sao result-object thay `Optional[MediaPacket]`? `None` không phân biệt "filter cố ý bỏ
    frame" (bình thường) với "stage lỗi" (cần alert). Result-object giữ status rõ ràng.
    """
    status: StageStatus
    packet: Optional[MediaPacket] = None
    failed_stage: str = ""
    reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    @property
    def is_processed(self) -> bool:
        return self.status == StageStatus.SUCCESS

    @classmethod
    def processed(cls, packet: MediaPacket) -> "ExecutionResult":
        return cls(status=StageStatus.SUCCESS, packet=packet)

    @classmethod
    def from_stage_result(cls, result: "StageResult") -> "ExecutionResult":
        """Map kết quả non-SUCCESS của 1 stage thành ExecutionResult của pipeline."""
        return cls(
            status=result.status,
            failed_stage=result.stage,
            reason=result.skip_reason,
            error_type=result.error_type,
            error_message=result.error_message,
            error_traceback=result.error_traceback,
        )


class SkipFrameSignal(Exception):
    """Stage raises this to skip frame intentionally (motion gate, ROI filter)."""
    pass


class IStage(Protocol):
    """Sync stage. Process 1 packet → 1 packet (or skip/error)."""
    @property
    def name(self) -> str: ...

    def process(self, packet: MediaPacket) -> StageResult: ...

    def setup(self) -> None: ...

    def teardown(self) -> None: ...
