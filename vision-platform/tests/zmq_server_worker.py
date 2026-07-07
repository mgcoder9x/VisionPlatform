"""Worker module-level cho test zmq-inference (spawn Windows cần picklable + không re-import test file).

`inference_server_worker` chạy TRONG process con: attach control-plane (create=False) + make_pool_opener
(lock thừa kế qua spawn) + ReaderEpochCoordinator (switchover-aware) + InferenceServer.serve(shutdown_event).
"""
from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import make_pool_opener
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator
from vision_platform.application.inference_server import InferenceServer
from vision_platform.adapters.fake_detector import FakeDetector


class CrashDetector:
    """Detector luôn ném (test bulkhead Property 4): 1 request lỗi KHÔNG làm chết server."""
    def setup(self) -> None: ...
    def teardown(self) -> None: ...
    def detect(self, frame):
        raise ValueError("boom detector")


def inference_server_worker(shutdown_event, endpoint, cp_name, locks_map, n_slots, h, w, c, detector_kind="fake"):
    cp = RingControlPlane(cp_name, create=False)
    opener = make_pool_opener(locks_map, n_slots, h, w, c)
    coord = ReaderEpochCoordinator(cp, opener)
    detector = CrashDetector() if detector_kind == "crash" else FakeDetector()
    server = InferenceServer(coord, detector, endpoint)
    server.serve(shutdown_event)
