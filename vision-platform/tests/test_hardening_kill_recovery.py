"""Test Task 4.3 (spec shm-production-hardening): recovery CROSS-PROCESS với process bị KILL thật.

Đây là bằng chứng thật cho Property 3/4: owner chết (kill cứng) còn giữ lock → writer dùng `owner_liveness`
THẬT (psutil) phát hiện DEAD + lease quá hạn → quarantine slot (terminal) qua lock-free peek, KHÔNG đụng
lock chết, ring KHÔNG deadlock (ghi được slot khác).

Windows spawn: worker phải ở module-level (importable); slot_locks truyền qua Process(args=).
"""
from __future__ import annotations

import multiprocessing as mp
import time
import uuid

import numpy as np
import pytest

from vision_platform.runtime.ipc.shm_frame_ring import (
    ShmRingBuffer, ShmFrameWriter, _write_header, SlotState,
)
from vision_platform.runtime.ipc._process_identity import current_identity


def _lock_holder_worker(ring_name, n_slots, h, w, c, slot_locks, slot_idx, queue):
    """Worker: attach ring, GIỮ lock slot_idx, ghi header WRITING + identity thật + lease QUÁ HẠN, rồi treo.

    Mô phỏng owner đang ghi thì CHẾT (parent sẽ kill) trong khi vẫn giữ lock.
    """
    ring = ShmRingBuffer(
        name=ring_name, n_slots=n_slots, height=h, width=w, channels=c,
        create=False, slot_locks=slot_locks,
    )
    lock = ring.slot_lock(slot_idx)
    lock.acquire()                                   # giữ lock (sẽ không bao giờ release — bị kill)
    pid, ct = current_identity()
    # lease quá hạn 1ms để recovery kích hoạt ngay (không phải chờ 2s).
    _write_header(ring._meta_shms[slot_idx].buf, SlotState.WRITING, 7, pid, ct, time.monotonic_ns() - 1_000_000)
    queue.put((pid, ct))                             # báo parent: đã giữ lock + set header
    time.sleep(60)                                   # treo tới khi bị kill


def test_writer_recovers_from_killed_owner_holding_lock():
    name = f"kill_{uuid.uuid4().hex[:8]}"
    ring = ShmRingBuffer(name=name, n_slots=4, height=8, width=8, channels=3, create=True)
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_lock_holder_worker,
        args=(name, 4, 8, 8, 3, ring.slot_locks_for_children, 0, queue),
    )
    try:
        proc.start()
        worker_pid, worker_ct = queue.get(timeout=15)   # chờ worker giữ lock + set header
        assert worker_pid > 0

        # KILL CỨNG worker giữa lúc giữ lock slot0.
        proc.kill()
        proc.join(timeout=15)
        assert proc.exitcode is not None                 # worker đã chết

        # Writer ở parent: slot0 lock bị giữ bởi pid CHẾT → acquire timeout → quarantine (DEAD thật + lease quá hạn).
        writer = ShmFrameWriter(ring)
        ref = writer.write(np.full((8, 8, 3), 9, dtype=np.uint8))

        assert ref is not None, "ring phải còn ghi được slot khỏe (không deadlock)"
        assert ref.slot != 0, "writer phải bỏ qua slot0 poisoned"
        assert ring.peek_state(0) == SlotState.QUARANTINED, "slot0 phải bị quarantine (terminal)"
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
        ring.cleanup_all()


def test_direct_quarantine_on_killed_owner():
    """Gọi quarantine_poisoned_slot trực tiếp sau khi owner bị kill → True (owner_liveness psutil = DEAD)."""
    name = f"killd_{uuid.uuid4().hex[:8]}"
    ring = ShmRingBuffer(name=name, n_slots=4, height=8, width=8, channels=3, create=True)
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_lock_holder_worker,
        args=(name, 4, 8, 8, 3, ring.slot_locks_for_children, 1, queue),
    )
    try:
        proc.start()
        worker_pid, worker_ct = queue.get(timeout=15)
        proc.kill()
        proc.join(timeout=15)
        assert proc.exitcode is not None

        assert ring.quarantine_poisoned_slot(1) is True
        assert ring.peek_state(1) == SlotState.QUARANTINED
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
        ring.cleanup_all()
