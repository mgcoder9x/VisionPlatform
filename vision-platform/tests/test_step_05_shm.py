"""Step 05: SHM frame ring buffer + multi-process transport.

13 test theo Design step-05 + 1 hardening dtype (F-6) + 2 defensive guard (re-review) = 16.
Cross-process test (writer subprocess, reader parent) CHẠY THẬT (F-8/F-10).

Lưu ý Windows spawn: worker `_camera_worker_with_queue` phải ở module-level (importable);
slot_locks truyền qua Process(args=) (inherit), refs trả qua Queue (tuple int).
"""
import multiprocessing as mp
import uuid

import numpy as np
import pytest

from vision_platform.kernel.shm_frame_ref import ShmFrameRefData
from vision_platform.runtime.ipc.shm_frame_ring import (
    SlotState, ShmRingBuffer, ShmFrameWriter, ShmFrameReader, _read_header,
)


@pytest.fixture
def ring():
    """Ring 4 slot, frame 10x10x3 (n_slots=4 BẮT BUỘC cho test recycle/ABA — F-7)."""
    r = ShmRingBuffer(
        name=f"tr_{uuid.uuid4().hex[:8]}",
        n_slots=4, height=10, width=10, channels=3, create=True,
    )
    yield r
    r.cleanup_all()


def _frame(value: int, h: int = 10, w: int = 10, c: int = 3) -> np.ndarray:
    return np.full((h, w, c), value, dtype=np.uint8)


# ============ Lifecycle (3) ============

def test_ring_allocates_segments(ring):
    assert len(ring._meta_shms) == 4
    assert len(ring._data_shms) == 4


def test_ring_initial_state_is_free(ring):
    for i in range(ring.n_slots):
        state, gen, _pid = _read_header(ring._meta_shms[i].buf)
        assert state == SlotState.FREE
        assert gen == 0


def test_cleanup_is_idempotent(ring):
    ring.cleanup_all()
    ring.cleanup_all()  # gọi lần 2 không được raise
    assert ring._meta_shms == []
    assert ring._data_shms == []


# ============ Writer (4) ============

def test_writer_writes_to_first_free(ring):
    writer = ShmFrameWriter(ring)
    ref = writer.write(_frame(7))
    assert ref is not None
    assert ref.slot == 0
    assert ref.generation == 1
    state, gen, _pid = _read_header(ring._meta_shms[0].buf)
    assert state == SlotState.READY
    assert gen == 1


def test_writer_round_robin(ring):
    writer = ShmFrameWriter(ring)
    slots = [writer.write(_frame(v)).slot for v in range(3)]
    assert slots == [0, 1, 2]


def test_writer_returns_none_when_all_busy(ring):
    writer = ShmFrameWriter(ring)
    for v in range(4):
        assert writer.write(_frame(v)) is not None  # 4 slot -> READY
    assert writer.write(_frame(99)) is None          # hết slot FREE/DONE


def test_writer_rejects_wrong_shape(ring):
    writer = ShmFrameWriter(ring)
    with pytest.raises(ValueError):
        writer.write(_frame(1, h=5, w=5))


# ============ Reader (3) ============

def test_reader_reads_after_write(ring):
    writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
    frame = _frame(42)
    ref = writer.write(frame)
    out = reader.read(ref.slot, ref.generation)
    assert out is not None
    assert np.array_equal(out, frame)
    state, _gen, _pid = _read_header(ring._meta_shms[ref.slot].buf)
    assert state == SlotState.DONE


def test_reader_none_for_wrong_generation(ring):
    writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
    ref = writer.write(_frame(1))
    assert reader.read(ref.slot, ref.generation + 999) is None


def test_reader_none_for_free_slot(ring):
    reader = ShmFrameReader(ring)
    assert reader.read(3, 1) is None  # slot 3 chưa ghi -> FREE


# ============ Recycle + ABA (2) ============

