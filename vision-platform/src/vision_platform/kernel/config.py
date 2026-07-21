"""Schema khai báo (declarative config) — sub-spec config-declarative, Task 1 (đóng K-040 C2).

Layer: kernel — THUẦN (chỉ stdlib: dataclasses/types/typing). KHÔNG I/O, KHÔNG đọc file, KHÔNG import adapter
(import-linter ép). Đây là MODEL BẤT BIẾN phản ánh 1 file config; việc đọc file + validate ở `application/
config_loader.py`, dựng object ở `profiles/pipeline_factory.py`.

Bất biến (Requirement 1.2): mọi *Config `@dataclass(frozen=True)`; `params` bọc `MappingProxyType` (read-only);
danh sách (stages/sinks/pipelines) lưu dạng `tuple` → không mutate được sau parse (chống sửa cấu hình toàn cục).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Sequence


def _freeze_params(params: Optional[Mapping]) -> Mapping:
    """Trả bản đọc-chỉ (MappingProxyType) của params; None → rỗng."""
    return MappingProxyType(dict(params)) if params is not None else MappingProxyType({})


@dataclass(frozen=True)
class SourceConfig:
    """Khai báo nguồn frame: `type` (fake/noise/video/rtsp...) + `params` khớp chữ ký adapter."""
    type: str
    params: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class StageConfig:
    """Khai báo 1 stage trong pipeline: `type` (detect/count...) + `params`."""
    type: str
    params: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class SinkConfig:
    """Khai báo 1 sink: `type` (jsonl...) + `params`. Danh sách rỗng = không lưu (lưu trữ optional)."""
    type: str
    params: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class DetectorConfig:
    """Khai báo detector cho stage `detect`: `type` (fake/pt...) + `params`. Optional khi không có detect."""
    type: str
    params: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class PipelineConfig:
    """Khai báo 1 pipeline: định danh + nguồn + chuỗi stage (theo thứ tự) + sink + detector? + max_frames?."""
    id: str
    source: SourceConfig
    stages: Sequence[StageConfig] = ()
    sinks: Sequence[SinkConfig] = ()
    detector: Optional[DetectorConfig] = None
    max_frames: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "sinks", tuple(self.sinks))


@dataclass(frozen=True)
class ObservabilityConfig:
    """Khai báo observability TOP-LEVEL (fleet/tiến-trình) — spec config-observability-toml (D-086).

    Ánh xạ 1:1 tới bộ tham số observability của `_run_from_config` (#299). TOP-LEVEL (không per-pipeline):
    observability là quyết định tiến-trình ("1 process = 1 scrape target"; `source_id` đã phân biệt cam).
    Mặc định = TẮT hoàn toàn (không section → AppConfig.observability=None → hành vi #299 giữ nguyên).
    """
    observe: bool = False
    metrics_port: Optional[int] = None
    metrics_host: str = "127.0.0.1"
    observe_interval_s: float = 0.0
    observe_every_n: int = 0
    log_file: Optional[str] = None          # F5.3/K-018: đường log production (non-blocking+rotating); None = tắt
    max_cardinality: Optional[int] = None   # K-019: budget series/metric (chống nổ label); None = không giới hạn


@dataclass(frozen=True)
class AppConfig:
    """Toàn bộ file config: danh sách pipeline (mỗi cái 1 camera/luồng) + observability (optional, top-level)."""
    pipelines: Sequence[PipelineConfig] = ()
    observability: Optional[ObservabilityConfig] = None   # None = không khai báo (backward-compat)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pipelines", tuple(self.pipelines))
