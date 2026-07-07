"""Test Task 2.1 (spec shm-production-hardening): layout header v2 + ring control.

Kiểm HỢP ĐỒNG NHỊ PHÂN bằng struct/alignment thật (Requirement 4.1–4.5, 4.7). Module thuần (kernel) →
KHÔNG đụng runtime/ring nên 16 test #05 cũ vẫn xanh (additive).
"""
from __future__ import annotations

import ast
import struct
from pathlib import Path

import pytest

from vision_platform.kernel import shm_layout as L


# ============ Kích thước & alignment per-slot header ============

def test_slot_header_is_256_bytes():
    assert L.SLOT_HEADER_V2_BYTES == 256


def test_slot_header_is_cache_line_multiple():
    assert L.SLOT_HEADER_V2_BYTES % L.CACHE_LINE_BYTES == 0


def test_eight_byte_fields_are_8_aligned():
    for off in (
        L.OFFSET_GENERATION,
        L.OFFSET_OWNER_PID,
        L.OFFSET_OWNER_CREATE_TIME_NS,
        L.OFFSET_LEASE_DEADLINE_NS,
    ):
        assert off % 8 == 0, f"offset {off} không chia hết 8"


def test_state_and_count_are_4_aligned():
    assert L.OFFSET_STATE == 0
    assert L.OFFSET_STATE % 4 == 0
    assert L.OFFSET_READER_COUNT % 4 == 0


def test_reader_entry_is_24_bytes():
    assert L.READER_ENTRY_BYTES == 24
    assert struct.calcsize(L.READER_ENTRY_FMT) == 24


def test_reader_registry_fits_within_header():
    end = L.OFFSET_READER_REGISTRY + L.MAX_READERS * L.READER_ENTRY_BYTES
    assert end == 240
    assert end <= L.SLOT_HEADER_V2_BYTES


def test_reader_entry_offsets_are_8_aligned_and_in_range():
    for i in range(L.MAX_READERS):
        off = L.reader_entry_offset(i)
        assert off % 8 == 0
        assert L.OFFSET_READER_REGISTRY <= off
        assert off + L.READER_ENTRY_BYTES <= L.SLOT_HEADER_V2_BYTES


@pytest.mark.parametrize("bad_index", [-1, L.MAX_READERS, L.MAX_READERS + 5])
def test_reader_entry_offset_rejects_out_of_range(bad_index):
    with pytest.raises(IndexError):
        L.reader_entry_offset(bad_index)


def test_single_field_formats_sizes():
    assert struct.calcsize(L.STATE_FMT) == 4
    assert struct.calcsize(L.U64_FMT) == 8
    assert struct.calcsize(L.COUNT_FMT) == 4


# ============ SlotState + QUARANTINED sentinel ============

def test_quarantined_fits_4_byte_state_field():
    # QUARANTINED = 0xFFFFFFFF phải pack được vào trường state <I (uint32 max).
    packed = struct.pack(L.STATE_FMT, int(L.SlotState.QUARANTINED))
    (val,) = struct.unpack(L.STATE_FMT, packed)
    assert val == 0xFFFFFFFF


def test_slot_states_distinct():
    values = [int(s) for s in L.SlotState]
    assert len(values) == len(set(values))


def test_normal_states_dont_collide_with_quarantined():
    for s in (L.SlotState.FREE, L.SlotState.WRITING, L.SlotState.READY, L.SlotState.READING, L.SlotState.DONE):
        assert int(s) != int(L.SlotState.QUARANTINED)


# ============ Ring control segment (self-describing, fail-fast) ============

def test_ring_control_roundtrip_ok():
    raw = L.pack_ring_control()
    assert len(raw) == L.RING_CONTROL_BYTES == 16
    L.check_ring_control(raw)  # không raise


@pytest.mark.parametrize("field_index,bad_value", [
    (0, 0xDEADBEEF),  # magic sai
    (1, 1),           # version sai (v1)
    (2, 999),         # header_size sai
    (3, 4),           # max_readers sai
])
def test_ring_control_mismatch_fails_fast(field_index, bad_value):
    fields = [L.RING_MAGIC, L.HEADER_VERSION, L.SLOT_HEADER_V2_BYTES, L.MAX_READERS]
    fields[field_index] = bad_value
    raw = struct.pack(L.RING_CONTROL_FMT, *fields)
    with pytest.raises(ValueError):
        L.check_ring_control(raw)


# ============ Guard kiến trúc: kernel THUẦN (không I/O lib) ============

def test_layout_module_is_pure_kernel():
    """Requirement: layout ở kernel KHÔNG được import multiprocessing/shared_memory/psutil/numpy/cv2..."""
    src = Path(__file__).resolve().parents[1] / "src" / "vision_platform" / "kernel" / "shm_layout.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    forbidden = {"multiprocessing", "shared_memory", "psutil", "numpy", "cv2", "torch", "zmq"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert forbidden.isdisjoint(imported), f"kernel layout import cấm: {forbidden & imported}"
