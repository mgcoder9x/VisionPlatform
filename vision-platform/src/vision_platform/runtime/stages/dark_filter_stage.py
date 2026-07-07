"""DarkFilterStage: skip frame nếu brightness < threshold."""
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.stage_contract import SkipFrameSignal
from vision_platform.runtime.base_stage import BaseStage


class DarkFilterStage(BaseStage):
    """Skip frame nếu artifact 'brightness' < threshold.

    Yêu cầu: BrightnessStage phải chạy TRƯỚC stage này.
    """

    def __init__(self, threshold: float):
        super().__init__("dark_filter")
        self._threshold = threshold

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        brightness = packet.artifacts.get("brightness")
        if brightness is None:
            raise ValueError(
                "DarkFilterStage requires 'brightness' artifact. "
                "Did you forget to add BrightnessStage before this?"
            )
        if brightness < self._threshold:
            raise SkipFrameSignal(f"too_dark (brightness={brightness:.2f})")
        return packet
