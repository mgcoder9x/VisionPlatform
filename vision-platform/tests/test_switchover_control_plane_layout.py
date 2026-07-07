"""Task 1.1 (sub-spec shm-ring-epoch-switchover): layout control-plane segment THUẦN.

Kiểm: offset/alignment · kích thước ≥128B & bội cache-line · tên ring `vp_ring_<32hex>` vừa field ·
pack/check_cp_header fail-fast (magic/version sai) · encode/decode round-trip.
_Requirements: 2.2, 6.2_
"""
from __future__ import annotations

import struct

import pytest

from vision_platform.kernel.shm_control_plane_layout import (
    CP_MAGIC, CP_VERSION, CP_SEGMENT_BYTES, CP_RING_NAME_BYTES, CACHE_LINE_BYTES,
    OFFSET_CP_MAGIC, OFFSET_CP_VERSION, OFFSET_CP_ATTACH_COUNT, OFFSET_CP_EPOCH, OFFSET_CP_RING_NAME,
    pack_cp_header, check_cp_header, encode_ring_name, decode_ring_name,
)


def test_offsets_alignment():
    # field 8B phải ở offset chia hết 8; field 4B chia hết 4 (điều kiện atomic khi aligned)
    assert OFFSET_CP_EPOCH % 8 == 0
    for off in (OFFSET_CP_MAGIC, OFFSET_CP_VERSION, OFFSET_CP_ATTACH_COUNT):
        assert off % 4 == 0
    # không chồng lấn giữa các field cố định
    assert OFFSET_CP_MAGIC == 0
    assert OFFSET_CP_VERSION == 4
    assert OFFSET_CP_ATTACH_COUNT == 8
    assert OFFSET_CP_EPOCH == 16
    assert OFFSET_CP_RING_NAME == 24


def test_segment_size():
    # ≥128B (design §Data Models) và bội cache-line
    assert CP_SEGMENT_BYTES >= 128
    assert CP_SEGMENT_BYTES % CACHE_LINE_BYTES == 0
    # vùng name nằm trọn trong segment
    assert OFFSET_CP_RING_NAME + CP_RING_NAME_BYTES <= CP_SEGMENT_BYTES


def test_ring_name_field_fits_uuid_name():
    # tên thực tế `vp_ring_<32 hex>` = 40 byte < 96
    name = "vp_ring_" + "a" * 32
    assert len(name.encode("utf-8")) <= CP_RING_NAME_BYTES
    encoded = encode_ring_name(name)
    assert len(encoded) == CP_RING_NAME_BYTES
    assert decode_ring_name(encoded) == name


def test_encode_name_too_long_raises():
    with pytest.raises(ValueError):
        encode_ring_name("x" * (CP_RING_NAME_BYTES + 1))


def test_pack_check_header_roundtrip():
    buf = bytearray(CP_SEGMENT_BYTES)
    buf[0:len(pack_cp_header())] = pack_cp_header()
    # không raise khi magic/version đúng
    check_cp_header(bytes(buf))


def test_check_header_wrong_magic_raises():
    buf = bytearray(CP_SEGMENT_BYTES)
    struct.pack_into("<I", buf, OFFSET_CP_MAGIC, 0xDEADBEEF)
    struct.pack_into("<I", buf, OFFSET_CP_VERSION, CP_VERSION)
    with pytest.raises(ValueError):
        check_cp_header(bytes(buf))


def test_check_header_wrong_version_raises():
    buf = bytearray(CP_SEGMENT_BYTES)
    struct.pack_into("<I", buf, OFFSET_CP_MAGIC, CP_MAGIC)
    struct.pack_into("<I", buf, OFFSET_CP_VERSION, CP_VERSION + 99)
    with pytest.raises(ValueError):
        check_cp_header(bytes(buf))


def test_decode_strips_null_pad():
    assert decode_ring_name(b"vp_ring_x" + b"\x00" * (CP_RING_NAME_BYTES - 9)) == "vp_ring_x"
