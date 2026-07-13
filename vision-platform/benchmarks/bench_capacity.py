"""bench_capacity — đo công suất 1-node (C_inf/C_dec/combined/latency) theo spec node-capacity-benchmark.

Hàm đo TÁCH BIỆT + nhận component TIÊM VÀO (detector/source/infer_batch_fn/sync_fn) → verify LOGIC được
trên máy dev với Fake* (không cần GPU). CLI `main()` wire component THẬT (Yolov5PtDetector/VideoFileFrameSource)
lazy theo --device (chỉ import torch khi cuda) + STAMP môi trường.

⚠️ TRUNG THỰC (K-047 · Property 5): chạy `--device cpu`/fake = VERIFY LOGIC, KHÔNG phải số capacity. Số capacity
thật CHỈ đo `--device cuda` trên máy GPU. Ô chưa đo = '[chưa đo]', KHÔNG bịa.

Lifecycle: các hàm measure_* GIẢ ĐỊNH detector/source ĐÃ setup() (caller quản vòng đời) — để test tiêm dễ.
Mốc thời gian: `perf_counter_ns` (đơn điệu). GPU async → truyền `sync_fn=torch.cuda.synchronize` (Property 2).
"""
from __future__ import annotations

import argparse
import sys
from time import perf_counter_ns
from typing import Callable, Optional, Sequence

import numpy as np

from vision_platform.kernel.read_result import ReadStatus

# Import nội bộ package (chạy qua `python -m benchmarks.bench_capacity` từ vision-platform/).
try:
    from benchmarks._stats import Stats, summarize, batch_throughput_per_s
    from benchmarks._env import collect_env, format_env
except ImportError:  # chạy trực tiếp trong thư mục benchmarks/
    from _stats import Stats, summarize, batch_throughput_per_s   # type: ignore
    from _env import collect_env, format_env                       # type: ignore


# ---------------- Hàm đo (DI — test được với Fake trên CPU) ----------------

def measure_infer(detector, frame: np.ndarray, *, count: int, warmup: int,
                  sync_fn: Optional[Callable[[], None]] = None) -> Stats:
    """Đo inference TỪNG-FRAME (batch=1) trên 1 frame dựng-sẵn (cô lập khỏi decode). detector ĐÃ setup()."""
    samples: list[int] = []
    for _ in range(count):
        t0 = perf_counter_ns()
        detector.detect(frame)
        if sync_fn is not None:
            sync_fn()
        samples.append(perf_counter_ns() - t0)
    return summarize(samples, warmup=warmup)


def measure_infer_batch(infer_batch_fn: Callable[[Sequence[np.ndarray]], object],
                        frames: Sequence[np.ndarray], *, batch: int, n_batches: int, warmup: int,
                        sync_fn: Optional[Callable[[], None]] = None) -> tuple[Stats, float]:
    """Đo inference THEO BATCH qua model nền (IDetector.detect theo-frame → batch phải gọi model = lỗ A1).

    `infer_batch_fn(list_frame)` chạy 1 batch. Trả (Stats latency-mỗi-batch, ảnh/giây). Test tiêm fn giả.
    """
    if batch < 1:
        raise ValueError("batch >= 1")
    if not frames:
        raise ValueError("cần >=1 frame")
    samples: list[int] = []
    for i in range(n_batches):
        imgs = [frames[(i * batch + j) % len(frames)] for j in range(batch)]
        t0 = perf_counter_ns()
        infer_batch_fn(imgs)
        if sync_fn is not None:
            sync_fn()
        samples.append(perf_counter_ns() - t0)
    stats = summarize(samples, warmup=warmup)
    kept = samples[warmup:]
    imgs_per_s = batch_throughput_per_s(len(kept), batch, sum(kept)) if kept else 0.0
    return stats, imgs_per_s


