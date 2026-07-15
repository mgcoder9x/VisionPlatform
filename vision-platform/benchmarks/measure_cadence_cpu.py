"""measure_cadence_cpu — ĐO CPU% của detect-loop dưới các cadence khác nhau (R3.1, adaptive-detection-perf Task 0/7).

ĐO BẢN CHẤT: cadence điều tiết TẦN SUẤT gọi detector → giảm CPU của inference (nút cổ chai #395 = ~111ms/detect).
Harness TÁI DÙNG policy production `domain.detect_cadence.should_detect` (KHÔNG nhân bản logic → không drift) +
detector THẬT `DetectorPipeline(OnnxDetector)` (giống `vision_web_app._detect_loop`) trên frame synthetic (xác định).

Mô hình hoá: video-loop chạy độc lập ở `--video-fps` (mặc định 120) → `frame_version` tăng theo THỜI GIAN thực
(giống web app: video≫detect). detect-loop lấy version mới nhất, qua cổng `should_detect` (min-interval/every-n/
heartbeat) mới gọi detector. Đo CPU% tiến-trình (psutil — GỒM mọi thread onnxruntime) + detect/s thực qua cửa sổ.

⚠️ TRUNG THỰC: CPU% có nhiễu nền máy → chạy cửa sổ đủ dài; **DELTA giữa variant là tín hiệu** (cùng detector+frame,
chỉ khác cadence). Video/JPEG-encode CPU TRỰC GIAO (không đo — cadence không điều khiển nó). Cần `--onnx` (số THẬT);
không onnx → chỉ verify harness chạy (FakeDetector rẻ, không phản ánh tiết kiệm).
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import numpy as np

from vision_platform.domain.detect_cadence import should_detect
from vision_platform.domain.motion_gate import MotionGate

try:
    from benchmarks._env import collect_env, format_env
except ImportError:  # chạy trực tiếp trong thư mục benchmarks/
    from _env import collect_env, format_env   # type: ignore


def _synthetic_frame(h: int, w: int) -> np.ndarray:
    """Frame xác định (nội dung không ảnh hưởng min-interval; đủ để detector chạy đường thật)."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _build_onnx_detector(onnx: str, imgsz: int, yolo: str, layout: str, conf: float, labels: Optional[str]):
    """Dựng DetectorPipeline(OnnxDetector) ĐÚNG đường sản phẩm (letterbox+NMS) — CPU provider (baseline)."""
    from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize
    from vision_platform.adapters.yolo_postprocess import yolov5_decode, yolov8_decode
    from vision_platform.adapters.detector_pipeline import DetectorPipeline
    lbls = labels.split(",") if labels else None
    if yolo == "v8":
        def _post(raw):
            return yolov8_decode(raw, conf_threshold=conf, labels=lbls, layout=layout)
    else:
        def _post(raw):
            return yolov5_decode(raw, conf_threshold=conf, labels=lbls)
    inner = OnnxDetector(onnx, preprocess_fn=chw_float_normalize, postprocess_fn=_post,
                         providers=["CPUExecutionProvider"])
    return DetectorPipeline(inner, model_h=imgsz, model_w=imgsz)


