"""project_overlay — chiếu OverlayViewSnapshot (immutable) → dict JSON cho `/overlay` (spec Task 8, Property 1).

Layer: runtime (THUẦN — snapshot + now_ns vào, dict ra; KHÔNG mutate snapshot, KHÔNG I/O). Đây là "pure
projection" của design §Data Models: endpoint chụp MỘT snapshot đã commit + MỘT serializedAtNs rồi tính mọi
age/remainingLease từ 2 input đó — snapshot lưu timestamp/deadline gốc, KHÔNG đổi age (age là dẫn xuất).

remainingLeaseMs = clamp(deadline - now, [0, ghostSlaMs]) (floor). Toạ độ clip [0,1]; box zero-area bị loại
(bounded reason: đếm ở caller nếu cần). KHÔNG import analytics (Property 10 — cưỡng chế bằng import-linter).
"""
from __future__ import annotations

from typing import Any, Dict

from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.overlay_view import OverlayViewSnapshot

_MS = 1_000_000


def _clip01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else float(v))


def _raw_box(d: Detection) -> Dict[str, Any]:
    return {
        "label": d.label,
        "confidence": round(float(d.confidence), 4),
        "x": _clip01(d.box.x), "y": _clip01(d.box.y),
        "width": _clip01(d.box.w), "height": _clip01(d.box.h),
    }


def project_overlay(snap: OverlayViewSnapshot, now_ns: int, ghost_sla_ms: int) -> Dict[str, Any]:
    """Chiếu snapshot → dict (pure). `now_ns`/`ghost_sla_ms` là 2 input dẫn xuất age/lease."""
    out: Dict[str, Any] = {
        "schemaVersion": snap.schemaVersion,
        "processEpoch": snap.processEpoch,
        "sourceEpoch": snap.sourceEpoch,
        "eventRevision": snap.eventRevision,
        "serializedAtMs": now_ns // _MS,
        "health": {"source": snap.health.source.value, "detector": snap.health.detector.value},
    }

    if snap.rawResult is None:
        out["rawResult"] = None
    else:
        r = snap.rawResult
        out["rawResult"] = {
            "inferenceGeneration": r.inferenceGeneration,
            "sourceFrameVersion": r.sourceFrameVersion,
            "outcome": r.outcome.value,
            "sourceAgeMs": max(0, (now_ns - r.inputAcquiredNs) // _MS),
            "resultAgeMs": max(0, (now_ns - r.publishedNs) // _MS),
            "boxes": [_raw_box(d) for d in r.boxes],
        }

    disp_boxes = []
    for t in snap.display.tracks:
        if t.box.w <= 0.0 or t.box.h <= 0.0:
            continue   # zero-area → loại (Property: reject non-finite/zero-area)
        rem = (t.leaseDeadlineNs - now_ns) // _MS
        rem = 0 if rem < 0 else (ghost_sla_ms if rem > ghost_sla_ms else rem)
        disp_boxes.append({
            "displayId": t.displayId,
            "trackRevision": t.trackRevision,
            "remainingLeaseMs": int(rem),
            "label": t.label,
            "confidence": round(float(t.confidence), 4),
            "x": _clip01(t.box.x), "y": _clip01(t.box.y),
            "width": _clip01(t.box.w), "height": _clip01(t.box.h),
            # vx/vy chuẩn-hoá/giây (Wave A) → client ngoại suy pos+vel*dt (dt tính từ thời-điểm-NHẬN của
            # client, KHÔNG dùng clock server — 2 đồng hồ khác nhau). Chưa đủ dữ liệu → 0 (client vẽ tĩnh).
            "vx": round(float(t.vx), 6), "vy": round(float(t.vy), 6),
        })
    out["display"] = {"revision": snap.display.revision, "reason": snap.display.reason, "boxes": disp_boxes}
    return out
