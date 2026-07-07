"""DetectStage — Stage-hoá 1 IDetector (đóng một phần Gap-2 K-037). Layer: runtime/stages.

Bọc bất kỳ detector (port IDetector, DI) → chạy detect trên frame → ghi artifacts["detections"].
STATELESS (không giữ state xuyên-frame). setup/teardown ủy quyền detector (nạp/giải phóng model).
KHÔNG lọc confidence ở đây (SRP) — lọc là việc detector/FilterStage. DetectStage chỉ truyền thẳng.
"""
from vision_platform.kernel.media_packet import MediaPacket
from vision_platform.kernel.ports.detector import IDetector
from vision_platform.runtime.base_stage import BaseStage


class DetectStage(BaseStage):
    def __init__(self, detector: IDetector):
        super().__init__("detect")
        self._detector = detector

    def setup(self) -> None:
        self._detector.setup()

    def teardown(self) -> None:
        self._detector.teardown()

    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        dets = self._detector.detect(packet.media_ref.array)
        return packet.with_artifact("detections", tuple(dets))
