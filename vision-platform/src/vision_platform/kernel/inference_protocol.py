"""Inference request/response protocol — DTO thuần cho tầng inference.

Layer: kernel — DỮ LIỆU THUẦN (frozen dataclass). KHÔNG import zmq/torch/cv2/multiprocessing.
Wire format tương lai: msgpack (do adapter ZMQ xử lý). DTO ở đây không biết transport.

Vì sao ở kernel mà được import domain (BBox) + kernel (ShmFrameRefData): contract import-linter
"Kernel chi phu thuoc domain" — kernel ĐƯỢC phụ thuộc domain, chỉ cấm I/O ngoài + runtime/application.

INVARIANT toạ độ (từ Step 02): Detection.box là BBox có CoordinateSpace tag — KHÔNG dùng x/y/w/h
trần. Detector khai báo space của nó (thường MODEL_INPUT khi vừa ra model); downstream phải
transform về ORIGINAL_FRAME/DISPLAY trước khi vẽ. Đặt float trần = bypass pattern Step 02.

INVARIANT SHM (F-2, tích hợp switchover #05): InferenceRequest MANG THẲNG ShmFrameRefData
(gồm ring_epoch). Client dùng ShmFrameReader.read_ref(frame_ref) để hưởng stale-check P0-3 —
sau switchover ring, ref epoch cũ → read trả None (không đọc nhầm frame ring mới).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from vision_platform.domain.bbox import BBox
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData


@dataclass(frozen=True)
class InferenceRequest:
    """Request gửi từ camera process → inference service.

    `frame_ref` là ShmFrameRefData ĐẦY ĐỦ (ring_name/slot/generation/ring_epoch/H/W/C) —
    1 nguồn sự thật về vị trí frame trong SHM. Không lặp lại field rời (tránh lệch dữ liệu).
    """
    request_id: str          # UUID — correlation key (khoá để match response)
    source_id: str           # camera_id (logging/routing)
    frame_ref: ShmFrameRefData


@dataclass(frozen=True)
class InferenceError:
    """Lỗi inference — CHỈ giữ chuỗi (không giữ Exception gốc; pattern R5 #04).

    Giữ Exception trực tiếp = rủi ro pickle/leak state qua wire. error_type/error_message là str.
    """
    error_type: str
    error_message: str
    retryable: bool = False   # production: timeout/transient=True; OOM/bad-input=False.


@dataclass(frozen=True)
class Detection:
    """Kết quả detection thuần — KHÔNG phụ thuộc model (YOLO/RTMDet/...).

    `box` là BBox có CoordinateSpace tag (invariant Step 02). Adapter model convert raw output
    → Detection; đổi model chỉ đổi adapter, Detection không động.
    """
    label: str
    confidence: float
    box: BBox


@dataclass(frozen=True)
class InferenceResponse:
    """Response echo `request_id` để client correlate đúng của mình."""
    request_id: str
    detections: tuple[Detection, ...] = field(default_factory=tuple)
    error: Optional[InferenceError] = None

    @property
    def is_success(self) -> bool:
        return self.error is None
