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

from typing import Optional

from vision_platform.kernel.config import (
    AppConfig, PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig, ObservabilityConfig,
)
from vision_platform.kernel.backpressure import BackpressurePolicy
from vision_platform.kernel.detection_cadence import DetectionCadenceConfig, DetectionConfigError


class ConfigError(Exception):
    """Config sai (thiếu field / type không phải chuỗi / id trùng / TOML hỏng / file thiếu). Fail-fast."""


def assert_policy_allowed_for_source(source_type: str, policy: BackpressurePolicy) -> None:
    """R3 (Wave 3.2): CẤM `Backpressure_Policy.BLOCK` cho nguồn RTSP.

    Vì sao (bản chất): BLOCK làm producer (camera) CHỜ khi hàng đợi outbound đầy. Với RTSP over TCP, việc
    ngừng đọc socket → cửa sổ nhận cạn → **TCP Zero Window** → server/camera nghẽn → rớt kết nối/frame IM LẶNG
    (đúng lỗ A2 đang đóng). RTSP là luồng real-time không thể "chờ" — phải bỏ frame (DROP_*) hoặc REJECT.

    Đặt ở tầng cấu hình per-source (R3.2) — KHÔNG ở `kernel/backpressure.py::BoundedQueue` (giữ nó
    policy-agnostic, tái dùng được cho nguồn non-RTSP với BLOCK). Guard THUẦN + fail-fast: gọi tại nơi
    map config→client khi dựng client cho 1 source. (Schema config hiện CHƯA mang `policy` per-source —
    guard sẵn-sàng-wire, xem journal D-050/K-053.) rtsp+BLOCK → ConfigError; tổ hợp khác → không làm gì.
    """
    if source_type == "rtsp" and policy == BackpressurePolicy.BLOCK:
        raise ConfigError(
            "policy 'BLOCK' KHÔNG hợp lệ cho nguồn RTSP: BLOCK khiến producer chờ khi hàng đợi đầy → "
            "TCP Zero Window làm nghẽn luồng → mất kết nối/frame im lặng. "
            "Dùng DROP_OLDEST / DROP_NEWEST / REJECT cho RTSP."
        )


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


def _parse_observability(raw: Any) -> ObservabilityConfig:
    """Parse table top-level `[observability]` → `ObservabilityConfig`. Validate KIỂU từng field (fail-fast).

    KHÔNG dùng bool vô-tình cho int (isinstance(True,int) là True trong Python) → kiểm loại tường minh."""
    _require(isinstance(raw, dict), f"observability phải là bảng, nhận {type(raw).__name__}")

    observe = raw.get("observe", False)
    _require(isinstance(observe, bool), f"observability.observe phải là bool (nhận {observe!r})")

    port = raw.get("metrics_port")
    _require(port is None or (isinstance(port, int) and not isinstance(port, bool)),
             f"observability.metrics_port phải là số nguyên hoặc vắng (nhận {port!r})")

    host = raw.get("metrics_host", "127.0.0.1")
    _require(isinstance(host, str) and host != "", f"observability.metrics_host phải là chuỗi không rỗng (nhận {host!r})")

    interval = raw.get("observe_interval_s", 0.0)
    _require(isinstance(interval, (int, float)) and not isinstance(interval, bool),
             f"observability.observe_interval_s phải là số (nhận {interval!r})")

    every = raw.get("observe_every_n", 0)
    _require(isinstance(every, int) and not isinstance(every, bool),
             f"observability.observe_every_n phải là số nguyên (nhận {every!r})")

    return ObservabilityConfig(
        observe=observe, metrics_port=port, metrics_host=host,
        observe_interval_s=float(interval), observe_every_n=every,
    )


