"""vision_slice_app — composition root cho lát cắt dọc: source → DetectStage → CountStage → sink.

Chạy qua PipelineRunner. Chế độ CI/dev: fake/noise + FakeDetector (xác định). Chế độ THẬT (ngoài CI):
--source video|rtsp + --detector pt (tái dùng adapter đã có). Lưu trữ optional qua --out (JsonlEventSink).

Lưu ý (design §Giới hạn SYNC vs LIVE): runner v1 đồng bộ — hợp video/synthetic (throughput). --rtsp = kiểm
chức năng, KHÔNG phải real-time (detect chặn read). Low-latency live = biến thể async sau.
"""
from __future__ import annotations

import argparse
import sys

from vision_platform.kernel.stage_contract import StageStatus
# F1 (#324): lắp-ráp pipeline dồn về `pipeline_factory.build_runner` (1 đường) → module này KHÔNG còn ráp tay
# (bỏ import SyncLinearExecutor/PipelineRunner/CompositeSink/DetectStage/CountStage). `build_runner` import lazy trong hàm.


class _TrackSummarySink:
    """Sink nhỏ (ISink) đọc `unique_count`/`active_count` từ ARTIFACTS pipeline (nguồn thật).

    Vì sao KHÔNG đọc `tracker.unique_count` sau `run()`: runner gọi `TrackingStage.teardown()` →
    `tracker.reset()` trong finally → state về 0. Đọc từ artifacts frame SUCCESS mới là số THẬT của lần chạy.
    `unique_count` đơn điệu → giá trị frame cuối = tổng distinct.
    """
    def __init__(self) -> None:
        self.unique = 0
        self.active = 0
        self.cross_in = 0
        self.cross_out = 0
        self.cross_total = 0

    def setup(self) -> None: ...

    def handle(self, result) -> None:
        if result.status == StageStatus.SUCCESS and result.packet is not None:
            a = result.packet.artifacts
            self.unique = a.get("unique_count", self.unique)
            self.active = a.get("active_count", self.active)
            self.cross_in = a.get("crossings_in", self.cross_in)
            self.cross_out = a.get("crossings_out", self.cross_out)
            self.cross_total = a.get("crossings_total", self.cross_total)

    def teardown(self) -> None: ...


class _CompositeObserver:
    """Fan-out snapshot tới nhiều observer (composition — vd vừa LoggingObserver vừa MetricsObserver).

    Mỗi observer bọc riêng → 1 observer lỗi KHÔNG chặn observer khác (quan sát phụ trợ, isolation).
    """
    def __init__(self, observers):
        self._observers = list(observers)

    def on_snapshot(self, snapshot):
        for o in self._observers:
            try:
                o.on_snapshot(snapshot)
            except Exception:  # noqa: BLE001 — quan sát phụ trợ: lỗi 1 observer không chặn cái khác
                pass


