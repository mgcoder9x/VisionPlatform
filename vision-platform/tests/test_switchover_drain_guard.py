"""Fix A (K-015): reset_for_reuse CƯỠNG CHẾ drain-before-reuse.

Nếu ring còn reader CÒN HIỆU LỰC (lease chưa hết / còn sống) → reset REFUSE (return False, chưa đụng gì) +
emit; supervisor HOÃN switchover (defer+retry). Tránh torn frame (reset xoá reader_count vô điều kiện lúc
reader đang copy-ngoài-lock). Test deterministic bằng cách set registry reader trực tiếp (lease tương lai).
"""
from __future__ import annotations

import time
import uuid

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool
from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ObservabilityHook,
    _registry_set, _registry_clear, _registry_count, _write_reader_count, _read_reader_count,
)
from vision_platform.runtime.ipc._process_identity import Liveness
from vision_platform.application.ring_supervisor import RingSupervisor

_H = _W = _C = 4
_N = 4
_FAR_LEASE = 10_000_000_000   # 10s tương lai (ns) — reader "con hieu luc"


def _ring(epoch=1, liveness=None):
    kw = {} if liveness is None else {"liveness_fn": liveness}
    return ShmRingBuffer(name=f"drain_{uuid.uuid4().hex[:8]}", n_slots=_N, height=_H, width=_W, channels=_C,
                         create=True, ring_epoch=epoch, **kw)


def _pin_fake_reader(ring, slot=0, lease_offset=_FAR_LEASE):
    """Đặt 1 ô registry reader trên slot (mo phong reader dang pin, con hieu luc)."""
    buf = ring._meta_shms[slot].buf
    _registry_set(buf, 0, 4242, 7777, time.monotonic_ns() + lease_offset)
    _write_reader_count(buf, _registry_count(buf))


def test_reset_refused_when_active_reader_present():
    ring = _ring(epoch=1)
    try:
        _pin_fake_reader(ring, slot=0)                 # reader con hieu luc (lease tuong lai)
        assert ring.reset_for_reuse(2) is False        # REFUSE (chua drain)
        assert ring.ring_epoch == 1                    # KHONG bump epoch (refuse toan phan)
        assert _read_reader_count(ring._meta_shms[0].buf) == 1   # registry KHONG bi xoa
    finally:
        ring.cleanup_all()


def test_reset_proceeds_after_reader_gone():
    ring = _ring(epoch=1)
    try:
        _pin_fake_reader(ring, slot=0)
        assert ring.reset_for_reuse(2) is False        # bi chan
        # reader roi (unpin): xoa registry
        _registry_clear(ring._meta_shms[0].buf, 0)
        _write_reader_count(ring._meta_shms[0].buf, 0)
        assert ring.reset_for_reuse(2) is True         # gio drain xong -> reset OK
        assert ring.ring_epoch == 2
    finally:
        ring.cleanup_all()


def test_reset_reaps_dead_reader_then_proceeds():
    # reader lease QUA HAN + liveness DEAD -> reap xoa -> reset duoc.
    ring = _ring(epoch=1, liveness=lambda p, c: Liveness.DEAD)
    try:
        buf = ring._meta_shms[0].buf
        _registry_set(buf, 0, 4242, 7777, time.monotonic_ns() - 1_000_000)   # lease qua han
        _write_reader_count(buf, _registry_count(buf))
        assert ring.reset_for_reuse(2) is True         # reap dead reader -> khong con bao ve -> reset
        assert ring.ring_epoch == 2
    finally:
        ring.cleanup_all()


def test_reset_emits_blocked_event():
    events = []

    class Rec(ObservabilityHook):
        def emit(self, event, **fields):
            events.append(event)

    ring = _ring(epoch=1)
    ring._obs = Rec()   # thay hook de ghi (ring tao voi obs mac dinh no-op)
    try:
        _pin_fake_reader(ring, slot=1)
        assert ring.reset_for_reuse(2) is False
        assert "shm_reset_blocked_active_readers" in events
    finally:
        ring.cleanup_all()


def test_pool_activate_returns_none_when_not_drained():
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"drain_{uuid.uuid4().hex[:8]}")
    try:
        target = pool.ring_for_epoch(1)                # ring se dung cho epoch 1
        _pin_fake_reader(target, slot=0)               # con reader hieu luc
        assert pool.activate(1) is None                # chua drain -> activate None
        assert target.ring_epoch == 0                  # KHONG bump
    finally:
        pool.close_all()


def test_supervisor_defers_switchover_when_not_drained():
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"drain_{uuid.uuid4().hex[:8]}")
    events = []

    class Rec(ObservabilityHook):
        def emit(self, event, **fields):
            events.append(event)

    sup = RingSupervisor(cp, pool, obs=Rec())
    try:
        _pin_fake_reader(pool.ring_for_epoch(1), slot=0)   # ring epoch 1 chua drain
        assert sup.switchover() is None                    # HOAN
        assert cp.read_current()[0] == 0                   # KHONG publish (control-plane giu nguyen)
        assert "shm_switchover_deferred" in events
    finally:
        pool.close_all()
        cp.close(); cp.unlink()
