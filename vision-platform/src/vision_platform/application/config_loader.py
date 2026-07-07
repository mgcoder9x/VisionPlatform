"""ConfigLoader — đọc + validate file config khai báo (sub-spec config-declarative, Task 2).

Layer: application (được import kernel + stdlib; KHÔNG import adapters/profiles — import-linter ép). Do đó
loader chỉ validate **CẤU TRÚC** (field bắt buộc, id duy nhất, type là chuỗi không rỗng). Kiểm `type` có
trong registry là việc của `profiles/pipeline_factory.py` (Task 3) — nơi biết registry.

`parse_app_config(dict) -> AppConfig` tách khỏi I/O để test không cần file. `load_app_config(path)` đọc TOML
bằng `tomllib` (Python 3.11 stdlib — KHÔNG thêm dependency). Sai → `ConfigError` fail-fast, thông điệp rõ.
"""
from __future__ import annotations

import tomllib
from typing import Any

from vision_platform.kernel.config import (
    AppConfig, PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
)


class ConfigError(Exception):
    """Config sai (thiếu field / type không phải chuỗi / id trùng / TOML hỏng / file thiếu). Fail-fast."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def _require_str(value: Any, what: str) -> str:
    _require(isinstance(value, str) and value != "", f"{what} phải là chuỗi không rỗng (nhận: {value!r})")
    return value


def _typed(raw: Any, what: str) -> tuple[str, dict]:
    """Ép 1 mục {type, params?} → (type:str, params:dict). Validate cấu trúc."""
    _require(isinstance(raw, dict), f"{what} phải là bảng (table), nhận {type(raw).__name__}")
    t = _require_str(raw.get("type"), f"{what}.type")
    params = raw.get("params", {})
    _require(isinstance(params, dict), f"{what}.params phải là bảng, nhận {type(params).__name__}")
    return t, params


def parse_app_config(raw: dict) -> AppConfig:
    """Dựng `AppConfig` từ dict đã đọc + validate CẤU TRÚC. Sai → `ConfigError`.

    KHÔNG kiểm `type` có trong registry (việc của pipeline_factory — layer profiles).
    """
    _require(isinstance(raw, dict), "config gốc phải là bảng")
    pipelines_raw = raw.get("pipelines")
    _require(isinstance(pipelines_raw, list), "config phải có mảng 'pipelines' (array-of-tables)")

    pipelines: list[PipelineConfig] = []
    seen_ids: set[str] = set()
    for i, p in enumerate(pipelines_raw):
        where = f"pipelines[{i}]"
        _require(isinstance(p, dict), f"{where} phải là bảng")
        pid = _require_str(p.get("id"), f"{where}.id")
        _require(pid not in seen_ids, f"id pipeline trùng: {pid!r} (mỗi pipeline phải duy nhất)")
        seen_ids.add(pid)

        s_type, s_params = _typed(p.get("source"), f"{where}.source")
        source = SourceConfig(s_type, s_params)

        stages_raw = p.get("stages", [])
        _require(isinstance(stages_raw, list), f"{where}.stages phải là mảng")
        stages = [StageConfig(*_typed(st, f"{where}.stages[{j}]")) for j, st in enumerate(stages_raw)]

        sinks_raw = p.get("sinks", [])
        _require(isinstance(sinks_raw, list), f"{where}.sinks phải là mảng")
        sinks = [SinkConfig(*_typed(sk, f"{where}.sinks[{j}]")) for j, sk in enumerate(sinks_raw)]

        detector = None
        if p.get("detector") is not None:
            d_type, d_params = _typed(p.get("detector"), f"{where}.detector")
            detector = DetectorConfig(d_type, d_params)

        max_frames = p.get("max_frames")
        _require(max_frames is None or isinstance(max_frames, int),
                 f"{where}.max_frames phải là số nguyên hoặc vắng (nhận {max_frames!r})")

        pipelines.append(PipelineConfig(
            id=pid, source=source, stages=stages, sinks=sinks,
            detector=detector, max_frames=max_frames,
        ))

    return AppConfig(pipelines=pipelines)


def load_app_config(path: str) -> AppConfig:
    """Đọc file TOML (`tomllib`, mở 'rb') → `parse_app_config`. File thiếu/sai TOML → `ConfigError`."""
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"không tìm thấy file config: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML sai cú pháp trong {path}: {e}") from e
    return parse_app_config(raw)
