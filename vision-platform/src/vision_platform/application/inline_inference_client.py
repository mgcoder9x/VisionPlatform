"""InlineInferenceClient — inference cùng process (no IPC), dùng cho dev/test.

Layer: application (F-1). KHÔNG đặt ở adapters/ vì client import runtime.ipc.ShmFrameReader,
mà contract import-linter cấm adapters→runtime. Bản chất: client là SERVICE ĐIỀU PHỐI
(ghép runtime SHM reader + IDetector *port* tiêm DI), không phải leaf-adapter → thuộc application/
(cùng chỗ ring_supervisor / *_epoch_coordinator). Layering domain←kernel←runtime←application
cho phép application→runtime; contract #4 chỉ cấm application→adapters/profiles.

Production Vision Platform dùng AsyncInferenceClient qua ZMQ ROUTER/DEALER (sub-spec riêng, hoãn).
Pattern GIỮ NGUYÊN: request_id correlation + InferenceResponse echo request_id. Chỉ khác transport.

TÍCH HỢP SWITCHOVER (F-2): dùng reader.read_ref(request.frame_ref) → tự kiểm ring_epoch (P0-3).
Ref epoch cũ sau switchover → read trả None → trả InferenceError (không đọc nhầm frame ring mới).
"""
from vision_platform.kernel.inference_protocol import (
    InferenceRequest,
    InferenceResponse,
    InferenceError,
)
from vision_platform.kernel.ports.detector import IDetector
from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameReader


class InlineInferenceClient:
    """Single-process inference: đọc frame từ SHM ring → detect → trả response echo request_id."""

    def __init__(self, ring: ShmRingBuffer, detector: IDetector):
        self._ring = ring
        self._reader = ShmFrameReader(ring)
        self._detector = detector

    def setup(self) -> None:
        self._detector.setup()

    def teardown(self) -> None:
        self._detector.teardown()

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        # 1. Đọc frame từ SHM qua read_ref (tự kiểm gen + ring_epoch stale — P0-3/F-2).
        frame = self._reader.read_ref(request.frame_ref)

        if frame is None:
            ref = request.frame_ref
            return InferenceResponse(
                request_id=request.request_id,
                error=InferenceError(
                    error_type="ShmReadFailed",
                    error_message=(
                        f"slot {ref.slot} gen {ref.generation} epoch {ref.ring_epoch} "
                        "not readable (overwritten / stale-epoch / wrong state)"
                    ),
                    retryable=False,
                ),
            )

        # 2. Detect. Exception → bọc thành InferenceError (chỉ string, không giữ Exception gốc).
        try:
            dets = self._detector.detect(frame)
            return InferenceResponse(
                request_id=request.request_id,
                detections=tuple(dets),   # freeze list → tuple ở biên DTO
            )
        except Exception as e:
            return InferenceResponse(
                request_id=request.request_id,
                error=InferenceError(
                    error_type=type(e).__qualname__,
                    error_message=str(e),
                    retryable=False,
                ),
            )
