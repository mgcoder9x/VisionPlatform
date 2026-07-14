"""vision_web_app — Web UI TÁCH LUỒNG: video (MJPEG) độc lập với detect (bbox JSON → browser vẽ overlay).

KIẾN TRÚC (đúng pattern VMS/analytics thật — decouple transport khỏi analytics):
- **Thread video** (`_video_loop`): đọc frame → encode JPEG → phát MJPEG. CHẠY FULL FPS CAMERA, KHÔNG chờ detect.
- **Thread detect** (`_detect_loop`): lấy frame MỚI NHẤT (dropping frame cũ) → detector → bbox chuẩn hoá 0–1 (JSON). Async.
- **Browser**: `<img src=/stream>` (video mượt) + `<canvas>` overlay; JS poll `/boxes` (JSON) rồi tự VẼ box.

→ Video KHÔNG bị detect làm chậm. Detect chậm chỉ làm box cập nhật thưa hơn, video vẫn mượt.
Đánh đổi: browser không phát RTSP trực tiếp → server VẪN transcode RTSP→MJPEG; box trễ nhẹ = độ trễ detect.

⚠️ Flask dev-server + không auth — chỉ demo/nội bộ (bảo mật hoãn).
"""
from __future__ import annotations

import argparse
import threading
import time
from typing import Optional

import cv2

from flask import Flask, Response, jsonify

from vision_platform.profiles.vision_demo_app import moving_square_frame, _build_detector
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
from vision_platform.adapters.rtsp_frame_source import RtspFrameSource, mask_rtsp
from vision_platform.adapters.webcam_frame_source import WebcamFrameSource
from vision_platform.kernel.read_result import ReadStatus

