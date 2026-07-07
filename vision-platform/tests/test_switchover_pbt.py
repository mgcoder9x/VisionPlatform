"""Task 8 (sub-spec shm-ring-epoch-switchover): Property-Based Tests (Hypothesis) cho Property 1–5.

Design §Correctness Properties:
  P1 stale→None · P2 epoch đơn điệu · P3 single-writer xuyên switchover · P4 no-leak (I/O → T-C, không PBT) ·
  P5 tiến triển/lọc-event.
Logic thuần (P2/P5) dùng FakeCP in-memory (tránh churn SHM trong Hypothesis). P1/P2b/P3 dùng 1 ring THẬT +
reset_for_reuse để đi epoch (max_examples giới hạn, deadline=None vì có I/O SHM).
_Requirements: 1.1, 2.1, 3.1, 5.1_
"""
from __future__ import annotations

import uuid

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, ShmFrameReader, SingleWriterViolation,
)
from vision_platform.application.ring_supervisor import RingSupervisor

_H = _W = _C = 4


class FakeCP:
    """Control-plane in-memory (thuần logic, không SHM) — đủ cho RingSupervisor (read_current/publish)."""

    def __init__(self):
        self._epoch = 0
        self._name = ""

    def read_current(self):
        return self._epoch, self._name

    def publish(self, epoch, name):
        self._epoch = epoch
        self._name = name


class FakePool:
    def activate(self, epoch):
        return f"ring_ep{epoch}"


def _ring(epoch=1, n=4):
    return ShmRingBuffer(name=f"pbt_{uuid.uuid4().hex[:8]}", n_slots=n, height=_H, width=_W, channels=_C,
                         create=True, ring_epoch=epoch)


def _frame(v):
    return np.full((_H, _W, _C), v, dtype=np.uint8)


# ── P2: epoch đơn điệu tăng (logic thuần) ─────────────────────────────────────────────
@given(n=st.integers(min_value=1, max_value=60))
def test_p2_epoch_strictly_monotonic(n):
    sup = RingSupervisor(FakeCP(), FakePool())
    epochs = [sup.switchover() for _ in range(n)]
    assert epochs == list(range(1, n + 1))         # 1,2,3,... không giảm/lặp


# ── P5: on_event chỉ trigger switchover cho 'shm_ring_rebuild_requested' ──────────────
@given(event=st.one_of(st.just("shm_ring_rebuild_requested"), st.text(), st.sampled_from(
    ["shm_slot_quarantined", "shm_writer_switched", "", "rebuild", "SHM_RING_REBUILD_REQUESTED"])))
def test_p5_on_event_triggers_only_for_rebuild_requested(event):
    cp = FakeCP()
    sup = RingSupervisor(cp, FakePool())
    result = sup.on_event(event)
    if event == "shm_ring_rebuild_requested":
        assert result == 1 and cp.read_current()[0] == 1
    else:
        assert result is None and cp.read_current()[0] == 0   # sự kiện khác → KHÔNG switchover


# ── P2b: reset_for_reuse ép epoch đơn điệu (ring thật) ────────────────────────────────
@given(increments=st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=8))
@settings(max_examples=25, deadline=None)
def test_p2b_reset_for_reuse_enforces_monotonic(increments):
    ring = _ring(epoch=1)
    try:
        cur = 1
        for inc in increments:
            nxt = cur + inc
            ring.reset_for_reuse(nxt)
            assert ring.ring_epoch == nxt
            with pytest.raises(ValueError):
                ring.reset_for_reuse(cur)               # <= hiện tại → từ chối (đơn điệu)
            cur = nxt
    finally:
        ring.cleanup_all()


# ── P1: ref epoch cũ → None sau khi ring đổi epoch (ring thật) ────────────────────────
@given(increments=st.lists(st.integers(min_value=1, max_value=4), min_size=1, max_size=6))
@settings(max_examples=20, deadline=None)
def test_p1_stale_ref_returns_none_after_epoch_advance(increments):
    ring = _ring(epoch=1)
    try:
        cur = 1
        for inc in increments:
            writer = ShmFrameWriter(ring)               # writer cache ring_epoch=cur lúc tạo
            ref = writer.write(_frame((cur % 250) + 1))
            assert ref is not None and ref.ring_epoch == cur
            reader = ShmFrameReader(ring)
            assert reader.read_ref(ref) is not None      # epoch khớp → đọc được

            cur += inc
            ring.reset_for_reuse(cur)                     # đổi epoch (switchover)
            assert reader.read_ref(ref) is None           # ref epoch cũ → stale → None (P1)
    finally:
        ring.cleanup_all()


# ── P3: single-writer/ring, tái lập sau mỗi reset (ring thật) ─────────────────────────
@given(n_resets=st.integers(min_value=0, max_value=6))
@settings(max_examples=15, deadline=None)
def test_p3_single_writer_across_resets(n_resets):
    ring = _ring(epoch=1)
    try:
        ring.register_writer()
        with pytest.raises(SingleWriterViolation):
            ring.register_writer()                        # gọi lần 2 → raise (1-writer)
        cur = 1
        for _ in range(n_resets):
            cur += 1
            ring.reset_for_reuse(cur)                     # reset → registry sạch
            ring.register_writer()                        # claim lại được
            with pytest.raises(SingleWriterViolation):
                ring.register_writer()                    # vẫn giữ 1-writer sau reset
    finally:
        ring.cleanup_all()