def measure_decode(source, *, count: int, warmup: int) -> Stats:
    """Đo decode fps qua nguồn thật (source ĐÃ setup()). Chỉ đọc, KHÔNG inference. Dừng sớm nếu EOF."""
    samples: list[int] = []
    got = 0
    while got < count:
        t0 = perf_counter_ns()
        r = source.read()
        dt = perf_counter_ns() - t0
        if r.status == ReadStatus.FRAME and r.has_data:
            samples.append(dt)
            got += 1
        elif r.status == ReadStatus.EOF and source.is_finite:
            break
        # TIMEOUT/RECONNECTING/ERROR/EOF-vô-hạn → bỏ qua, đọc tiếp
    return summarize(samples, warmup=warmup)


def measure_latency(detector, source, *, count: int, warmup: int,
                    sync_fn: Optional[Callable[[], None]] = None) -> Stats:
    """Đo latency ingest→detections mỗi frame (M4): t0 khi CÓ frame → detect → t1. detector+source ĐÃ setup()."""
    samples: list[int] = []
    got = 0
    while got < count:
        r = source.read()
        if r.status == ReadStatus.FRAME and r.has_data:
            t0 = perf_counter_ns()
            detector.detect(r.data)
            if sync_fn is not None:
                sync_fn()
            samples.append(perf_counter_ns() - t0)
            got += 1
        elif r.status == ReadStatus.EOF and source.is_finite:
            break
    return summarize(samples, warmup=warmup)


# ---------------- CLI (wire component THẬT — không unit-test, cần GPU cho số thật) ----------------

