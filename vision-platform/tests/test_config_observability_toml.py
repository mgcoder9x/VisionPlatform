"""config-observability-toml (D-086): khai báo `[observability]` trong TOML + merge precedence CLI↔TOML — no-GPU.

Reviewed #310 (host-sentinel fix). Deterministic (parse/merge thuần + spy `_build_config_observability` → không
dựng exporter thật khi test merge; test host-sentinel dùng port=0 ephemeral).
_Requirements: 1.1–1.4, 2.1–2.4, 3.1–3.4, 4.1–4.4._
"""
from __future__ import annotations

import pytest

from vision_platform.kernel.config import ObservabilityConfig
from vision_platform.application.config_loader import parse_app_config, ConfigError
from vision_platform.profiles.vision_slice_app import (
    _merge_observability, _build_config_observability, _run_from_config,
)
import vision_platform.profiles.vision_slice_app as app_mod


def _base():
    return {"pipelines": [{"id": "cam0", "max_frames": 3,
                           "source": {"type": "fake", "params": {"max_frames": 3}},
                           "stages": [{"type": "count"}]}]}


def _write(tmp_path, body: str) -> str:
    p = tmp_path / "cam.toml"
    p.write_text(body, encoding="utf-8")
    return str(p)


_PIPE_TOML = ("[[pipelines]]\nid='cam0'\nmax_frames=3\n"
              "[pipelines.source]\ntype='fake'\nparams={ max_frames = 3 }\n"
              "[[pipelines.stages]]\ntype='count'\n")


# ---------- R1: parse [observability] ----------

def test_parse_observability_section():
    raw = _base()
    raw["observability"] = {"observe": True, "metrics_port": 9100, "observe_interval_s": 2.5, "observe_every_n": 4}
    o = parse_app_config(raw).observability
    assert o is not None
    assert (o.observe, o.metrics_port, o.metrics_host, o.observe_interval_s, o.observe_every_n) \
        == (True, 9100, "127.0.0.1", 2.5, 4)


def test_parse_no_observability_is_none():
    assert parse_app_config(_base()).observability is None   # backward-compat (R1.2)


def test_parse_observability_bad_types_raise():
    for bad in ({"metrics_port": "9100"}, {"observe": "yes"}, {"observe_every_n": 1.5}):
        raw = _base(); raw["observability"] = bad
        with pytest.raises(ConfigError):
            parse_app_config(raw)
    raw = _base(); raw["observability"] = ["not", "table"]
    with pytest.raises(ConfigError):
        parse_app_config(raw)


# ---------- R2: merge precedence ----------

def test_merge_toml_only_when_cli_unset():
    t = ObservabilityConfig(observe=True, metrics_port=9100, metrics_host="0.0.0.0",
                            observe_interval_s=3.0, observe_every_n=2)
    m = _merge_observability(
        {"observe": False, "metrics_port": None, "metrics_host": None, "observe_interval_s": 0.0, "observe_every_n": 0}, t)
    assert m == {"observe": True, "metrics_port": 9100, "metrics_host": "0.0.0.0",
                 "observe_interval_s": 3.0, "observe_every_n": 2,
                 "log_file": None, "max_cardinality": None}


def test_merge_cli_explicit_overrides_toml():
    t = ObservabilityConfig(metrics_port=9100, metrics_host="0.0.0.0")
    m = _merge_observability(
        {"observe": False, "metrics_port": 8888, "metrics_host": "127.0.0.1", "observe_interval_s": 0.0, "observe_every_n": 0}, t)
    assert m["metrics_port"] == 8888 and m["metrics_host"] == "127.0.0.1"


def test_merge_observe_or_semantics():
    m_toml = _merge_observability(
        {"observe": False, "metrics_port": None, "metrics_host": None, "observe_interval_s": 0.0, "observe_every_n": 0},
        ObservabilityConfig(observe=True))
    assert m_toml["observe"] is True                      # TOML bật
    m_cli = _merge_observability(
        {"observe": True, "metrics_port": None, "metrics_host": None, "observe_interval_s": 0.0, "observe_every_n": 0}, None)
    assert m_cli["observe"] is True                       # CLI bật, không TOML


def test_merge_none_toml_gives_defaults():
    m = _merge_observability(
        {"observe": False, "metrics_port": None, "metrics_host": None, "observe_interval_s": 0.0, "observe_every_n": 0}, None)
    # toml=None → dùng ObservabilityConfig() default → metrics_host="127.0.0.1" (KHÔNG None); host None-resolve ở _build_config_observability
    assert m == {"observe": False, "metrics_port": None, "metrics_host": "127.0.0.1",
                 "observe_interval_s": 0.0, "observe_every_n": 0,
                 "log_file": None, "max_cardinality": None}


# ---------- #310: host-sentinel None → resolve 127.0.0.1 (không crash CLI-direct) ----------

def test_build_config_observability_host_none_resolves():
    _o, exporter, _lh = _build_config_observability(observe=False, metrics_port=0, metrics_host=None)
    try:
        assert exporter is not None and exporter.port > 0   # resolve 127.0.0.1 → start OK, KHÔNG crash
    finally:
        exporter.stop()


