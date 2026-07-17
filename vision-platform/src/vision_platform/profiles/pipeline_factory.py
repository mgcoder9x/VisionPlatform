"""PipelineFactory — dựng PipelineRunner từ PipelineConfig (sub-spec config-declarative, Task 3).

Layer: profiles (composition root — được import mọi thứ: adapters/runtime/kernel/application). Map `type`
(chuỗi) → hàm dựng object, qua REGISTRY (điểm mở rộng: thêm loại = đăng ký entry, KHÔNG sửa lõi — Req 3.3).
Additive: bọc đúng các constructor mà `vision_slice_app` dùng tay (đọc nguyên văn `_build_*`). KHÔNG sửa
`PipelineRunner`/adapter/stage.

Lazy-import trong từng builder → registry import KHÔNG kéo dep nặng/optional (torch của `pt`, cv2 của video/rtsp)
lúc nạp module; chỉ import khi thực sự dựng loại đó.
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Mapping, Sequence

from vision_platform.kernel.config import PipelineConfig
from vision_platform.kernel.capabilities import resolve_device
from vision_platform.application.config_loader import ConfigError
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.composite_sink import CompositeSink
from vision_platform.adapters.capability_probe import probe_capabilities


# ---- Builders (mỗi cái lazy-import, khớp vision_slice_app._build_*) ----
def _src_fake(params: Mapping):
    from vision_platform.adapters.fake_frame_source import FakeFrameSource
    return FakeFrameSource(max_frames=params.get("max_frames", 20))


def _src_noise(params: Mapping):
    from vision_platform.adapters.noise_frame_source import NoiseFrameSource
    return NoiseFrameSource(max_frames=params.get("max_frames", 20))


def _src_video(params: Mapping):
    from vision_platform.adapters.video_file_frame_source import VideoFileFrameSource
    _need(params, "path", "source video")
    return VideoFileFrameSource(params["path"])


def _src_rtsp(params: Mapping):
    from vision_platform.adapters.rtsp_frame_source import RtspFrameSource
    _need(params, "url", "source rtsp")
    return RtspFrameSource(params["url"], max_reconnect=params.get("max_reconnect"))


def _det_fake(params: Mapping):
    from vision_platform.adapters.fake_detector import FakeDetector
    from vision_platform.adapters.detector_pipeline import DetectorPipeline
    size = params.get("model_size", 640)
    return DetectorPipeline(FakeDetector(), size, size)


def _det_pt(params: Mapping):
    from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
    _need(params, "weights", "detector pt")
    # Capability-aware: resolve device theo năng lực máy (auto→best / cuda-thiếu→CapabilityError fail-fast).
    # probe TRƯỚC construct (construct không import torch → resolve raise được mà không kéo dep nặng).
    # CapabilityError (RuntimeError) ở đường config → _run_from_config bulkhead cô lập (log + chạy tiếp cam kế).
    caps = probe_capabilities()
    dev = resolve_device(params.get("device", "cpu"), caps)
    # F1/H1 (#324): LOG device THỰC TẾ đã chọn ở ĐÂY (1 nơi, cả đường CLI-direct lẫn config cùng hưởng —
    # chống "tưởng GPU mà chạy CPU", R3.2). Trước: chỉ đường CLI-direct log qua `_resolve_device_logged`.
    print(f"[device] yêu cầu={params.get('device', 'cpu')!r} → dùng={dev!r} "
          f"(has_cuda={caps.has_cuda}, gpu={caps.gpu_name})", file=sys.stderr)
    return Yolov5PtDetector(params["weights"], device=dev)


def _det_onnx(params: Mapping):
    """Detector NN THẬT qua ONNX (onnxruntime) — deploy-by-config detector chạy được trên CPU (no torch/GPU).

    Params: weights (path .onnx, bắt buộc) · yolo ('v5'|'v8', default v8) · layout ('nc_first'|'nc_last' cho v8) ·
    conf (default 0.25) · model_size (default 640, letterbox) · labels (list HOẶC chuỗi phân-phẩy, tùy chọn).
    Mirror `vision_demo_app._build_detector` nhánh onnx → DetectorPipeline(OnnxDetector+decode) tự lo letterbox/NMS/inverse.
    OnnxDetector nạp model ở setup() (không phải construct) → build_runner construct KHÔNG cần file; setup lúc run.
    """
    from vision_platform.adapters.onnx_detector import OnnxDetector, chw_float_normalize, onnx_providers_for
    from vision_platform.adapters.yolo_postprocess import yolov5_decode, yolov8_decode
    from vision_platform.adapters.detector_pipeline import DetectorPipeline
    _need(params, "weights", "detector onnx")

    raw_labels = params.get("labels")
    if raw_labels is None:
        labels = None
    elif isinstance(raw_labels, str):
        labels = [s.strip() for s in raw_labels.split(",") if s.strip()]
    else:
        labels = [str(x) for x in raw_labels]

    ver = params.get("yolo", "v8")
    conf = float(params.get("conf", 0.25))
    if ver == "v8":
        layout = params.get("layout", "nc_first")
        if layout not in ("nc_first", "nc_last"):
            raise ConfigError(f"detector onnx 'layout' phải 'nc_first'|'nc_last', got {layout!r}")

        def _post(raw):
            return yolov8_decode(raw, conf_threshold=conf, labels=labels, layout=layout)
    elif ver == "v5":
        def _post(raw):
            return yolov5_decode(raw, conf_threshold=conf, labels=labels)
    else:
        raise ConfigError(f"detector onnx 'yolo' phải 'v5'|'v8', got {ver!r}")

    size = int(params.get("model_size", 640))
    # Capability-aware ONNX (F3.2/D-139): device đi qua resolve_device (đối xứng _det_pt) — hỗ trợ 'auto',
    # FAIL-FAST CapabilityError khi 'cuda' mà máy KHÔNG CUDA (không fallback CPU âm thầm) + LOG device THẬT.
    # OnnxDetector.setup tự lo DLL nvidia khi provider CUDA (K-088). 1 chính sách device chung mọi đường ONNX.
    caps = probe_capabilities()
    providers, dev = onnx_providers_for(params.get("device", "cpu"), caps)
    print(f"[device] onnx yêu cầu={params.get('device', 'cpu')!r} → dùng={dev!r} "
          f"(has_cuda={caps.has_cuda}, gpu={caps.gpu_name})", file=sys.stderr)
    inner = OnnxDetector(params["weights"], preprocess_fn=chw_float_normalize,
                         postprocess_fn=_post, providers=providers)
    return DetectorPipeline(inner, size, size)


def _stage_detect(params: Mapping, detector: Any):
    from vision_platform.runtime.stages.detect_stage import DetectStage
    if detector is None:
        raise ConfigError("stage 'detect' cần khai báo 'detector' trong pipeline")
    return DetectStage(detector)


def _stage_count(params: Mapping, detector: Any):
    from vision_platform.runtime.stages.count_stage import CountStage
    return CountStage()


def _parse_roi(raw: Any) -> tuple:
    """Parse config 'roi' (list/tuple 4 số [x,y,w,h]) → tuple + validate range NGAY (fail-fast config-time)."""
    from vision_platform.domain.motion import validate_roi
    try:
        vals = tuple(float(v) for v in raw)
    except (TypeError, ValueError):
        raise ConfigError(f"motion_gate 'roi' phải là 4 số [x,y,w,h], got {raw!r}")
    if len(vals) != 4:
        raise ConfigError(f"motion_gate 'roi' cần đúng 4 số [x,y,w,h], got {len(vals)}")
    try:
        validate_roi(*vals)
    except ValueError as e:
        raise ConfigError(f"motion_gate 'roi' không hợp lệ: {e}")
    return vals


def _stage_motion_gate(params: Mapping, detector: Any):
    # Gate CPU chặn frame tĩnh trước detector (giảm tải GPU). Đặt TRƯỚC 'detect' trong chuỗi.
    from vision_platform.runtime.stages.motion_gate_stage import MotionGateStage
    roi = params.get("roi", None)
    if roi is not None:
        roi = _parse_roi(roi)
    return MotionGateStage(
        pixel_diff_threshold=params.get("pixel_diff_threshold", 25),
        min_area_ratio=params.get("min_area_ratio", 0.005),
        max_consecutive_skip=params.get("max_consecutive_skip", 0),
        roi=roi,
        illumination_robust=bool(params.get("illumination_robust", False)),
    )


def _stage_track(params: Mapping, detector: Any):
    # Analytics stateful (đếm-không-trùng). Đọc artifacts["detections"] (cần stage 'detect' trước).
    from vision_platform.runtime.iou_tracker import IouTracker
    from vision_platform.runtime.stages.tracking_stage import TrackingStage
    return TrackingStage(IouTracker(
        iou_threshold=params.get("iou_threshold", 0.3),
        max_age=params.get("max_age", 30),
    ))


def _stage_line_crossing(params: Mapping, detector: Any):
    # Đếm qua vạch (cần stage 'track' trước → đọc artifacts["tracks"]).
    from vision_platform.runtime.stages.line_crossing_stage import LineCrossingStage
    for k in ("ax", "ay", "bx", "by"):
        _need(params, k, "stage line_crossing")
    return LineCrossingStage(params["ax"], params["ay"], params["bx"], params["by"])


def _sink_jsonl(params: Mapping):
    from vision_platform.adapters.jsonl_event_sink import JsonlEventSink
    _need(params, "path", "sink jsonl")
    return JsonlEventSink(params["path"])


def _sink_crossing_events(params: Mapping):
    from vision_platform.adapters.crossing_event_sink import CrossingEventJsonlSink
    _need(params, "path", "sink crossing_events")
    return CrossingEventJsonlSink(params["path"])


def _sink_crossing_events_sqlite(params: Mapping):
    from vision_platform.adapters.crossing_event_sqlite_sink import CrossingEventSqliteSink
    _need(params, "path", "sink crossing_events_sqlite")
    return CrossingEventSqliteSink(params["path"])


def _need(params: Mapping, key: str, what: str) -> None:
    if key not in params:
        raise ConfigError(f"{what} thiếu params['{key}']")


# --- K-046: tập params HỢP LỆ mỗi builder (chống typo nuốt im lặng) ---
# Builder là nơi ĐỌC params → là "authority" về key hợp lệ; khai báo NGAY CẠNH đây (thêm loại mới → khai báo).
# `_check_params` từ chối key lạ (fail-fast) — chạy ở CẢ validate_config (dry-run, --validate) lẫn build_runner
# (đường chạy thật, vì _run_from_config gọi build_runner KHÔNG qua validate_config).
_src_fake.allowed_params = frozenset({"max_frames"})
_src_noise.allowed_params = frozenset({"max_frames"})
_src_video.allowed_params = frozenset({"path"})
_src_rtsp.allowed_params = frozenset({"url", "max_reconnect"})
_det_fake.allowed_params = frozenset({"model_size"})
_det_pt.allowed_params = frozenset({"weights", "device"})
_det_onnx.allowed_params = frozenset({"weights", "labels", "yolo", "layout", "conf", "model_size", "device"})
_stage_detect.allowed_params = frozenset()
_stage_count.allowed_params = frozenset()
_stage_motion_gate.allowed_params = frozenset(
    {"pixel_diff_threshold", "min_area_ratio", "max_consecutive_skip", "roi", "illumination_robust"}
)
_stage_track.allowed_params = frozenset({"iou_threshold", "max_age"})
_stage_line_crossing.allowed_params = frozenset({"ax", "ay", "bx", "by"})
_sink_jsonl.allowed_params = frozenset({"path"})
_sink_crossing_events.allowed_params = frozenset({"path"})
_sink_crossing_events_sqlite.allowed_params = frozenset({"path"})


def _check_params(builder: Callable, where: str, params: Mapping) -> None:
    """Từ chối key params LẠ (typo) → chống nuốt im lặng (K-046).

    Builder CHƯA khai báo `allowed_params` (vd builder tùy biến bên thứ 3 trong registry ngoài) → BỎ QUA
    (lenient, không siết cái mình không biết). 9 builder mặc định đều đã khai báo đủ.
    """
    allowed = getattr(builder, "allowed_params", None)
    if allowed is None:
        return
    unknown = set(params) - allowed
    if unknown:
        valid = ", ".join(sorted(allowed)) or "(không có)"
        raise ConfigError(f"{where} có tham số lạ: {sorted(unknown)}. Params hợp lệ: {valid}")


DEFAULT_REGISTRY: dict[str, dict[str, Callable]] = {
    "sources": {"fake": _src_fake, "noise": _src_noise, "video": _src_video, "rtsp": _src_rtsp},
    "detectors": {"fake": _det_fake, "pt": _det_pt, "onnx": _det_onnx},
    "stages": {"detect": _stage_detect, "count": _stage_count, "motion_gate": _stage_motion_gate,
               "track": _stage_track, "line_crossing": _stage_line_crossing},
    "sinks": {"jsonl": _sink_jsonl, "crossing_events": _sink_crossing_events,
              "crossing_events_sqlite": _sink_crossing_events_sqlite},
}


def _lookup(registry: Mapping, section: str, type_: str):
    table = registry.get(section, {})
    if type_ not in table:
        valid = ", ".join(sorted(table)) or "(rỗng)"
        raise ConfigError(f"{section}.type không hỗ trợ: {type_!r}. Hợp lệ: {valid}")
    return table[type_]


def validate_config(app, *, registry: Mapping = DEFAULT_REGISTRY) -> None:
    """Kiểm config HỢP LỆ mà KHÔNG dựng object (no-GPU/no-torch): mọi `type` ∈ registry + detect-có-detector.

    Dùng để validate file config (kể cả cấu hình GPU) TRƯỚC khi chạy — vd chạy trên máy dev để chắc file
    đúng trước khi mang lên máy GPU. `_lookup` chỉ tra dict (KHÔNG gọi builder → KHÔNG import torch/cv2).
    Sai → `ConfigError` kèm pipeline id.
    """
    for p in app.pipelines:
        try:
            _check_params(_lookup(registry, "sources", p.source.type), f"source '{p.source.type}'", p.source.params)
            for st in p.stages:
                _check_params(_lookup(registry, "stages", st.type), f"stage '{st.type}'", st.params)
            for sk in p.sinks:
                _check_params(_lookup(registry, "sinks", sk.type), f"sink '{sk.type}'", sk.params)
            if p.detector is not None:
                _check_params(_lookup(registry, "detectors", p.detector.type),
                              f"detector '{p.detector.type}'", p.detector.params)
            if any(st.type == "detect" for st in p.stages) and p.detector is None:
                raise ConfigError("stage 'detect' cần khai báo 'detector'")
        except ConfigError as e:
            raise ConfigError(f"pipeline {p.id!r}: {e}") from e


def build_runner(pcfg: PipelineConfig, *, registry: Mapping = DEFAULT_REGISTRY,
                 observer=None, emit_every_n: int = 0, emit_interval_s: float = 0.0,
                 extra_sinks: Sequence = ()) -> PipelineRunner:
    """Dựng `PipelineRunner` từ 1 `PipelineConfig`. Type lạ → `ConfigError` (liệt kê type hợp lệ).

    `observer`/`emit_every_n`/`emit_interval_s` (opt-in, mặc định = không quan sát → NoopObserver trong
    PipelineRunner): wire quan sát vận hành vào ĐƯỜNG CONFIG-DECLARATIVE (deploy ~100 cam qua TOML). Không
    truyền → hành vi #265 giữ nguyên (backward-compat tuyệt đối). KHÔNG đưa vào schema TOML: quan sát là quyết
    định VẬN HÀNH toàn-fleet cho 1 lần chạy (source_id đã label per-camera), không phải cấu hình per-pipeline.

    `extra_sinks` (F1/#324, additive default `()`): các ISink dựng-sẵn NGOÀI config, append SAU sink-từ-config
    vào `CompositeSink`. Dùng cho sink PRESENTATION không thuộc config (vd `_TrackSummarySink` đọc artifacts để
    in summary CLI). Default `()` → đường config KHÔNG đổi hành vi. Đây là mảnh cho F1 hợp nhất đường CLI-direct
    → dùng chung `build_runner` (1 nguồn lắp-ráp) mà vẫn giữ được summary CLI.
    """
    # _check_params TRƯỚC khi gọi builder → typo bị chặn trước cả lazy-import (torch/cv2) → an toàn máy no-GPU.
    detector = None
    if pcfg.detector is not None:
        db = _lookup(registry, "detectors", pcfg.detector.type)
        _check_params(db, f"detector '{pcfg.detector.type}'", pcfg.detector.params)
        detector = db(pcfg.detector.params)

    sb = _lookup(registry, "sources", pcfg.source.type)
    _check_params(sb, f"source '{pcfg.source.type}'", pcfg.source.params)
    source = sb(pcfg.source.params)

    stages = []
    for st in pcfg.stages:
        stb = _lookup(registry, "stages", st.type)
        _check_params(stb, f"stage '{st.type}'", st.params)
        stages.append(stb(st.params, detector))

    sinks = []
    for sk in pcfg.sinks:
        skb = _lookup(registry, "sinks", sk.type)
        _check_params(skb, f"sink '{sk.type}'", sk.params)
        sinks.append(skb(sk.params))
    sinks.extend(extra_sinks)   # F1/#324: sink presentation ngoài-config (vd _TrackSummarySink) — append cuối

    executor = SyncLinearExecutor(stages)
    sink = CompositeSink(sinks)
    return PipelineRunner(source, executor, sink, observer=observer,
                          emit_every_n=emit_every_n, emit_interval_s=emit_interval_s)
