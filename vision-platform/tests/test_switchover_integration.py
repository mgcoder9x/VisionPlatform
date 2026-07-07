"""H2 bước 3 (K-012): tích hợp IN-PROCESS toàn bộ thành phần THẬT của switchover.

Nối: RingPool (K ring thật) + RingControlPlane + RingSupervisor + WriterEpochCoordinator +
ReaderEpochCoordinator + ShmFrameWriter/ShmFrameReader THẬT (qua make_pool_opener). Chứng minh:
  - writer/reader bootstrap ra cùng ring hiện tại; ghi→đọc frame khớp (SHM + lock thật, in-process);
  - rebuild → supervisor switchover → writer chuyển ring mới (register_writer) + ghi; reader chuyển + đọc;
  - ref epoch cũ → None (stale); pool TÁI DÙNG vòng (epoch 1..4 → ring1,2,0,1) chạy đúng với SHM thật.

GIỚI HẠN (nói thật): đây là 1 PROCESS (lock chia sẻ qua object). KHÔNG chứng minh lock thừa kế CROSS-PROCESS
qua spawn — đó là Task 6 (T-B). Test này là cổng verify in-process cuối trước T-B.
_Requirements: 1.1, 1.2, 1.3, 2.1, 3.1, 3.2, 3.3_
"""
from __future__ import annotations

import uuid

import numpy as np

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.application.ring_supervisor import RingSupervisor
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator

_H, _W, _C, _N = 8, 8, 3, 4


def _frame(v):
    return np.full((_H, _W, _C), v, dtype=np.uint8)


def test_full_switchover_loop_with_real_components():
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"itest_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
    wc = WriterEpochCoordinator(cp, opener)          # writer_factory mặc định = ShmFrameWriter THẬT
    rc = ReaderEpochCoordinator(cp, opener)          # reader_factory mặc định = ShmFrameReader THẬT
    try:
        # --- Bootstrap epoch 1 ---
        assert sup.switchover() == 1                 # pool.activate(1) + publish
        assert wc.bootstrap() == 1                   # attach ring1 + register_writer
        assert rc.bootstrap() == 1

        # Ghi → đọc frame khớp (SHM + lock thật).
        ref1 = wc.write(_frame(11))
        assert ref1 is not None and ref1.ring_epoch == 1
        assert np.array_equal(rc.read_ref(ref1), _frame(11))

        # --- Vòng switchover epoch 2,3,4 (4%3==1 → tái dùng ring của epoch 1) ---
        prev_ref = ref1
        for epoch in (2, 3, 4):
            assert sup.on_event("shm_ring_rebuild_requested", reason="test") == epoch
            assert cp.read_current()[0] == epoch

            val = 20 + epoch
            ref = wc.write(_frame(val))              # writer phát hiện đổi epoch → chuyển ring + register + ghi
            assert wc.epoch == epoch
            assert ref.ring_epoch == epoch           # ghi vào RING MỚI (đúng epoch)

            got = rc.read_ref(ref)                   # reader chuyển ring + đọc
            assert rc.epoch == epoch
            assert np.array_equal(got, _frame(val))

            assert rc.read_ref(prev_ref) is None     # ref epoch trước → stale → None (không đọc nhầm ring cũ)
            prev_ref = ref

        # epoch 4 dùng lại ring vật lý của epoch 1 (pool_size=3) — chứng minh tái dùng vòng với SHM thật.
        assert pool.name_for_epoch(4) == pool.name_for_epoch(1)
    finally:
        if wc.current_ring is not None:
            wc.current_ring.close()
        if rc.current_ring is not None:
            rc.current_ring.close()
        pool.close_all()
        cp.close(); cp.unlink()


def test_single_writer_invariant_holds_across_pool():
    """2 writer coordinator cùng epoch trên cùng pool ring → cái thứ 2 register_writer raise (bất biến giữ)."""
    from vision_platform.runtime.ipc.shm_frame_ring import SingleWriterViolation
    import pytest

    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=2, session_prefix=f"itest_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
    try:
        sup.switchover()                             # epoch 1
        wc1 = WriterEpochCoordinator(cp, opener)
        wc1.bootstrap()                              # register_writer ring1 (OK)
        wc2 = WriterEpochCoordinator(cp, opener)
        with pytest.raises(SingleWriterViolation):
            wc2.bootstrap()                          # ring1 đã có writer → raise (1-writer/ring)
        wc1.current_ring.close()
    finally:
        pool.close_all()
        cp.close(); cp.unlink()
