"""Spec metrics-exposition — test XÁC ĐỊNH (dựng MetricSample tay + InMemoryMetrics), KHÔNG GPU.

Phủ Correctness Properties:
- P1 gauge · P2 counter+không-nhãn · P3 escaping · P4 1 TYPE/family · P5 idempotent · P6 rỗng
- P7 không-lossy (iter_metrics cấu trúc) · P8 layer(lint riêng) · P9 tích hợp MetricsObserver
- P10 inf/nan → +Inf/-Inf/NaN · P11 xung đột name↔type → ValueError.
"""
import math

import pytest

from vision_platform.kernel.metric_sample import MetricSample
from vision_platform.adapters.metrics_exposition import render_prometheus
from vision_platform.runtime.observability import InMemoryMetrics


def _g(name, value, **labels):
    return MetricSample("gauge", name, float(value), dict(labels))


def _c(name, value, **labels):
    return MetricSample("counter", name, float(value), dict(labels))


# ============ P1: gauge ============

def test_gauge_render():
    out = render_prometheus([_g("g", 1.5, source="cam0")])
    assert "# TYPE g gauge" in out
    assert 'g{source="cam0"} 1.5' in out


# ============ P2: counter + không nhãn ============

def test_counter_no_labels():
    out = render_prometheus([_c("c", 7)])
    assert "# TYPE c counter" in out
    assert "\nc 7.0\n" in out or out.startswith("# TYPE c counter\nc 7.0")


# ============ P3: escaping ============

def test_label_value_escaping():
    # value nhãn: a " b \ c <newline>
    out = render_prometheus([_g("g", 1.0, k='a"b\\c\n')])
    # kỳ vọng: a\"b\\c\n  (backslash escape trước)
    assert 'k="a\\"b\\\\c\\n"' in out


# ============ P4: 1 TYPE cho family nhiều sample ============

def test_one_type_per_family():
    out = render_prometheus([_g("g", 1.0, source="cam0"), _g("g", 2.0, source="cam1")])
    assert out.count("# TYPE g gauge") == 1
    assert 'g{source="cam0"} 1.0' in out and 'g{source="cam1"} 2.0' in out


# ============ P5: xác định / idempotent ============

def test_deterministic():
    s = [_g("b", 2.0, x="1"), _g("a", 1.0, y="2"), _c("a_total", 3)]
    assert render_prometheus(s) == render_prometheus(list(reversed(s)))  # thứ tự input không đổi output


# ============ P6: rỗng ============

def test_empty():
    assert render_prometheus([]) == ""


# ============ P10: inf/nan ============

def test_inf_nan_values():
    out = render_prometheus([
        _g("pos", math.inf), _g("neg", -math.inf), _g("nan", math.nan), _g("fin", 0.005),
    ])
    assert "pos +Inf" in out
    assert "neg -Inf" in out
    assert "nan NaN" in out
    assert "fin 0.005" in out               # số hữu hạn giữ độ chính xác (không thành 0)


# ============ P11: xung đột name↔type ============

def test_name_type_conflict_raises():
    with pytest.raises(ValueError) as ei:
        render_prometheus([_c("x", 1), _g("x", 2.0)])
    assert "x" in str(ei.value) and "type" in str(ei.value).lower()


# ============ P7: iter_metrics KHÔNG lossy (nhãn chứa ,/=) ============

def test_iter_metrics_no_lossy_with_separator_labels():
    m = InMemoryMetrics()
    m.gauge("pipeline_fps", 12.5, source="cam,x=1")   # value nhãn chứa , và = (bẫy parse chuỗi)
    samples = m.iter_metrics()
    assert len(samples) == 1
    s = samples[0]
    assert s.name == "pipeline_fps"
    assert s.labels == {"source": "cam,x=1"}          # giữ NGUYÊN (không parse-ngược lossy)
    out = render_prometheus(samples)
    assert 'pipeline_fps{source="cam,x=1"} 12.5' in out


# ============ iter_metrics: counter + gauge, invariant getter không mutate ============

def test_iter_metrics_counter_and_gauge():
    m = InMemoryMetrics()
    m.counter("hits", 3, route="a")
    m.gauge("temp", 9.0)
    _ = m.get_counter("never_written")                # getter KHÔNG được tạo key rác
    _ = m.get_histogram("never_hist")
    samples = m.iter_metrics()
    names = {(s.mtype, s.name) for s in samples}
    assert ("counter", "hits") in names
    assert ("gauge", "temp") in names
    assert not any(s.name == "never_written" for s in samples)   # bất biến: chỉ key ĐÃ GHI


# ============ P9: tích hợp MetricsObserver (end-to-end no-GPU) ============

def test_integration_with_metrics_observer():
    import numpy as np
    from vision_platform.kernel.read_result import ReadResult, ReadStatus
    from vision_platform.runtime.pipeline_runner import PipelineRunner
    from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
    from vision_platform.runtime.composite_sink import CompositeSink
    from vision_platform.runtime.base_stage import BaseStage
    from vision_platform.runtime.observers import MetricsObserver

    class _Src:
        def __init__(self, n): self._n = n; self._i = 0; self.source_id = "cam7"; self.is_finite = True
        def setup(self): self._i = 0
        def teardown(self): pass
        def read(self, timeout_ms=100):
            if self._i < self._n:
                self._i += 1
                return ReadResult(status=ReadStatus.FRAME, data=np.zeros((4, 4, 3), np.uint8))
            return ReadResult(status=ReadStatus.EOF)

    class _Pass(BaseStage):
        def __init__(self): super().__init__("pass")
        def _do_process(self, packet): return packet

    m = InMemoryMetrics()
    r = PipelineRunner(_Src(5), SyncLinearExecutor([_Pass()]), CompositeSink([]),
                       observer=MetricsObserver(m), emit_every_n=5)
    r.run(max_frames=5)
    out = render_prometheus(m.iter_metrics())
    assert 'pipeline_fps{source="cam7"}' in out
    assert 'pipeline_skip_rate{source="cam7"}' in out
    assert "# TYPE pipeline_fps gauge" in out
