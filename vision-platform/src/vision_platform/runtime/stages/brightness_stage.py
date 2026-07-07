"""BrightnessStage: tính brightness trung bình, ghi vào artifact."""
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.runtime.base_stage import BaseStage


class BrightnessStage(BaseStage):
    """Tính frame.mean() → packet.artifacts['brightness']."""

    def __init__(self):
        super().__init__("brightness")

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        frame = packet.media_ref.array
        brightness = float(frame.mean())
        return packet.with_artifact("brightness", brightness)
