"""Test Task 7 (spec shm-production-hardening): single-writer invariant (Req 5 / P1-3).

register_writer: trống→claim · ALIVE→reject · DEAD→rebuild_requested+reject · UNKNOWN→reject · >1/process→raise.
Tiêm liveness_fn để deterministic.
"""
from __future__ import annotations

import struct
import time
import uuid

import pytest

from vision_platform.kernel.shm_layout import (
    OFFSET_WRITER_PID, OFFSET_WRITER_CREATE_TIME_NS, U64_FMT,
)
from vision_platform.runtime.ipc._process_identity import Liveness, current_identity
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ObservabilityHook, SingleWriterViolation,
)


class RecordingHook(ObservabilityHook):
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append((event, fields))

    @property
    def names(self):
        return [e for e, _ in self.events]


def _ring(liveness=Liveness.ALIVE, hook=None):
    return ShmRingBuffer(
        name=f"sw_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
        create=True, liveness_fn=lambda p, c: liveness, obs=hook,
    )


def test_register_writer_claims_empty_ring():
    ring = _ring()
    try:
        ring.register_writer()
        pid, ct = ring._read_writer()
        exp_pid, exp_ct = current_identity()
        assert pid == exp_pid and ct == exp_ct
    finally:
        ring.cleanup_all()


def test_register_writer_twice_same_process_raises():
    ring = _ring()
    try:
        ring.register_writer()
        with pytest.raises(SingleWriterViolation):
            ring.register_writer()
    finally:
        ring.cleanup_all()


def test_register_writer_rejects_when_live_writer_exists():
    ring = _ring(Liveness.ALIVE)
    try:
        # Giả lập đã có writer khác (pid=999) còn sống.
        ctrl = ring._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, 999)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, 111)
        with pytest.raises(SingleWriterViolation):
            ring.register_writer()
    finally:
        ring.cleanup_all()


def test_register_writer_dead_writer_requests_rebuild():
    hook = RecordingHook()
    ring = _ring(Liveness.DEAD, hook=hook)
    try:
        ctrl = ring._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, 999)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, 111)
        with pytest.raises(SingleWriterViolation):
            ring.register_writer()
        assert "shm_ring_rebuild_requested" in hook.names   # KHÔNG takeover, yêu cầu rebuild
    finally:
        ring.cleanup_all()


def test_register_writer_unknown_rejects():
    ring = _ring(Liveness.UNKNOWN)
    try:
        ctrl = ring._ctrl_shm.buf
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_PID, 999)
        struct.pack_into(U64_FMT, ctrl, OFFSET_WRITER_CREATE_TIME_NS, 111)
        with pytest.raises(SingleWriterViolation):
            ring.register_writer()
    finally:
        ring.cleanup_all()


def test_cross_instance_same_process_second_register_rejected():
    """2 ShmRingBuffer cùng process cùng ring: instance 1 claim → instance 2 (attach) bị reject (live writer)."""
    name = f"swx_{uuid.uuid4().hex[:8]}"
    creator = ShmRingBuffer(name=name, n_slots=4, height=8, width=8, channels=3,
                            create=True, liveness_fn=lambda p, c: Liveness.ALIVE)
    try:
        creator.register_writer()
        attached = ShmRingBuffer(name=name, n_slots=4, height=8, width=8, channels=3,
                                 create=False, slot_locks=creator.slot_locks_for_children,
                                 liveness_fn=lambda p, c: Liveness.ALIVE)
        with pytest.raises(SingleWriterViolation):
            attached.register_writer()    # ctrl đã có writer còn sống (chính process này)
    finally:
        creator.cleanup_all()
