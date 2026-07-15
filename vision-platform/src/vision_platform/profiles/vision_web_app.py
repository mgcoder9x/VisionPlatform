"""vision_web_app — Web UI TÁCH LUỒNG: video (MJPEG) độc lập với detect (overlay).

KIẾN TRÚC (decouple transport ⊥ analytics):
- **Thread video** (`_video_loop`): đọc frame → JPEG → MJPEG, full fps. Publish (raw, ver, acquired_ns).
- **Thread detect** (`_detect_loop`): frame mới nhất → detector → feed `OverlayStateStore` (raw truth ⊥ display).
- **Thread scheduler** (`OverlayExpiryScheduler`): phát TimerTick → box hết hạn đúng giờ.
- **Browser**: `<img src=/stream>` + `<canvas>`; JS poll **`/overlay`** (fix gốc: epoch/lease/frame-identity) vẽ box.

FIX FLICKER (spec web-live-overlay-sync #378-390, D-106..114): thay `HOLD_MS` mù bằng OverlayStateStore
(authority check-and-commit) + per-track lease + epoch rollback client. `/boxes` GIỮ legacy (best-effort, cũ).

⚠️ Flask dev-server + không auth — chỉ demo/nội bộ (bảo mật hoãn).
"""
from __future__ import annotations

import argparse
import threading
import time
import uuid
from typing import Optional

import cv2

from flask import Flask, Response, jsonify

from vision_platform.profiles.vision_demo_app import moving_square_frame, _build_detector
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
from vision_platform.adapters.rtsp_frame_source import RtspFrameSource, mask_rtsp
from vision_platform.adapters.webcam_frame_source import WebcamFrameSource
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome, SourceState, DetectorState
from vision_platform.kernel.detection_cadence import DetectionCadenceConfig, assert_cadence_fits_lease
from vision_platform.domain.detect_cadence import should_detect
from vision_platform.domain.motion_gate import MotionGate
from vision_platform.runtime.overlay_state_store import OverlayStateStore
from vision_platform.runtime.overlay_expiry_scheduler import OverlayExpiryScheduler
from vision_platform.runtime.overlay_projection import project_overlay
from vision_platform.runtime.overlay_health import derive_health

app = Flask(__name__)
_lock = threading.Lock()
_jpeg: Optional[bytes] = None
_raw = None
_raw_ver = 0
_raw_acquired_ns = 0               # thời điểm read() frame hiện tại (server monotonic) — cho freshness
_legacy_boxes: list = []           # /boxes legacy (best-effort, giữ hành vi cũ)
_vframes = 0
_dframes = 0
_last_read_ns = 0                  # health: nhịp read-success của source
_stop = threading.Event()