# ---------- R4: e2e — TOML observability chảy qua _run_from_config ----------

def test_run_from_config_uses_toml_observability(tmp_path, monkeypatch):
    cfg = _write(tmp_path, "[observability]\nmetrics_port = 0\nobserve = true\n\n" + _PIPE_TOML)
    cap: dict = {}

    def spy(observe, metrics_port, metrics_host, log_file=None, max_cardinality=None):
        cap.update(observe=observe, metrics_port=metrics_port, metrics_host=metrics_host,
                   log_file=log_file, max_cardinality=max_cardinality)
        return None, None, None                             # không dựng exporter thật (observer, exporter, log_handle)

    monkeypatch.setattr(app_mod, "_build_config_observability", spy)
    rc = _run_from_config(cfg)                               # KHÔNG cờ CLI → dùng TOML
    assert rc == 0
    assert cap["observe"] is True and cap["metrics_port"] == 0 and cap["metrics_host"] == "127.0.0.1"


def test_run_from_config_cli_overrides_toml(tmp_path, monkeypatch):
    cfg = _write(tmp_path, "[observability]\nmetrics_port = 9100\n\n" + _PIPE_TOML)
    cap: dict = {}
    monkeypatch.setattr(app_mod, "_build_config_observability",
                        lambda o, p, h, log_file=None, max_cardinality=None: (cap.update(port=p) or (None, None, None)))
    _run_from_config(cfg, metrics_port=8888)                # CLI override TOML
    assert cap["port"] == 8888


def test_run_from_config_backward_compat_no_section(tmp_path, monkeypatch):
    cfg = _write(tmp_path, _PIPE_TOML)                      # KHÔNG [observability]
    cap: dict = {}
    monkeypatch.setattr(app_mod, "_build_config_observability",
                        lambda o, p, h, log_file=None, max_cardinality=None: (cap.update(observe=o, port=p) or (None, None, None)))
    rc = _run_from_config(cfg)
    assert rc == 0 and cap == {"observe": False, "port": None}   # default → hành vi #299


# ---------- F5.3/K-019: wire log_file + max_cardinality qua [observability] TOML ----------

def test_parse_observability_log_file_and_cardinality():
    raw = _base()
    raw["observability"] = {"log_file": "/var/log/vp.jsonl", "max_cardinality": 500}
    o = parse_app_config(raw).observability
    assert o is not None and o.log_file == "/var/log/vp.jsonl" and o.max_cardinality == 500


def test_parse_observability_new_fields_default_none():
    raw = _base(); raw["observability"] = {"observe": True}
    o = parse_app_config(raw).observability
    assert o.log_file is None and o.max_cardinality is None   # vắng → None (opt-in, backward-compat)


def test_parse_observability_new_fields_bad_types_raise():
    # log_file rỗng · max_cardinality không dương / là bool / là float → ConfigError (fail-fast)
    for bad in ({"log_file": ""}, {"max_cardinality": 0}, {"max_cardinality": -5},
                {"max_cardinality": True}, {"max_cardinality": 1.5}, {"log_file": 123}):
        raw = _base(); raw["observability"] = bad
        with pytest.raises(ConfigError):
            parse_app_config(raw)


def test_merge_new_fields_toml_only_when_cli_unset():
    t = ObservabilityConfig(log_file="/t/a.jsonl", max_cardinality=300)
    m = _merge_observability(
        {"observe": False, "metrics_port": None, "metrics_host": None,
         "observe_interval_s": 0.0, "observe_every_n": 0, "log_file": None, "max_cardinality": None}, t)
    assert m["log_file"] == "/t/a.jsonl" and m["max_cardinality"] == 300


def test_merge_new_fields_cli_explicit_overrides_toml():
    t = ObservabilityConfig(log_file="/t/toml.jsonl", max_cardinality=300)
    m = _merge_observability(
        {"observe": False, "metrics_port": None, "metrics_host": None,
         "observe_interval_s": 0.0, "observe_every_n": 0,
         "log_file": "/t/cli.jsonl", "max_cardinality": 999}, t)
    assert m["log_file"] == "/t/cli.jsonl" and m["max_cardinality"] == 999


def test_run_from_config_wires_new_fields_from_toml(tmp_path, monkeypatch):
    cfg = _write(tmp_path, "[observability]\nlog_file = '/t/vp.jsonl'\nmax_cardinality = 250\n\n" + _PIPE_TOML)
    cap: dict = {}

    def spy(observe, metrics_port, metrics_host, log_file=None, max_cardinality=None):
        cap.update(log_file=log_file, max_cardinality=max_cardinality)
        return None, None, None

    monkeypatch.setattr(app_mod, "_build_config_observability", spy)
    rc = _run_from_config(cfg)                               # KHÔNG cờ CLI → dùng TOML
    assert rc == 0 and cap["log_file"] == "/t/vp.jsonl" and cap["max_cardinality"] == 250