app = Flask(__name__)
_lock = threading.Lock()
_jpeg: Optional[bytes] = None      # frame video mới nhất (JPEG) — cho /stream
_raw = None                        # frame RAW mới nhất (np.ndarray) — cho detect thread
_raw_ver = 0                       # phiên bản frame RAW (đếm tăng) — detect dùng để bỏ frame trùng (không dùng id())
_boxes: list = []                  # bbox chuẩn hoá 0–1 mới nhất — cho /boxes
_vframes = 0
_dframes = 0
_stop = threading.Event()

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Vision Platform — Live</title>
<style>body{background:#111;color:#eee;font-family:sans-serif;text-align:center;margin:0;padding:10px}
#wrap{position:relative;display:inline-block}#v{max-width:98vw;display:block;border:1px solid #444}
#c{position:absolute;left:0;top:0;pointer-events:none}</style></head>
<body><h3>Vision Platform — video + nhận diện (overlay)</h3>
<div id="wrap"><img id="v" src="/stream"><canvas id="c"></canvas></div>
<p id="s"></p>
<script>
const img=document.getElementById('v'),cv=document.getElementById('c'),ctx=cv.getContext('2d');
// CHỐNG NHẤP NHÁY: giữ box cuối trong HOLD_MS (detect ~8fps < redraw) + fetch TRƯỚC rồi mới clear+draw.
let lastBoxes=[],lastSeen=0;const HOLD_MS=500;
async function tick(){
  let bs=null;
  try{bs=await(await fetch('/boxes',{cache:'no-store'})).json();}catch(e){bs=null;}   // fetch TRƯỚC (canvas chưa xoá)
  const now=performance.now();
  if(bs&&bs.length){lastBoxes=bs;lastSeen=now;}          // có box mới → cập nhật + mốc thời gian
  const draw=(now-lastSeen<=HOLD_MS)?lastBoxes:[];        // giữ box cuối tới HOLD_MS (lấp gián đoạn detect)
  if(cv.width!==img.clientWidth||cv.height!==img.clientHeight){cv.width=img.clientWidth;cv.height=img.clientHeight;}  // resize CHỈ khi đổi
  ctx.clearRect(0,0,cv.width,cv.height);                  // clear + draw SÁT nhau (không await ở giữa → không chớp)
  ctx.strokeStyle='#00ff66';ctx.lineWidth=2;ctx.font='16px sans-serif';ctx.fillStyle='#00ff66';
  for(const b of draw){const x=b.x*cv.width,y=b.y*cv.height,w=b.w*cv.width,h=b.h*cv.height;
    ctx.strokeRect(x,y,w,h);ctx.fillText(b.label+' '+b.conf,x,Math.max(12,y-4));}
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
        s = WebcamFrameSource(args.camera); s.setup(); return s   # webcam cục bộ theo index
    return None   # synthetic


def _video_loop(args) -> None:
    """Đọc frame → cập nhật RAW (cho detect) + encode JPEG (cho stream). KHÔNG detect ở đây."""
    global _jpeg, _raw, _raw_ver, _vframes
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
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
            if ok:
                with _lock:
                    _raw = frame
                    _raw_ver += 1
                    _jpeg = buf.tobytes()
                    _vframes += 1
            if args.pace > 0:
                time.sleep(args.pace)
    finally:
        if src is not None:
            src.teardown()


def _detect_loop(args) -> None:
    """Lấy frame RAW mới nhất (drop frame cũ) → detect → bbox chuẩn hoá 0–1. CHẠY ĐỘC LẬP video."""
    global _boxes, _dframes
    detector = _build_detector(args)
    detector.setup()
    last_ver = -1
    errors = 0
    try:
        while not _stop.is_set():
            with _lock:
                frame = _raw
                ver = _raw_ver
            if frame is None or ver == last_ver:
                time.sleep(0.005)          # chưa có frame MỚI → chờ ngắn (drop frame cũ, không xử lý lại)
                continue
            last_ver = ver
            # BULKHEAD (K-024): 1 lỗi inference (frame lỗi / CUDA hiccup) KHÔNG được giết detect thread.
            try:
                h, w = frame.shape[:2]
                dets = detector.detect(frame)
                boxes = [
                    {"label": d.label, "conf": round(float(d.confidence), 2),
                     "x": d.box.x / w, "y": d.box.y / h, "w": d.box.w / w, "h": d.box.h / h}
                    for d in dets
                ]
                with _lock:
                    _boxes = boxes
                    _dframes += 1
                errors = 0
            except Exception as e:
                errors += 1
                print(f"[web] detect error #{errors}: {type(e).__qualname__}: {e}", flush=True)
                time.sleep(0.3)
                if errors >= 3:
                    # Lỗi dai (vd CUDA context hỏng) → thử KHÔI PHỤC: reload detector.
                    print("[web] detect: thử khôi phục detector (reload)...", flush=True)
                    try:
                        detector.teardown()
                        detector.setup()
                        errors = 0
                    except Exception as e2:
                        print(f"[web] khôi phục thất bại: {e2}", flush=True)
                        time.sleep(2.0)
    finally:
        try:
            detector.teardown()
        except Exception:
            pass


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


@app.route("/boxes")
def boxes():
    with _lock:
        return jsonify(_boxes)


@app.route("/stats")
def stats():
    with _lock:
        return f"video={_vframes} · detect={_dframes} · boxes={len(_boxes)}"


def main() -> int:
    p = argparse.ArgumentParser(prog="vision_platform.profiles.vision_web_app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--height", type=int, default=240)
    p.add_argument("--width", type=int, default=320)
    p.add_argument("--pace", type=float, default=0.0, help="Trễ giữa frame video (s); 0 = full fps")
    p.add_argument("--quality", type=int, default=70, help="JPEG quality stream (thấp = nhẹ băng thông)")
    p.add_argument("--threshold", type=int, default=127)
    p.add_argument("--video", type=str, default=None)
    p.add_argument("--rtsp", type=str, default=None)
    p.add_argument("--camera", type=int, default=None, help="index webcam cục bộ (0,1,...) — cv2.VideoCapture")
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
    args = p.parse_args()

    src_name = (f"rtsp={mask_rtsp(args.rtsp)}" if args.rtsp else
                f"video={args.video}" if args.video else
                f"webcam={args.camera}" if args.camera is not None else
                f"synthetic {args.height}x{args.width}")
    det_name = (f"Yolov5PtDetector({args.pt},dev={args.device})" if args.pt else
                f"OnnxDetector({args.onnx})" if args.onnx else f"BrightBlobDetector({args.threshold})")
    print(f"[web] TÁCH LUỒNG · nguồn={src_name} · detector={det_name}")
    print(f"[web] Mở: http://{args.host}:{args.port}/")

    import logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)   # tắt spam access-log /boxes

    threading.Thread(target=_video_loop, args=(args,), daemon=True).start()
    threading.Thread(target=_detect_loop, args=(args,), daemon=True).start()
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