# --- overlay (fix flicker) — khởi tạo trong main() trước khi phục vụ ---
_store: Optional[OverlayStateStore] = None
_cfg = OverlayConfig()
_cadence_cfg = DetectionCadenceConfig()   # mặc định = hành vi hiện tại; main() build lại từ CLI + assert P5

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Vision Platform — Live</title>
<style>body{background:#111;color:#eee;font-family:sans-serif;text-align:center;margin:0;padding:10px}
#wrap{position:relative;display:inline-block}#v{max-width:98vw;display:block;border:1px solid #444}
#c{position:absolute;left:0;top:0;pointer-events:none}#s{font:12px monospace;color:#9f9}</style></head>
<body><h3>Vision Platform — video + overlay (freshness/lease, fix flicker)</h3>
<div id="wrap"><img id="v" src="/stream"><canvas id="c"></canvas></div>
<p id="s"></p>
<script>
const img=document.getElementById('v'),cv=document.getElementById('c'),ctx=cv.getContext('2d');
// FIX FLICKER: đọc /overlay (epoch/per-track lease). KHÔNG giữ box mù theo thời-gian-poll.
// Mỗi box có deadline RIÊNG (từ remainingLeaseMs server + trừ RTT); chỉ gia hạn khi trackRevision của
// CHÍNH box tăng; vắng trong list → xóa; hết hạn → xóa. Epoch rollback: reject epoch cũ/retired.
let procEpoch=null, srcEpoch=null; const retired=new Set();
const boxes=new Map();  // displayId -> {rev, deadline(perf.now ms), b}
function resize(){ if(cv.width!==img.clientWidth||cv.height!==img.clientHeight){cv.width=img.clientWidth;cv.height=img.clientHeight;} }
async function tick(){
  const t0=performance.now(); let o=null;
  try{o=await(await fetch('/overlay',{cache:'no-store'})).json();}catch(e){o=null;}
  const rtt=performance.now()-t0, now=performance.now();
  if(o&&o.processEpoch){
    // process epoch anti-rollback
    if(procEpoch===null){procEpoch=o.processEpoch;}
    else if(o.processEpoch!==procEpoch){
      if(!retired.has(o.processEpoch)){retired.add(procEpoch);procEpoch=o.processEpoch;srcEpoch=null;boxes.clear();}
      else{o=null;} // epoch đã retired → bỏ qua
    }
    if(o&&o.processEpoch===procEpoch){
      if(srcEpoch===null){srcEpoch=o.sourceEpoch;}
      else if(o.sourceEpoch<srcEpoch){o=null;}            // rollback → bỏ
      else if(o.sourceEpoch>srcEpoch){srcEpoch=o.sourceEpoch;boxes.clear();}  // epoch mới → clear
    }
    if(o&&o.display&&o.sourceEpoch===srcEpoch){
      const present=new Set();
      for(const b of o.display.boxes){
        present.add(b.displayId);
        const prev=boxes.get(b.displayId);
        if(!prev||b.trackRevision>prev.rev){        // CHỈ gia hạn khi revision CHÍNH box tăng
          const rem=Math.max(0,b.remainingLeaseMs-rtt);
          boxes.set(b.displayId,{rev:b.trackRevision,deadline:now+rem,b:b});
        }else{prev.b=b;}                            // same rev: cập nhật toạ độ, GIỮ deadline (không kéo dài)
      }
      for(const id of [...boxes.keys()]) if(!present.has(id)) boxes.delete(id);  // vắng → xóa
    }
  }
  // clear + draw SÁT nhau (không await ở giữa). Hết hạn → xóa trước khi vẽ (bounded ghost).
  resize(); ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle='#00ff66';ctx.lineWidth=2;ctx.font='14px sans-serif';ctx.fillStyle='#00ff66';
  for(const [id,e] of [...boxes]){
    if(e.deadline<=now){boxes.delete(id);continue;}
    const b=e.b, x=b.x*cv.width, y=b.y*cv.height, w=b.width*cv.width, h=b.height*cv.height;
    ctx.strokeRect(x,y,w,h); ctx.fillText(b.label+' '+b.confidence.toFixed(2),x,Math.max(12,y-4));
  }
}
setInterval(tick,80);
setInterval(async()=>{try{document.getElementById('s').innerText=await(await fetch('/stats',{cache:'no-store'})).text()}catch(e){}},1000);
</script></body></html>"""


def _open_source(args):
    if args.rtsp:
        s = RtspFrameSource(args.rtsp, max_reconnect=args.max_reconnect); s.setup(); return s
    if args.video:
        s = VideoFileFrameSource(args.video, loop=True); s.setup(); return s
    if getattr(args, "camera", None) is not None:
        s = WebcamFrameSource(args.camera); s.setup(); return s
    return None


def _video_loop(args) -> None:
    global _jpeg, _raw, _raw_ver, _raw_acquired_ns, _vframes, _last_read_ns
    src = _open_source(args)
    i = 0
    try:
        while not _stop.is_set():
            if src is None:
                frame = moving_square_frame(i, args.height, args.width); i += 1
            else:
                r = src.read()
                if r.status in (ReadStatus.EOF, ReadStatus.ERROR):
                    break
                if not r.has_data:
                    continue
                frame = r.data
            acquired = time.monotonic_ns()
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
            if ok:
                with _lock:
                    _raw = frame
                    _raw_ver += 1
                    _raw_acquired_ns = acquired
                    _jpeg = buf.tobytes()
                    _vframes += 1
                    _last_read_ns = acquired
            if args.pace > 0:
                time.sleep(args.pace)
    finally:
        if src is not None:
            src.teardown()


def _norm_boxes(dets, w: int, h: int):
    """Detection (pixel, ORIGINAL_FRAME) → list (label, BBox NORMALIZED, conf). Bỏ box zero-area/ngoài khung."""
    out = []
    for d in dets:
        nx = min(1.0, max(0.0, d.box.x / w)); ny = min(1.0, max(0.0, d.box.y / h))
        nw = min(1.0, max(0.0, d.box.w / w)); nh = min(1.0, max(0.0, d.box.h / h))
        if nw <= 0.0 or nh <= 0.0:
            continue
        out.append((d.label, BBox(nx, ny, nw, nh, CoordinateSpace.NORMALIZED), round(float(d.confidence), 4)))
    return out


def _detect_loop(args) -> None:
    global _legacy_boxes, _dframes
    detector = _build_detector(args)
    detector.setup()
    last_ver = -1
    errors = 0
    assert _store is not None
    # --- điều tiết detect (adaptive-detection-perf) — mặc định = hành vi hiện tại (additive) ---
    cc = _cadence_cfg
    min_interval_ns = cc.detectMinIntervalMs * 1_000_000
    max_interval_ns = cc.detectMaxIntervalMs * 1_000_000
    mgate = MotionGate(
        pixel_diff_threshold=cc.motionPixelDiffThreshold, min_area_ratio=cc.motionMinAreaRatio,
        max_consecutive_skip=cc.motionMaxConsecutiveSkip, roi=cc.motionRoi,
    ) if cc.motionGate else None
    last_detect_ns: Optional[int] = None
    last_detect_version: Optional[int] = None
    try:
        while not _stop.is_set():
            with _lock:
                frame = _raw; ver = _raw_ver; acquired = _raw_acquired_ns; read_ns = _last_read_ns
            if frame is None or ver == last_ver:
                time.sleep(0.005); continue
            last_ver = ver
            # GATE: motion-gate (bỏ frame tĩnh) + cadence. LUÔN gọi mgate.decide để prev-frame theo kịp.
            # HEARTBEAT (max-interval) ÉP detect → override motion-gate (chống mất box vật đứng-yên, K-103).
            motion_ok = mgate.decide(frame)[0] if mgate is not None else True
            cad_ok, reason = should_detect(
                now_ns=time.monotonic_ns(), last_detect_ns=last_detect_ns,
                frame_version=ver, last_detect_version=last_detect_version,
                min_interval_ns=min_interval_ns, every_n=cc.detectEveryN, max_interval_ns=max_interval_ns)
            run = True if reason == "MAX_INTERVAL" else (motion_ok and cad_ok)
            if not run:
                # Bỏ detect có CHỦ ĐÍCH (không phải lỗi): giữ overlay cũ (lease lo). Detector vẫn LIVE (không stale-giả).
                now = time.monotonic_ns()
                _store.set_health(*_health_states(now, read_ns, now))
                continue
            token = _store.begin_inference()
            start = time.monotonic_ns()
            try:
                h, w = frame.shape[:2]
                dets = detector.detect(frame)
                end = time.monotonic_ns()
                store_boxes = _norm_boxes(dets, w, h)
                outcome = Outcome.DETECTED if store_boxes else Outcome.EMPTY
                _store.apply_completion(
                    process_epoch=_store_process_epoch(), source_epoch=1, source_frame_version=ver,
                    token=token, outcome=outcome, boxes=store_boxes,
                    input_acquired_ns=acquired, inference_start_ns=start, inference_end_ns=end,
                    published_ns=time.monotonic_ns())
                # health LIVE (source theo read cadence · detector vừa completion)
                now = time.monotonic_ns()
                _store.set_health(*_health_states(now, read_ns, now))
                # legacy /boxes (best-effort, giữ hành vi cũ): list bbox chuẩn hoá
                _legacy = [{"label": lbl, "conf": c, "x": bx.x, "y": bx.y, "w": bx.w, "h": bx.h}
                           for (lbl, bx, c) in store_boxes]
                with _lock:
                    _legacy_boxes = _legacy; _dframes += 1
                last_detect_ns = time.monotonic_ns(); last_detect_version = ver
                errors = 0
            except Exception as e:
                errors += 1
                print(f"[web] detect error #{errors}: {type(e).__qualname__}: {e}", flush=True)
                # KHÔNG bịa empty — chỉ báo detector ERROR (Property 6). Box cũ sống hết lease rồi thôi.
                now = time.monotonic_ns()
                _store.set_health(*_health_states(now, read_ns, None, detector_error=True))
                time.sleep(0.3)
                if errors >= 3:
                    print("[web] detect: thử khôi phục detector (reload)...", flush=True)
                    try:
                        detector.teardown(); detector.setup(); errors = 0
                    except Exception as e2:
                        print(f"[web] khôi phục thất bại: {e2}", flush=True); time.sleep(2.0)
    finally:
        try:
            detector.teardown()
        except Exception:
            pass


# process epoch cố định cho phiên (UUID) — client dùng chống rollback qua restart
_PROCESS_EPOCH = uuid.uuid4().hex


def _store_process_epoch() -> str:
    return _PROCESS_EPOCH


def _health_states(now_ns, last_read_ns, last_completion_ns, detector_error=False):
    """Trả (SourceState, DetectorState) từ derive_health (Task 6)."""
    h = derive_health(now_ns=now_ns, config=_cfg,
                      last_read_ns=last_read_ns or None,
                      last_completion_ns=last_completion_ns,
                      detector_error=detector_error)
    return h.source, h.detector


def _mjpeg():
    while True:
        with _lock:
            j = _jpeg
        if j is not None:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + j + b"\r\n"
        time.sleep(0.02)


@app.route("/")
def index():
    return _PAGE


@app.route("/stream")
def stream():
    return Response(_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/overlay")
def overlay():
    snap = _store.snapshot() if _store is not None else None
    if snap is None:
        return jsonify({"schemaVersion": 1, "rawResult": None, "display": {"boxes": []}})
    resp = jsonify(project_overlay(snap, time.monotonic_ns(), _cfg.ghostSlaMs))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/boxes")
def boxes():
    with _lock:
        return jsonify(_legacy_boxes)   # legacy best-effort (giữ hành vi cũ)


@app.route("/stats")
def stats():
    with _lock:
        n = len(_legacy_boxes)
    ev = _store.snapshot().eventRevision if _store is not None else 0
    return f"video={_vframes} · detect={_dframes} · boxes={n} · overlay_rev={ev}"


def main() -> int:
    global _store
    p = argparse.ArgumentParser(prog="vision_platform.profiles.vision_web_app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--height", type=int, default=240)
    p.add_argument("--width", type=int, default=320)
    p.add_argument("--pace", type=float, default=0.0)
    p.add_argument("--quality", type=int, default=70)
    p.add_argument("--threshold", type=int, default=127)
    p.add_argument("--video", type=str, default=None)
    p.add_argument("--rtsp", type=str, default=None)
    p.add_argument("--camera", type=int, default=None, help="index webcam (0,1,...)")
    p.add_argument("--max-reconnect", type=int, default=None)
    p.add_argument("--pt", type=str, default=None)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--onnx", type=str, default=None)
    p.add_argument("--labels", type=str, default=None)
    p.add_argument("--model-size", type=int, default=640)
    p.add_argument("--layout", type=str, default="nc_first", choices=["nc_first", "nc_last"])
    p.add_argument("--yolo", type=str, default="v5", choices=["v5", "v8"])
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.5)
    # --- điều tiết detect (adaptive-detection-perf) — mặc định = hành vi hiện tại ---
    p.add_argument("--detect-min-interval-ms", type=int, default=0,
                   help="ns tối thiểu giữa 2 detect (0=không giới hạn). Phải <= displayLeaseMs (chống giật).")
    p.add_argument("--detect-max-interval-ms", type=int, default=0,
                   help="HEARTBEAT: ép detect nếu quá lâu không detect (0=tắt). Phải <= displayLeaseMs "
                        "(chống mất box vật đứng-yên khi bật motion-gate). Nên đặt khi dùng --motion-gate.")
    p.add_argument("--detect-every-n", type=int, default=1, help="chỉ detect mỗi N frame-version (1=mọi frame)")
    p.add_argument("--motion-gate", action="store_true", help="bỏ detect khi cảnh tĩnh (tiết kiệm CPU)")
    p.add_argument("--motion-threshold", type=int, default=25, help="ngưỡng pixel đổi (0..255)")
    p.add_argument("--motion-min-area", type=float, default=0.005, help="tỉ lệ pixel đổi < ngưỡng → coi là tĩnh")
    p.add_argument("--motion-max-skip", type=int, default=0, help="sau N skip liên tiếp ép 1 detect (0=không ép)")
    args = p.parse_args()

    global _cadence_cfg
    _cadence_cfg = DetectionCadenceConfig(
        detectMinIntervalMs=args.detect_min_interval_ms, detectMaxIntervalMs=args.detect_max_interval_ms,
        detectEveryN=args.detect_every_n,
        motionGate=args.motion_gate, motionPixelDiffThreshold=args.motion_threshold,
        motionMinAreaRatio=args.motion_min_area, motionMaxConsecutiveSkip=args.motion_max_skip,
    )
    assert_cadence_fits_lease(_cadence_cfg, display_lease_ms=_cfg.displayLeaseMs)   # P5 fail-fast startup

    _store = OverlayStateStore(_PROCESS_EPOCH, 1, _cfg)

    src_name = (f"rtsp={mask_rtsp(args.rtsp)}" if args.rtsp else
                f"video={args.video}" if args.video else
                f"webcam={args.camera}" if args.camera is not None else
                f"synthetic {args.height}x{args.width}")
    det_name = (f"Yolov5PtDetector({args.pt},dev={args.device})" if args.pt else
                f"OnnxDetector({args.onnx})" if args.onnx else f"BrightBlobDetector({args.threshold})")
    cad = (f"min-interval={_cadence_cfg.detectMinIntervalMs}ms · max-interval(heartbeat)="
           f"{_cadence_cfg.detectMaxIntervalMs}ms · every-n={_cadence_cfg.detectEveryN} · "
           f"motion-gate={'ON' if _cadence_cfg.motionGate else 'off'}")
    print(f"[web] TÁCH LUỒNG + OVERLAY(fix flicker) · nguồn={src_name} · detector={det_name}")
    print(f"[web] cadence: {cad}  (mặc định = hành vi cũ nếu không set)")
    print(f"[web] Mở: http://{args.host}:{args.port}/  (/overlay = bản fix · /boxes = legacy)")

    import logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    threading.Thread(target=_video_loop, args=(args,), daemon=True).start()
    threading.Thread(target=_detect_loop, args=(args,), daemon=True).start()
    threading.Thread(target=lambda: OverlayExpiryScheduler(_store).serve(_stop), daemon=True).start()
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
