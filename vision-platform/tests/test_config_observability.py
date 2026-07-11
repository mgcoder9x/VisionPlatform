"""config-observability (D-082, review #298): bật `/metrics` cho đường `--config` — no-GPU.

Test đánh vào SEAM `_build_config_observability` TRỰC TIẾP (Lỗ-5 #298): `_run_from_config` đồng bộ + `finally:
exporter.stop()` → KHÔNG scrape được sau khi return (cổng đã đóng, không lộ ra ngoài). Seam trả `(observer,
exporter)` đã `start()` → có `.port` → feed snapshot qua observer → urllib GET `/metrics` → stop.

_Requirements: 1.1–1.4, 3.1–3.4, 4.1–4.4._
"""
from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from vision_platform.kernel.observability_port import PipelineSnapshot
from vision_platform.profiles.vision_slice_app import _build_config_observability, _run_from_config


def _snap(source_id: str, fps: float) -> PipelineSnapshot:
    return PipelineSnapshot(
        source_id=source_id, frames_read=10, processed=8, skipped=2,
        stage_errors=0, frames_per_second=fps, skip_rate=0.2, is_final=True,
    )


def _get(port: int, path: str = "/metrics", timeout: float = 2.0) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return r.read().decode("utf-8")


# ---------- P1/P2: 1 exporter + 1 metrics DÙNG CHUNG → /metrics aggregate theo source_id ----------

def test_shared_exporter_aggregates_two_cameras():
    """P1/P2 (R1.2, R1.3): observe+metrics → composite observer; feed 2 camera khác source_id → /metrics có CẢ 2."""
    observer, exporter = _build_config_observability(observe=True, metrics_port=0, metrics_host="127.0.0.1")
    assert observer is not None and exporter is not None
    try:
        observer.on_snapshot(_snap("cam-A", 5.0))
        observer.on_snapshot(_snap("cam-B", 9.0))
        body = _get(exporter.port)
        assert 'source="cam-A"' in body           # aggregate: mỗi camera 1 series
        assert 'source="cam-B"' in body
        assert "pipeline_fps" in body             # metric name render đúng
    finally:
        exporter.stop()


def test_metrics_without_observe_still_serves():
    """R1.2: chỉ metrics_port (KHÔNG observe) → vẫn có MetricsObserver + /metrics phục vụ (Lỗ-4 #298)."""
    observer, exporter = _build_config_observability(observe=False, metrics_port=0, metrics_host="127.0.0.1")
    assert observer is not None and exporter is not None   # observer = MetricsObserver đơn (không None)
    try:
        observer.on_snapshot(_snap("cam-X", 3.0))
        body = _get(exporter.port)
        assert 'source="cam-X"' in body
    finally:
        exporter.stop()


# ---------- P3: backward-compat tuyệt đối ----------

def test_no_flags_returns_none_none():
    """R1.4/R2.2: không cờ nào → (None, None) → _run_from_config hành xử y hệt hiện tại (Noop, không exporter)."""
    observer, exporter = _build_config_observability(observe=False, metrics_port=None, metrics_host="127.0.0.1")
    assert observer is None
    assert exporter is None


def test_observe_only_returns_single_observer_no_exporter():
    """observe đơn lẻ → observer LoggingObserver, KHÔNG exporter (giữ hành vi D-070)."""
    observer, exporter = _build_config_observability(observe=True, metrics_port=None, metrics_host="127.0.0.1")
    assert observer is not None
    assert exporter is None


# ---------- P5: exporter lifecycle (stop → cổng đóng, không rò) ----------

def test_exporter_stop_closes_port():
    """R3.2: sau stop() → GET cổng → từ chối kết nối (đã đóng, không rò socket/thread)."""
    _observer, exporter = _build_config_observability(observe=False, metrics_port=0, metrics_host="127.0.0.1")
    port = exporter.port
    _get(port)                        # còn sống: OK
    exporter.stop()
    with pytest.raises((urllib.error.URLError, OSError, ConnectionError)):
        _get(port, timeout=1.0)       # đã đóng


# ---------- P6: cảnh báo phơi-mạng ----------

def test_warns_on_non_loopback_bind(capsys):
    """R3.3: bind non-loopback → cảnh báo 'KHÔNG xác thực'; loopback → không cảnh báo."""
    _o, exporter = _build_config_observability(observe=False, metrics_port=0, metrics_host="0.0.0.0")
    try:
        err = capsys.readouterr().err
        assert "CẢNH BÁO" in err and "xác thực" in err
    finally:
        exporter.stop()

    _o2, exporter2 = _build_config_observability(observe=False, metrics_port=0, metrics_host="127.0.0.1")
    try:
        err2 = capsys.readouterr().err
        assert "CẢNH BÁO" not in err2
    finally:
        exporter2.stop()


# ---------- main routing: cờ metrics xuống đường --config ----------

def test_main_routes_metrics_flags_to_config(tmp_path, monkeypatch):
    """main(--config --metrics-port P) → _run_from_config nhận metrics_port/metrics_host (route đúng)."""
    import vision_platform.profiles.vision_slice_app as app_mod

    cfg = tmp_path / "app.toml"
    cfg.write_text("[[pipelines]]\nid='x'\n[pipelines.source]\ntype='fake'\n", encoding="utf-8")

    captured: dict = {}

    def _spy(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(app_mod, "_run_from_config", _spy)
    rc = app_mod.main(["--config", str(cfg), "--metrics-port", "7", "--metrics-host", "127.0.0.1", "--observe"])
    assert rc == 0
    assert captured["metrics_port"] == 7
    assert captured["metrics_host"] == "127.0.0.1"
    assert captured["observe"] is True
    # --observe (hoặc --metrics-port) → main set nhịp 5s (thấy sức khỏe định kỳ)
    assert captured["observe_interval_s"] == 5.0


# ---------- integration: _run_from_config thật + metrics bật → chạy xong + exporter stop sạch (không rò) ----------

def test_run_from_config_with_metrics_runs_and_cleans_up(tmp_path):
    """R3.1/R3.2 end-to-end: config fake 1 pipeline + metrics_port=0 → chạy xong return 0; exporter đã stop
    trong finally (không treo/không rò — nếu rò thì test-suite sẽ treo ở đây)."""
    cfg = tmp_path / "app.toml"
    cfg.write_text(
        "[[pipelines]]\nid='cam-1'\nmax_frames=3\n"
        "[pipelines.source]\ntype='fake'\nparams={ max_frames = 3 }\n"
        "[[pipelines.stages]]\ntype='count'\n",
        encoding="utf-8",
    )
    rc = _run_from_config(str(cfg), observe=False, metrics_port=0, metrics_host="127.0.0.1")
    assert rc == 0
