"""Step 08: Observability — structlog + log_context (contextvars) + InMemoryMetrics.

12 test theo Design step-08:
- Metrics (6): counter basic · counter labels · gauge overwrite · histogram append · thread-safe (10×100) · snapshot độc lập.
- log_context (4): set/restore · nested · multi-field · partial fields.
- Logger integration (2): setup_logging chạy + log qua capture_logs · _add_context_vars inject contextvars.
"""
import threading

import structlog
from structlog.testing import capture_logs

from vision_platform.runtime.observability import (
    InMemoryMetrics,
    log_context,
    setup_logging,
    _add_context_vars,
)


# ============ Metrics (6) ============

def test_counter_basic():
    m = InMemoryMetrics()
    m.counter("frames")
    m.counter("frames", 2)
    assert m.get_counter("frames") == 3


def test_counter_with_labels():
    m = InMemoryMetrics()
    m.counter("frames", camera_id="cam_1", status="ok")
    m.counter("frames", camera_id="cam_1", status="ok")
    m.counter("frames", camera_id="cam_2", status="ok")
    assert m.get_counter("frames", camera_id="cam_1", status="ok") == 2
    assert m.get_counter("frames", camera_id="cam_2", status="ok") == 1
    # label thứ tự khác nhau → cùng key (sorted)
    assert m.get_counter("frames", status="ok", camera_id="cam_1") == 2


def test_gauge_overwrites():
    m = InMemoryMetrics()
    m.gauge("queue_depth", 5)
    m.gauge("queue_depth", 3)
    assert m.get_gauge("queue_depth") == 3
    assert m.get_gauge("missing") is None


def test_histogram_appends():
    m = InMemoryMetrics()
    for v in (1.0, 2.5, 3.0):
        m.histogram("latency_ms", v)
    assert m.get_histogram("latency_ms") == [1.0, 2.5, 3.0]


def test_metrics_thread_safe():
    """Increment đồng thời không được mất update (lock cho atomicity)."""
    m = InMemoryMetrics()
    n_threads, n_per = 10, 100

    def worker():
        for _ in range(n_per):
            m.counter("ops")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert m.get_counter("ops") == n_threads * n_per


def test_snapshot_is_independent_copy():
    m = InMemoryMetrics()
    m.counter("c")
    m.histogram("h", 1.0)
    snap = m.snapshot()
    snap["counters"]["c"] = 999          # mutate snapshot
    snap["histograms"]["h"].append(2.0)
    assert m.get_counter("c") == 1        # internal KHÔNG bị ảnh hưởng
    assert m.get_histogram("h") == [1.0]


# ============ log_context (4) ============

def test_log_context_set_and_restore():
    assert _camera_none()
    with log_context(camera_id="cam_1"):
        d = _add_context_vars(None, None, {})
        assert d["camera_id"] == "cam_1"
    # sau block → khôi phục (không còn camera_id)
    assert _camera_none()


def test_log_context_nested_restores_outer():
    with log_context(camera_id="A"):
        with log_context(camera_id="B"):
            assert _add_context_vars(None, None, {})["camera_id"] == "B"
        # thoát B → khôi phục A
        assert _add_context_vars(None, None, {})["camera_id"] == "A"
    assert _camera_none()


def test_log_context_multi_field():
    with log_context(camera_id="c1", packet_id="p1", request_id="r1"):
        d = _add_context_vars(None, None, {})
        assert d["camera_id"] == "c1"
        assert d["packet_id"] == "p1"
        assert d["request_id"] == "r1"


def test_log_context_partial_fields_only_inject_set():
    with log_context(camera_id="only_cam"):
        d = _add_context_vars(None, None, {})
        assert d["camera_id"] == "only_cam"
        assert "packet_id" not in d
        assert "request_id" not in d


# ============ Logger integration (2) ============

def test_setup_logging_and_log_capture():
    setup_logging("INFO")
    log = structlog.get_logger()
    with capture_logs() as caps:
        log.info("frame_received", foo="bar")
    assert caps[0]["event"] == "frame_received"
    assert caps[0]["foo"] == "bar"


def test_processor_injects_context_vars_into_event_dict():
    # Ngoài context → không inject
    assert "camera_id" not in _add_context_vars(None, None, {})
    # Trong context → inject
    with log_context(camera_id="cam_x", request_id="req_y"):
        d = _add_context_vars(None, None, {"event": "x"})
        assert d["camera_id"] == "cam_x"
        assert d["request_id"] == "req_y"


# ---- helper ----
def _camera_none() -> bool:
    return "camera_id" not in _add_context_vars(None, None, {})