def measure_one(detector, frame, *, min_interval_ms: int, max_interval_ms: int, every_n: int,
                motion_gate: bool, window_s: float, video_fps: float, proc) -> dict:
    """Chạy detect-loop mô-phỏng 1 cadence trong `window_s` giây → trả {detect_per_s, cpu_percent, detects}.

    Tái dùng NGUYÊN VĂN logic cổng của `vision_web_app._detect_loop` (should_detect + motion + heartbeat override).
    """
    min_interval_ns = min_interval_ms * 1_000_000
    max_interval_ns = max_interval_ms * 1_000_000
    mgate = MotionGate(pixel_diff_threshold=25, min_area_ratio=0.005,
                       max_consecutive_skip=0, roi=None) if motion_gate else None
    last_detect_ns: Optional[int] = None
    last_detect_version: Optional[int] = None
    detects = 0
    start = time.monotonic_ns()
    proc.cpu_percent()   # reset baseline psutil (lần đầu trả 0.0)
    end = start + int(window_s * 1e9)
    while True:
        now = time.monotonic_ns()
        if now >= end:
            break
        ver = int((now - start) / 1e9 * video_fps)   # video advance theo thời gian thực (độc lập detect)
        motion_ok = mgate.decide(frame)[0] if mgate is not None else True
        cad_ok, reason = should_detect(
            now_ns=now, last_detect_ns=last_detect_ns,
            frame_version=ver, last_detect_version=last_detect_version,
            min_interval_ns=min_interval_ns, every_n=every_n, max_interval_ns=max_interval_ns)
        run = True if reason == "MAX_INTERVAL" else (motion_ok and cad_ok)
        if not run:
            time.sleep(0.005)   # giống web app: nhường CPU khi bỏ detect
            continue
        detector.detect(frame)
        last_detect_ns = time.monotonic_ns()
        last_detect_version = ver
        detects += 1
    cpu = proc.cpu_percent()   # % trên cửa sổ vừa chạy (mọi thread)
    return {"detect_per_s": detects / window_s, "cpu_percent": cpu, "detects": detects}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="benchmarks.measure_cadence_cpu",
        description="Đo CPU% detect-loop theo cadence (R3.1). --onnx = số THẬT; DELTA giữa variant là tín hiệu.")
    p.add_argument("--onnx", default=None, help="path .onnx (BẮT BUỘC để có số thật; vắng → FakeDetector verify harness)")
    p.add_argument("--yolo", choices=["v5", "v8"], default="v8")
    p.add_argument("--layout", choices=["nc_first", "nc_last"], default="nc_first")
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--labels", default=None)
    p.add_argument("--model-size", type=int, default=640)
    p.add_argument("--frame-h", type=int, default=480)
    p.add_argument("--frame-w", type=int, default=640)
    p.add_argument("--video-fps", type=float, default=120.0, help="nhịp video mô phỏng (version tăng theo thời gian)")
    p.add_argument("--window", type=float, default=8.0, help="giây đo mỗi variant")
    p.add_argument("--warmup", type=float, default=2.5, help="giây warmup mỗi variant (JIT/cache, không tính)")
    p.add_argument("--min-intervals", default="0,200,500", help="danh sách min-interval-ms quét (phẩy)")
    p.add_argument("--also-motion-gate", action="store_true",
                   help="thêm 1 variant motion-gate ON (min-interval=0) — LƯU Ý frame synthetic tĩnh → skip mạnh")
    args = p.parse_args(argv)

    try:
        import psutil
    except Exception:
        print("LỖI: cần psutil (có trong extras dev). Dừng — KHÔNG tạo số giả.", file=sys.stderr)
        return 3

    env = collect_env(weight=None, imgsz=args.model_size)
    print("=== measure_cadence_cpu ===", file=sys.stderr)
    print(format_env(env), file=sys.stderr)

    is_real = bool(args.onnx)
    if not is_real:
        print("⚠️  KHÔNG --onnx → FakeDetector (rẻ) = CHỈ verify harness, KHÔNG phản ánh tiết kiệm CPU thật.",
              file=sys.stderr)
        from vision_platform.adapters.fake_detector import FakeDetector
        detector = FakeDetector()
    else:
        print("ℹ️  --onnx CPU → số THẬT của detector NN (CPU-baseline, không phải GPU).", file=sys.stderr)
        detector = _build_onnx_detector(args.onnx, args.model_size, args.yolo, args.layout, args.conf, args.labels)

    frame = _synthetic_frame(args.frame_h, args.frame_w)
    proc = psutil.Process()

    variants = []
    for tok in args.min_intervals.split(","):
        tok = tok.strip()
        if tok:
            variants.append({"label": f"min-interval={tok}ms", "min": int(tok), "max": 0, "every": 1, "motion": False})
    if args.also_motion_gate:
        variants.append({"label": "motion-gate ON (min=0)", "min": 0, "max": 0, "every": 1, "motion": True})

    detector.setup()
    results = []
    try:
        # warmup GLOBAL (nạp model + JIT) trước khi đo variant đầu
        w_end = time.monotonic_ns() + int(args.warmup * 1e9)
        while time.monotonic_ns() < w_end:
            detector.detect(frame)
        for v in variants:
            measure_one(detector, frame, min_interval_ms=v["min"], max_interval_ms=v["max"],
                        every_n=v["every"], motion_gate=v["motion"],
                        window_s=args.warmup, video_fps=args.video_fps, proc=proc)  # warmup per-variant (bỏ)
            r = measure_one(detector, frame, min_interval_ms=v["min"], max_interval_ms=v["max"],
                            every_n=v["every"], motion_gate=v["motion"],
                            window_s=args.window, video_fps=args.video_fps, proc=proc)
            r["label"] = v["label"]
            results.append(r)
    finally:
        detector.teardown()

    # --- Bảng kết quả (stdout) ---
    baseline_cpu = results[0]["cpu_percent"] if results else 0.0
    print("\n=== KẾT QUẢ (window={:.0f}s/variant · video-fps={:.0f} · frame {}x{} · onnx={}) ==="
          .format(args.window, args.video_fps, args.frame_h, args.frame_w, args.onnx or "FakeDetector"))
    print(f"{'cadence':<26} {'detect/s':>9} {'CPU%':>8} {'vs baseline CPU':>18}")
    for r in results:
        delta = ""
        if baseline_cpu > 0:
            saved = (baseline_cpu - r["cpu_percent"]) / baseline_cpu * 100.0
            delta = f"{saved:+.1f}% (giảm)" if saved >= 0 else f"{saved:+.1f}%"
        print(f"{r['label']:<26} {r['detect_per_s']:>9.2f} {r['cpu_percent']:>8.1f} {delta:>18}")
    if not is_real:
        print("(nhắc: FakeDetector — số CHỈ để kiểm harness, KHÔNG phải capacity/CPU thật.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
