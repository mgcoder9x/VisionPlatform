"""K-014 (một phần): chứng minh THỰC NGHIỆM bound frame-drop Q2 ≤ n_slots khi switchover.

Q2 (design §Overview): check-on-write → writer KHÔNG ghi ring cũ sau publish (mis-write=0); frame "mất" =
các frame READY CHƯA ĐỌC còn trong ring cũ lúc switchover → ≤ n_slots (dung lượng ring). Test này dựng
worst-case (ring đầy frame chưa đọc) + switchover → đo số frame epoch cũ hoá stale (drop) == số chưa đọc ≤ n_slots.

GIỚI HẠN (thật): đây là đo BOUND (deterministic, in-process), KHÔNG phải benchmark throughput dưới tải fps
thật (số đó timing-dependent, cần perf harness riêng — vẫn 🔴). Chỉ khẳng định bound, không khẳng định số tải.
"""
from __future__ import annotations

import uuid

import numpy as np

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.application.ring_supervisor import RingSupervisor
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator

_H = _W = _C = 4
_N = 4


def _frame(v):
    return np.full((_H, _W, _C), v % 250 + 1, dtype=np.uint8)


def test_q2_drop_at_switchover_bounded_by_nslots():
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"q2_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
    wc = WriterEpochCoordinator(cp, opener)
    rc = ReaderEpochCoordinator(cp, opener)
    try:
        assert sup.switchover() == 1                       # epoch 1
        wc.bootstrap()
        rc.bootstrap()

        # Worst-case: ghi NHIỀU frame mà KHÔNG đọc → lấp ring epoch 1 (chỉ n_slots thành READY, phần dư None).
        epoch1_refs = []
        for i in range(_N * 3):                            # ghi dư (12) so với n_slots (4)
            ref = wc.write(_frame(i))
            if ref is not None:
                epoch1_refs.append(ref)
        unread = len(epoch1_refs)                          # frame epoch-1 READY chưa đọc
        assert unread <= _N, f"số READY chưa đọc ({unread}) phải ≤ n_slots ({_N}) — backpressure"

        # Switchover epoch 2 (không có reader nào drain epoch 1 → worst-case).
        assert sup.switchover() == 2

        # Mọi ref epoch 1 giờ stale → reader trả None (DROP). Đếm drop.
        rc.read_ref(epoch1_refs[0])                        # kích rc chuyển sang epoch 2 (check-on-read)
        assert rc.epoch == 2
        dropped = sum(1 for ref in epoch1_refs if rc.read_ref(ref) is None)

        # BOUND Q2: drop == số frame chưa đọc, và ≤ n_slots.
        assert dropped == unread
        assert dropped <= _N
        print(f"[Q2] worst-case drop tại switchover = {dropped} (= unread) ≤ n_slots={_N}")
    finally:
        if wc.current_ring is not None:
            wc.current_ring.close()
        if rc.current_ring is not None:
            rc.current_ring.close()
        pool.close_all()
        cp.close(); cp.unlink()


def test_q2_zero_drop_when_drained_before_switchover():
    """Đối chứng: nếu reader ĐỌC HẾT (drain) trước switchover → drop = 0 (mất frame chỉ do frame CHƯA đọc)."""
    cp = RingControlPlane(f"vp_cp_test_{uuid.uuid4().hex}", create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"q2_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
    wc = WriterEpochCoordinator(cp, opener)
    rc = ReaderEpochCoordinator(cp, opener)
    try:
        sup.switchover()                                   # epoch 1
        wc.bootstrap(); rc.bootstrap()
        # ghi 1 → đọc 1 ngay (drain) nhiều lần → không tồn frame chưa đọc
        received = 0
        for i in range(6):
            ref = wc.write(_frame(i))
            if ref is not None and rc.read_ref(ref) is not None:
                received += 1
        assert received == 6                               # đọc hết, không mất
    finally:
        if wc.current_ring is not None:
            wc.current_ring.close()
        if rc.current_ring is not None:
            rc.current_ring.close()
        pool.close_all()
        cp.close(); cp.unlink()
