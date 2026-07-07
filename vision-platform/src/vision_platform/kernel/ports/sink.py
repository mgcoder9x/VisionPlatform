"""ISink — outbound port: ĐÍCH xử lý packet sau pipeline (print/DB/queue/file/none).

Layer: kernel/ports — Protocol thuần. Chỉ phụ thuộc kernel (ExecutionResult). Impl (JsonlEventSink/
CollectingSink/EventSink...) sống ở runtime/adapters. Đối xứng IFrameSource/IDetector.

VÌ SAO TỒN TẠI (Gap-1 K-037): hoàn thiện tam giác hexagonal inbound(IFrameSource) → mechanism(executor)
→ outbound(ISink). `handle` nhận CẢ ExecutionResult non-SUCCESS (SKIPPED/ERROR/CANCELLED) — sink tự quyết
xử/bỏ (giữ đầy đủ trạng thái, không bóp về None — cùng triết lý ExecutionResult).
"""
from typing import Protocol, runtime_checkable

from vision_platform.kernel.stage_contract import ExecutionResult


@runtime_checkable
class ISink(Protocol):
    """Đích nhận kết quả pipeline. Lifecycle setup/teardown (mở/đóng DB/file/socket)."""

    def setup(self) -> None: ...

    def handle(self, result: ExecutionResult) -> None: ...

    def teardown(self) -> None: ...