def _build_config_observability(observe, metrics_port, metrics_host):
    """Dựng observer + optional exporter `/metrics` DÙNG CHUNG (khử trùng lặp: cả main CLI-direct lẫn `_run_from_config`).

    Trả `(observer, exporter)`: observer=None nếu không bật gì; exporter=None nếu `metrics_port is None`.
    `metrics_port=0` → OS cấp cổng ephemeral (test). DÙNG CHUNG **1** `InMemoryMetrics` → `MetricsObserver` gắn nhãn
    `source=snapshot.source_id` → `/metrics` aggregate MỌI pipeline trong 1 process (mỗi camera 1 series gauge).
    Điều kiện wire = `observe OR metrics_port is not None` (metrics đơn lẻ, không cần --observe, vẫn lên).
    `metrics_host=None` → resolve "127.0.0.1" (sentinel merge #310/K-076: phủ cả 2 đường qua HÀM CHUNG này, chống CLI-direct host=None crash ThreadingHTTPServer).
    """
    metrics_host = metrics_host or "127.0.0.1"   # #310/K-076: resolve default TẠI HÀM CHUNG (1 chỗ, phủ mọi call-site)
    observers_list = []
    if observe:
        from vision_platform.runtime.observers import LoggingObserver
        observers_list.append(LoggingObserver())
    exporter = None
    if metrics_port is not None:
        from vision_platform.runtime.observability import InMemoryMetrics
        from vision_platform.runtime.observers import MetricsObserver
        from vision_platform.adapters.metrics_http_server import MetricsHttpExporter, is_loopback
        metrics = InMemoryMetrics()
        observers_list.append(MetricsObserver(metrics))
        if not is_loopback(metrics_host):
            print(f"[metrics] CẢNH BÁO: /metrics bind {metrics_host} KHÔNG xác thực — chỉ dùng mạng nội bộ tin cậy",
                  file=sys.stderr)
        exporter = MetricsHttpExporter(metrics.iter_metrics, host=metrics_host, port=metrics_port)
        _p = exporter.start()
        print(f"[metrics] phục vụ http://{metrics_host}:{_p}/metrics", file=sys.stderr)
    if len(observers_list) == 1:
        observer = observers_list[0]
    elif len(observers_list) >= 2:
        observer = _CompositeObserver(observers_list)
    else:
        observer = None
    return observer, exporter


def _merge_observability(cli: dict, toml_obs) -> dict:
    """Hợp nhất observability TỪ cờ CLI ↔ section `[observability]` TOML (spec config-observability-toml, D-086).

    Precedence: **CLI-explicit > TOML > built-in default** (cờ = tinh chỉnh ad-hoc, TOML = mặc-định-deploy GitOps).
    Sentinel "CLI không set": metrics_port/metrics_host=None · observe_interval_s=0.0 · observe_every_n=0.
    `observe` = OR-semantics (store_true không phân biệt not-set/false → `--observe` HOẶC TOML observe=true → bật).
    Hạn chế v1 (Non-Goal, ghi rõ): không tắt-observe-qua-CLI khi TOML bật; không đè-tường-minh-0 qua CLI.
    `toml_obs` = ObservabilityConfig | None (None → chỉ dùng CLI/default).
    """
    from vision_platform.kernel.config import ObservabilityConfig
    t = toml_obs or ObservabilityConfig()
    return {
        "observe": bool(cli.get("observe")) or t.observe,
        "metrics_port": cli.get("metrics_port") if cli.get("metrics_port") is not None else t.metrics_port,
        "metrics_host": cli.get("metrics_host") if cli.get("metrics_host") is not None else t.metrics_host,
        "observe_interval_s": cli.get("observe_interval_s") if cli.get("observe_interval_s") else t.observe_interval_s,
        "observe_every_n": cli.get("observe_every_n") if cli.get("observe_every_n") else t.observe_every_n,
    }


