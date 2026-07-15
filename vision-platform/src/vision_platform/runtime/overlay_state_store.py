"""OverlayStateStore — authority DUY NHẤT cho semantic state của overlay (spec Task 4).

Layer: runtime. MỌI mutation đi qua đây dưới **một lock authority** (check-and-commit serialized):
validate epochs/token/version → pure transition (stabilizer) → tăng revision → thay MỘT immutable
`OverlayViewSnapshot`. HTTP endpoint (Task 8) chỉ đọc `snapshot()` (reference đã commit) — KHÔNG mutate/
lazy-expire. Nhờ vậy: không trả epoch mới ghép raw/display cũ (Property 1), không cho completion cũ chen
giữa gate-check và clear (Property 2/3), poll lặp không đổi state (Property 4).

Clock TIÊM (`clock`) → test fake-clock, xác định. Không I/O/network. Dùng `DisplayStabilizer` (Task 3).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Sequence

from vision_platform.kernel.inference_protocol import Detection
from vision_platform.kernel.overlay_config import OverlayConfig
from vision_platform.kernel.overlay_view import (
    DetectorState,
    DisplayView,
    HealthSnapshot,
    Outcome,
    OverlayViewSnapshot,
    RawDetectionSnapshot,
    SourceState,
)
from vision_platform.runtime.display_stabilizer import REASON_INIT, DisplayStabilizer, InputBox

_SCHEMA_VERSION = 1


class OverlayStateStore:
    """Authority check-and-commit. Một instance / một source."""

    def __init__(self, process_epoch: str, source_epoch: int, config: OverlayConfig,
                 *, clock: Callable[[], int] = time.monotonic_ns) -> None:
        if not process_epoch:
            raise ValueError("process_epoch rỗng")
        if source_epoch < 1:
            raise ValueError("source_epoch >= 1")
        self._lock = threading.Lock()
        self._process_epoch = process_epoch
        self._source_epoch = source_epoch
        self._clock = clock
        self._cfg = config
        self._stab = DisplayStabilizer(source_epoch, config)
        self._event_revision = 0
        self._inference_generation = 0
        self._last_accepted_version = -1
        self._current_token = 0
        self._health = HealthSnapshot(SourceState.INITIALIZING, DetectorState.INITIALIZING)
        self._raw: Optional[RawDetectionSnapshot] = None
        self._display = DisplayView(revision=0, reason=REASON_INIT, tracks=())
        self._reject_reasons: dict[str, int] = {}
        self._snapshot = self._build()

    # ---- đọc (read-only, không mutate) ----
    def snapshot(self) -> OverlayViewSnapshot:
        """Trả reference immutable đã commit (Property 1/4). KHÔNG mutate/lazy-expire."""
        with self._lock:
            return self._snapshot

    def reject_reasons(self) -> dict[str, int]:
        with self._lock:
            return dict(self._reject_reasons)

    def begin_inference(self) -> int:
        """Cấp single-flight token cho lần dispatch inference kế. Completion phải mang token này."""
        with self._lock:
            self._current_token += 1
            return self._current_token

    @property
    def source_epoch(self) -> int:
        with self._lock:
            return self._source_epoch

    def next_expiry_ns(self) -> Optional[int]:
        """Deadline lease sớm nhất (delegate stabilizer) — scheduler dùng để chờ đúng lúc."""
        with self._lock:
            return self._stab.next_expiry_ns()

    # ---- ghi (mọi mutation qua đây, dưới lock) ----
    def apply_completion(
        self, *, process_epoch: str, source_epoch: int, source_frame_version: int, token: int,
        outcome: Outcome, boxes: Sequence[InputBox],
        input_acquired_ns: int, inference_start_ns: int, inference_end_ns: int, published_ns: int,
    ) -> OverlayViewSnapshot:
        """Nhận một inference completion. GATE: epochs khớp + token single-flight hiện hành +
        version tăng-nghiêm-ngặt. Reject → no-op + bounded reason counter (KHÔNG tăng generation/revision)."""
        with self._lock:
            reason = self._gate(process_epoch, source_epoch, source_frame_version, token)
            if reason is not None:
                self._reject_reasons[reason] = self._reject_reasons.get(reason, 0) + 1
                return self._snapshot   # NO change (Property 3/4)

            self._last_accepted_version = source_frame_version
            self._inference_generation += 1
            now = self._clock()
            display = self._stab.on_accepted_result(boxes, now)
            dets = tuple(Detection(lbl, conf, bx) for (lbl, bx, conf) in boxes)
            self._raw = RawDetectionSnapshot(
                processEpoch=self._process_epoch, sourceEpoch=self._source_epoch,
                sourceFrameVersion=source_frame_version, inferenceGeneration=self._inference_generation,
                inputAcquiredNs=input_acquired_ns, inferenceStartNs=inference_start_ns,
                inferenceEndNs=inference_end_ns, publishedNs=published_ns,
                outcome=outcome, boxes=dets)
            self._commit(display)
            return self._snapshot

    def apply_tick(self, now_ns: Optional[int] = None) -> OverlayViewSnapshot:
        """TimerTick: hết hạn lease. Không đổi gì → no-op (KHÔNG tăng eventRevision — Property 4/13)."""
        with self._lock:
            now = now_ns if now_ns is not None else self._clock()
            before = self._stab.display_revision
            display = self._stab.on_tick(now)
            if self._stab.display_revision != before:
                self._commit(display)
            return self._snapshot

    def apply_source_discontinuity(self, new_source_epoch: int) -> OverlayViewSnapshot:
        """LIVE→discontinuity: tăng sourceEpoch + clear ĐÚNG MỘT LẦN + invalidate token in-flight +
        reset version. (Quyết định KHI tăng epoch = Task 7; store cung cấp primitive nguyên tử này.)"""
        with self._lock:
            display = self._stab.on_discontinuity(new_source_epoch)
            self._source_epoch = new_source_epoch
            self._last_accepted_version = -1
            self._current_token += 1     # completion in-flight (token cũ) → sẽ bị gate reject (chống race)
            self._raw = None
            self._commit(display)
            return self._snapshot

    def set_health(self, source: SourceState, detector: DetectorState) -> OverlayViewSnapshot:
        """Cập nhật health. Đổi → commit (eventRevision++); không đổi → no-op."""
        with self._lock:
            new_health = HealthSnapshot(source, detector)
            if new_health != self._health:
                self._health = new_health
                self._commit(self._display)
            return self._snapshot

    # ---- nội bộ ----
    def _gate(self, pe: str, se: int, ver: int, token: int) -> Optional[str]:
        if pe != self._process_epoch:
            return "PROCESS_EPOCH_MISMATCH"
        if se != self._source_epoch:
            return "SOURCE_EPOCH_MISMATCH"      # completion thuộc epoch cũ (stale sau discontinuity)
        if token != self._current_token:
            return "STALE_TOKEN"                # không phải single-flight hiện hành
        if ver <= self._last_accepted_version:
            return "NON_MONOTONIC_VERSION"      # duplicate/old (Property 3)
        return None

    def _commit(self, display: DisplayView) -> None:
        self._display = display
        self._event_revision += 1
        self._snapshot = self._build()

    def _build(self) -> OverlayViewSnapshot:
        return OverlayViewSnapshot(
            schemaVersion=_SCHEMA_VERSION, processEpoch=self._process_epoch,
            sourceEpoch=self._source_epoch, eventRevision=self._event_revision,
            health=self._health, display=self._display, rawResult=self._raw)
