"""Task 9 (sub-spec shm-ring-epoch-switchover): observability taxonomy END-TO-END + fail-fast control-plane.

Req 6.1: switchover start/complete + teardown + reset emit qua MỘT ObservabilityHook dùng chung (xuyên
pool + supervisor + coordinator). Req 6.2: attach control-plane magic sai → ValueError (đã có
`test_switchover_control_plane.py::test_attach_wrong_magic_fail_fast` — không nhân đôi ở đây).
_Requirements: 6.1, 6.2_
"""
from __future__ import annotations

import uuid

import numpy as np

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.runtime.ipc.shm_frame_ring import ObservabilityHook
from vision_platform.application.ring_supervisor import RingSupervisor
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator

_H = _W = _C = 4
_N = 4


class RecordingHook(ObservabilityHook):
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, event, **fields):
        self.events.append((event, fields))

    def names(self) -> set[str]:
        return {e for e, _ in self.events}

    def fields_of(self, event: str) -> dict:
        for e, f in self.events:
            if e == event:
                return f
        return {}


def _frame(v):
    return np.full((_H, _W, _C), v, dtype=np.uint8)


def test_switchover_observability_taxonomy_end_to_end():
    """1 hook dùng chung phải thấy TOÀN BỘ taxonomy switchover qua 1 vòng rebuild."""
    hook = RecordingHook()
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"obs_{uuid.uuid4().hex[:8]}", obs=hook)
    sup = RingSupervisor(cp, pool, obs=hook)
    opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C, obs=hook)
    wc = WriterEpochCoordinator(cp, opener, obs=hook)
    rc = ReaderEpochCoordinator(cp, opener, obs=hook)
    try:
        sup.switchover()                              # started + reset_for_reuse (pool ring) + completed
        wc.bootstrap()
        rc.bootstrap()
        ref1 = wc.write(_frame(11))
        assert np.array_equal(rc.read_ref(ref1), _frame(11))

        sup.switchover()                              # epoch 2: started + reset + completed
        ref2 = wc.write(_frame(22))                   # writer_switched + teardown_pending
        assert ref2.ring_epoch == 2
        assert np.array_equal(rc.read_ref(ref2), _frame(22))   # reader_switched + teardown_pending

        names = hook.names()
        expected = {
            "shm_switchover_started",
            "shm_switchover_completed",
            "shm_ring_reset_for_reuse",
            "shm_writer_switched",
            "shm_reader_switched",
            "shm_ring_teardown_pending",
        }
        missing = expected - names
        assert not missing, f"thiếu event taxonomy: {missing}; đã thấy: {sorted(names)}"

        # Kiểm field tối thiểu (không chỉ tên event).
        assert hook.fields_of("shm_switchover_started").get("new_epoch") in (1, 2)
        assert hook.fields_of("shm_switchover_completed").get("new_ring_name", "").startswith(pool._prefix)
        assert hook.fields_of("shm_writer_switched").get("new_epoch") == 2
        assert hook.fields_of("shm_reader_switched").get("new_epoch") == 2
        assert hook.fields_of("shm_ring_reset_for_reuse").get("new_epoch") in (1, 2)

        if wc.current_ring is not None:
            wc.current_ring.close()
        if rc.current_ring is not None:
            rc.current_ring.close()
    finally:
        pool.close_all()
        cp.close(); cp.unlink()


def test_default_hook_is_noop_no_events():
    """Mặc định (không truyền obs) = no-op → không phát event, không tốn (hợp real-time)."""
    hook = RecordingHook()
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=2, session_prefix=f"obs_{uuid.uuid4().hex[:8]}")  # KHÔNG obs
    sup = RingSupervisor(cp, pool)                    # KHÔNG obs → dùng ObservabilityHook() no-op
    try:
        sup.switchover()
        assert hook.events == []                      # hook ngoài không nhận gì (supervisor dùng no-op mặc định)
    finally:
        pool.close_all()
        cp.close(); cp.unlink()
