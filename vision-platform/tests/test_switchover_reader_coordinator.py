"""Task 4.3 (sub-spec shm-ring-epoch-switchover): ReaderEpochCoordinator — reader chuyển epoch an toàn.

_Requirements: 1.1, 1.2, 1.3, 4.1_
Deterministic in-proc: fake ring/reader tiêm qua DI. FakeReader mô phỏng stale-check thật của ShmFrameReader
(ref.ring_epoch != ring.ring_epoch → None). Publish THẲNG qua control-plane (cô lập khỏi supervisor teardown).
Teardown quyết định B = ring.close(). Cross-process = Task 6 (K-012).
"""
from __future__ import annotations

import uuid

import pytest

from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook, new_ring_name
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator


def _uniq() -> str:
    return f"vp_cp_test_{uuid.uuid4().hex}"


class FakeRing:
    def __init__(self, name: str, ring_epoch: int):
        self.name = name
        self.ring_epoch = ring_epoch
        self.closed = False

    def close(self):
        self.closed = True


class FakeReader:
    """Giả ShmFrameReader: mô phỏng stale-check (ref epoch != ring epoch → None)."""

    def __init__(self, ring: FakeRing):
        self.ring = ring
        self.reads: list = []

    def read_ref(self, ref: ShmFrameRefData):
        self.reads.append(ref)
        if ref.ring_epoch != self.ring.ring_epoch:
            return None                                  # stale-ref (P0-3) → drop
        return (self.ring.name, self.ring.ring_epoch)    # "frame" giả mang epoch để assert đúng ring


def _make_opener(registry: dict):
    def opener(name: str) -> FakeRing:
        return registry[name]
    return opener


def _publish(cp: RingControlPlane, registry: dict, epoch: int) -> str:
    name = new_ring_name()
    registry[name] = FakeRing(name, epoch)
    cp.publish(epoch, name)
    return name


def _ref(ring_name: str, ring_epoch: int) -> ShmFrameRefData:
    return ShmFrameRefData(
        ring_name=ring_name, slot=0, generation=1,
        height=2, width=2, channels=3, ring_epoch=ring_epoch,
    )


def test_bootstrap_opens_current_ring():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name = _publish(cp, registry, 1)
        coord = ReaderEpochCoordinator(cp, _make_opener(registry), reader_factory=FakeReader)
        assert coord.bootstrap() == 1
        assert coord.epoch == 1
        assert coord.current_ring is registry[name]
    finally:
        cp.close(); cp.unlink()


def test_read_switches_ring_when_epoch_changes():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = ReaderEpochCoordinator(cp, _make_opener(registry), reader_factory=FakeReader)
        coord.bootstrap()
        assert coord.read_ref(_ref(name1, 1)) == (name1, 1)  # đọc ring epoch 1

        name2 = _publish(cp, registry, 2)
        frame = coord.read_ref(_ref(name2, 2))               # ref epoch 2 → chuyển + đọc ring mới
        assert coord.epoch == 2
        assert frame == (name2, 2)
        assert registry[name1].closed is True                # teardown B: ring cũ close()
    finally:
        cp.close(); cp.unlink()


def test_stale_ref_old_epoch_returns_none_after_switch():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = ReaderEpochCoordinator(cp, _make_opener(registry), reader_factory=FakeReader)
        coord.bootstrap()
        _publish(cp, registry, 2)                            # epoch 2 → coord sẽ switch khi read
        # ref epoch 1 (đến muộn) sau khi control-plane đã sang epoch 2:
        assert coord.read_ref(_ref(name1, 1)) is None        # switch sang ring2 rồi → ref epoch 1 stale → None
        assert coord.epoch == 2
        assert registry[name1].closed is True
    finally:
        cp.close(); cp.unlink()


def test_no_switch_when_epoch_unchanged():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = ReaderEpochCoordinator(cp, _make_opener(registry), reader_factory=FakeReader)
        coord.bootstrap()
        coord.read_ref(_ref(name1, 1)); coord.read_ref(_ref(name1, 1))
        assert coord.epoch == 1
        assert registry[name1].closed is False               # không chuyển → không close
        assert len(registry) == 1
    finally:
        cp.close(); cp.unlink()


def test_read_before_bootstrap_raises():
    cp = RingControlPlane(_uniq(), create=True)
    try:
        coord = ReaderEpochCoordinator(cp, lambda n: None, reader_factory=FakeReader)
        with pytest.raises(RuntimeError):
            coord.read_ref(_ref("x", 1))
    finally:
        cp.close(); cp.unlink()


def test_switch_emits_observability_events():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    events: list[str] = []

    class Rec(ObservabilityHook):
        def emit(self, event, **fields):
            events.append(event)

    try:
        _publish(cp, registry, 1)
        coord = ReaderEpochCoordinator(cp, _make_opener(registry), reader_factory=FakeReader, obs=Rec())
        coord.bootstrap()
        _publish(cp, registry, 2)
        coord.read_ref(_ref("dummy", 2))                     # ref epoch 2 → coord switch (emit events)
        assert "shm_reader_switched" in events
        assert "shm_ring_teardown_pending" in events
    finally:
        cp.close(); cp.unlink()
