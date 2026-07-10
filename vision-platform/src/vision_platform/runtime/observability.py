"""Observability: structlog setup + log_context (contextvars) + InMemoryMetrics.

Layer: runtime — được phép import structlog (contract #3 chỉ cấm application/adapters/profiles).
KHÔNG import application/adapters/profiles.

3 trụ observability (vision_demo làm logs + metrics; traces để Module 04):
    Logs    → structlog (JSON, parse được bởi Loki/ELK/Datadog).
    Metrics → InMemoryMetrics (counter/gauge/histogram, thay bằng Prometheus/StatsD ở production).

⚠️ Ranh giới (K-018): bản này CỐ Ý bỏ so với production (`08-observability.md`): _BoundedQueueHandler
non-blocking, RotatingFileHandler xoay theo size, LoggingHandle.shutdown() flush lúc cascade. Đủ học
pattern contextvars + processor; sản phẩm thật cần bổ sung 3 cái đó.
⚠️ Cardinality (K-019): label metric PHẢI bounded (camera_id/status...). KHÔNG đặt packet_id/bbox
coords vào label (nổ số key → Prometheus OOM) — cho vào LOGS (high-cardinality OK).
"""
from __future__ import annotations

import contextvars
import logging
from collections import defaultdict
from threading import Lock
from typing import Any

import structlog


# Context vars cho các field xuyên suốt (cross-cutting) của log.
_camera_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "camera_id", default=None,
)
_packet_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "packet_id", default=None,
)
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None,
)


def _add_context_vars(_, __, event_dict: dict) -> dict:
    """structlog processor: chèn giá trị contextvars vào mỗi dòng log (nếu có set)."""
    cid = _camera_id_var.get()
    pid = _packet_id_var.get()
    rid = _request_id_var.get()
    if cid:
        event_dict["camera_id"] = cid
    if pid:
        event_dict["packet_id"] = pid
    if rid:
        event_dict["request_id"] = rid
    return event_dict


class log_context:
    """Context manager bind contextvars trong suốt block (nested-safe).

    Usage:
        with log_context(camera_id="cam_1", packet_id="pkt_42"):
            logger.info("frame_received")   # → log tự có camera_id + packet_id
    """

    def __init__(self, *, camera_id=None, packet_id=None, request_id=None):
        self._kwargs = {
            "camera_id": camera_id,
            "packet_id": packet_id,
            "request_id": request_id,
        }
        self._tokens: list = []

    def __enter__(self):
        if self._kwargs["camera_id"] is not None:
            self._tokens.append(_camera_id_var.set(self._kwargs["camera_id"]))
        if self._kwargs["packet_id"] is not None:
            self._tokens.append(_packet_id_var.set(self._kwargs["packet_id"]))
        if self._kwargs["request_id"] is not None:
            self._tokens.append(_request_id_var.set(self._kwargs["request_id"]))
        return self

    def __exit__(self, *args):
        # Reset LIFO (ngược thứ tự set): token set sau cùng reset trước → contextvar khôi phục
        # đúng giá trị trước đó khi log_context lồng nhau. reversed() đảm bảo điều này.
        for token in reversed(self._tokens):
            token.var.reset(token)


def setup_logging(level: str = "INFO") -> None:
    """Cấu hình structlog. Gọi 1 lần mỗi tiến trình lúc khởi động."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context_vars,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO),
        ),
        cache_logger_on_first_use=True,
    )


class InMemoryMetrics:
    """Metrics trong bộ nhớ, thread-safe. Production: thay bằng adapter Prometheus/StatsD."""

    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        # (name, labels) CÓ CẤU TRÚC theo key — ghi lúc write để iter_metrics KHỎI parse-ngược chuỗi key
        # (parse `name{k=v}` bị lossy khi value chứa ,/=/} — spec metrics-exposition D-071). Bounded (K-019).
        self._labelsets: dict[str, tuple[str, dict]] = {}

    def counter(self, name: str, value: float = 1.0, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += int(value)
            self._labelsets[key] = (name, dict(labels))

    def gauge(self, name: str, value: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value
            self._labelsets[key] = (name, dict(labels))

    def histogram(self, name: str, value: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            self._labelsets[key] = (name, dict(labels))

    def get_counter(self, name: str, **labels) -> int:
        # .get (KHÔNG mutate) → getter không tạo key rác (giữ bất biến: key trong store ⟺ đã ghi ⟺ có labelset).
        with self._lock:
            return self._counters.get(self._key(name, labels), 0)

    def get_gauge(self, name: str, **labels) -> float | None:
        with self._lock:
            return self._gauges.get(self._key(name, labels))

    def get_histogram(self, name: str, **labels) -> list[float]:
        # PHẢI giữ lock — list() duyệt qua; histogram() append đồng thời sẽ race. .get → không mutate.
        with self._lock:
            return list(self._histograms.get(self._key(name, labels), ()))

    def iter_metrics(self) -> "list[MetricSample]":
        """Snapshot CÓ CẤU TRÚC (counter+gauge) → list `MetricSample` SORTED, dưới lock.

        Dùng (name, labels) đã lưu ở `_labelsets` (KHÔNG parse chuỗi key → không lossy). Histogram = Non-Goal
        v1 (cần bucket → bỏ qua). Sort theo (name, sorted(labels)) → output renderer xác định (spec P5).
        """
        from vision_platform.kernel.metric_sample import MetricSample

        out: list[MetricSample] = []
        with self._lock:
            for key, cval in self._counters.items():
                name, labels = self._labelsets[key]
                out.append(MetricSample("counter", name, float(cval), dict(labels)))
            for key, gval in self._gauges.items():
                name, labels = self._labelsets[key]
                out.append(MetricSample("gauge", name, float(gval), dict(labels)))
        out.sort(key=lambda s: (s.name, sorted(s.labels.items())))
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: list(v) for k, v in self._histograms.items()},
            }

    @staticmethod
    def _key(name: str, labels: dict) -> str:
        if not labels:
            return name
        labelstr = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{labelstr}}}"
