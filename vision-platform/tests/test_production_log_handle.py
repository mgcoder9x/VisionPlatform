"""Spec F5.3/K-018 — ProductionLogHandle: non-blocking + rotating + flush-on-shutdown (stdlib, no-GPU/no-network)."""
from __future__ import annotations

import os
import queue as _queue

from vision_platform.adapters.production_log_handle import ProductionLogHandle, _DropCountingQueueHandler


def _read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [ln for ln in f.read().splitlines() if ln.strip()]


# ---- flush-on-shutdown: mọi record enqueue trước shutdown PHẢI có mặt trong file (không mất log cuối) ----
def test_flush_on_shutdown_no_loss(tmp_path):
    p = str(tmp_path / "app.log")
    h = ProductionLogHandle(p, capacity=10000).start()
    for i in range(200):
        h.emit(f'{{"i":{i}}}')
    h.shutdown()                       # drain + flush + close
    lines = _read_lines(p)
    assert len(lines) == 200
    assert lines[0] == '{"i":0}' and lines[-1] == '{"i":199}'   # đúng nội dung + thứ tự


# ---- rotation: vượt max_bytes → tạo file backup (chống đầy đĩa 24/7) ----
def test_rotation_creates_backup(tmp_path):
    p = str(tmp_path / "rot.log")
    h = ProductionLogHandle(p, max_bytes=500, backup_count=3).start()
    for i in range(300):
        h.emit(f'{{"msg":"line-{i:04d}-padding-xxxxxxxxxx"}}')
    h.shutdown()
    assert os.path.exists(p)               # file hiện tại
    assert os.path.exists(p + ".1")        # ÍT NHẤT 1 backup (đã xoay)


# ---- non-blocking drop: queue đầy → drop + đếm, KHÔNG raise/chặn (test handler trực tiếp, xác định) ----
def test_drop_counting_when_full():
    q: _queue.Queue = _queue.Queue(maxsize=2)
    qh = _DropCountingQueueHandler(q)
    import logging
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "m", None, None)
    qh.enqueue(rec); qh.enqueue(rec)       # đầy (maxsize=2)
    assert qh.dropped == 0
    qh.enqueue(rec); qh.enqueue(rec)       # 2 lần nữa → drop (KHÔNG raise)
    assert qh.dropped == 2


# ---- shutdown idempotent (gọi 2 lần / chưa start-lại không raise) ----
def test_shutdown_idempotent(tmp_path):
    p = str(tmp_path / "idem.log")
    h = ProductionLogHandle(p).start()
    h.emit('{"a":1}')
    h.shutdown()
    h.shutdown()                            # lần 2 KHÔNG raise
    assert _read_lines(p) == ['{"a":1}']


# ---- emit trước start → lỗi RÕ ----
def test_emit_before_start_raises(tmp_path):
    import pytest
    h = ProductionLogHandle(str(tmp_path / "x.log"))
    with pytest.raises(RuntimeError):
        h.emit("nope")


# ---- validate tham số fail-fast ----
def test_bad_params():
    import pytest
    with pytest.raises(ValueError):
        ProductionLogHandle("x", max_bytes=0)
    with pytest.raises(ValueError):
        ProductionLogHandle("x", capacity=0)
    with pytest.raises(ValueError):
        ProductionLogHandle("x", backup_count=-1)


# ---- FileLoggingObserver (runtime) ghi non-blocking qua sink tiêm (DI, không import adapter) ----
def test_file_logging_observer_emits_json():
    from vision_platform.runtime.observers import FileLoggingObserver
    from vision_platform.kernel.observability_port import PipelineSnapshot

    captured: list[str] = []

    class _FakeSink:
        def emit(self, msg: str) -> None:
            captured.append(msg)

    obs = FileLoggingObserver(_FakeSink())
    snap = PipelineSnapshot(
        source_id="cam0", frames_read=10, processed=8, skipped=2, stage_errors=0,
        frames_per_second=24.0, skip_rate=0.2, is_final=False,
    )
    obs.on_snapshot(snap)
    assert len(captured) == 1
    import json
    d = json.loads(captured[0])
    assert d["source_id"] == "cam0" and d["fps"] == 24.0 and d["event"] == "pipeline_snapshot"