def _args_to_pipeline_config(args):
    """Map cờ CLI (argparse.Namespace) → 1 `PipelineConfig` in-memory (F1/#324, thuần — test được).

    Đường CLI-direct DÙNG CHUNG `build_runner` với đường `--config` → 1 nguồn lắp-ráp duy nhất (đóng phân kỳ,
    review F1). GIỮ NGUYÊN thứ tự stage suy từ cờ: [motion_gate?] → detect → count → [track?] → [line?].
    Default builder KHỚP default cũ (verify #323: motion-gate 25/0.005 · model_size 640 · iou 0.3/max_age 30 ·
    max_frames 20) → KHÔNG đổi hành vi. `_validate(args, parser)` PHẢI chạy TRƯỚC (H4) — hàm này giả định cờ hợp lệ.
    """
    from vision_platform.kernel.config import (
        PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
    )
    # --- source ---
    if args.source in ("fake", "noise"):
        source = SourceConfig(args.source, {"max_frames": args.frames})
    elif args.source == "video":
        source = SourceConfig("video", {"path": args.video})
    else:  # rtsp (đã validate có --rtsp)
        source = SourceConfig("rtsp", {"url": args.rtsp, "max_reconnect": args.max_reconnect})
    # --- detector (luôn có; 'fake' mặc định). Registry: fake→DetectorPipeline(FakeDetector), pt→Yolov5PtDetector ---
    if args.detector == "fake":
        detector = DetectorConfig("fake", {"model_size": args.model_size})
    else:  # pt (đã validate có --weights)
        detector = DetectorConfig("pt", {"weights": args.weights, "device": args.device})
    # --- stages (GIỮ THỨ TỰ hiện tại) ---
    stages = []
    if args.motion_gate:
        mg = {
            "max_consecutive_skip": args.motion_gate_max_skip,
            "illumination_robust": args.motion_gate_illum_robust,
        }
        if args.motion_gate_roi:
            mg["roi"] = tuple(float(p) for p in args.motion_gate_roi.split(","))
        stages.append(StageConfig("motion_gate", mg))
    stages.append(StageConfig("detect", {}))
    stages.append(StageConfig("count", {}))
    if args.track:
        stages.append(StageConfig("track", {"iou_threshold": args.track_iou, "max_age": args.track_max_age}))
    if args.line:
        ax, ay, bx, by = (float(p) for p in args.line.split(","))
        stages.append(StageConfig("line_crossing", {"ax": ax, "ay": ay, "bx": bx, "by": by}))
    # --- sinks ---
    sinks = []
    if args.out:
        sinks.append(SinkConfig("jsonl", {"path": args.out}))
    if args.crossing_out:
        sinks.append(SinkConfig("crossing_events", {"path": args.crossing_out}))
    if args.crossing_db:
        sinks.append(SinkConfig("crossing_events_sqlite", {"path": args.crossing_db}))
    return PipelineConfig(
        id="cli", source=source, stages=stages, sinks=sinks,
        detector=detector, max_frames=args.max_frames,
    )


def _print_summary(stats, track_summary, args) -> None:
    """In summary CLI-direct ra stderr (F1/#324: tách khỏi `main` — F2). Giữ NGUYÊN từng dòng (backward-compat)."""
    print("=== vision_slice summary ===", file=sys.stderr)
    print(f"  frames_read : {stats.frames_read}", file=sys.stderr)
    print(f"  processed   : {stats.processed}", file=sys.stderr)
    print(f"  skipped     : {stats.skipped}", file=sys.stderr)
    print(f"  stage_errors: {stats.stage_errors}", file=sys.stderr)
    print(f"  source_errors: {stats.source_errors}", file=sys.stderr)
    print(f"  eof         : {stats.eof}", file=sys.stderr)
    if track_summary is not None:
        print(f"  unique_tracks: {track_summary.unique}", file=sys.stderr)
        print(f"  active_tracks: {track_summary.active}", file=sys.stderr)
    if args.line:
        print(f"  crossings_in : {track_summary.cross_in}", file=sys.stderr)
        print(f"  crossings_out: {track_summary.cross_out}", file=sys.stderr)
        print(f"  crossings_tot: {track_summary.cross_total}", file=sys.stderr)
    if args.crossing_out:
        print(f"  crossing events → {args.crossing_out}", file=sys.stderr)
    if args.crossing_db:
        print(f"  crossing events db → {args.crossing_db}", file=sys.stderr)
    if args.out:
        print(f"  events → {args.out}", file=sys.stderr)


def _validate(args, parser):
    if args.source == "video" and not args.video:
        parser.error("--source video cần --video <path>")
    if args.source == "rtsp" and not args.rtsp:
        parser.error("--source rtsp cần --rtsp <url>")
    if args.detector == "pt" and not args.weights:
        parser.error("--detector pt cần --weights <path.pt>")
    if args.line:
        if not args.track:
            parser.error("--line cần --track (LineCrossingStage đọc artifacts['tracks'])")
        parts = args.line.split(",")
        if len(parts) != 4:
            parser.error("--line dạng 'ax,ay,bx,by'")
        try:
            [float(p) for p in parts]
        except ValueError:
            parser.error("--line: cần 4 số 'ax,ay,bx,by'")
    if args.crossing_out and not args.line:
        parser.error("--crossing-out cần --line (ghi sự kiện qua vạch)")
    if args.crossing_db and not args.line:
        parser.error("--crossing-db cần --line (ghi sự kiện qua vạch vào SQLite)")


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


