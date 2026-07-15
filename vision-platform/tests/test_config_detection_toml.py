"""adaptive-detection-perf Task 5: khai báo `[detection]` trong TOML + merge precedence CLI↔TOML — no-GPU.

Mirror cấu trúc `test_config_observability_toml.py` (tiền lệ D-086). Deterministic (parse/merge thuần —
KHÔNG dựng detector/Flask thật; chỉ kiểm parser + hàm merge thuần + file ví dụ template).

Thiết kế (design-first, valid với code thật #400):
- `[detection]` là section TOP-LEVEL, parse bởi `_parse_detection` (application, validate KIỂU fail-fast →
  ConfigError; range/invariant do `DetectionCadenceConfig.__post_init__` — 1 nguồn sự thật).
- Consumer là `vision_web_app` (KHÔNG theo mô hình pipelines) → dùng `load_detection_config(path)` standalone
  (KHÔNG đòi `[[pipelines]]`). Merge `_merge_detection(cli, toml)` precedence CLI-explicit > TOML > default.
_Requirements: 4.2, 1.3_
"""
from __future__ import annotations

import pathlib

import pytest

from vision_platform.kernel.detection_cadence import DetectionCadenceConfig
from vision_platform.application.config_loader import (
    _parse_detection, load_detection_config, ConfigError,
)
from vision_platform.profiles.vision_web_app import _merge_detection

CONFIGS = pathlib.Path(__file__).resolve().parents[1] / "configs"


def _write(tmp_path, body: str) -> str:
    p = tmp_path / "web.toml"
    p.write_text(body, encoding="utf-8")
    return str(p)


# ---------- R1: parse [detection] (type fail-fast + reuse invariant kernel) ----------

def test_parse_detection_full():
    raw = {
        "detect_min_interval_ms": 200, "detect_max_interval_ms": 500, "detect_every_n": 2,
        "motion_gate": True, "motion_threshold": 30, "motion_min_area": 0.01,
        "motion_max_skip": 15, "motion_roi": [0.1, 0.1, 0.8, 0.8], "experimental": False,
    }
    c = _parse_detection(raw)
    assert isinstance(c, DetectionCadenceConfig)
    assert (c.detectMinIntervalMs, c.detectMaxIntervalMs, c.detectEveryN) == (200, 500, 2)
    assert c.motionGate is True and c.motionPixelDiffThreshold == 30
    assert c.motionMinAreaRatio == 0.01 and c.motionMaxConsecutiveSkip == 15
    assert c.motionRoi == (0.1, 0.1, 0.8, 0.8) and c.experimental is False


def test_parse_detection_defaults_when_empty():
    c = _parse_detection({})
    assert c == DetectionCadenceConfig()   # section rỗng → mặc định = hành vi hiện tại


def test_parse_detection_bad_types_raise_configerror():
    for bad in (
        {"detect_min_interval_ms": "200"},      # str thay int
        {"detect_every_n": 1.5},                # float thay int
        {"detect_min_interval_ms": True},       # bool-as-int
        {"motion_gate": "yes"},                 # str thay bool
        {"motion_min_area": "0.01"},            # str thay số
        {"motion_roi": [0.1, 0.1, 0.8]},        # thiếu phần tử
        {"motion_roi": "0.1,0.1"},              # không phải mảng
    ):
        with pytest.raises(ConfigError):
            _parse_detection(bad)
    with pytest.raises(ConfigError):
        _parse_detection(["not", "table"])      # không phải bảng


def test_parse_detection_invariant_violation_raises_configerror():
    # min > max (heartbeat) → DetectionConfigError của kernel → chuyển thành ConfigError ở loader
    with pytest.raises(ConfigError):
        _parse_detection({"detect_min_interval_ms": 800, "detect_max_interval_ms": 500})
    # roi ngoài [0,1] → validate_roi domain → ConfigError
    with pytest.raises(ConfigError):
        _parse_detection({"motion_roi": [0.5, 0.5, 0.8, 0.8]})


