"""K-006: stress đa reader THẬT cross-process (nhiều process đọc đồng thời qua lock thừa kế).

#05 mới test multi-reader IN-PROCESS (deterministic). Đây lấp khoảng: N reader PROCESS riêng đọc cùng ring
đồng thời (barrier đồng bộ), nhận lock qua Process(args=). Assert: đọc đúng data, không corrupt, không crash.
Windows spawn: worker module-level; slot_locks qua args. Guard win32 (nền hiện tại); POSIX chưa verify.
"""
from __future__ import annotations

import multiprocessing as mp
import sys
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc.shm_frame_ring import ShmRingBuffer, ShmFrameWriter, ShmFrameReader

_H = _W = _C = 8


def _reader_worker(ring_name, n, h, w, c, slot_locks, slot, gen, epoch, barrier, result_q):
    """Attach ring (create=False, lock thừa kế) → chờ barrier → đọc 1 slot → báo kết quả."""
    try:
        ring = ShmRingBuffer(name=ring_name, n_slots=n, height=h, width=w, channels=c,
                             create=False, slot_locks=slot_locks)
        reader = ShmFrameReader(ring)
        barrier.wait(timeout=15)                      # mọi reader đọc ~đồng thời
        frame = reader.read(slot, gen, ring_epoch=epoch)
        if frame is None:
            result_q.put((slot, "NONE", None))
        else:
            # kiểm data đồng nhất (không torn): mọi pixel == frame[0,0,0]
            v = int(frame[0, 0, 0])
            uniform = bool(np.all(frame == v))
            result_q.put((slot, "OK" if uniform else "TORN", v))
    except Exception as e:
        result_q.put((slot, "ERROR", repr(e)))


@pytest.mark.skipif(sys.platform != "win32", reason="verify Windows (nền hiện tại); POSIX spawn chưa verify")
def test_n_readers_distinct_slots_all_correct():
    """N reader process, mỗi process đọc 1 slot riêng đồng thời → tất cả đọc đúng data (không corrupt)."""
    name = f"mr_{uuid.uuid4().hex[:8]}"
    ring = ShmRingBuffer(name=name, n_slots=4, height=_H, width=_W, channels=_C, create=True)
    writer = ShmFrameWriter(ring)
    vals = [11, 22, 33, 44]
    refs = [writer.write(np.full((_H, _W, _C), v, dtype=np.uint8)) for v in vals]
    assert all(r is not None for r in refs)
    n = len(refs)
    barrier = mp.Barrier(n)
    q: mp.Queue = mp.Queue()
    procs = []
    for ref, v in zip(refs, vals):
        p = mp.Process(target=_reader_worker,
                       args=(name, 4, _H, _W, _C, ring.slot_locks_for_children,
                             ref.slot, ref.generation, ref.ring_epoch, barrier, q))
        procs.append((p, ref, v))
    try:
        for p, _, _ in procs:
            p.start()
        results = {}
        for _ in range(n):
            item = q.get(timeout=25)
            results[item[0]] = item                   # key = slot
        for p, _, _ in procs:
            p.join(timeout=15)
        for ref, v in zip(refs, vals):
            r = results.get(ref.slot)
            assert r is not None, f"thiếu kết quả slot {ref.slot}"
            assert r[1] == "OK", f"slot {ref.slot}: {r} (mong OK, không TORN/NONE/ERROR)"
            assert r[2] == v, f"slot {ref.slot}: đọc {r[2]} != ghi {v}"
    finally:
        for p, _, _ in procs:
            if p.is_alive():
                p.kill(); p.join(timeout=5)
        ring.cleanup_all()


@pytest.mark.skipif(sys.platform != "win32", reason="verify Windows; POSIX chưa verify")
def test_n_readers_same_slot_no_corruption():
    """N reader process cùng đọc 1 slot đồng thời → mỗi reader nhận OK(đúng data) HOẶC None (slot đã DONE),
    KHÔNG BAO GIỜ TORN/ERROR (multi-reader registry cross-process an toàn)."""
    name = f"mr_{uuid.uuid4().hex[:8]}"
    ring = ShmRingBuffer(name=name, n_slots=4, height=_H, width=_W, channels=_C, create=True)
    writer = ShmFrameWriter(ring)
    ref = writer.write(np.full((_H, _W, _C), 99, dtype=np.uint8))
    n = 4
    barrier = mp.Barrier(n)
    q: mp.Queue = mp.Queue()
    procs = [mp.Process(target=_reader_worker,
                        args=(name, 4, _H, _W, _C, ring.slot_locks_for_children,
                              ref.slot, ref.generation, ref.ring_epoch, barrier, q))
             for _ in range(n)]
    try:
        for p in procs:
            p.start()
        outcomes = [q.get(timeout=25) for _ in range(n)]
        for p in procs:
            p.join(timeout=15)
        ok = 0
        for slot, status, v in outcomes:
            assert status in ("OK", "NONE"), f"reader outcome bất thường: {(slot, status, v)}"  # KHÔNG TORN/ERROR
            if status == "OK":
                assert v == 99                          # data đúng, không corrupt
                ok += 1
        assert ok >= 1, "ít nhất 1 reader phải đọc được frame"
    finally:
        for p in procs:
            if p.is_alive():
                p.kill(); p.join(timeout=5)
        ring.cleanup_all()
