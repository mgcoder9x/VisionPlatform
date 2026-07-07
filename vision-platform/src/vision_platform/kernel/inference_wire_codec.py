"""Wire codec: DTO inference ↔ dict Python thuần (QĐ-2).

Layer: kernel — THUẦN, KHÔNG import msgpack/zmq (kernel dependency-free). Chỉ chuyển DTO ↔ `dict`
(msgpack-friendly: str/int/float/list/dict/None). Mã hoá dict↔bytes (msgpack) làm ở RÌA transport
(adapter client + application server) — đổi msgpack→protobuf sau chỉ đổi rìa.

Round-trip PHẢI giữ: `ring_epoch` (int), `CoordinateSpace` (qua .value), confidence (float). (Property 6)
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.kernel.inference_protocol import (
    InferenceRequest, InferenceResponse, InferenceError, Detection,
)


# ---- BBox ----
def bbox_to_dict(b: BBox) -> dict:
    return {"x": b.x, "y": b.y, "w": b.w, "h": b.h, "space": b.space.value}


def dict_to_bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"], space=CoordinateSpace(d["space"]))


# ---- ShmFrameRefData ----
def frame_ref_to_dict(r: ShmFrameRefData) -> dict:
    return {
        "ring_name": r.ring_name, "slot": r.slot, "generation": r.generation,
        "height": r.height, "width": r.width, "channels": r.channels, "ring_epoch": r.ring_epoch,
    }


def dict_to_frame_ref(d: dict) -> ShmFrameRefData:
    return ShmFrameRefData(
        ring_name=d["ring_name"], slot=d["slot"], generation=d["generation"],
        height=d["height"], width=d["width"], channels=d["channels"], ring_epoch=d["ring_epoch"],
    )


# ---- Detection ----
def detection_to_dict(d: Detection) -> dict:
    return {"label": d.label, "confidence": d.confidence, "box": bbox_to_dict(d.box)}


def dict_to_detection(d: dict) -> Detection:
    return Detection(label=d["label"], confidence=d["confidence"], box=dict_to_bbox(d["box"]))


# ---- InferenceError ----
def error_to_dict(e: InferenceError | None) -> dict | None:
    if e is None:
        return None
    return {"error_type": e.error_type, "error_message": e.error_message, "retryable": e.retryable}


def dict_to_error(d: dict | None) -> InferenceError | None:
    if d is None:
        return None
    return InferenceError(error_type=d["error_type"], error_message=d["error_message"], retryable=d["retryable"])


# ---- InferenceRequest ----
def request_to_dict(req: InferenceRequest) -> dict:
    return {"request_id": req.request_id, "source_id": req.source_id, "frame_ref": frame_ref_to_dict(req.frame_ref)}


def dict_to_request(d: dict) -> InferenceRequest:
    return InferenceRequest(
        request_id=d["request_id"], source_id=d["source_id"], frame_ref=dict_to_frame_ref(d["frame_ref"]),
    )


# ---- InferenceResponse ----
def response_to_dict(resp: InferenceResponse) -> dict:
    return {
        "request_id": resp.request_id,
        "detections": [detection_to_dict(x) for x in resp.detections],
        "error": error_to_dict(resp.error),
    }


def dict_to_response(d: dict) -> InferenceResponse:
    return InferenceResponse(
        request_id=d["request_id"],
        detections=tuple(dict_to_detection(x) for x in d["detections"]),
        error=dict_to_error(d["error"]),
    )