def _parse_detection(raw: Any) -> DetectionCadenceConfig:
    """Parse table top-level `[detection]` → `DetectionCadenceConfig` (spec adaptive-detection-perf Task 5).

    PHÂN VAI (tránh drift 2 validator): loader kiểm **KIỂU/CẤU TRÚC** (fail-fast ConfigError, chặn bool-as-int
    như `_parse_observability`); **RANGE + INVARIANT** (min<=max, roi∈[0,1], threshold∈[0,255]...) do
    `DetectionCadenceConfig.__post_init__` — 1 nguồn sự thật. Lỗi invariant kernel (`DetectionConfigError`)
    được gói lại thành `ConfigError` để caller nhận một loại lỗi thống nhất.

    Khoá TOML = snake_case bám tên cờ CLI (`vision_web_app`): detect_min_interval_ms / detect_max_interval_ms /
    detect_every_n / motion_gate / motion_threshold / motion_min_area / motion_max_skip / motion_roi / experimental.
    """
    _require(isinstance(raw, dict), f"detection phải là bảng, nhận {type(raw).__name__}")

    def _int(key: str, default: int) -> int:
        v = raw.get(key, default)
        _require(isinstance(v, int) and not isinstance(v, bool),
                 f"detection.{key} phải là số nguyên (nhận {v!r})")
        return v

    def _bool(key: str, default: bool) -> bool:
        v = raw.get(key, default)
        _require(isinstance(v, bool), f"detection.{key} phải là bool (nhận {v!r})")
        return v

    min_interval = _int("detect_min_interval_ms", 0)
    max_interval = _int("detect_max_interval_ms", 0)
    every_n = _int("detect_every_n", 1)
    motion_gate = _bool("motion_gate", False)
    threshold = _int("motion_threshold", 25)

    area = raw.get("motion_min_area", 0.005)
    _require(isinstance(area, (int, float)) and not isinstance(area, bool),
             f"detection.motion_min_area phải là số (nhận {area!r})")

    max_skip = _int("motion_max_skip", 0)

    roi_raw = raw.get("motion_roi")
    roi: Optional[tuple] = None
    if roi_raw is not None:
        _require(isinstance(roi_raw, (list, tuple)) and len(roi_raw) == 4,
                 f"detection.motion_roi phải là mảng 4 số [x,y,w,h] chuẩn-hoá [0,1] (nhận {roi_raw!r})")
        for elem in roi_raw:
            _require(isinstance(elem, (int, float)) and not isinstance(elem, bool),
                     f"detection.motion_roi phần tử phải là số (nhận {elem!r})")
        roi = tuple(float(x) for x in roi_raw)

    experimental = _bool("experimental", True)

    try:
        return DetectionCadenceConfig(
            detectMinIntervalMs=min_interval, detectMaxIntervalMs=max_interval, detectEveryN=every_n,
            motionGate=motion_gate, motionPixelDiffThreshold=threshold, motionMinAreaRatio=float(area),
            motionMaxConsecutiveSkip=max_skip, motionRoi=roi, experimental=experimental,
        )
    except DetectionConfigError as e:
        raise ConfigError(f"detection: {e}") from e


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

    obs_raw = raw.get("observability")
    observability = _parse_observability(obs_raw) if obs_raw is not None else None
    return AppConfig(pipelines=pipelines, observability=observability)


def _read_toml(path: str) -> dict:
    """Đọc file TOML (`tomllib`, mở 'rb') → dict. File thiếu/sai TOML → `ConfigError`. DÙNG CHUNG (DRY)."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"không tìm thấy file config: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML sai cú pháp trong {path}: {e}") from e


def load_app_config(path: str) -> AppConfig:
    """Đọc file TOML → `parse_app_config` (mô hình pipelines — cho `vision_slice_app --config`)."""
    return parse_app_config(_read_toml(path))


def load_detection_config(path: str) -> Optional[DetectionCadenceConfig]:
    """Đọc `[detection]` từ file TOML → `DetectionCadenceConfig` (hoặc None nếu không có section).

    Dành cho profile KHÔNG theo mô hình pipelines (vd `vision_web_app`) — KHÔNG đòi `[[pipelines]]` (khác
    `load_app_config`). Vì `vision_web_app` là webcam→detect bespoke, không có khái niệm pipeline; ép nó
    mang `[[pipelines]]` giả sẽ sai bản chất. Parser `_parse_detection` dùng chung → không drift validate.
    """
    raw = _read_toml(path)
    det = raw.get("detection")
    return _parse_detection(det) if det is not None else None
