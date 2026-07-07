"""vision_slice_app — composition root cho lát cắt dọc: source → DetectStage → CountStage → sink.

Chạy qua PipelineRunner. Chế độ CI/dev: fake/noise + FakeDetector (xác định). Chế độ THẬT (ngoài CI):
--source video|rtsp + --detector pt (tái dùng adapter đã có). Lưu trữ optional qua --out (JsonlEventSink).

Lưu ý (design §Giới hạn SYNC vs LIVE): runner v1 đồng bộ — hợp video/synthetic (throughput). --rtsp = kiểm
chức năng, KHÔNG phải real-time (detect chặn read). Low-latency live = biến thể async sau.
"""
from __future__ import annotations

import argparse
import sys

from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.composite_sink import CompositeSink
from vision_platform.runtime.stages.detect_stage import DetectStage
from vision_platform.runtime.stages.count_stage import CountStage


def _build_source(args):
    if args.source == "fake":
        from vision_platform.adapters.fake_frame_source import FakeFrameSource
        return FakeFrameSource(max_frames=args.frames)
    if args.source == "noise":
        from vision_platform.adapters.noise_frame_source import NoiseFrameSource
        return NoiseFrameSource(max_frames=args.frames)
    if args.source == "video":
        from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
        return VideoFileFrameSource(args.video)
    if args.source == "rtsp":
        from vision_platform.adapters.rtsp_frame_source import RtspFrameSource
        return RtspFrameSource(args.rtsp, max_reconnect=args.max_reconnect)
    raise ValueError(f"nguồn không hỗ trợ: {args.source}")


def _build_detector(args):
    """Trả về 1 IDetector đã sẵn sàng làm inner cho DetectStage.

    - fake → DetectorPipeline(FakeDetector) để box về ORIGINAL_FRAME (FakeDetector trả MODEL_INPUT).
    - pt   → Yolov5PtDetector THẲNG (đã ORIGINAL_FRAME, KHÔNG bọc DetectorPipeline).
    """
    if args.detector == "fake":
        from vision_platform.adapters.fake_detector import FakeDetector
        from vision_platform.adapters.detector_pipeline import DetectorPipeline
        return DetectorPipeline(FakeDetector(), args.model_size, args.model_size)
    if args.detector == "pt":
        from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
        return Yolov5PtDetector(args.weights, device=args.device)
    raise ValueError(f"detector không hỗ trợ: {args.detector}")


def _validate(args, parser):
    if args.source == "video" and not args.video:
        parser.error("--source video cần --video <path>")
    if args.source == "rtsp" and not args.rtsp:
        parser.error("--source rtsp cần --rtsp <url>")
    if args.detector == "pt" and not args.weights:
        parser.error("--detector pt cần --weights <path.pt>")


def _validate_config_only(path: str) -> int:
    """Kiểm config hợp lệ (type/detector) mà KHÔNG chạy/dựng object — chạy được trên máy no-GPU.

    Trả 0 nếu hợp lệ, 2 nếu sai (in lý do ra stderr). Dùng: kiểm file GPU trên máy dev trước khi mang đi.
    """
    from vision_platform.application.config_loader import load_app_config, ConfigError
    from vision_platform.profiles.pipeline_factory import validate_config

    try:
        app = load_app_config(path)
        validate_config(app)
    except ConfigError as e:
        print(f"CONFIG KHÔNG HỢP LỆ: {e}", file=sys.stderr)
        return 2
    print(f"config OK: {path} — {len(app.pipelines)} pipeline, mọi type/detector hợp lệ", file=sys.stderr)
    return 0


