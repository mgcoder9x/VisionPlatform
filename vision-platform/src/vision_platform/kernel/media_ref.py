"""IMediaRef — port trừu tượng cho "tham chiếu frame".

Layer: kernel (port/DTO thuần). Chỉ phụ thuộc numpy + typing — KHÔNG import
multiprocessing/shared_memory/adapter cụ thể (giữ contract import-linter của kernel).

VÌ SAO TỒN TẠI (seam K-038): trước đây `MediaPacket.media_ref` cứng kiểu concrete
`InMemoryArrayRef` → World-A (Stage pipeline in-process) và World-B (SHM cross-process)
không hợp qua cùng 1 packet. Rút port này để packet phụ thuộc ABSTRACTION, cho phép nhiều
backend frame (in-memory hôm nay, SHM `ShmMediaRef` ở runtime/ipc về sau) cắm vào cùng 1
Stage pipeline mà KHÔNG sửa packet/Stage.

BỀ MẶT TỐI THIỂU (YAGNI — verify bằng grep: consumers chỉ dùng `.array`):
    array -> np.ndarray   # materialize frame hiện tại ra ndarray, read-only BY CONTRACT

Read-only là CONVENTION (giống InMemoryArrayRef set write=False), KHÔNG phải bảo đảm tuyệt
đối nếu impl còn giữ alias writable. Impl chịu trách nhiệm materialize read-only.
"""
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class IMediaRef(Protocol):
    """Port: tham chiếu tới dữ liệu frame, materialize được ra ndarray.

    `@runtime_checkable` cho phép `isinstance(x, IMediaRef)` kiểm SỰ TỒN TẠI thuộc tính
    `array` (không kiểm kiểu trả về — đó là giới hạn của Protocol runtime-check). Đủ để
    test/chẩn đoán; ràng buộc kiểu thật do type-checker (mypy) đảm nhiệm lúc tĩnh.
    """

    @property
    def array(self) -> np.ndarray:
        """Frame hiện tại dưới dạng ndarray (read-only by contract)."""
        ...
