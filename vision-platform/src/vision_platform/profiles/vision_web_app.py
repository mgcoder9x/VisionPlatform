"""vision_web_app — Web UI TÁCH LUỒNG: video (MJPEG) độc lập với detect (overlay).

KIẾN TRÚC (decouple transport ⊥ analytics):
- **Thread video** (`_video_loop`): đọc frame → JPEG → MJPEG, full fps. Publish (raw, ver, acquired_ns).
- **Thread detect** (`_detect_loop`): frame mới nhất → detector → feed `OverlayStateStore` (raw truth ⊥ display).
- **Thread scheduler** (`OverlayExpiryScheduler`): phát TimerTick → box hết hạn đúng giờ.
- **Browser**: `<img src=/stream>` + `<canvas>`; JS poll **`/overlay`** (fix gốc: epoch/lease/frame-identity) vẽ box.

FIX FLICKER (spec web-live-overlay-sync #378-390, D-106..114): thay `HOLD_MS` mù bằng OverlayStateStore
(authority check-and-commit) + per-track lease + epoch rollback client. `/boxes` GIỮ legacy (best-effort, cũ).

SERVING (spec web-production-hardening): `--server waitress` = WSGI production (Wave 1). XÁC THỰC (Wave 2):
đặt env `VP_WEB_USER`/`VP_WEB_PASS` → Basic Auth phủ mọi route; secure-default = bind 127.0.0.1, phơi mạng bắt
buộc có credential (hoặc `--insecure`). TLS = reverse-proxy (Wave 3, chưa nhúng vào app → Basic Auth chỉ an toàn sau TLS).
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from typing import Optional

import cv2

from flask import Flask, Response, jsonify, stream_with_context

from vision_platform.profiles.vision_demo_app import moving_square_frame, _build_detector
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
from vision_platform.adapters.rtsp_frame_source import RtspFrameSource, mask_rtsp
from vision_platform.adapters.webcam_frame_source import WebcamFrameSource
from vision_platform.adapters.wsgi_server import serve_wsgi
from vision_platform.adapters.auth_middleware import BasicAuthMiddleware, make_env_verifier
from vision_platform.adapters.security_headers import SecurityHeadersMiddleware
from vision_platform.adapters.metrics_http_server import is_loopback
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.domain.bbox import BBox, CoordinateSpace
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import Outcome, SourceState, DetectorState
from vision_platform.kernel.detection_cadence import DetectionCadenceConfig, assert_cadence_fits_lease
from vision_platform.application.config_loader import load_detection_config
from vision_platform.domain.detect_cadence import should_detect
from vision_platform.domain.motion_gate import MotionGate
from vision_platform.runtime.overlay_state_store import OverlayStateStore
from vision_platform.runtime.stream_admission import StreamAdmission, capacity_from_threads
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
# Bulkhead kết nối streaming (Wave 2, ĐO #456) — khởi tạo trong main(); None = không giới hạn (đường test/legacy)
_admission: Optional[StreamAdmission] = None
_cfg = OverlayConfig()
_cadence_cfg = DetectionCadenceConfig()   # mặc định = hành vi hiện tại; main() build lại từ CLI + assert P5

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Vision Platform — Live</title>
<style>body{background:#111;color:#eee;font-family:sans-serif;text-align:center;margin:0;padding:10px}
#wrap{position:relative;display:inline-block;border:1px solid #444;font-size:0}#v{max-width:98vw;display:block}
#c{position:absolute;left:0;top:0;pointer-events:none}#s{font:12px monospace;color:#9f9}</style></head>
<body><h3>Vision Platform — video + overlay (freshness/lease, fix flicker)</h3>
<div id="wrap"><img id="v"><canvas id="c"></canvas></div>
<p id="s"></p>
<div id="conn" style="display:none;position:fixed;top:8px;right:8px;background:#a00;color:#fff;padding:6px 10px;border-radius:4px;font:12px sans-serif;z-index:9">⚠ mất kết nối — đang thử lại…</div>
<script>
// MỌI request dựng URL TUYỆT ĐỐI từ `location.origin` (KHÔNG dùng path tương đối).
// LÝ DO ĐO ĐƯỢC (#457/K-124): mở UI bằng URL kiểu http://user:pass@host/ (bookmark tiện tay) thì
// `document.baseURI`/`document.URL` GIỮ credential ⇒ path tương đối resolve thành URL-có-credential ⇒ **mọi
// `fetch()` NÉM LỖI** ("Request cannot be constructed from a URL that includes credentials") ⇒ `/stats` + ĐƯỜNG
// LUI poll chết, mà SSE + <img> vẫn chạy nên trông như bình thường = hỏng ÂM THẦM một phần. `location.origin`
// KHÔNG bao giờ chứa credential ⇒ miễn nhiễm. (Đối chứng đã đo: absolute BASE+"/stats" → 200 · path tương đối
// "/stats" → TypeError. Guard chống hồi quy: tests/test_web_sse.py::test_client_uses_absolute_urls_not_relative_paths.)
const BASE=location.origin;
const img=document.getElementById('v'),cv=document.getElementById('c'),ctx=cv.getContext('2d');
// KIẾN TRÚC: TÁCH poll (dữ liệu) ⊥ render (vẽ). poll SELF-RESCHEDULING (tối đa 1 fetch in-flight →
// KHÔNG pile-up → hết ERR_INSUFFICIENT_RESOURCES khi /overlay chậm lúc CPU tải, #415). render qua
// requestAnimationFrame (mượt, decouple network) + ngoại suy vị trí theo vận tốc vx/vy nếu server gửi
// (forward-compatible Wave A — hiện /overlay chưa gửi → vẽ tĩnh, no-op). Giữ epoch-rollback + per-track lease.
let procEpoch=null, srcEpoch=null; const retired=new Set();
const boxes=new Map();  // displayId -> {rev, deadline(perf.now ms), b, updatedAt(perf.now ms)}
function resize(){ if(cv.width!==img.clientWidth||cv.height!==img.clientHeight){cv.width=img.clientWidth;cv.height=img.clientHeight;} }
const clamp01=(v)=>v<0?0:(v>1?1:v);
let pollFails=0, statsFails=0, imgFails=0;  // đếm lỗi-liên-tiếp → backoff (giảm flood console + đỡ đốt mạng lúc server mất kết nối, #436)
const _connBadge=document.getElementById('conn');
function setConn(ok){ if(_connBadge) _connBadge.style.display = ok ? 'none' : 'block'; }
// ---- POLL: cập nhật STATE (không vẽ), tự hẹn lần kế SAU khi xong → 1 in-flight ----
// ---- APPLY: 1 payload overlay → cập nhật STATE (epoch-rollback + per-track lease + boxes Map). DÙNG CHUNG
//      cho SSE (rtt≈0) lẫn poll-fallback → logic đồng nhất, không nhân đôi (spec overlay-sse-transport). ----
function applyOverlay(o, rtt){
  const now=performance.now();
  if(o&&o.processEpoch){
    if(procEpoch===null){procEpoch=o.processEpoch;}
    else if(o.processEpoch!==procEpoch){
      if(!retired.has(o.processEpoch)){retired.add(procEpoch);procEpoch=o.processEpoch;srcEpoch=null;boxes.clear();}
      else{o=null;}
    }
    if(o&&o.processEpoch===procEpoch){
      if(srcEpoch===null){srcEpoch=o.sourceEpoch;}
      else if(o.sourceEpoch<srcEpoch){o=null;}
      else if(o.sourceEpoch>srcEpoch){srcEpoch=o.sourceEpoch;boxes.clear();}
    }
    if(o&&o.display&&o.sourceEpoch===srcEpoch){
      const present=new Set();
      for(const b of o.display.boxes){
        present.add(b.displayId);
        const prev=boxes.get(b.displayId);
        if(!prev||b.trackRevision>prev.rev){
          const rem=Math.max(0,b.remainingLeaseMs-rtt);
          boxes.set(b.displayId,{rev:b.trackRevision,deadline:now+rem,b:b,updatedAt:now});
        }else{prev.b=b;prev.updatedAt=now;}   // same rev: cập nhật toạ độ + mốc (GIỮ deadline)
      }
      for(const id of [...boxes.keys()]) if(!present.has(id)) boxes.delete(id);
    }
  }
}
// ---- SSE (transport ưu tiên): 1 kết nối dài server-push → outage = ~1 lỗi + EventSource TỰ reconnect
//      (thay vòng poll flood mỗi fetch hỏng, fix gốc K-119). ----
let sseFails=0, degraded=false;   // SSE lỗi liên tiếp → rơi về poll (vd server trả 503 vì đạt trần bulkhead)
function degradeToPoll(es){ if(degraded) return; degraded=true; try{es.close();}catch(e){} poll(); }   // 1 lần duy nhất
function startSSE(){
  try{
    const es=new EventSource(BASE+'/events');
    es.addEventListener('overlay',ev=>{ if(pollFails>0){imgFails=0;reloadStream();} pollFails=0; sseFails=0; setConn(true); applyOverlay(JSON.parse(ev.data),0); });
    es.onopen=()=>{ pollFails=0; sseFails=0; setConn(true); };
    es.onerror=()=>{ pollFails++; sseFails++; setConn(false);            // server down: 1 lỗi + ES tự reconnect (KHÔNG flood)
      // readyState CLOSED(2) = lỗi VĨNH VIỄN (HTTP status lỗi như 503 đạt trần bulkhead, hoặc MIME sai):
      // trình duyệt KHÔNG tự reconnect nữa (ĐO #456: /events 503 → đúng 1 lần thử, im 59s) → phải rơi về poll
      // NGAY. Chờ ngưỡng ở đây = overlay chết vĩnh viễn dù server sống. Ngưỡng chỉ dành cho lỗi TẠM (CONNECTING).
      if(es.readyState===2 || sseFails>=3) degradeToPoll(es); };
    return true;
  }catch(e){ return false; }
}
// ---- POLL (fallback khi trình duyệt không có EventSource): self-rescheduling ≤1 in-flight + backoff ----
async function poll(){
  try{
    const t0=performance.now(); let o=null, fetchOk=false;
    try{o=await(await fetch(BASE+'/overlay',{cache:'no-store'})).json();fetchOk=true;}catch(e){o=null;}
    if(fetchOk){if(pollFails>0){imgFails=0;reloadStream();}pollFails=0;setConn(true);}else{pollFails++;setConn(false);}   // backoff+badge; poll hồi phục → nối lại stream NGAY (#436)
    applyOverlay(o, performance.now()-t0);
  }finally{ setTimeout(poll, pollFails===0?80:Math.min(80*Math.pow(2,pollFails),2000)); }   // reschedule DÙ lỗi; BACKOFF khi lỗi liên tiếp (80ms→cap 2s) → giảm flood console lúc outage; ≤1 in-flight (#415/#436)
}
// ---- RENDER: vẽ mỗi animation-frame; ngoại suy pos+vel*dt nếu có vx/vy (Wave A); hết hạn → xóa ----
function render(){
  const now=performance.now();
  resize(); ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle='#00ff66';ctx.lineWidth=2;ctx.font='14px sans-serif';ctx.fillStyle='#00ff66';
  for(const [id,e] of [...boxes]){
    if(e.deadline<=now){boxes.delete(id);continue;}
    const b=e.b, hasV=(typeof b.vx==='number'&&typeof b.vy==='number');
    const dt=hasV?(now-e.updatedAt)/1000:0;
    const bx=hasV?clamp01(b.x+b.vx*dt):b.x, by=hasV?clamp01(b.y+b.vy*dt):b.y;
    const x=bx*cv.width, y=by*cv.height, w=b.width*cv.width, h=b.height*cv.height;
    ctx.strokeRect(x,y,w,h); ctx.fillText(b.label+' '+b.confidence.toFixed(2),x,Math.max(12,y-4));
  }
  requestAnimationFrame(render);
}
// ---- STATS: self-rescheduling (1 in-flight) ----
async function statsLoop(){
  let ok=false;
  try{document.getElementById('s').innerText=await(await fetch(BASE+'/stats',{cache:'no-store'})).text();ok=true;}catch(e){}
  finally{ statsFails=ok?0:statsFails+1; setTimeout(statsLoop, statsFails===0?1000:Math.min(1000*Math.pow(2,statsFails),5000)); }   // backoff (#436)
}
// ---- MJPEG resilience: tab nền → trình duyệt treo/hủy stream <img> + KHÔNG tự nối lại (video đen tới khi
// reload). Nối lại khi tab HIỆN lại (visibilitychange) + tự reconnect khi stream lỗi. ?t= ép kết nối mới. ----
function reloadStream(){ img.src=BASE+'/stream?t='+Date.now(); }
img.addEventListener('load',()=>{ imgFails=0; });   // stream nhận frame → reset backoff (#436)
document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='visible'){ imgFails=0; reloadStream(); } });
img.addEventListener('error',()=>{ imgFails++; setTimeout(reloadStream, Math.min(500*Math.pow(2,imgFails-1),5000)); });   // BACKOFF reconnect (500ms→cap 5s) giảm flood outage (#436)
// khởi động: ảnh nạp qua URL TUYỆT ĐỐI (K-124) → SSE ưu tiên (push, ít lỗi lúc outage) → fallback poll nếu
// trình duyệt không hỗ trợ EventSource.
reloadStream();
if(window.EventSource){ if(!startSSE()){ poll(); } } else { poll(); }
requestAnimationFrame(render); statsLoop();
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
# COCO 80 lớp (thứ tự chuẩn Ultralytics: 0=person, 2=car, 7=truck — khớp label số quan sát #403).
# Dùng qua --coco-labels (opt-in) để hiện tên đẹp thay chỉ số; KHÔNG auto để tránh gán sai cho model custom.
_COCO80 = ("person,bicycle,car,motorcycle,airplane,bus,train,truck,boat,traffic light,fire hydrant,stop sign,"
           "parking meter,bench,bird,cat,dog,horse,sheep,cow,elephant,bear,zebra,giraffe,backpack,umbrella,"
           "handbag,tie,suitcase,frisbee,skis,snowboard,sports ball,kite,baseball bat,baseball glove,skateboard,"
           "surfboard,tennis racket,bottle,wine glass,cup,fork,knife,spoon,bowl,banana,apple,sandwich,orange,"
           "broccoli,carrot,hot dog,pizza,donut,cake,chair,couch,potted plant,bed,dining table,toilet,tv,laptop,"
           "mouse,remote,keyboard,cell phone,microwave,oven,toaster,sink,refrigerator,book,clock,vase,scissors,"
           "teddy bear,hair drier,toothbrush")


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


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)   # No Content — tránh 404 favicon mỗi lần load (polish thương mại)


def _admit_or_503(kind: str):
    """Bulkhead (Wave 2): xin slot streaming. Trả `None` nếu được phép; ngược lại trả Response **503 NGAY**.

    Vì sao 503 chứ KHÔNG cứ stream: WSGI sync = 1 thread/kết nối, `/stream`+`/events` vô hạn → nhận quá trần là
    cạn pool ⇒ MỌI request ngắn treo vô hạn (ĐO #456). 503 = tín hiệu tường minh để client suy giảm (SSE→poll,
    ảnh→retry backoff) thay vì hang âm thầm."""
    if _admission is None or _admission.try_acquire():
        return None
    resp = Response(f"streaming busy: dat tran {_admission.max_streams} ket noi dong thoi\n",
                    status=503, mimetype="text/plain")
    resp.headers["Retry-After"] = "5"
    print(f"[web] TỪ CHỐI {kind}: đạt trần {_admission.max_streams} kết nối streaming đồng thời "
          f"(tăng --threads / --max-stream-conns nếu cần nhiều viewer hơn)")
    return resp


def _released_after(gen):
    """Bọc generator streaming: LUÔN `release()` slot khi kết nối đóng/lỗi (client rời, server dừng)."""
    try:
        yield from gen
    finally:
        if _admission is not None:
            _admission.release()


@app.route("/stream")
def stream():
    busy = _admit_or_503("/stream")
    if busy is not None:
        return busy
    return Response(_released_after(_mjpeg()), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/overlay")
def overlay():
    snap = _store.snapshot() if _store is not None else None
    if snap is None:
        return jsonify({"schemaVersion": 1, "rawResult": None, "display": {"boxes": []}})
    resp = jsonify(project_overlay(snap, time.monotonic_ns(), _cfg.ghostSlaMs))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


# --- SSE transport (spec overlay-sse-transport #448): PUSH thay poll → outage ~1 lỗi thay flood ---
_SSE_TICK_S = 0.05        # nhịp quét store (50ms) — cân freshness ⊥ CPU (≈ cadence poll cũ)
_SSE_HEARTBEAT_S = 15.0   # heartbeat ": ping" giữ kết nối sống (proxy idle) khi eventRevision không đổi


def _sse_overlay_stream():
    """Generator SSE: PUSH snapshot overlay khi `eventRevision` đổi + heartbeat định kỳ.

    Đọc `_store` (authority) — KHÔNG mutate. Payload = CÙNG dict `project_overlay(...)` mà `/overlay` trả
    (không đổi schema/DTO). Freshness (epoch/lease) bảo toàn (Property 1). Bọc khung SSE `event:`/`data:`.
    """
    last_rev = None
    last_ping = time.monotonic()
    yield "retry: 2000\n\n"   # gợi ý EventSource khoảng reconnect khi đứt
    while True:
        emitted = False
        snap = _store.snapshot() if _store is not None else None
        if snap is not None:
            payload = project_overlay(snap, time.monotonic_ns(), _cfg.ghostSlaMs)
            rev = payload.get("eventRevision")
            if rev != last_rev:
                last_rev = rev
                yield f"event: overlay\ndata: {json.dumps(payload)}\n\n"
                last_ping = time.monotonic()
                emitted = True
        if not emitted and (time.monotonic() - last_ping >= _SSE_HEARTBEAT_S):
            last_ping = time.monotonic()
            yield ": ping\n\n"
        time.sleep(_SSE_TICK_S)


@app.route("/events")
def events():
    """SSE transport: 1 kết nối dài server-push (thay vòng poll `/overlay` ~14/s) → khi mất kết nối, trình
    duyệt chỉ log ~1 lỗi + `EventSource` tự reconnect (thay vì flood mỗi fetch hỏng, fix gốc K-119).
    ADDITIVE: `/overlay` poll GIỮ nguyên làm fallback (client tự chọn — cũng là đường suy giảm khi 503)."""
    busy = _admit_or_503("/events")
    if busy is not None:
        return busy
    resp = Response(stream_with_context(_released_after(_sse_overlay_stream())), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["X-Accel-Buffering"] = "no"   # tắt buffering reverse-proxy (nginx) cho streaming
    # KHÔNG set "Connection" — hop-by-hop header bị PEP 3333 CẤM trong WSGI app (waitress cưỡng chế,
    # werkzeug-dev bỏ qua). WSGI server tự quản keep-alive cho response streaming.
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
    # Phơi trạng thái bulkhead (D-152): tài nguyên CÓ TRẦN mà không quan sát được thì vận hành chỉ biết khi nó
    # ĐÃ từ chối (503). `streams=a/b` cho operator thấy mức bão hoà + phát hiện RÒ RỈ slot (a không về 0 khi
    # không còn viewer nào) — đây là cách kiểm rò rỉ trong soak dài, thay vì suy đoán.
    st = f" · streams={_admission.active}/{_admission.max_streams}" if _admission is not None else ""
    return f"video={_vframes} · detect={_dframes} · boxes={n} · overlay_rev={ev}{st}"


def _merge_detection(cli: dict, toml_det: Optional[DetectionCadenceConfig]) -> DetectionCadenceConfig:
    """Hợp nhất cadence TỪ cờ CLI ↔ section `[detection]` TOML (spec adaptive-detection-perf Task 5).

    Precedence: **CLI-explicit > TOML > built-in default** (tiền lệ observability D-086). Arg số dùng sentinel
    `None` (chưa gõ cờ → None → lấy TOML/default); `motion_gate` là store_true nên OR-semantics như `observe`
    (`--motion-gate` HOẶC TOML motion_gate=true → bật). Hạn chế v1 (Non-Goal, ghi rõ): không TẮT motion-gate
    qua CLI khi TOML bật. `motionRoi` chỉ từ TOML (CLI chưa có `--motion-roi`). `toml_det=None` → chỉ CLI/default.
    """
    t = toml_det or DetectionCadenceConfig()

    def pick(cli_key: str, toml_val):
        v = cli.get(cli_key)
        return toml_val if v is None else v

    return DetectionCadenceConfig(
        detectMinIntervalMs=pick("detect_min_interval_ms", t.detectMinIntervalMs),
        detectMaxIntervalMs=pick("detect_max_interval_ms", t.detectMaxIntervalMs),
        detectEveryN=pick("detect_every_n", t.detectEveryN),
        motionGate=bool(cli.get("motion_gate")) or t.motionGate,   # OR-semantics (store_true)
        motionPixelDiffThreshold=pick("motion_threshold", t.motionPixelDiffThreshold),
        motionMinAreaRatio=pick("motion_min_area", t.motionMinAreaRatio),
        motionMaxConsecutiveSkip=pick("motion_max_skip", t.motionMaxConsecutiveSkip),
        motionRoi=t.motionRoi,   # roi: TOML-only (CLI chưa expose --motion-roi)
        experimental=t.experimental,
    )


def main() -> int:
    global _store, _admission
    p = argparse.ArgumentParser(prog="vision_platform.profiles.vision_web_app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    # --- serving production (spec web-production-hardening Wave 1) ---
    p.add_argument("--server", default="auto", choices=["auto", "waitress", "dev"],
                   help="WSGI server: auto (waitress nếu cài, else dev+cảnh báo) | waitress (production, fail-fast) "
                        "| dev (werkzeug dev-server, chỉ local). Mặc định auto.")
    p.add_argument("--threads", type=int, default=8, help="số thread của waitress (chỉ khi --server waitress/auto).")
    # --- bulkhead kết nối streaming (Wave 2, ĐO #456): WSGI sync = 1 thread/kết nối; /stream + /events KHÔNG
    #     bao giờ kết thúc → cạn pool là MỌI request ngắn treo vô hạn. Trần tường minh + reserve → 503 thay hang.
    p.add_argument("--max-stream-conns", type=int, default=None,
                   help="trần kết nối streaming ĐỒNG THỜI (/stream + /events). Mặc định = --threads − reserve "
                        "(chừa thread cho /stats,/overlay,/). Vượt trần → 503 + Retry-After (client rơi về poll).")
    p.add_argument("--stream-reserve-threads", type=int, default=2,
                   help="số thread CHỪA cho request ngắn khi tự suy trần streaming (mặc định 2).")
    p.add_argument("--insecure", action="store_true",
                   help="CHO PHÉP bind non-loopback KHÔNG xác thực (rủi ro: ai cũng xem được camera). "
                        "Mặc định: phơi mạng bắt buộc đặt VP_WEB_USER/VP_WEB_PASS.")
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
    # --- điều tiết detect (adaptive-detection-perf) — mặc định = hành vi hiện tại (additive) ---
    # Cấu hình qua TOML `[detection]` (--config) + cờ CLI; precedence CLI-explicit > TOML > default (D-086).
    # Default = None (sentinel "chưa gõ cờ") để merge phân biệt CLI-explicit vs TOML — KHÔNG phải 0/1 (0/1 là
    # giá trị TOML/mặc định hợp lệ; nếu để default 0/1 thì không biết user có gõ hay không → TOML bị đè oan).
    p.add_argument("--config", type=str, default=None,
                   help="file .toml khai báo [detection] (min/max-interval, every-n, motion-gate...). "
                        "Cờ CLI đè TOML; TOML đè mặc định. Web app KHÔNG cần [[pipelines]].")
    p.add_argument("--detect-min-interval-ms", type=int, default=None,
                   help="ns tối thiểu giữa 2 detect (0=không giới hạn). Phải <= displayLeaseMs (chống giật).")
    p.add_argument("--detect-max-interval-ms", type=int, default=None,
                   help="HEARTBEAT: ép detect nếu quá lâu không detect (0=tắt). Phải <= displayLeaseMs "
                        "(chống mất box vật đứng-yên khi bật motion-gate). Nên đặt khi dùng --motion-gate.")
    p.add_argument("--detect-every-n", type=int, default=None, help="chỉ detect mỗi N frame-version (1=mọi frame)")
    p.add_argument("--motion-gate", action="store_true", help="bỏ detect khi cảnh tĩnh (tiết kiệm CPU)")
    p.add_argument("--motion-threshold", type=int, default=None, help="ngưỡng pixel đổi (0..255)")
    p.add_argument("--motion-min-area", type=float, default=None, help="tỉ lệ pixel đổi < ngưỡng → coi là tĩnh")
    p.add_argument("--motion-max-skip", type=int, default=None, help="sau N skip liên tiếp ép 1 detect (0=không ép)")
    # --- confidence hysteresis (chống flicker vật xa, K-106) — opt-in, mặc định tắt ---
    p.add_argument("--overlay-create-conf", type=float, default=0.0,
                   help="hysteresis: ngưỡng conf CAO để TẠO track mới (0=tắt). Chống bbox vật xa nhấp nháy.")
    p.add_argument("--overlay-sustain-conf", type=float, default=0.0,
                   help="hysteresis: ngưỡng conf THẤP để NUÔI track đã tồn tại (<=create). Bật thì decode conf tự hạ về đây.")
    p.add_argument("--overlay-evict-offframe", action="store_true",
                   help="motion: khi track bị miss, dự đoán tâm theo vận tốc — ra ngoài khung → xoá NGAY (chống ghost người đã đi qua).")
    p.add_argument("--overlay-motion", action="store_true",
                   help="BẬT motion model đầy đủ (mini-tracker): match theo vị trí DỰ ĐOÁN (chống flicker vật di chuyển) + off-frame evict (chống ghost). = predict-match + evict-offframe.")
    # --- S2 "tắt chậm" (Wave B): giảm displayLeaseMs = removal evidence-based (lease refresh từ lần khớp cuối
    # → lease CHÍNH LÀ time-since-update; maxAgeMs riêng = TRÙNG, không thêm). Mặc định None → giữ 600 (additive).
    p.add_argument("--overlay-display-lease-ms", type=int, default=None,
                   help="hạn giữ box sau lần khớp cuối (mặc định 600). Giảm (vd 350) → box tắt nhanh khi người rời (S2). Phải >= candidate-lease.")
    p.add_argument("--overlay-candidate-lease-ms", type=int, default=None,
                   help="hạn giữ candidate (mặc định 300). Hạ cùng khi display-lease < 300 (giữ candidate<=display).")
    p.add_argument("--coco-labels", action="store_true",
                   help="dùng 80 nhãn COCO (person/car/... thay chỉ số) — chỉ đúng cho model train COCO (vd yolov8n).")
    args = p.parse_args()

    if args.coco_labels and not args.labels:
        args.labels = _COCO80   # tên lớp đẹp cho model COCO (opt-in an toàn)

    global _cfg
    _cfg_kwargs = {}
    if args.overlay_create_conf > 0.0:
        # bật hysteresis: HẠ decode conf xuống sustain để box yếu tới được stabilizer.
        _cfg_kwargs.update(createConfThreshold=args.overlay_create_conf,
                           sustainConfThreshold=args.overlay_sustain_conf)
        if args.conf > args.overlay_sustain_conf:
            args.conf = args.overlay_sustain_conf
    if args.overlay_evict_offframe or args.overlay_motion:
        _cfg_kwargs["evictPredictedOffFrame"] = True
    if args.overlay_motion:
        _cfg_kwargs["matchUsePrediction"] = True
    if args.overlay_display_lease_ms is not None:      # S2 (Wave B): removal nhanh hơn = lease ngắn hơn
        _cfg_kwargs["displayLeaseMs"] = args.overlay_display_lease_ms
    if args.overlay_candidate_lease_ms is not None:
        _cfg_kwargs["candidateLeaseMs"] = args.overlay_candidate_lease_ms
    if _cfg_kwargs:
        _cfg = OverlayConfig(**_cfg_kwargs)

    global _cadence_cfg
    toml_det = load_detection_config(args.config) if args.config else None   # None → chỉ CLI/default (additive)
    _cadence_cfg = _merge_detection(
        {"detect_min_interval_ms": args.detect_min_interval_ms,
         "detect_max_interval_ms": args.detect_max_interval_ms,
         "detect_every_n": args.detect_every_n, "motion_gate": args.motion_gate,
         "motion_threshold": args.motion_threshold, "motion_min_area": args.motion_min_area,
         "motion_max_skip": args.motion_max_skip},
        toml_det)
    assert_cadence_fits_lease(_cadence_cfg, display_lease_ms=_cfg.displayLeaseMs)   # P5 fail-fast startup

    _store = OverlayStateStore(_PROCESS_EPOCH, 1, _cfg)

    # --- bulkhead streaming (Wave 2): trần tường minh + reserve thread cho request ngắn (ĐO #456) ---
    _max_streams = (args.max_stream_conns if args.max_stream_conns is not None
                    else capacity_from_threads(args.threads, reserve=args.stream_reserve_threads))
    _admission = StreamAdmission(_max_streams)
    print(f"[web] bulkhead streaming: trần {_max_streams} kết nối đồng thời "
          f"(threads={args.threads}, chừa {args.stream_reserve_threads} cho request ngắn) → "
          f"≈{max(1, _max_streams // 2)} viewer (mỗi viewer dùng /stream + /events); vượt trần → 503 + client rơi về poll")

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

    # --- access-control (Wave 2): Basic Auth bọc NGOÀI (phủ mọi route gồm /stream) + secure-default binding ---
    verify = make_env_verifier()                       # None nếu chưa đặt VP_WEB_USER/VP_WEB_PASS
    if verify is not None:
        app.wsgi_app = BasicAuthMiddleware(app.wsgi_app, verify)   # áp cho cả waitress lẫn dev (Flask.__call__→wsgi_app)
        print("[web] xác thực: Basic Auth BẬT (credential từ VP_WEB_USER/VP_WEB_PASS)")
    elif not is_loopback(args.host) and not args.insecure:
        raise SystemExit(
            f"[web] TỪ CHỐI khởi động: bind non-loopback ({args.host}) nhưng CHƯA đặt VP_WEB_USER/VP_WEB_PASS "
            f"→ web sẽ MỞ cho mọi người trong mạng. Đặt credential (khuyến nghị), hoặc --insecure để chấp nhận rủi ro.")
    elif not is_loopback(args.host):                   # args.insecure = True
        print(f"[web] ⚠️  CẢNH BÁO: phơi {args.host} KHÔNG xác thực (--insecure). "
              f"Ai truy cập host:port đều xem được camera. Chỉ dùng mạng nội bộ tin cậy + nên có TLS reverse-proxy.")

    # security headers NGOÀI CÙNG (Wave 3): phủ mọi response gồm 401 auth (chống clickjacking/MIME-sniff)
    app.wsgi_app = SecurityHeadersMiddleware(app.wsgi_app)

    serve_wsgi(app, args.host, args.port, threads=args.threads, server=args.server)   # WSGI production (Wave 1)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
