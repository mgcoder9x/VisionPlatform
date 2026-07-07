"""Task 4.2 (sub-spec shm-ring-epoch-switchover): WriterEpochCoordinator — writer chuyển epoch an toàn.

_Requirements: 3.1, 3.2, 3.3_
Deterministic in-proc: fake ring/writer tiêm qua DI. Publish THẲNG qua control-plane (không qua supervisor)
để cô lập hành vi coordinator khỏi teardown của supervisor. Teardown quyết định B = ring.close().
Cross-process lock provisioning = Task 6 (K-012, ngoài phạm vi 4.2).
"""
from __future__ import annotations

import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook, SingleWriterViolation, new_ring_name
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator


def _uniq() -> str:
    return f"vp_cp_test_{uuid.uuid4().hex}"


class FakeRing:
    """Giả ShmRingBuffer đủ dùng cho coordinator: register_writer (1 lần) + close."""

    def __init__(self, name: str, ring_epoch: int, *, taken: bool = False):
        self.name = name
        self.ring_epoch = ring_epoch
        self.registered = False
        self.closed = False
        self._taken = taken            # mô phỏng ring đã có writer sống → register raise

    def register_writer(self, pid=None, create_time_ns=None):
        if self._taken:
            raise SingleWriterViolation(f"ring {self.name} đã có writer sống")
        if self.registered:
            raise SingleWriterViolation("register_writer gọi >1 lần")
        self.registered = True

    def close(self):
        self.closed = True


class FakeWriter:
    def __init__(self, ring: FakeRing):
        self.ring = ring
        self.frames: list = []

    def write(self, frame):
        self.frames.append(frame)
        return (self.ring.name, self.ring.ring_epoch)   # ref giả mang epoch để assert đúng ring


def _make_opener(registry: dict):
    def opener(name: str) -> FakeRing:
        return registry[name]                            # in-proc: object chia sẻ (writer mở ring đã tạo)
    return opener


def _publish(cp: RingControlPlane, registry: dict, epoch: int, *, taken: bool = False) -> str:
    """Tạo FakeRing epoch mới + publish THẲNG qua control-plane (mô phỏng supervisor đã switchover)."""
    name = new_ring_name()
    registry[name] = FakeRing(name, epoch, taken=taken)
    cp.publish(epoch, name)
    return name


def _frame():
    return np.zeros((2, 2, 3), dtype=np.uint8)


def test_bootstrap_registers_writer_on_current_ring():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name = _publish(cp, registry, 1)
        coord = WriterEpochCoordinator(cp, _make_opener(registry), writer_factory=FakeWriter)
        assert coord.bootstrap() == 1
        assert registry[name].registered is True
        assert coord.epoch == 1
    finally:
        cp.close(); cp.unlink()


def test_write_switches_ring_when_epoch_changes():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = WriterEpochCoordinator(cp, _make_opener(registry), writer_factory=FakeWriter)
        coord.bootstrap()
        assert coord.write(_frame()) == (name1, 1)           # ghi ring epoch 1

        name2 = _publish(cp, registry, 2)                    # epoch 2 (ring mới)
        ref = coord.write(_frame())                          # phát hiện đổi → chuyển
        assert coord.epoch == 2
        assert ref == (name2, 2)                             # ghi vào RING MỚI (đúng epoch)
        assert registry[name2].registered is True            # register ring mới TRƯỚC frame đầu (Req 3.2)
        assert registry[name1].closed is True                # teardown B: ring cũ close()
    finally:
        cp.close(); cp.unlink()


def test_single_writer_violation_on_new_ring_is_fail_fast():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = WriterEpochCoordinator(cp, _make_opener(registry), writer_factory=FakeWriter)
        coord.bootstrap()

        name2 = _publish(cp, registry, 2, taken=True)        # ring mới đã có writer sống
        with pytest.raises(SingleWriterViolation):
            coord.write(_frame())                            # fail-fast
        assert coord.epoch == 1                              # GIỮ nguyên epoch cũ
        assert registry[name1].closed is False               # ring cũ KHÔNG bị đóng
        assert registry[name2].closed is True                # ring mới đã dọn handle (không leak)
    finally:
        cp.close(); cp.unlink()


def test_no_switch_when_epoch_unchanged():
    cp = RingControlPlane(_uniq(), create=True)
    registry: dict = {}
    try:
        name1 = _publish(cp, registry, 1)
        coord = WriterEpochCoordinator(cp, _make_opener(registry), writer_factory=FakeWriter)
        coord.bootstrap()
        coord.write(_frame()); coord.write(_frame())
        assert coord.epoch == 1
        assert registry[name1].closed is False               # không chuyển → không close
        assert len(registry) == 1                            # không mở ring nào khác
    finally:
        cp.close(); cp.unlink()


def test_write_before_bootstrap_raises():
    cp = RingControlPlane(_uniq(), create=True)
    try:
        coord = WriterEpochCoordinator(cp, lambda n: None, writer_factory=FakeWriter)
        with pytest.raises(RuntimeError):
            coord.write(_frame())
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
        coord = WriterEpochCoordinator(cp, _make_opener(registry), writer_factory=FakeWriter, obs=Rec())
        coord.bootstrap()
        _publish(cp, registry, 2)
        coord.write(_frame())
        assert "shm_writer_switched" in events
        assert "shm_ring_teardown_pending" in events
    finally:
        cp.close(); cp.unlink()
