"""T-B (sub-spec shm-ring-epoch-switchover, Task 6): switchover CROSS-PROCESS THẬT (spawn).

CRUX K-012 (điều in-process CHƯA phủ): worker process riêng nhận `locks_map` (toàn bộ lock pool) qua THỪA KẾ
(Process args). Sau khi supervisor switchover sang pool ring KHÁC, coordinator worker tự chuyển ring mới +
KHOÁ được nó → chứng minh locks thừa kế PHỦ cả ring đích switchover (giải pháp H2 cho K-012).

Chống flaky: ack-queue serialize (worker ghi 1 → parent đọc+ack → ghi tiếp) ⇒ không lapping slot (tránh ABA
ngẫu nhiên) ⇒ deterministic. Parent trigger switchover giữa stream.

Windows spawn: worker ở module-level; cp tên cố định (attach create=False); locks_map truyền qua Process args.
_Requirements: 1.1, 1.2, 3.1, 5.1, 5.2_
"""
from __future__ import annotations

import multiprocessing as mp
import time
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.application.ring_supervisor import RingSupervisor
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator

_H, _W, _C, _N = 8, 8, 3, 4


def _writer_worker(cp_name, locks_map, n_slots, h, w, c, ref_q, ack_q, ready_q):
    """Worker process: writer coordinator ghi frame nối tiếp (chờ ack mỗi frame → không lapping)."""
    # import trong worker (spawn re-import module OK vì module-level).
    from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
    try:
        cp = RingControlPlane(cp_name, create=False)
        opener = make_pool_opener(locks_map, n_slots, h, w, c)
        wc = WriterEpochCoordinator(cp, opener)
        wc.bootstrap()
        ready_q.put(("READY", None))
        i = 0
        while True:
            token = ack_q.get()                      # chờ lệnh: "WRITE" ghi tiếp, "STOP" dừng
            if token == "STOP":
                break
            val = (i % 250) + 1                       # 1..250 (tránh 0)
            ref = wc.write(np.full((h, w, c), val, dtype=np.uint8))
            if ref is None:
                ref_q.put(("NONE", None, None, None))
            else:
                ref_q.put((ref.ring_epoch, ref.slot, ref.generation, val))
            i += 1
    except Exception as e:  # báo lỗi thật về parent (không nuốt)
        ref_q.put(("ERROR", repr(e), None, None))


@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="T-B verify trên Windows (nền hiện tại); POSIX spawn/teardown ở T-C (K-003).",
)
def test_switchover_cross_process_writer_reader():
    cp_name = f"vp_cp_tb_{uuid.uuid4().hex}"
    cp = RingControlPlane(cp_name, create=True)
    pool = RingPool(_N, _H, _W, _C, pool_size=3, session_prefix=f"tb_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    ref_q: mp.Queue = mp.Queue()
    ack_q: mp.Queue = mp.Queue()
    ready_q: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_writer_worker,
        args=(cp_name, pool.slot_locks_map(), _N, _H, _W, _C, ref_q, ack_q, ready_q),
    )
    from vision_platform.kernel.shm_frame_ref import ShmFrameRefData

    def _read(epoch, slot, gen, val, rc, pool):
        ref = ShmFrameRefData(ring_name=pool.name_for_epoch(epoch), slot=slot, generation=gen,
                              height=_H, width=_W, channels=_C, ring_epoch=epoch)
        frame = rc.read_ref(ref)
        return frame

    try:
        sup.switchover()                                 # epoch 1 (pool.activate + publish)
        proc.start()
        assert ready_q.get(timeout=20)[0] == "READY"     # worker bootstrap xong (register_writer ring1 THẬT)

        opener = make_pool_opener(pool.slot_locks_map(), _N, _H, _W, _C)
        rc = ReaderEpochCoordinator(cp, opener)
        rc.bootstrap()

        got_epoch1 = got_epoch2 = 0

        # --- Pha epoch 1: đọc 3 frame worker ghi (cross-process) ---
        for k in range(3):
            ack_q.put("WRITE")
            item = ref_q.get(timeout=20)
            assert item[0] not in ("ERROR", "NONE"), f"worker lỗi/None: {item}"
            epoch, slot, gen, val = item
            assert epoch == 1
            frame = _read(epoch, slot, gen, val, rc, pool)
            assert frame is not None and int(frame[0, 0, 0]) == val   # đọc đúng data cross-process
            got_epoch1 += 1

        # --- Trigger switchover epoch 2 (worker frame KẾ sẽ tự sang epoch 2) ---
        assert sup.switchover() == 2

        # --- Pha epoch 2: đọc frame epoch 2 (chứng minh worker khoá được ring đích switchover) ---
        for k in range(4):
            ack_q.put("WRITE")
            item = ref_q.get(timeout=20)
            assert item[0] not in ("ERROR", "NONE"), f"worker lỗi/None: {item}"
            epoch, slot, gen, val = item
            assert epoch in (1, 2)                        # KHÔNG bao giờ epoch lạ (không đọc nhầm ring)
            frame = _read(epoch, slot, gen, val, rc, pool)
            if epoch == 2 and frame is not None and int(frame[0, 0, 0]) == val:
                got_epoch2 += 1
            if got_epoch2 >= 1:
                break

        assert got_epoch1 >= 1, "phải đọc được frame epoch 1 do worker ghi (cross-process)"
        assert got_epoch2 >= 1, "phải đọc được frame epoch 2 do worker ghi SAU switchover — CRUX K-012"

        if rc.current_ring is not None:
            rc.current_ring.close()
    finally:
        try:
            ack_q.put("STOP")
        except Exception:
            pass
        proc.join(timeout=15)
        if proc.is_alive():
            proc.kill(); proc.join(timeout=5)
        pool.close_all()
        cp.close(); cp.unlink()
