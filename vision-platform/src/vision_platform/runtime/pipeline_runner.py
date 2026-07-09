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
import structlog

from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.media_ref import IMediaRef
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.kernel.ports.frame_source import IFrameSource
from vision_platform.kernel.ports.sink import ISink
from vision_platform.kernel.observability_port import PipelineSnapshot, IPipelineObserver
from vision_platform.runtime.observers import NoopObserver
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor

_log = structlog.get_logger("pipeline_runner")


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
        observer: Optional[IPipelineObserver] = None,
        emit_every_n: int = 0,
        emit_interval_s: float = 0.0,
    ):
        self._source = source
        self._executor = executor
        self._sink = sink
        self._media_ref_factory = media_ref_factory
        self._clock_ns = clock_ns
        # Quan sát vận hành (spec pipeline-observability). Default NoopObserver → backward-compat (opt-in).
        self._observer: IPipelineObserver = observer if observer is not None else NoopObserver()
        self._emit_every_n = emit_every_n          # >0: emit sau mỗi N frame ĐỌC ĐƯỢC
        self._emit_interval_s = emit_interval_s    # >0: emit khi trôi >= interval (kiểm ở ĐẦU loop — kể cả no-data)
        self._observer_errors = 0                  # đếm lỗi observer (isolation — không sập pipeline)

    def run(
        self,
        *,
        max_frames: Optional[int] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        timeout_ms: int = 100,
    ) -> RunStats:
        frames_read = processed = skipped = stage_errors = cancelled = eof = source_errors = 0
        seq = 0
        # --- Quan sát vận hành (spec pipeline-observability): state cho emit định kỳ + interval-fps ---
        start_ns = self._clock_ns()
        last_emit_ns = start_ns
        last_emit_frames = 0

        def _emit(is_final: bool) -> None:
            """Dựng + phát PipelineSnapshot. Cập nhật mốc TRƯỚC (tránh re-emit dồn); mọi lỗi emit/observer
            bị CÔ LẬP (đếm + log) → KHÔNG sập vòng lặp xử lý frame (quan sát là phụ trợ — R4.2)."""
            nonlocal last_emit_ns, last_emit_frames
            now = self._clock_ns()
            dt = (now - last_emit_ns) / 1e9
            d_frames = frames_read - last_emit_frames
            last_emit_ns = now
            last_emit_frames = frames_read
            try:
                fps = d_frames / dt if dt > 1e-9 else 0.0
                skip_rate = skipped / frames_read if frames_read > 0 else 0.0
                snap = PipelineSnapshot(
                    source_id=self._source.source_id,
                    frames_read=frames_read, processed=processed, skipped=skipped,
                    stage_errors=stage_errors, frames_per_second=fps, skip_rate=skip_rate,
                    is_final=is_final,
                )
                self._observer.on_snapshot(snap)
            except Exception:  # noqa: BLE001 — quan sát phụ trợ: cô lập lỗi observer, KHÔNG sập pipeline
                self._observer_errors += 1
                _log.warning("observer_error", is_final=is_final, exc_info=True)

        # Lifecycle: setup source→executor→sink; teardown NGƯỢC trong finally (kể cả khi raise).
        # Bọc NGOÀI CÙNG bằng finally để LUÔN phát snapshot CUỐI (is_final) — kể cả khi thân raise (R1.3).
        try:
            self._source.setup()
            try:
                self._executor.setup_all()
                try:
                    self._sink.setup()
                    try:
                        while True:
                            # Emit THEO GIỜ ở ĐẦU loop → mất-camera/reconnecting (no-data→continue) VẪN phát
                            # snapshot (frames_read đứng yên + source_errors tăng) = thấy sự cố live (Lỗ-review-A).
                            if self._emit_interval_s > 0 and (self._clock_ns() - last_emit_ns) / 1e9 >= self._emit_interval_s:
                                _emit(is_final=False)
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
                            # Emit THEO FRAME (nhánh có data) sau khi cập nhật đếm.
                            if self._emit_every_n > 0 and frames_read % self._emit_every_n == 0:
                                _emit(is_final=False)
                            self._sink.handle(result)  # LUÔN gọi, mọi status
                    finally:
                        self._sink.teardown()
                finally:
                    self._executor.teardown_all()
            finally:
                self._source.teardown()
        finally:
            _emit(is_final=True)  # snapshot CHỐT — LUÔN phát (NoopObserver là guard nếu không bật obs)
        return RunStats(
            frames_read=frames_read,
            processed=processed,
            skipped=skipped,
            stage_errors=stage_errors,
            cancelled=cancelled,
            eof=eof,
            source_errors=source_errors,
        )
