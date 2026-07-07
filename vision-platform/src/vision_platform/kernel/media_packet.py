"""MediaPacket — immutable frame packet với CoW semantics.

"Immutable" ở đây = container immutable: metadata/artifacts wrap MappingProxyType
(chặn mutate qua packet), media_ref read-only by contract. Phần ndarray là read-only
theo convention (xem InMemoryArrayRef), không phải bảo đảm tuyệt đối nếu còn alias writable.
"""
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping
import numpy as np

from vision_platform.kernel.media_ref import IMediaRef


@dataclass(frozen=True)
class InMemoryArrayRef:
    """Frame data, read-only BY CONTRACT (không phải immutability tuyệt đối).

    `setflags(write=False)` chặn ghi qua *chính ndarray này*. Nếu còn alias/base array
    writable trỏ vào cùng buffer, dữ liệu vẫn có thể đổi qua alias đó → đây là convention
    "đừng ghi nữa", không phải bảo đảm tuyệt đối.

    - `from_owned_array(arr)`: caller TRAO quyền sở hữu (zero-copy, nhanh).
    - `from_copy(arr)`: defensive copy — caller tự do mutate tiếp; ref giữ snapshot riêng.
    """
    array: np.ndarray

    def __post_init__(self):
        if not isinstance(self.array, np.ndarray):
            raise TypeError(
                f"array phải là numpy.ndarray, nhận {type(self.array).__name__}"
            )
        if self.array.flags.writeable:
            self.array.setflags(write=False)

    def __setstate__(self, state):
        # pickle KHÔNG chạy lại __post_init__, và numpy KHÔNG giữ cờ write=False qua
        # pickle (verify thật numpy 2.4.6 → writeable=True sau round-trip). Re-lock tại
        # đây để giữ contract read-only qua ranh giới process/pickle. (ERRATA E-11)
        object.__setattr__(self, "array", state["array"])
        if self.array.flags.writeable:
            self.array.setflags(write=False)

    @classmethod
    def from_owned_array(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Nhận quyền sở hữu array (zero-copy). Caller cam kết KHÔNG mutate nữa."""
        return cls(array=array)

    @classmethod
    def from_copy(cls, array: np.ndarray) -> "InMemoryArrayRef":
        """Defensive copy — caller can keep mutating original safely."""
        snapshot = np.ascontiguousarray(array.copy())
        return cls(array=snapshot)


@dataclass(frozen=True)
class MediaPacket:
    """Immutable MediaPacket with CoW semantics.

    Mutation antipattern (BLOCKED):  packet.metadata["new"] = "value"   # raises
    CoW pattern (CORRECT):           new_packet = packet.with_metadata("new", "value")
    """
    packet_id: str
    source_id: str
    media_ref: IMediaRef      # port (seam K-038): in-memory HOẶC SHM impl đều cắm được
    capture_time_ns: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Wrap dict-like fields trong MappingProxyType với defensive copy.
        # object.__setattr__ bypass frozen=True — chỉ dùng trong __post_init__.
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if not isinstance(self.artifacts, MappingProxyType):
            object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))

    def __getstate__(self) -> dict:
        # ERRATA E-16: MappingProxyType KHÔNG pickle được (`TypeError: cannot pickle
        # 'mappingproxy' object` — verify thật). Hệ đa tiến trình gửi MediaPacket qua
        # IPC sẽ crash. → convert metadata/artifacts về dict THÔ khi pickle.
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "media_ref": self.media_ref,
            "capture_time_ns": self.capture_time_ns,
            "metadata": dict(self.metadata),
            "artifacts": dict(self.artifacts),
        }

    def __setstate__(self, state: dict) -> None:
        # pickle KHÔNG chạy __post_init__ → tự re-wrap MappingProxyType để GIỮ bất biến
        # sau unpickle. object.__setattr__ vì frozen=True. (ERRATA E-16)
        object.__setattr__(self, "packet_id", state["packet_id"])
        object.__setattr__(self, "source_id", state["source_id"])
        object.__setattr__(self, "media_ref", state["media_ref"])
        object.__setattr__(self, "capture_time_ns", state["capture_time_ns"])
        object.__setattr__(self, "metadata", MappingProxyType(dict(state["metadata"])))
        object.__setattr__(self, "artifacts", MappingProxyType(dict(state["artifacts"])))

    # ---- CoW operations ----
    def with_artifact(self, key: str, value: Any) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts[key] = value
        return replace(self, artifacts=MappingProxyType(new_artifacts))

    def with_metadata(self, key: str, value: Any) -> "MediaPacket":
        new_metadata = dict(self.metadata)
        new_metadata[key] = value
        return replace(self, metadata=MappingProxyType(new_metadata))

    def without_artifact(self, key: str) -> "MediaPacket":
        new_artifacts = dict(self.artifacts)
        new_artifacts.pop(key, None)
        return replace(self, artifacts=MappingProxyType(new_artifacts))
