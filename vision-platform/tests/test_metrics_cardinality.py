"""K-019 — cưỡng chế cardinality budget trong InMemoryMetrics (chống Prometheus OOM). No-GPU, xác định."""
from __future__ import annotations

import pytest

from vision_platform.runtime.observability import InMemoryMetrics


def _series_count(m: InMemoryMetrics) -> int:
    return len(m.snapshot()["gauges"]) + len(m.snapshot()["counters"])


# ---- default None: KHÔNG giới hạn (tương thích ngược) ----
def test_no_cap_unlimited():
    m = InMemoryMetrics()
    for i in range(100):
        m.gauge("fps", float(i), source=f"cam{i}")
    assert len(m.snapshot()["gauges"]) == 100
    assert m.cardinality_dropped == 0


# ---- cap per-name: series MỚI vượt cap → drop + đếm; series đã có vẫn update ----
def test_cap_drops_new_series_over_budget():
    m = InMemoryMetrics(max_cardinality=2)
    m.gauge("fps", 1.0, source="cam0")     # series 1 (nhận)
    m.gauge("fps", 2.0, source="cam1")     # series 2 (nhận, = cap)
    m.gauge("fps", 3.0, source="cam2")     # series 3 → DROP
    assert m.get_gauge("fps", source="cam0") == 1.0
    assert m.get_gauge("fps", source="cam1") == 2.0
    assert m.get_gauge("fps", source="cam2") is None    # bị drop, không tạo series
    assert m.cardinality_dropped == 1

    # series ĐÃ CÓ vẫn update bình thường (không tính là series mới, không drop)
    m.gauge("fps", 99.0, source="cam0")
    assert m.get_gauge("fps", source="cam0") == 99.0
    assert m.cardinality_dropped == 1                   # không tăng


# ---- cap ĐỘC LẬP theo từng metric-name ----
def test_cap_is_per_name():
    m = InMemoryMetrics(max_cardinality=1)
    m.gauge("a", 1.0, source="x")          # a: series 1 (cap)
    m.gauge("b", 1.0, source="x")          # b: series 1 (cap) — độc lập a
    m.gauge("a", 2.0, source="y")          # a: series 2 → drop
    m.gauge("b", 2.0, source="y")          # b: series 2 → drop
    assert m.get_gauge("a", source="x") == 1.0 and m.get_gauge("a", source="y") is None
    assert m.get_gauge("b", source="x") == 1.0 and m.get_gauge("b", source="y") is None
    assert m.cardinality_dropped == 2


# ---- áp cho cả counter + histogram (cùng cơ chế _admit) ----
def test_cap_applies_to_counter_and_histogram():
    m = InMemoryMetrics(max_cardinality=1)
    m.counter("c", 1.0, k="a"); m.counter("c", 1.0, k="b")   # b → drop
    m.histogram("h", 1.0, k="a"); m.histogram("h", 2.0, k="b")   # b → drop
    assert m.get_counter("c", k="a") == 1 and m.get_counter("c", k="b") == 0
    assert m.get_histogram("h", k="a") == [1.0] and m.get_histogram("h", k="b") == []
    assert m.cardinality_dropped == 2


# ---- re-ghi CÙNG labelset khi đang ở cap → KHÔNG drop (không phải series mới) ----
def test_rewrite_existing_at_cap_not_dropped():
    m = InMemoryMetrics(max_cardinality=1)
    m.gauge("fps", 1.0, source="cam0")
    m.gauge("fps", 2.0, source="cam0")     # cùng labelset → update, không drop
    m.gauge("fps", 3.0, source="cam0")
    assert m.get_gauge("fps", source="cam0") == 3.0
    assert m.cardinality_dropped == 0


# ---- fail-fast tham số ----
def test_bad_max_cardinality():
    with pytest.raises(ValueError):
        InMemoryMetrics(max_cardinality=0)
    with pytest.raises(ValueError):
        InMemoryMetrics(max_cardinality=-5)


# ---- iter_metrics chỉ trả series đã nhận (bị drop KHÔNG xuất hiện) ----
def test_iter_metrics_excludes_dropped():
    m = InMemoryMetrics(max_cardinality=2)
    for i in range(5):
        m.gauge("fps", float(i), source=f"cam{i}")
    names = [(s.name, s.labels.get("source")) for s in m.iter_metrics()]
    assert len(names) == 2                  # chỉ 2 series nhận (cam0, cam1); cam2-4 drop
    assert m.cardinality_dropped == 3