def _run_from_config(path: str, *, build=None) -> int:
    """Đường declarative (config-declarative): file TOML → dựng + chạy từng pipeline tuần tự (v1 sync).

    BULKHEAD per-pipeline (K-045): mỗi pipeline chạy trong khoang CÔ LẬP — lỗi khi BUILD (constructor thiếu
    weights/file/type...) HOẶC khi RUN (setup/sink I/O/exception bất ngờ) của 1 pipeline KHÔNG được kéo sập
    các pipeline còn lại (yêu cầu sống-còn cho hệ nhiều camera). Bắt `Exception` (KHÔNG bắt `BaseException` →
    giữ Ctrl+C/SystemExit dừng được toàn hệ), log rõ (không nuốt im lặng), rồi chạy tiếp pipeline kế.

    Return: 0 nếu MỌI pipeline chạy xong; 1 nếu có ≥1 pipeline lỗi (vẫn chạy hết). KHÔNG bao giờ báo thành
    công (0) khi còn camera chết — để orchestration/CI phát hiện sự cố một phần (chống giấu lỗi).

    `build` (DI, mặc định `build_runner`): hàm dựng runner từ 1 PipelineConfig — tiêm được để test bulkhead
    xác định (không cần adapter thật lỗi).
    """
    from vision_platform.application.config_loader import load_app_config
    from vision_platform.profiles.pipeline_factory import build_runner

    if build is None:
        build = build_runner

    app = load_app_config(path)
    print(f"=== vision_slice (config: {path}) — {len(app.pipelines)} pipeline ===", file=sys.stderr)
    ok = 0
    failed = 0
    for pcfg in app.pipelines:
        try:
            runner = build(pcfg)
            stats = runner.run(max_frames=pcfg.max_frames)
            print(f"[{pcfg.id}] frames_read={stats.frames_read} processed={stats.processed} "
                  f"skipped={stats.skipped} stage_errors={stats.stage_errors} eof={stats.eof}", file=sys.stderr)
            ok += 1
        except Exception as e:  # noqa: BLE001 — bulkhead có chủ đích: cô lập lỗi 1 pipeline (chừa BaseException)
            failed += 1
            print(f"[{pcfg.id}] LỖI — bỏ qua, chạy tiếp pipeline kế: {type(e).__name__}: {e}", file=sys.stderr)
    print(f"=== tổng: {ok} ok / {failed} lỗi / {len(app.pipelines)} pipeline ===", file=sys.stderr)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vision_platform.profiles.vision_slice_app")
    parser.add_argument("--config", default=None,
                        help="file .toml khai báo pipeline(s) — bật đường declarative (bỏ qua các cờ --source/... khi có)")
    parser.add_argument("--validate", action="store_true",
                        help="chỉ KIỂM config (type/detector) hợp lệ rồi thoát — KHÔNG chạy (dùng để check file GPU trên máy dev)")
    parser.add_argument("--source", choices=["fake", "noise", "video", "rtsp"], default="fake")
    parser.add_argument("--detector", choices=["fake", "pt"], default="fake")
    parser.add_argument("--weights", default=None, help="path .pt (khi --detector pt)")
    parser.add_argument("--device", default="cpu", help="cpu|cuda (khi --detector pt)")
    parser.add_argument("--model-size", type=int, default=640, help="model_h=model_w cho DetectorPipeline")
    parser.add_argument("--frames", type=int, default=20, help="max_frames cho fake/noise")
    parser.add_argument("--max-frames", type=int, default=None, help="giới hạn frame runner (rtsp/video)")
    parser.add_argument("--video", default=None)
    parser.add_argument("--rtsp", default=None)
    parser.add_argument("--max-reconnect", type=int, default=None)
    parser.add_argument("--out", default=None, help="path .jsonl → bật JsonlEventSink (lưu trữ optional)")
    args = parser.parse_args(argv)

    if args.validate and not args.config:
        parser.error("--validate cần --config <file.toml>")

    if args.config:
        if args.validate:
            return _validate_config_only(args.config)
        return _run_from_config(args.config)

    _validate(args, parser)

    source = _build_source(args)
    detector = _build_detector(args)
    executor = SyncLinearExecutor([DetectStage(detector), CountStage()])

    sinks = []
    if args.out:
        from vision_platform.adapters.jsonl_event_sink import JsonlEventSink
        sinks.append(JsonlEventSink(args.out))
    sink = CompositeSink(sinks)

    runner = PipelineRunner(source, executor, sink)
    stats = runner.run(max_frames=args.max_frames)

    print("=== vision_slice summary ===", file=sys.stderr)
    print(f"  frames_read : {stats.frames_read}", file=sys.stderr)
    print(f"  processed   : {stats.processed}", file=sys.stderr)
    print(f"  skipped     : {stats.skipped}", file=sys.stderr)
    print(f"  stage_errors: {stats.stage_errors}", file=sys.stderr)
    print(f"  source_errors: {stats.source_errors}", file=sys.stderr)
    print(f"  eof         : {stats.eof}", file=sys.stderr)
    if args.out:
        print(f"  events → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
