"""PipelineFactory — dựng PipelineRunner từ PipelineConfig (sub-spec config-declarative, Task 3).

Layer: profiles (composition root — được import mọi thứ: adapters/runtime/kernel/application). Map `type`
(chuỗi) → hàm dựng object, qua REGISTRY (điểm mở rộng: thêm loại = đăng ký entry, KHÔNG sửa lõi — Req 3.3).
Additive: bọc đúng các constructor mà `vision_slice_app` dùng tay (đọc nguyên văn `_build_*`). KHÔNG sửa
`PipelineRunner`/adapter/stage.

Lazy-import trong từng builder → registry import KHÔNG kéo dep nặng/optional (torch của `pt`, cv2 của video/rtsp)
lúc nạp module; chỉ import khi thực sự dựng loại đó.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from vision_platform.kernel.config import PipelineConfig
from vision_platform.application.config_loader import ConfigError
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.composite_sink import CompositeSink


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
    return Yolov5PtDetector(params["weights"], device=params.get("device", "cpu"))


def _stage_detect(params: Mapping, detector: Any):
    from vision_platform.runtime.stages.detect_stage import DetectStage
    if detector is None:
        raise ConfigError("stage 'detect' cần khai báo 'detector' trong pipeline")
    return DetectStage(detector)


def _stage_count(params: Mapping, detector: Any):
    from vision_platform.runtime.stages.count_stage import CountStage
    return CountStage()


def _sink_jsonl(params: Mapping):
    from vision_platform.adapters.jsonl_event_sink import JsonlEventSink
    _need(params, "path", "sink jsonl")
    return JsonlEventSink(params["path"])


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
_stage_detect.allowed_params = frozenset()
_stage_count.allowed_params = frozenset()
_sink_jsonl.allowed_params = frozenset({"path"})


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
    "detectors": {"fake": _det_fake, "pt": _det_pt},
    "stages": {"detect": _stage_detect, "count": _stage_count},
    "sinks": {"jsonl": _sink_jsonl},
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


def build_runner(pcfg: PipelineConfig, *, registry: Mapping = DEFAULT_REGISTRY) -> PipelineRunner:
    """Dựng `PipelineRunner` từ 1 `PipelineConfig`. Type lạ → `ConfigError` (liệt kê type hợp lệ)."""
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

    executor = SyncLinearExecutor(stages)
    sink = CompositeSink(sinks)
    return PipelineRunner(source, executor, sink)
