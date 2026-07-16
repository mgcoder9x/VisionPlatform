"""Test project_overlay (spec Task 8, Property 1) — pure projection, null-before-first, ages, lease clamp.

THUẦN + xác định (now_ns tiêm). Chứng minh projection KHÔNG mutate snapshot (đọc 2 lần = giống nhau).
"""
from __future__ import annotations

from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome
from vision_platform.runtime.overlay_projection import project_overlay
from vision_platform.runtime.overlay_state_store import OverlayStateStore

MS = 1_000_000


def _nbox(x, y, w=0.1, h=0.1):
    return BBox(x, y, w, h, CoordinateSpace.NORMALIZED)


def _store(**cfg):
    base = dict(minHits=1, displayLeaseMs=500, ghostSlaMs=1500)
    base.update(cfg)
    return OverlayStateStore("proc-1", 1, OverlayConfig(**base), clock=lambda: 0)


def test_null_before_first_result():
    s = _store()
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500)
    assert out["rawResult"] is None
    assert out["health"] == {"source": "INITIALIZING", "detector": "INITIALIZING"}
    assert out["display"]["boxes"] == []
    assert out["schemaVersion"] == 1 and out["processEpoch"] == "proc-1"


def test_projection_after_detection():
    s = _store()
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.2), 0.87)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    out = project_overlay(s.snapshot(), now_ns=100 * MS, ghost_sla_ms=1500)
    assert out["rawResult"]["outcome"] == "DETECTED"
    assert out["rawResult"]["sourceFrameVersion"] == 1
    assert out["rawResult"]["sourceAgeMs"] == 100          # (100ms-0)/1ms
    b = out["display"]["boxes"][0]
    assert b["label"] == "person" and b["displayId"] == "1:1"
    assert 0.0 <= b["x"] <= 1.0 and 0.0 < b["width"] <= 1.0
    # lease: deadline = 0+500ms; now=100ms → remaining 400ms
    assert b["remainingLeaseMs"] == 400


def test_remaining_lease_clamped_zero_and_ghost():
    # Config hợp lệ (display<=ghost). Test upper-clamp bằng cách TRUYỀN ghost_sla_ms nhỏ hơn vào projection
    # (param clamp độc lập config) — remaining thực 500ms > 300 → clamp 300. (Với config thật display<=ghost
    # nên remaining không bao giờ vượt ghost; clamp là defensive — test trực tiếp logic projection.)
    s = _store(displayLeaseMs=500)   # 300<=500<=1500 hợp lệ
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.1), 0.9)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=300)
    assert out["display"]["boxes"][0]["remainingLeaseMs"] == 300     # clamp trên = ghost_sla_ms
    out2 = project_overlay(s.snapshot(), now_ns=999 * MS, ghost_sla_ms=300)
    assert out2["display"]["boxes"][0]["remainingLeaseMs"] == 0      # quá hạn → 0 (không âm)


def test_projection_does_not_mutate_snapshot():
    s = _store()
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.1), 0.9)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    snap = s.snapshot()
    a = project_overlay(snap, now_ns=10 * MS, ghost_sla_ms=1500)
    b = project_overlay(snap, now_ns=10 * MS, ghost_sla_ms=1500)
    assert a == b                                # cùng input → cùng output (không mutate)
    assert s.snapshot() is snap                  # snapshot không đổi


class _Clk:
    def __init__(self): self.t = 0
    def __call__(self): return self.t


def test_project_includes_velocity_after_motion():
    """Wave A Task 1: /overlay display box phơi vx/vy (chuẩn-hoá/giây) để client ngoại suy.
    Vật di chuyển sang phải giữa 2 detect (IoU vẫn overlap) → vx>0, vy≈0."""
    clk = _Clk()
    s = OverlayStateStore("proc-1", 1, OverlayConfig(minHits=1, displayLeaseMs=500, ghostSlaMs=1500),
                          clock=clk)
    t1 = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=t1,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.10, 0.5, 0.2, 0.2), 0.9)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    clk.t = 100 * MS                      # tiến 100ms
    t2 = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=2, token=t2,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.16, 0.5, 0.2, 0.2), 0.9)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    out = project_overlay(s.snapshot(), now_ns=100 * MS, ghost_sla_ms=1500)
    b = out["display"]["boxes"][0]
    assert "vx" in b and "vy" in b              # trường vận tốc có mặt
    assert b["vx"] > 0                          # di chuyển sang phải → vx dương (chuẩn-hoá/giây)
    assert abs(b["vy"]) < 1e-6                   # không di chuyển dọc → vy≈0


def test_project_velocity_zero_when_no_motion_history():
    """Track mới (1 detect, chưa đủ 2 khớp) → vx=vy=0 (không ngoại suy sai)."""
    s = _store()
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.DETECTED, boxes=[("person", _nbox(0.1, 0.1), 0.9)],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    b = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500)["display"]["boxes"][0]
    assert b["vx"] == 0.0 and b["vy"] == 0.0


def test_empty_outcome_no_raw_boxes():
    s = _store()
    tok = s.begin_inference()
    s.apply_completion(process_epoch="proc-1", source_epoch=1, source_frame_version=1, token=tok,
                       outcome=Outcome.EMPTY, boxes=[],
                       input_acquired_ns=0, inference_start_ns=1, inference_end_ns=2, published_ns=3)
    out = project_overlay(s.snapshot(), now_ns=0, ghost_sla_ms=1500)
    assert out["rawResult"]["outcome"] == "EMPTY" and out["rawResult"]["boxes"] == []