def _run_from_config(path: str, *, build=None,
                     observe: bool = False, observe_interval_s: float = 0.0,
                     observe_every_n: int = 0,
                     metrics_port: int | None = None, metrics_host: str | None = None) -> int:
    """Đường declarative (config-declarative): file TOML → dựng + chạy từng pipeline tuần tự (v1 sync).

    BULKHEAD per-pipeline (K-045): mỗi pipeline chạy trong khoang CÔ LẬP — lỗi khi BUILD (constructor thiếu
    weights/file/type...) HOẶC khi RUN (setup/sink I/O/exception bất ngờ) của 1 pipeline KHÔNG được kéo sập
    các pipeline còn lại (yêu cầu sống-còn cho hệ nhiều camera). Bắt `Exception` (KHÔNG bắt `BaseException` →
    giữ Ctrl+C/SystemExit dừng được toàn hệ), log rõ (không nuốt im lặng), rồi chạy tiếp pipeline kế.

    Return: 0 nếu MỌI pipeline chạy xong; 1 nếu có ≥1 pipeline lỗi (vẫn chạy hết). KHÔNG bao giờ báo thành
    công (0) khi còn camera chết — để orchestration/CI phát hiện sự cố một phần (chống giấu lỗi).

    `build` (DI, mặc định `build_runner`): hàm dựng runner từ 1 PipelineConfig — tiêm được để test bulkhead
    xác định (không cần adapter thật lỗi). Khi `build` được tiêm → tôn trọng build đó, BỎ QUA observability.

    Observability (opt-in, đóng nợ 🟡 wire config D-069): `observe`→LoggingObserver; `metrics_port`→exporter
    `/metrics` (Prometheus scrape) DÙNG CHUNG 1 InMemoryMetrics cho MỌI pipeline (aggregate theo source_id —
    mô hình "1 process/1 camera → 1 scrape target"). `metrics_host` non-loopback → cảnh báo không-auth. Cả 2
    tắt → hành vi `--config` giữ NGUYÊN (backward-compat). Exporter luôn `stop()` trong finally (không rò cổng).
    """
    from vision_platform.application.config_loader import load_app_config
    from vision_platform.profiles.pipeline_factory import build_runner

    app = load_app_config(path)   # LOAD TRƯỚC: cần app.observability để merge cờ-CLI↔TOML (D-086)

    exporter = None
    if build is None:
        # Hợp nhất cờ CLI (tham số) ↔ section [observability] TOML (precedence CLI-explicit>TOML>default, D-086).
        m = _merge_observability(
            {"observe": observe, "metrics_port": metrics_port, "metrics_host": metrics_host,
             "observe_interval_s": observe_interval_s, "observe_every_n": observe_every_n},
            app.observability)
        # Smart-default nhịp emit SAU merge: (observe∨metrics) & chưa set nhịp → 5s (self-consistent).
        if (m["observe"] or m["metrics_port"] is not None) and m["observe_every_n"] == 0 and m["observe_interval_s"] == 0.0:
            m["observe_interval_s"] = 5.0
        observer, exporter = _build_config_observability(m["observe"], m["metrics_port"], m["metrics_host"])
        if observer is not None:
            build = lambda pcfg: build_runner(  # noqa: E731 — observer DÙNG CHUNG mọi pipeline (source_id từ snapshot)
                pcfg, observer=observer,
                emit_every_n=m["observe_every_n"], emit_interval_s=m["observe_interval_s"])
        else:
            build = build_runner

    try:
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
    finally:
        if exporter is not None:
            exporter.stop()   # R3.2: luôn đóng cổng/thread (kể cả 1 pipeline raise ra ngoài / KeyboardInterrupt)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vision_platform.profiles.vision_slice_app")
    parser.add_argument("--config", default=None,
                        help="file .toml khai báo pipeline(s) — bật đường declarative (bỏ qua các cờ --source/... khi có)")
    parser.add_argument("--validate", action="store_true",
                        help="chỉ KIỂM config (type/detector) hợp lệ rồi thoát — KHÔNG chạy (dùng để check file GPU trên máy dev)")
    parser.add_argument("--source", choices=["fake", "noise", "video", "rtsp"], default="fake")
    parser.add_argument("--detector", choices=["fake", "pt"], default="fake")
    parser.add_argument("--weights", default=None, help="path .pt (khi --detector pt)")
    parser.add_argument("--device", default="cpu",
                        help="auto|cpu|cuda|cuda:N (khi --detector pt). auto=tự chọn theo máy; cuda thiếu GPU→lỗi rõ")
    parser.add_argument("--model-size", type=int, default=640, help="model_h=model_w cho DetectorPipeline")
    parser.add_argument("--frames", type=int, default=20, help="max_frames cho fake/noise")
    parser.add_argument("--max-frames", type=int, default=None, help="giới hạn frame runner (rtsp/video)")
    parser.add_argument("--video", default=None)
    parser.add_argument("--rtsp", default=None)
    parser.add_argument("--max-reconnect", type=int, default=None)
    parser.add_argument("--out", default=None, help="path .jsonl → bật JsonlEventSink (lưu trữ optional)")
    parser.add_argument("--motion-gate", action="store_true",
                        help="bật MotionGateStage (chặn frame tĩnh TRƯỚC detector → giảm tải GPU)")
    parser.add_argument("--motion-gate-max-skip", type=int, default=0,
                        help="ép chạy 1 frame sau N skip liên tiếp (0=không giới hạn) — chống bỏ sót khi tĩnh lâu")
    parser.add_argument("--motion-gate-roi", default=None,
                        help="ROI 'x,y,w,h' chuẩn-hoá [0,1] — motion-gate chỉ đo TRONG vùng này (bỏ trời/cây)")
    parser.add_argument("--motion-gate-illum-robust", action="store_true",
                        help="motion-gate bền đổi-sáng-ĐỀU (mean-subtraction) — chống trigger oan khi đèn/mây đổi sáng toàn cục")
    parser.add_argument("--track", action="store_true",
                        help="bật TrackingStage (theo dõi + đếm-không-trùng) sau CountStage")
    parser.add_argument("--track-iou", type=float, default=0.3, help="ngưỡng IoU association (khi --track)")
    parser.add_argument("--track-max-age", type=int, default=30, help="số frame giữ track khi mất dấu (khi --track)")
    parser.add_argument("--line", default=None,
                        help="vạch đếm-qua dạng 'ax,ay,bx,by' (ORIGINAL_FRAME) — cần --track")
    parser.add_argument("--crossing-out", default=None,
                        help="path .jsonl ghi CrossingEvent mỗi lượt qua vạch — cần --line")
    parser.add_argument("--crossing-db", default=None,
                        help="path .sqlite ghi CrossingEvent vào SQLite (queryable) — cần --line")
    parser.add_argument("--observe", action="store_true",
                        help="bật quan sát vận hành (log snapshot fps/skip_rate/errors định kỳ) — thấy sức khỏe live")
    parser.add_argument("--observe-interval", type=float, default=0.0,
                        help="giây giữa 2 snapshot (0=tắt theo-giờ). Bật --observe mà không set nhịp → mặc định 5s")
    parser.add_argument("--observe-every", type=int, default=0,
                        help="số frame giữa 2 snapshot (0=tắt theo-frame)")
    parser.add_argument("--metrics-port", type=int, default=None,
                        help="bật exporter HTTP /metrics (Prometheus scrape) ở cổng này (0=ephemeral). Bật → cũng emit snapshot định kỳ")
    parser.add_argument("--metrics-host", default=None,
                        help="địa chỉ bind exporter /metrics (không set → 127.0.0.1 an toàn; 0.0.0.0=phơi mạng, KHÔNG auth → chỉ mạng nội bộ). Sentinel None để merge với [observability] TOML")
    parser.add_argument("--capabilities", action="store_true",
                        help="IN năng lực máy hiện tại (torch/cuda/cv2/gpu) dạng JSON rồi thoát — kiểm máy TRƯỚC khi deploy (đổi máy GPU/không-GPU)")
    return parser