def test_writer_recycles_done_slot(ring):
    writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
    ref1 = writer.write(_frame(1))            # slot0 gen1
    reader.read(ref1.slot, ref1.generation)   # slot0 -> DONE
    for v in [2, 3, 4]:
        writer.write(_frame(v))               # lấp slot 1,2,3
    ref2 = writer.write(_frame(5))            # wrap về slot0 (DONE) -> recycle
    assert ref2.slot == 0
    assert ref2.generation > ref1.generation


def test_aba_prevention_old_ref_cannot_read_new_data(ring):
    writer, reader = ShmFrameWriter(ring), ShmFrameReader(ring)
    f1 = _frame(11)
    ref_old = writer.write(f1)                # gen1, slot0
    assert np.array_equal(reader.read(ref_old.slot, ref_old.generation), f1)  # -> DONE

    for v in [2, 3, 4]:
        writer.write(_frame(v))               # ép tái dùng slot0
    f_new = _frame(99)
    ref_new = writer.write(f_new)
    assert ref_new.slot == ref_old.slot
    assert ref_new.generation > ref_old.generation

    # ref CŨ đọc -> None (gen mismatch — ABA prevented)
    assert reader.read(ref_old.slot, ref_old.generation) is None
    # ref MỚI đọc -> data mới
    assert np.array_equal(reader.read(ref_new.slot, ref_new.generation), f_new)


# ============ Hardening dtype (1) — brief #05 F-6 (thêm so với Design) ============

def test_writer_rejects_wrong_dtype(ring):
    writer = ShmFrameWriter(ring)
    with pytest.raises(ValueError):
        writer.write(np.full((10, 10, 3), 1, dtype=np.float32))


# ============ Defensive guards (2) — bịt nhánh __init__ chưa phủ (re-review Pha 2) ============

def test_attach_without_locks_raises():
    """create=False mà KHÔNG truyền slot_locks → RuntimeError (child không tự tạo lock local được)."""
    with pytest.raises(RuntimeError):
        ShmRingBuffer(
            name=f"guard_{uuid.uuid4().hex[:8]}",
            n_slots=4, height=8, width=8, channels=3, create=False,
        )


def test_slot_locks_length_mismatch_raises():
    """slot_locks sai số lượng so với n_slots → ValueError."""
    locks = [mp.Lock(), mp.Lock()]  # 2 != 4
    with pytest.raises(ValueError):
        ShmRingBuffer(
            name=f"guard_{uuid.uuid4().hex[:8]}",
            n_slots=4, height=8, width=8, channels=3, create=False, slot_locks=locks,
        )


# ============ Multi-process integration (1) ============

def _camera_worker_with_queue(ring_name, n_slots, height, width, channels,
                              slot_locks, n_frames, sentinel_value, queue):
    """Worker process: re-attach ring (create=False) + ghi N frame, trả refs qua queue."""
    ring = ShmRingBuffer(
        name=ring_name, n_slots=n_slots, height=height, width=width,
        channels=channels, create=False, slot_locks=slot_locks,
    )
    writer = ShmFrameWriter(ring)
    refs = []
    for i in range(n_frames):
        ref = writer.write(np.full((height, width, channels), i + sentinel_value, dtype=np.uint8))
        if ref is None:
            break
        refs.append((ref.slot, ref.generation))
    queue.put(refs)


def test_writer_in_subprocess_reader_in_parent():
    """Cross-process THẬT: writer ở subprocess, reader ở parent (parent = creator, còn sống — F-8)."""
    name = f"xproc_{uuid.uuid4().hex[:8]}"
    ring = ShmRingBuffer(
        name=name, n_slots=4, height=8, width=8, channels=3, create=True,
    )
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_camera_worker_with_queue,
        args=(name, 4, 8, 8, 3, ring.slot_locks_for_children, 4, 100, queue),
    )
    try:
        proc.start()
        proc.join(timeout=10)
        assert proc.exitcode == 0
        refs = queue.get(timeout=2)
        assert len(refs) == 4

        reader = ShmFrameReader(ring)
        for i, (slot, gen) in enumerate(refs):
            frame = reader.read(slot, gen)
            assert frame is not None, f"Frame {i} not readable"
            assert frame[0, 0, 0] == i + 100
    finally:
        ring.cleanup_all()
