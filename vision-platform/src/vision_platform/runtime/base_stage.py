"""BaseStage - common scaffolding cho stage implementation."""
import traceback
from abc import ABC, abstractmethod
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.stage_contract import StageResult, SkipFrameSignal


class BaseStage(ABC):
    """Scaffold: tự handle SkipFrameSignal + Exception thành StageResult."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def setup(self) -> None: ...

    def teardown(self) -> None: ...

    def process(self, packet: MediaPacket) -> StageResult:
        try:
            result_packet = self._do_process(packet)
            # R6 (ERRATA E-16): fail-fast nếu lớp con trả sai kiểu (None / ndarray / ...)
            # → biến thành ERROR result ngay tại stage, không để lọt xuống downstream xa.
            if not isinstance(result_packet, MediaPacket):
                raise TypeError(
                    f"_do_process must return MediaPacket, got "
                    f"{type(result_packet).__name__}"
                )
            return StageResult.success(result_packet, stage=self._name)
        except SkipFrameSignal as e:
            return StageResult.skipped(reason=str(e), stage=self._name)
        except Exception as e:
            # R1 (ERRATA E-16): giữ traceback DẠNG CHUỖI (format_exc) cho debug —
            # chuỗi KHÔNG giữ tham chiếu frame/biến local → không rò RAM.
            return StageResult.error(
                error=e, stage=self._name, traceback_str=traceback.format_exc()
            )

    @abstractmethod
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        """Subclass implement. Return new MediaPacket (CoW). Raise to skip/error."""
        ...