def _one_synthetic_frame(imgsz: int) -> np.ndarray:
    return np.full((imgsz, imgsz, 3), 128, dtype=np.uint8)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="benchmarks.bench_capacity",
                                description="Đo capacity 1-node (spec node-capacity-benchmark). "
                                            "device=cpu = VERIFY LOGIC (không phải số capacity).")
    p.add_argument("--mode", choices=["infer", "decode", "latency"], default="infer")
    p.add_argument("--device", default="cpu", help="cpu (verify logic, Fake) | cuda (số thật, máy GPU)")
    p.add_argument("--weights", default=None, help="path .pt YOLOv5 (khi --device cuda)")
    p.add_argument("--onnx", default=None,
                   help="path .onnx → đo detector NN THẬT qua onnxruntime (CPU/GPU tùy provider). "
                        "Số này LÀ capacity THẬT của detector (khác Fake), nhãn rõ CPU-baseline nếu chạy CPU.")
    p.add_argument("--labels", default=None, help="nhãn lớp phân tách phẩy (khi --onnx, tùy chọn)")
    p.add_argument("--yolo", choices=["v5", "v8"], default="v8", help="phiên bản decode cho --onnx")
    p.add_argument("--layout", choices=["nc_first", "nc_last"], default="nc_first",
                   help="layout output cho --onnx --yolo v8")
    p.add_argument("--conf", type=float, default=0.25, help="ngưỡng conf decode (khi --onnx)")
    p.add_argument("--video", default=None, help="path video (mode decode/latency)")
    p.add_argument("--rtsp", default=None, help="url rtsp (mode decode/latency)")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--warmup", type=int, default=20)
    p.add_argument("--measure", type=int, default=200)
    args = p.parse_args(argv)

    env = collect_env(weight=args.weights, imgsz=args.imgsz)
    print("=== bench_capacity ===", file=sys.stderr)
    print(format_env(env), file=sys.stderr)

    # "Số THẬT" khi: (a) detector NN qua ONNX (onnxruntime chạy model thật, kể cả CPU), HOẶC
    # (b) --device cuda (Yolov5Pt trên GPU). Fake/cpu-không-onnx = chỉ verify logic harness.
    is_real = bool(args.onnx) or (args.device not in ("cpu", "fake"))
    onnx_cpu_baseline = bool(args.onnx) and args.device in ("cpu", "fake")
    if not is_real:
        print("⚠️  device=cpu/fake → ĐÂY LÀ VERIFY LOGIC HARNESS, KHÔNG PHẢI SỐ CAPACITY. "
              "Số capacity thật phải chạy --device cuda (GPU) hoặc --onnx (detector NN thật) (K-047).",
              file=sys.stderr)
    if onnx_cpu_baseline:
        print("ℹ️  --onnx trên CPU → SỐ THẬT của detector (khác Fake) nhưng là CPU-BASELINE, "
              "KHÔNG phải đích production GPU. Nhãn số rõ 'CPU'.", file=sys.stderr)

    # --- Dựng detector ---
    sync_fn = None
    if args.onnx:
        # Đo ĐÚNG đường sản phẩm: DetectorPipeline(OnnxDetector) — letterbox + NMS + inverse-transform.
        from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize
        from vision_platform.adapters.yolo_postprocess import yolov5_decode, yolov8_decode
        from vision_platform.adapters.detector_pipeline import DetectorPipeline
        labels = args.labels.split(",") if args.labels else None
        if args.yolo == "v8":
            def _post(raw):
                return yolov8_decode(raw, conf_threshold=args.conf, labels=labels, layout=args.layout)
        else:
            def _post(raw):
                return yolov5_decode(raw, conf_threshold=args.conf, labels=labels)
        inner = OnnxDetector(args.onnx, preprocess_fn=chw_float_normalize, postprocess_fn=_post)
        detector = DetectorPipeline(inner, model_h=args.imgsz, model_w=args.imgsz)
        # onnxruntime CPU đồng bộ (blocking) → KHÔNG cần sync_fn.
    elif is_real:
        if not args.weights:
            p.error("--device cuda cần --weights <path.pt>")
        try:
            import torch  # noqa: F401
        except Exception:
            print("LỖI: --device cuda cần torch (env .[pt]) + GPU. Máy này không có → dừng (K-047). "
                  "KHÔNG tạo số giả.", file=sys.stderr)
            return 3
        from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
        detector = Yolov5PtDetector(args.weights, device=args.device)
        import torch as _t
        sync_fn = _t.cuda.synchronize if _t.cuda.is_available() else None
        if sync_fn is None:
            print("CẢNH BÁO: torch.cuda.is_available()=False → số KHÔNG phải GPU thật. Dừng.", file=sys.stderr)
            return 3
    else:
        from vision_platform.adapters.fake_detector import FakeDetector
        detector = FakeDetector()

    # --- Dựng source (mode decode/latency) ---
    def _build_source():
        if args.video:
            from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
            return VideoFileFrameSource(args.video)
        if args.rtsp:
            from vision_platform.adapters.rtsp_frame_source import RtspFrameSource
            return RtspFrameSource(args.rtsp)
        from vision_platform.adapters.fake_frame_source import FakeFrameSource
        return FakeFrameSource(width=args.imgsz, height=args.imgsz, max_frames=args.warmup + args.measure + 5)

    try:
        if args.mode == "infer":
            detector.setup()
            try:
                frame = _one_synthetic_frame(args.imgsz)
                stats = measure_infer(detector, frame, count=args.warmup + args.measure,
                                      warmup=args.warmup, sync_fn=sync_fn)
                print(f"[infer batch=1] {stats.as_row()}", file=sys.stderr)
                print(f"  → C_inf(batch1) ≈ {stats.throughput_per_s:.2f} infer/s", file=sys.stderr)
            finally:
                detector.teardown()
        elif args.mode == "decode":
            src = _build_source()
            src.setup()
            try:
                stats = measure_decode(src, count=args.warmup + args.measure, warmup=args.warmup)
                print(f"[decode] {stats.as_row()}", file=sys.stderr)
                print(f"  → C_dec ≈ {stats.throughput_per_s:.2f} frame/s "
                      f"({'cv2' if (args.video or args.rtsp) else 'fake'})", file=sys.stderr)
            finally:
                src.teardown()
        else:  # latency
            src = _build_source()
            src.setup(); detector.setup()
            try:
                stats = measure_latency(detector, src, count=args.warmup + args.measure,
                                        warmup=args.warmup, sync_fn=sync_fn)
                print(f"[latency ingest→detections] {stats.as_row()}", file=sys.stderr)
            finally:
                detector.teardown(); src.teardown()
    except Exception as e:  # noqa: BLE001 — công cụ đo: báo lỗi rõ, không tạo số giả
        print(f"LỖI đo ({type(e).__name__}): {e}", file=sys.stderr)
        return 1

    if not is_real:
        print("(nhắc lại: số trên là của Fake* — chỉ để kiểm harness chạy đúng, KHÔNG dùng làm capacity.)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
