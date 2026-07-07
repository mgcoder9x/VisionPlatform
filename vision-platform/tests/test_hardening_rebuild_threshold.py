"""Test Task 10.1/10.2 (spec shm-production-hardening): rebuild_requested khi quá REBUILD_THRESHOLD.

THRESHOLD mặc định thận trọng = ceil(n_slots/2); 🔴 cần tuning theo SLA production thật (Task 10.2).
Switchover ĐẦY ĐỦ tách sub-spec shm-ring-epoch-switchover (Task 10.3, KHÔNG triển khai ở đây).
"""
from __future__ import annotations

import time
import uuid

from vision_platform.runtime.ipc._process_identity import Liveness
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ObservabilityHook, _write_header, SlotState,
)


class RecordingHook(ObservabilityHook):
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append((event, fields))

    @property
    def names(self):
        return [e for e, _ in self.events]


def _dead_writing(ring, idx):
    _write_header(ring._meta_shms[idx].buf, SlotState.WRITING, 5, 999, 111, time.monotonic_ns() - 1)


def test_default_threshold_is_half_slots():
    ring = ShmRingBuffer(name=f"th_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3, create=True)
    try:
        assert ring._rebuild_threshold == 2   # ceil(4/2)
    finally:
        ring.cleanup_all()


def test_rebuild_requested_only_at_threshold():
    hook = RecordingHook()
    ring = ShmRingBuffer(name=f"th_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
                         create=True, liveness_fn=lambda p, c: Liveness.DEAD, obs=hook, rebuild_threshold=2)
    try:
        _dead_writing(ring, 0)
        assert ring.quarantine_poisoned_slot(0) is True
        assert "shm_ring_rebuild_requested" not in hook.names   # count=1 < 2

        _dead_writing(ring, 1)
        assert ring.quarantine_poisoned_slot(1) is True
        assert "shm_ring_rebuild_requested" in hook.names        # count=2 >= 2
        f = dict(hook.events)["shm_ring_rebuild_requested"]
        assert f["quarantined_count"] == 2
        assert f["threshold"] == 2
    finally:
        ring.cleanup_all()
