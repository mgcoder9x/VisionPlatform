"""Spec metrics-http-endpoint — test XÁC ĐỊNH (ephemeral port 127.0.0.1 + urllib), KHÔNG GPU/mạng-ngoài.

Phủ Property: P1 GET /metrics đúng+content-type · P2 404/healthz · P3 cập-nhật mỗi scrape · P4 lỗi→500 server sống
· P5 non-blocking + start/stop sạch (kể cả stop NGAY sau start — chống deadlock) · P6 default localhost.
"""
import socket
import urllib.error
import urllib.request

import pytest

from vision_platform.kernel.metric_sample import MetricSample
from vision_platform.adapters.metrics_http_server import MetricsHttpExporter, is_loopback


def _get(port, path="/metrics", timeout=5.0):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")


def _provider_fixed():
    return [MetricSample("gauge", "pipeline_fps", 12.5, {"source": "cam0"}),
            MetricSample("counter", "frames_total", 7.0, {})]


# ============ P1: GET /metrics đúng + content-type ============

def test_metrics_endpoint_serves_prometheus():
    exp = MetricsHttpExporter(_provider_fixed, host="127.0.0.1", port=0)
    port = exp.start()
    try:
        status, ctype, body = _get(port)
        assert status == 200
        assert ctype == "text/plain; version=0.0.4; charset=utf-8"
        assert 'pipeline_fps{source="cam0"} 12.5' in body
        assert "# TYPE pipeline_fps gauge" in body
        assert "# TYPE frames_total counter" in body
    finally:
        exp.stop()


# ============ P2: 404 path lạ + /healthz ============

def test_unknown_path_404_and_healthz():
    exp = MetricsHttpExporter(_provider_fixed, port=0, enable_healthz=True)
    port = exp.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as ei:
            _get(port, "/")
        assert ei.value.code == 404
        status, _ctype, body = _get(port, "/healthz")
        assert status == 200 and "ok" in body
    finally:
        exp.stop()


def test_healthz_disabled_is_404():
    exp = MetricsHttpExporter(_provider_fixed, port=0, enable_healthz=False)
    port = exp.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as ei:
            _get(port, "/healthz")
        assert ei.value.code == 404
    finally:
        exp.stop()


# ============ P3: cập-nhật mỗi scrape ============

def test_metrics_reflects_current_state_each_scrape():
    state = {"v": 1.0}
    exp = MetricsHttpExporter(lambda: [MetricSample("gauge", "g", state["v"], {})], port=0)
    port = exp.start()
    try:
        _, _, b1 = _get(port)
        assert "g 1.0" in b1
        state["v"] = 2.0
        _, _, b2 = _get(port)
        assert "g 2.0" in b2         # scrape mới phản ánh state mới (không cache)
    finally:
        exp.stop()


# ============ P4: provider lỗi → 500, server vẫn sống ============

def test_provider_error_returns_500_and_server_survives():
    flag = {"boom": True}
    def provider():
        if flag["boom"]:
            raise RuntimeError("provider hỏng")
        return [MetricSample("gauge", "g", 1.0, {})]
    exp = MetricsHttpExporter(provider, port=0)
    port = exp.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as ei:
            _get(port)
        assert ei.value.code == 500
        flag["boom"] = False           # sửa provider → scrape sau phải OK (server không sập)
        status, _c, body = _get(port)
        assert status == 200 and "g 1.0" in body
    finally:
        exp.stop()


# ============ P5: non-blocking + start/stop sạch (chống deadlock) ============

def test_start_stop_immediate_no_deadlock():
    """stop() NGAY sau start() (serve_forever có thể chưa vào) → KHÔNG deadlock (nhờ _serving Event)."""
    exp = MetricsHttpExporter(_provider_fixed, port=0)
    port = exp.start()
    exp.stop()                          # nếu deadlock → test treo (join/wait bounded → vẫn thoát, cổng đóng)
    # sau stop: cổng đóng → connect refused
    with pytest.raises((urllib.error.URLError, ConnectionError, socket.timeout, OSError)):
        _get(port, timeout=1.0)


def test_stop_idempotent():
    exp = MetricsHttpExporter(_provider_fixed, port=0)
    exp.start()
    exp.stop()
    exp.stop()                          # 2 lần → không raise


# ============ CLI wire smoke (vision_slice_app --metrics-port) ============

def test_cli_metrics_port_smoke():
    """Wire inline: --metrics-port 0 → tạo InMemoryMetrics+MetricsObserver+exporter, chạy, stop sạch → rc 0."""
    from vision_platform.profiles.vision_slice_app import main
    rc = main(["--source", "fake", "--frames", "5", "--metrics-port", "0"])
    assert rc == 0


# ============ P6: default localhost + is_loopback ============

def test_default_host_is_loopback():
    exp = MetricsHttpExporter(_provider_fixed)   # không truyền host
    assert exp._host == "127.0.0.1"
    assert is_loopback("127.0.0.1") and is_loopback("localhost") and is_loopback("::1")
    assert not is_loopback("0.0.0.0")
