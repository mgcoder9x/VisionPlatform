"""Test Task 5 (spec shm-production-hardening): multi-reader registry.

Deterministic: dùng helper registry + tiêm liveness_fn (không cần đa process thật). Phủ Req 3.1–3.8:
reader_count dẫn xuất, pin/unpin, registry-full fail-fast, reap dead reader (giữ reader sống), writer-guard.
"""
from __future__ import annotations

import struct
import time
import uuid

import numpy as np
import pytest

from vision_platform.kernel.shm_layout import (
    MAX_READERS, OFFSET_STATE, STATE_FMT, OFFSET_GENERATION, U64_FMT,
)
from vision_platform.runtime.ipc._process_identity import Liveness
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader, ReaderRegistryFull,
    _registry_set, _registry_count, _registry_entry, _read_reader_count,
    _write_reader_count, _reap_dead_readers, SlotState,
)


def _ring(liveness=Liveness.ALIVE):
    return ShmRingBuffer(
        name=f"mr_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
        create=True, liveness_fn=lambda pid, ct: liveness,
    )


def _frame(v):
    return np.full((8, 8, 3), v, dtype=np.uint8)


def _set_state_gen(ring, idx, state, gen):
    buf = ring._meta_shms[idx].buf
    struct.pack_into(U64_FMT, buf, OFFSET_GENERATION, gen)
    struct.pack_into(STATE_FMT, buf, OFFSET_STATE, int(state))


def _pin_fake_reader(ring, idx, reg_idx, *, pid, ct=111, lease_offset_ns=5_000_000_000):
    buf = ring._meta_shms[idx].buf
    _registry_set(buf, reg_idx, pid, ct, time.monotonic_ns() + lease_offset_ns)
    _write_reader_count(buf, _registry_count(buf))


# ============ reader_count dẫn xuất từ registry (Req 3.3) ============

def test_reader_count_equals_active_entries():
    ring = _ring()
    try:
        buf = ring._meta_shms[0].buf
        assert _registry_count(buf) == 0
        _registry_set(buf, 0, 101, 1, 999)
        _registry_set(buf, 3, 202, 1, 999)
        assert _registry_count(buf) == 2
        _registry_set(buf, 0, 0, 0, 0)   # clear ô 0
        assert _registry_count(buf) == 1
    finally:
        ring.cleanup_all()


# ============ Reader thứ N pin slot đang READING (Req 3.1) + unpin không DONE khi còn reader (Req 3.5) ============

def test_second_reader_pins_while_first_active():
    ring = _ring(Liveness.ALIVE)   # reader A "sống" → không bị reap
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(42))                 # slot READY, gen=1
        # Giả lập reader A đã pin (registry[0], còn sống, lease tương lai) + state READING.
        _pin_fake_reader(ring, ref.slot, 0, pid=99999)
        _set_state_gen(ring, ref.slot, SlotState.READING, ref.generation)

        reader_b = ShmFrameReader(ring)
        out = reader_b.read(ref.slot, ref.generation)  # B pin trong khi A đang giữ
        assert out is not None
        assert np.array_equal(out, _frame(42))

        buf = ring._meta_shms[ref.slot].buf
        # B đã unpin; A vẫn còn → count==1, state vẫn READING (Req 3.5: không DONE khi còn reader).
        assert _registry_count(buf) == 1
        assert ring.peek_state(ref.slot) == SlotState.READING
        # A vẫn trong registry
        assert any(_registry_entry(buf, i)[0] == 99999 for i in range(MAX_READERS))
    finally:
        ring.cleanup_all()


# ============ Registry đầy → fail-fast (Req 3.4) ============

def test_read_raises_when_registry_full():
    ring = _ring(Liveness.ALIVE)   # các reader giả "sống" → reap không xoá → đầy
    try:
        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(7))
        buf = ring._meta_shms[ref.slot].buf
        for i in range(MAX_READERS):                   # lấp đầy MAX_READERS ô
            _registry_set(buf, i, 1000 + i, 1, time.monotonic_ns() + 5_000_000_000)
        _write_reader_count(buf, _registry_count(buf))
        _set_state_gen(ring, ref.slot, SlotState.READING, ref.generation)

        reader = ShmFrameReader(ring)
        with pytest.raises(ReaderRegistryFull):
            reader.read(ref.slot, ref.generation)
    finally:
        ring.cleanup_all()


# ============ Writer KHÔNG tái dùng slot còn reader (Req 3.6) ============

def test_writer_skips_slot_with_nonzero_reader_count():
    ring = _ring(Liveness.ALIVE)
    try:
        # slot0 = DONE nhưng reader_count=1 (bất thường) → writer KHÔNG được tái dùng (belt-and-suspenders).
        buf0 = ring._meta_shms[0].buf
        _set_state_gen(ring, 0, SlotState.DONE, 0)
        _pin_fake_reader(ring, 0, 0, pid=55555)
        assert _read_reader_count(buf0) == 1

        writer = ShmFrameWriter(ring)
        ref = writer.write(_frame(3))
        assert ref is not None
        assert ref.slot != 0                           # bỏ qua slot0 vì còn reader
    finally:
        ring.cleanup_all()


# ============ Reap reader chết, GIỮ reader sống (Req 3.7 / R-2.2) ============

def test_reap_removes_dead_keeps_alive():
    dead_pid = 70001
    alive_pid = 70002

    def liveness(pid, ct):
        return Liveness.DEAD if pid == dead_pid else Liveness.ALIVE

    ring = ShmRingBuffer(
        name=f"reap_{uuid.uuid4().hex[:8]}", n_slots=4, height=8, width=8, channels=3,
        create=True, liveness_fn=liveness,
    )
    try:
        buf = ring._meta_shms[0].buf
        _registry_set(buf, 0, dead_pid, 1, time.monotonic_ns() - 1_000_000)    # chết + lease quá hạn
        _registry_set(buf, 1, alive_pid, 1, time.monotonic_ns() - 1_000_000)   # "sống" + lease quá hạn
        _write_reader_count(buf, 2)

        count = _reap_dead_readers(buf, ring._liveness_fn)
        assert count == 1                                # chỉ xoá ô chết
        assert _registry_entry(buf, 0)[0] == 0           # dead reaped
        assert _registry_entry(buf, 1)[0] == alive_pid   # alive giữ lại
        assert _read_reader_count(buf) == 1
    finally:
        ring.cleanup_all()


def test_single_reader_round_trip_returns_done():
    """Sanity: 1 reader đọc xong → reader_count 0, state DONE (giữ hành vi #05)."""
    ring = _ring(Liveness.ALIVE)
    try:
        writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
        ref = writer.write(_frame(9))
        out = reader.read(ref.slot, ref.generation)
        assert np.array_equal(out, _frame(9))
        assert ring.peek_state(ref.slot) == SlotState.DONE
        assert _read_reader_count(ring._meta_shms[ref.slot].buf) == 0
    finally:
        ring.cleanup_all()
