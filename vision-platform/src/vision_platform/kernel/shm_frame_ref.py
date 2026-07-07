"""ShmFrameRefData — DTO mô tả 1 frame nằm trong SHM ring.

Layer: kernel — đây là DỮ LIỆU THUẦN (không import multiprocessing/shared_memory).
Transport thật (ShmRingBuffer/Writer/Reader) ở runtime/ipc/shm_frame_ring.py.

Reader dùng (slot, generation) để lookup + verify slot chưa bị ghi đè.
DTO này có thể đi qua wire (ZMQ msgpack) hoặc gắn vào MediaPacket.

INVARIANT (xem brief #05 F-4): generation là WRITER-LOCAL → 1 ring chỉ an toàn với
DUY NHẤT 1 writer (1 camera = 1 process). Nhiều writer/ring sẽ trùng generation → vỡ ABA.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ShmFrameRefData:
    """Pure data carried by MediaPacket pointing to SHM slot."""
    ring_name: str        # ShmRingBuffer.name
    slot: int             # slot index
    generation: int       # ABA-prevention counter
    height: int
    width: int
    channels: int
    ring_epoch: int = 0   # P0-3: phiên bản ring; reader cầm ref epoch cũ sau switchover → trả None (stale).
