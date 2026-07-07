"""CollectingSink — ISink gom kết quả vào bộ nhớ (debug/test). Layer: runtime.

Giữ mọi ExecutionResult để assert/quan sát. Không I/O → runtime hợp lệ.
"""
from __future__ import annotations

from vision_platform.kernel.stage_contract import ExecutionResult, StageStatus
from vision_platform.kernel.ports.sink import ISink


class CollectingSink:
    def __init__(self) -> None:
        self.results: list[ExecutionResult] = []

    def setup(self) -> None:
        self.results = []

    def handle(self, result: ExecutionResult) -> None:
        self.results.append(result)

    def teardown(self) -> None:
        pass

    @property
    def counts(self) -> list:
        """Danh sách count của các frame SUCCESS (tiện cho test)."""
        return [
            r.packet.artifacts.get("count")
            for r in self.results
            if r.status == StageStatus.SUCCESS and r.packet is not None
        ]
