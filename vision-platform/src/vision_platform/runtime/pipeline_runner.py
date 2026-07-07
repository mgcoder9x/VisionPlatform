"""PipelineRunner + RunStats — engine chạy `source → executor → sink` (đóng Gap-1 K-037).

Layer: runtime. Rút vòng lặp chung (read→dựng MediaPacket→execute→sink.handle→thống kê) mà 4 profile trước
tự viết lại. DI: source(IFrameSource) + executor(SyncLinearExecutor) + sink(ISink) + media_ref_factory
(nối port IMediaRef D-038 — mặc định in-memory) + clock_ns + điều kiện dừng.

Teardown ĐẢM BẢO chạy (finally) kể cả khi thân raise, thứ tự sink→executor→source (ngược lúc setup).
media_ref_factory mặc định InMemoryArrayRef.from_copy → SHM backend (ShmMediaRef) về sau cắm KHÔNG sửa runner.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.media_ref import IMediaRef
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.kernel.ports.frame_source import IFrameSource
from vision_platform.kernel.ports.sink import ISink
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor


@dataclass(frozen=True)
class RunStats:
    """Số liệu 1 lần chạy (immutable). Tổng dispatch = processed+skipped+stage_errors+cancelled = frames_read."""
    frames_read: int = 0
    processed: int = 0
    skipped: int = 0
    stage_errors: int = 0
    cancelled: int = 0
    eof: int = 0
    source_errors: int = 0


class PipelineRunner:
    def __init__(
        self,
        source: IFrameSource,
        executor: SyncLinearExecutor,
        sink: ISink,
        *,
        media_ref_factory: Callable[[np.ndarray], IMediaRef] = InMemoryArrayRef.from_copy,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ):
        self._source = source
        self._executor = executor
        self._sink = sink
        self._media_ref_factory = media_ref_factory
        self._clock_ns = clock_ns

    def run(
        self,
        *,
        max_frames: Optional[int] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        timeout_ms: int = 100,
    ) -> RunStats:
        frames_read = processed = skipped = stage_errors = cancelled = eof = source_errors = 0
        seq = 0
        # Lifecycle: setup source→executor→sink; teardown NGƯỢC trong finally (kể cả khi raise).
        self._source.setup()
        try:
            self._executor.setup_all()
            try:
                self._sink.setup()
                try:
                    while True:
                        if should_stop is not None and should_stop():
                            break
                        # max_frames đếm theo FRAME ĐỌC ĐƯỢC (có data), không theo vòng lặp (QĐ-2).
                        if max_frames is not None and frames_read >= max_frames:
                            break
                        r = self._source.read(timeout_ms)
                        if r.status == ReadStatus.EOF:
                            eof += 1
                            if self._source.is_finite:
                                break
                            continue
                        if r.status == ReadStatus.ERROR:
                            source_errors += 1
                            continue
                        if not r.has_data:
                            continue  # TIMEOUT/RECONNECTING/DROPPED → bỏ qua
                        frames_read += 1
                        packet = MediaPacket(
                            packet_id=f"{self._source.source_id}-{seq}",
                            source_id=self._source.source_id,
                            media_ref=self._media_ref_factory(r.data),
                            capture_time_ns=self._clock_ns(),
                        )
                        seq += 1
                        result = self._executor.execute(packet)
                        if result.status == StageStatus.SUCCESS:
                            processed += 1
                        elif result.status == StageStatus.SKIPPED:
                            skipped += 1
                        elif result.status == StageStatus.ERROR:
                            stage_errors += 1
                        else:
                            cancelled += 1
                        self._sink.handle(result)  # LUÔN gọi, mọi status
                finally:
                    self._sink.teardown()
            finally:
                self._executor.teardown_all()
        finally:
            self._source.teardown()
        return RunStats(
            frames_read=frames_read,
            processed=processed,
            skipped=skipped,
            stage_errors=stage_errors,
            cancelled=cancelled,
            eof=eof,
            source_errors=source_errors,
        )