# ---------- R1.2 backward-compat: load_detection_config không đòi pipelines ----------

def test_load_detection_config_none_when_absent(tmp_path):
    cfg = _write(tmp_path, "# file rỗng, không có [detection]\n")
    assert load_detection_config(cfg) is None    # không section → None (dùng CLI/default)


def test_load_detection_config_reads_section(tmp_path):
    cfg = _write(tmp_path, "[detection]\ndetect_min_interval_ms = 250\nmotion_gate = true\n")
    c = load_detection_config(cfg)
    assert c is not None and c.detectMinIntervalMs == 250 and c.motionGate is True


def test_load_detection_config_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_detection_config(str(tmp_path / "khong-ton-tai.toml"))


def test_load_detection_config_no_pipelines_required(tmp_path):
    # điểm mấu chốt thiết kế: web app KHÔNG cần [[pipelines]] (khác load_app_config)
    cfg = _write(tmp_path, "[detection]\ndetect_every_n = 3\n")
    c = load_detection_config(cfg)
    assert c is not None and c.detectEveryN == 3


# ---------- R4.2: merge precedence CLI-explicit > TOML > default ----------

def _cli(**over):
    base = {"detect_min_interval_ms": None, "detect_max_interval_ms": None, "detect_every_n": None,
            "motion_gate": False, "motion_threshold": None, "motion_min_area": None, "motion_max_skip": None}
    base.update(over)
    return base


def test_merge_toml_only_when_cli_unset():
    t = DetectionCadenceConfig(detectMinIntervalMs=300, detectEveryN=2, motionGate=True,
                               motionMaxConsecutiveSkip=20)
    m = _merge_detection(_cli(), t)
    assert m.detectMinIntervalMs == 300 and m.detectEveryN == 2
    assert m.motionGate is True and m.motionMaxConsecutiveSkip == 20


def test_merge_cli_explicit_overrides_toml():
    t = DetectionCadenceConfig(detectMinIntervalMs=300, detectEveryN=2)
    m = _merge_detection(_cli(detect_min_interval_ms=100, detect_every_n=5), t)
    assert m.detectMinIntervalMs == 100 and m.detectEveryN == 5


def test_merge_motion_gate_or_semantics():
    # TOML bật, CLI không set store_true → bật
    assert _merge_detection(_cli(), DetectionCadenceConfig(motionGate=True)).motionGate is True
    # CLI bật, không TOML → bật
    assert _merge_detection(_cli(motion_gate=True), None).motionGate is True
    # cả hai tắt → tắt
    assert _merge_detection(_cli(), None).motionGate is False


def test_merge_none_toml_gives_defaults():
    m = _merge_detection(_cli(), None)
    assert m == DetectionCadenceConfig()   # không TOML + CLI unset → hành vi hiện tại (Property 1 additive)


def test_merge_roi_from_toml_only():
    t = DetectionCadenceConfig(motionRoi=(0.2, 0.2, 0.5, 0.5))
    m = _merge_detection(_cli(detect_min_interval_ms=50), t)
    assert m.motionRoi == (0.2, 0.2, 0.5, 0.5)   # roi giữ từ TOML (CLI chưa có --motion-roi)


# ---------- template ví dụ (configs/web/, KHÔNG bị glob bởi test_example_configs) ----------

def test_web_detection_example_template_valid():
    example = CONFIGS / "web" / "example_web_detection.toml"
    assert example.exists(), "phải có template ví dụ [detection] cho web app"
    c = load_detection_config(str(example))
    assert c is not None
    # P5 (liên-spec overlay displayLeaseMs=600): ví dụ phải hợp lệ để không giật
    assert c.detectMinIntervalMs <= 600 and (c.detectMaxIntervalMs == 0 or c.detectMaxIntervalMs <= 600)
