"""vision_demo_app — APP DEMO trực quan: xem LUỒNG frame + cách VẼ BOX nhận diện. Layer: profiles.

Mục đích (user yêu cầu "app đơn giản xem luồng camera + cách nhận diện"): dựng 1 vòng
  nguồn frame → DetectorPipeline(detector) → vẽ box + nhãn lên frame → hiển thị/lưu.

2 chế độ xem:
  --save DIR   : lưu từng frame đã vẽ box ra PNG (chạy headless, verify được — KHÔNG cần màn hình).
  --show       : cửa sổ LIVE (cv2.imshow) — bạn chạy để xem realtime.

Nguồn (v1 chưa có camera thật): ô vuông sáng DI CHUYỂN (synthetic) → `BrightBlobDetector` bám theo → thấy
"nhận diện" trực quan. Khi có camera: dùng `--camera 0` (webcam) / `--rtsp URL` (cv2.VideoCapture).
Khi có weight YOLO: `--onnx path.onnx --labels a,b,c` → SWAP sang OnnxDetector+yolov8_decode, KHUNG GIỮ NGUYÊN.

⚠️ FakeDetector/BrightBlobDetector chỉ minh hoạ LUỒNG + cách vẽ; nhận diện THẬT (bám vật đa lớp) cần YOLO.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

import cv2
import numpy as np

from vision_platform.kernel.read_result import ReadStatus
from vision_platform.adapters.blob_detector import BrightBlobDetector
from vision_platform.adapters.detector_pipeline import DetectorPipeline
from vision_platform.adapters.rtsp_frame_source import RtspFrameSource
from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource


# ------------------------------------------------------------------ nguồn frame demo

def moving_square_frame(i: int, h: int, w: int, sq: Optional[int] = None, step: Optional[int] = None) -> np.ndarray:
    """Frame HxWx3 (uint8): ô vuông sáng di chuyển ngang (vật để 'nhận diện').

    Nền XÁM nhạt (đỡ đen thui) + ô SÁNG to. `step` = px dịch mỗi frame (nhỏ = chậm, dễ nhìn).
    """
    sq = sq or max(8, min(h, w) // 3)
    step = step or max(1, w // 40)                         # chậm: quét ngang trong ~40 frame
    frame = np.full((h, w, 3), 30, dtype=np.uint8)         # nền xám 30 (< ngưỡng 127 → không bị detect)
    max_x = max(0, w - sq)
    x = (i * step) % (max_x + 1) if max_x > 0 else 0
    y = max(0, (h - sq) // 2)
    frame[y:y + sq, x:x + sq] = 255                        # ô trắng (> 127 → BrightBlobDetector bắt)
    return frame


# ------------------------------------------------------------------ vẽ box

def draw_detections(frame: np.ndarray, dets) -> np.ndarray:
    """Vẽ box (xanh) + nhãn+conf lên frame (box ở ORIGINAL_FRAME sau DetectorPipeline). Trả ảnh mới."""
    img = frame.copy()
    for d in dets:
        b = d.box
        x0, y0 = int(round(b.x)), int(round(b.y))
        x1, y1 = int(round(b.x + b.w)), int(round(b.y + b.h))
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 0), 1)
        cv2.putText(img, f"{d.label} {d.confidence:.2f}", (x0, max(8, y0 - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)
    return img


# ------------------------------------------------------------------ dựng detector (swap-ready)

def _build_detector(args):
    """--pt → Yolov5PtDetector (chạy thẳng .pt, box ORIGINAL_FRAME, KHÔNG bọc pipeline). --onnx → OnnxDetector+decode.
    Mặc định → BrightBlobDetector qua DetectorPipeline."""
    if getattr(args, "pt", None):
        from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
        return Yolov5PtDetector(args.pt, device=getattr(args, "device", "cpu"),
                                conf=args.conf, iou=args.iou)
    if args.onnx:
        import sys
        from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize, onnx_providers_for
        from vision_platform.adapters.capability_probe import probe_capabilities
        from vision_platform.adapters.yolo_postprocess import yolov5_decode, yolov8_decode
        from vision_platform.adapters.label_map_loader import load_label_map
        labels = args.labels.split(",") if args.labels else None
        ver = getattr(args, "yolo", "v5")
        # LabelMap 1-nguồn (R1/D-162): `.names`/metadata cạnh weights → config `labels` → rỗng; fail-safe
        # idx-lạ → `class_<id>`. Đây là choke-point CHUNG cho cả web app sản phẩm (gọi `_build_detector`).
        label_map = load_label_map(args.onnx, labels)

        if ver == "v8":
            def _post(raw):
                return yolov8_decode(raw, conf_threshold=args.conf, label_map=label_map, layout=args.layout)
        else:   # v5 (mặc định — weight user là YOLOv5): output có objectness
            def _post(raw):
                return yolov5_decode(raw, conf_threshold=args.conf, label_map=label_map)

        # Capability-aware ONNX (F3.2/D-139): trước đây nhánh onnx BỎ QUA --device → luôn CPU (không GPU
        # được kể cả trên máy GPU). Nay đi qua resolve_device (đối xứng .pt + _det_onnx): hỗ trợ 'auto',
        # fail-fast khi 'cuda' mà máy không CUDA, + LOG device THẬT. 1 chính sách device chung mọi đường ONNX.
        caps = probe_capabilities()
        providers, dev = onnx_providers_for(getattr(args, "device", "cpu"), caps)
        print(f"[device] onnx yêu cầu={getattr(args, 'device', 'cpu')!r} → dùng={dev!r} "
              f"(has_cuda={caps.has_cuda}, gpu={caps.gpu_name})", file=sys.stderr)
        inner = OnnxDetector(args.onnx, preprocess_fn=chw_float_normalize, postprocess_fn=_post,
                             providers=providers, expected_input_size=getattr(args, "model_size", None))
        return DetectorPipeline(inner, model_h=args.model_size, model_w=args.model_size, nms_iou=args.iou)
    # Demo mặc định: model = kích thước frame (letterbox identity → box bám vật chính xác).
    return DetectorPipeline(BrightBlobDetector(threshold=args.threshold),
                            model_h=args.height, model_w=args.width)


# ------------------------------------------------------------------ vòng chạy

def run_demo(detector, source_iter, *, save_dir: Optional[str] = None, show: bool = False,
             delay_ms: int = 60) -> dict:
    """Chạy: mỗi frame → detect → vẽ → lưu/hiện. Trả {frames, frames_with_detection}."""
    detector.setup()
    frames = det_frames = 0
    try:
        for frame in source_iter:
            dets = detector.detect(frame)
            annotated = draw_detections(frame, dets)
            frames += 1
            det_frames += 1 if dets else 0
            if save_dir:
                cv2.imwrite(os.path.join(save_dir, f"frame_{frames:03d}.png"), annotated)
            if show:
                cv2.imshow("vision-demo (q=thoat)", annotated)
                if (cv2.waitKey(delay_ms) & 0xFF) == ord("q"):
                    break
    finally:
        detector.teardown()
        if show:
            cv2.destroyAllWindows()
    return {"frames": frames, "frames_with_detection": det_frames}


def _synthetic_source(n: int, h: int, w: int):
    for i in range(n):
        yield moving_square_frame(i, h, w)


def _rtsp_source(url: str, n: int, max_reconnect=None):
    """Nguồn RTSP qua RtspFrameSource (tự reconnect). Bỏ frame RECONNECTING, dừng nếu ERROR. Bọc safety cap."""
    src = RtspFrameSource(url, max_reconnect=max_reconnect)
    src.setup()
    got = 0
    safety = n + (max_reconnect or 5) + 5      # chống vòng vô hạn nếu toàn reconnect
    try:
        while got < n and safety > 0:
            safety -= 1
            r = src.read()
            if r.has_data:
                got += 1
                yield r.data
            elif r.status == ReadStatus.ERROR:
                print(f"[demo] RTSP lỗi (dừng): {r.error}")
                break
            # RECONNECTING → thử tiếp
    finally:
        src.teardown()


def _videofile_source(path: str, n: int):
    """Nguồn file video qua VideoFileFrameSource. Dừng khi đủ n frame hoặc EOF."""
    src = VideoFileFrameSource(path)
    src.setup()
    got = 0
    try:
        while got < n:
            r = src.read()
            if r.status == ReadStatus.EOF:
                break
            if r.has_data:
                got += 1
                yield r.data
    finally:
        src.teardown()


def _camera_source(spec, n: int):
    """spec = index webcam (int) hoặc URL rtsp (str). Đọc tối đa n frame."""
    cap = cv2.VideoCapture(int(spec) if str(spec).isdigit() else spec)
    if not cap.isOpened():
        raise RuntimeError(f"Không mở được nguồn camera: {spec}")
    try:
        for _ in range(n):
            ok, frame = cap.read()
            if not ok:
                break
            yield frame
    finally:
        cap.release()


def main() -> int:
    p = argparse.ArgumentParser(prog="vision_platform.profiles.vision_demo_app")
    p.add_argument("--frames", type=int, default=30, help="Số frame chạy")
    p.add_argument("--height", type=int, default=120)
    p.add_argument("--width", type=int, default=160)
    p.add_argument("--threshold", type=int, default=127, help="Ngưỡng sáng cho BrightBlobDetector")
    p.add_argument("--save", type=str, default=None, help="Thư mục lưu PNG đã vẽ box (headless)")
    p.add_argument("--show", action="store_true", help="Cửa sổ live cv2.imshow")
    p.add_argument("--camera", type=str, default=None, help="Index webcam (0) — cv2.VideoCapture trực tiếp")
    p.add_argument("--rtsp", type=str, default=None, help="URL rtsp:// (qua RtspFrameSource tự reconnect)")
    p.add_argument("--video", type=str, default=None, help="Đường dẫn FILE video (mp4/avi) — chạy detect trên clip quay sẵn")
    p.add_argument("--max-reconnect", type=int, default=None, help="Giới hạn lần reconnect RTSP (None=vô hạn)")
    # YOLO thật (khi có weight):
    p.add_argument("--pt", type=str, default=None, help="Đường dẫn weight .pt YOLOv5 (chạy thẳng, cần env có torch+yolov5)")
    p.add_argument("--device", type=str, default="cpu", help="cpu / cuda cho .pt")
    p.add_argument("--onnx", type=str, default=None, help="Đường dẫn model .onnx YOLO")
    p.add_argument("--labels", type=str, default=None, help="Nhãn lớp, phân tách dấu phẩy")
    p.add_argument("--model-size", type=int, default=640, help="Input size model YOLO")
    p.add_argument("--layout", type=str, default="nc_first", choices=["nc_first", "nc_last"])
    p.add_argument("--yolo", type=str, default="v5", choices=["v5", "v8"], help="Phiên bản YOLO của .onnx (weight user = v5)")
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.5)
    p.add_argument("--delay", type=int, default=120, help="Nhịp trễ giữa frame (ms) khi --show (lớn = chậm, dễ nhìn)")
    args = p.parse_args()

    if args.save:
        os.makedirs(args.save, exist_ok=True)
    if not args.save and not args.show:
        print("[demo] Chưa chọn --save DIR hay --show → mặc định lưu vào ./demo_frames")
        args.save = "demo_frames"
        os.makedirs(args.save, exist_ok=True)

    detector = _build_detector(args)
    if args.video is not None:
        source = _videofile_source(args.video, args.frames)
        src_name = f"video={args.video}"
    elif args.rtsp is not None:
        source = _rtsp_source(args.rtsp, args.frames, max_reconnect=args.max_reconnect)
        from vision_platform.adapters.rtsp_frame_source import mask_rtsp
        src_name = f"rtsp={mask_rtsp(args.rtsp)}"
    elif args.camera is not None:
        source = _camera_source(args.camera, args.frames)
        src_name = f"camera={args.camera}"
    else:
        source = _synthetic_source(args.frames, args.height, args.width)
        src_name = f"synthetic {args.height}x{args.width} (ô vuông sáng di chuyển)"
    det_name = f"OnnxDetector({args.onnx})" if args.onnx else f"BrightBlobDetector(thr={args.threshold})"

    print(f"[demo] nguồn={src_name} · detector={det_name} · frames={args.frames}")
    stats = run_demo(detector, source, save_dir=args.save, show=args.show, delay_ms=args.delay)
    print(f"[demo] xong: {stats['frames']} frame · {stats['frames_with_detection']} frame CÓ box nhận diện")
    if args.save:
        print(f"[demo] Ảnh đã vẽ box lưu ở: {os.path.abspath(args.save)} (mở xem luồng + box)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
