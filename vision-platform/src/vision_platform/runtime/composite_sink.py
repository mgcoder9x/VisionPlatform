"""CompositeSink — 1 ISink hợp thành, forward tới nhiều sink con.

Layer: runtime. Lý do TỒN TẠI: PipelineRunner nhận 1 sink, nhưng thường cần NHIỀU đích cùng lúc
(vd gom in-memory để test + ghi file JSONL). Hợp thành sạch, thoả ISink.

setup: thuận thứ tự. teardown: NGƯỢC thứ tự + nuốt-lỗi-từng-cái (dọn dẹp không được kẹt vì 1 sink hỏng).
handle: forward TẤT CẢ, KHÔNG nuốt lỗi (fail-fast — lỗi sink là bug wiring, không che; teardown vẫn chạy ở runner).
"""
from __future__ import annotations

from typing import Iterable

from vision_platform.kernel.stage_contract import ExecutionResult
from vision_platform.kernel.ports.sink import ISink


class CompositeSink:
    def __init__(self, sinks: Iterable[ISink]):
        self._sinks = list(sinks)

    def setup(self) -> None:
        for s in self._sinks:
            s.setup()

    def handle(self, result: ExecutionResult) -> None:
        for s in self._sinks:
            s.handle(result)

    def teardown(self) -> None:
        for s in reversed(self._sinks):
            try:
                s.teardown()
            except Exception:
                pass
