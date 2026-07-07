"""IInferenceClient — port (driven) cho inference client. Layer: kernel/ports (Protocol thuần).

Hợp đồng CHUNG cho `InlineInferenceClient` (#06, cùng process) và `ZmqInferenceClient` (cross-process ZMQ).
Tách port ở sub-spec zmq (D-023 đã cố ý HOÃN ở #06 tới khi có bản thứ 2 → nay justify).
"""
from typing import Protocol

from vision_platform.kernel.inference_protocol import InferenceRequest, InferenceResponse


class IInferenceClient(Protocol):
    """Client gửi InferenceRequest → nhận InferenceResponse (echo request_id).

    Contract:
        - setup() trước infer() đầu (mở transport/nạp detector). Idempotent.
        - infer(request) trả InferenceResponse (SYNC, blocking tới khi có response/timeout).
        - teardown() giải phóng (đóng socket/detector). Idempotent.
    """
    def infer(self, request: InferenceRequest) -> InferenceResponse: ...

    def setup(self) -> None: ...

    def teardown(self) -> None: ...