def main(argv=None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    if args.capabilities:
        # Lệnh operator: dò + in năng lực máy (JSON stdout, parse được bởi script vận hành) rồi thoát.
        import dataclasses
        import json
        from vision_platform.adapters.capability_probe import probe_capabilities
        caps = probe_capabilities()
        print(json.dumps(dataclasses.asdict(caps), ensure_ascii=False))
        print(f"[capabilities] torch={caps.has_torch} cuda={caps.has_cuda} "
              f"gpu={caps.gpu_name} cv2={caps.has_cv2}", file=sys.stderr)
        return 0

    if args.validate and not args.config:
        parser.error("--validate cần --config <file.toml>")

    # Observe settings tính MỘT LẦN (dùng chung cả đường config-declarative lẫn đường inline).
    # Default thông minh: bật --observe mà không set nhịp → 5s/snapshot (theo-giờ) → thấy sức khỏe
    # cả khi camera mất kết nối (fix Lỗ-A #275: emit theo-giờ ở đầu loop không cần frame chảy).
    obs_every = args.observe_every
    obs_interval = args.observe_interval
    # --metrics-port cũng cần emit định kỳ (để /metrics cập nhật), không chỉ --observe.
    _want_periodic = args.observe or (args.metrics_port is not None)
    if _want_periodic and obs_every == 0 and obs_interval == 0.0:
        obs_interval = 5.0

    if args.config:
        if args.validate:
            return _validate_config_only(args.config)
        return _run_from_config(args.config, observe=args.observe,
                                observe_interval_s=args.observe_interval, observe_every_n=args.observe_every,
                                metrics_port=args.metrics_port, metrics_host=args.metrics_host)

    _validate(args, parser)   # H4: validate cờ TRƯỚC khi map sang PipelineConfig

    from vision_platform.kernel.capabilities import CapabilityError
    from vision_platform.profiles.pipeline_factory import build_runner

    # F1 (#324): CLI-direct DÙNG CHUNG build_runner (1 đường lắp-ráp, xoá hand-assembly) — map cờ → PipelineConfig.
    pcfg = _args_to_pipeline_config(args)
    track_summary = _TrackSummarySink() if args.track else None
    extra_sinks = [track_summary] if track_summary is not None else []

    # Observer(s) + optional exporter /metrics (đường inline) — DÙNG CHUNG helper với đường --config (DRY, #298).
    observer, exporter = _build_config_observability(args.observe, args.metrics_port, args.metrics_host)
    try:
        runner = build_runner(pcfg, observer=observer, emit_every_n=obs_every,
                              emit_interval_s=obs_interval, extra_sinks=extra_sinks)
    except CapabilityError as e:   # H2: ép cuda thiếu GPU → thông báo gọn + exit 2 (không traceback thô)
        print(f"LỖI NĂNG LỰC (device): {e}", file=sys.stderr)
        if exporter is not None:
            exporter.stop()   # exporter đã start trong _build_config_observability → đóng cổng, không rò
        return 2
    try:
        stats = runner.run(max_frames=args.max_frames)
    finally:
        if exporter is not None:
            exporter.stop()

    _print_summary(stats, track_summary, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
