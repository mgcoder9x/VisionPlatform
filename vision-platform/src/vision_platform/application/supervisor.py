"""Supervisor: spawn worker processes, monitor, graceful shutdown cascade.

Layer: application — điều phối vòng đời process (được import multiprocessing/signal/structlog;
contract #4 chỉ cấm application→adapters/profiles).

Bulkhead (Module 02 file 03): mỗi worker = 1 process → cách ly crash (1 worker chết không kéo cả hệ).

⚠️ Windows spawn: worker function PHẢI ở module riêng (picklable), KHÔNG ở test file.
⚠️ Graceful shutdown = COOPERATIVE (worker poll shutdown_event) — cách DUY NHẤT graceful trên Windows
(TerminateProcess không chạy finally). Xem ERRATA E-10 (cascade cooperative-first).

LIVENESS (sub-spec supervisor-liveness, đóng K-020/K-021 — ADDITIVE, default TẮT):
- **Heartbeat (K-020):** WorkerSpec.uses_heartbeat=True → supervisor tạo `mp.Value('d')` (wall-clock),
  truyền cho worker; worker `hb.value=time.time()` định kỳ. Supervisor coi HANG nếu alive nhưng
  (now − nhịp-cuối) > heartbeat_timeout_s → terminate + xử lý như failure (restart theo cap). Bắt được
  hang/deadlock mà `is_alive()` KHÔNG bắt được (camera chết thầm).
- **Backoff (K-021):** restart_backoff_base_s>0 → giữa các lần restart giãn `base·2^(n-1)` (trần cap),
  NON-BLOCKING (deadline `_next_spawn_ok`, không sleep chặn giám sát worker khác).
- Default TẮT (uses_heartbeat=False, backoff=0) → hành vi Y HỆT #09 (chỉ crash-detection, respawn ngay).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WorkerSpec:
    """Spec để spawn 1 worker process."""
    worker_id: str
    target: Callable[..., None]
    args: tuple = ()
    max_restarts: int = 3
    uses_shutdown_event: bool = False
    """True nếu `target` nhận `shutdown_event: mp.Event` làm THAM SỐ ĐẦU (cooperative graceful — ERRATA E-10)."""
    uses_heartbeat: bool = False
    """True nếu `target` nhận `heartbeat: mp.Value('d')` để cập nhật nhịp (K-020).

    Thứ tự args prepend CỐ ĐỊNH: `[shutdown_event?, heartbeat?] + args`. Ví dụ cả hai:
    `target(shutdown_event, heartbeat, *args)`. Worker gọi `heartbeat.value = time.time()` định kỳ.
    """
    heartbeat_timeout_s: float = 2.0
    """Quá hạn này (giây, wall-clock) mà không có nhịp → coi HANG (chỉ khi uses_heartbeat)."""
    restart_backoff_base_s: float = 0.0
    """0 = KHÔNG backoff (respawn ngay như #09). >0 = giãn `base·2^(n-1)` giữa restart (K-021)."""
    restart_backoff_cap_s: float = 30.0
    """Trần backoff."""


@dataclass
class Supervisor:
    """Supervisor process: quản lý vòng đời workers."""
    workers: list[WorkerSpec]
    poll_interval_s: float = 0.5
    shutdown_grace_s: float = 5.0

    _procs: dict[str, mp.Process] = field(default_factory=dict)
    _restart_counts: dict[str, int] = field(default_factory=dict)
    _shutdown_requested: bool = False
    _shutdown_event: "mp.Event" = field(default=None, init=False)  # type: ignore[assignment]
    # Liveness/backoff state (chỉ dùng khi bật):
    _heartbeats: dict[str, "mp.Value"] = field(default_factory=dict)  # type: ignore[type-arg]
    _spawn_walltime: dict[str, float] = field(default_factory=dict)   # time.time() lúc spawn (startup grace)
    _pending_respawn: dict[str, bool] = field(default_factory=dict)   # đang chờ backoff để respawn
    _next_spawn_ok: dict[str, float] = field(default_factory=dict)    # monotonic deadline được respawn

    def _spawn(self, spec: WorkerSpec) -> mp.Process:
        # Thứ tự prepend CỐ ĐỊNH: [shutdown_event?, heartbeat?] + spec.args.
        prepend: list = []
        if spec.uses_shutdown_event:
            prepend.append(self._shutdown_event)
        if spec.uses_heartbeat:
            hb = self._heartbeats.get(spec.worker_id)
            if hb is None:
                hb = mp.Value("d", 0.0)
                self._heartbeats[spec.worker_id] = hb
            else:
                hb.value = 0.0   # reset → re-arm startup grace cho instance mới
            prepend.append(hb)
        p = mp.Process(
            target=spec.target,
            args=(*prepend, *spec.args),
            name=f"worker-{spec.worker_id}",
            daemon=True,
        )
        p.start()
        self._spawn_walltime[spec.worker_id] = time.time()
        return p

    def _request_shutdown(self, signum: int, _frame) -> None:
        logger.warning("shutdown_signal_received", signal=signum)
        self._shutdown_requested = True

    def request_stop(self) -> None:
        """Yêu cầu dừng vòng giám sát từ LUỒNG KHÁC (spec test-stability-hardening, D-076).

        Chỉ set cờ bool đọc trong vòng `run()` → thread-safe (GIL + gán bool đơn), additive: KHÔNG gọi →
        hành vi cũ Y HỆT. Dùng để test đồng-bộ theo SỰ KIỆN (chạy run() trong thread nền, chờ tiến-độ rồi
        request_stop) thay cửa-sổ-wall-clock; cũng hữu ích orchestration production (dừng ngoài signal).
        KHÔNG đổi semantics liveness/heartbeat/backoff/cascade.
        """
        self._shutdown_requested = True

    def _is_hung(self, spec: WorkerSpec) -> bool:
        """True nếu worker (bật heartbeat) alive nhưng nhịp quá hạn. Startup grace: chưa beat → mốc = spawn time."""
        hb = self._heartbeats.get(spec.worker_id)
        if hb is None:
            return False
        last = hb.value if hb.value > 0 else self._spawn_walltime.get(spec.worker_id, time.time())
        return (time.time() - last) > spec.heartbeat_timeout_s

    def _backoff_for(self, spec: WorkerSpec, restart_count: int) -> float:
        if spec.restart_backoff_base_s <= 0:
            return 0.0
        return min(spec.restart_backoff_base_s * (2 ** (restart_count - 1)), spec.restart_backoff_cap_s)

    def _terminate_proc(self, p: mp.Process) -> None:
        """Kết thúc process treo: terminate → kill nếu ngoan cố."""
        p.terminate()
        p.join(timeout=1.0)
        if p.is_alive():
            p.kill()
            p.join(timeout=1.0)

    def run(self, duration_s: float | None = None) -> dict[str, int]:
        """Spawn workers, monitor (crash + hang), shutdown. Trả dict restart_counts theo worker_id."""
        self._shutdown_event = mp.Event()

        try:
            signal.signal(signal.SIGINT, self._request_shutdown)
            signal.signal(signal.SIGTERM, self._request_shutdown)
        except ValueError:
            pass   # Không phải main thread (pytest) → bỏ qua an toàn.

        for spec in self.workers:
            self._procs[spec.worker_id] = self._spawn(spec)
            self._restart_counts[spec.worker_id] = 0

        logger.info("supervisor_started", n_workers=len(self.workers), pid=os.getpid())

        start = time.monotonic()

        while not self._shutdown_requested:
            if duration_s is not None and (time.monotonic() - start) >= duration_s:
                break

            for spec in self.workers:
                wid = spec.worker_id
                p = self._procs.get(wid)

                if p is None:
                    # Đã give-up → bỏ qua; hoặc đang chờ backoff → respawn khi tới deadline.
                    if self._pending_respawn.get(wid, False) and time.monotonic() >= self._next_spawn_ok.get(wid, 0.0):
                        self._pending_respawn[wid] = False
                        self._procs[wid] = self._spawn(spec)
                    continue

                # Phát hiện failure: crash (exit) HOẶC hang (alive nhưng nhịp quá hạn).
                reason: Optional[str] = None
                exit_code = None
                if not p.is_alive():
                    reason = "crash"
                    exit_code = p.exitcode
                    p.join()
                elif spec.uses_heartbeat and self._is_hung(spec):
                    reason = "hang"
                    logger.warning("worker_heartbeat_timeout", worker_id=wid,
                                   timeout_s=spec.heartbeat_timeout_s)
                    self._terminate_proc(p)

                if reason is None:
                    continue

                # Xử lý failure THỐNG NHẤT (crash + hang): count + cap + backoff.
                self._restart_counts[wid] += 1
                if self._restart_counts[wid] > spec.max_restarts:
                    logger.error("worker_giving_up", worker_id=wid, reason=reason,
                                 restart_count=self._restart_counts[wid])
                    self._procs.pop(wid, None)
                    self._pending_respawn[wid] = False
                    continue

                logger.warning("worker_restarting", worker_id=wid, reason=reason, exit_code=exit_code,
                               restart_count=self._restart_counts[wid])

                backoff = self._backoff_for(spec, self._restart_counts[wid])
                if backoff <= 0:
                    self._procs[wid] = self._spawn(spec)   # respawn NGAY (hành vi #09)
                else:
                    self._procs.pop(wid, None)
                    self._pending_respawn[wid] = True
                    self._next_spawn_ok[wid] = time.monotonic() + backoff

            time.sleep(self.poll_interval_s)

        logger.info("supervisor_shutting_down")
        self._cascade_shutdown()

        return dict(self._restart_counts)

    def _cascade_shutdown(self) -> None:
        """Cascade cooperative-FIRST (ERRATA E-10):
        0. Set shutdown_event → worker cooperative tự thoát + cleanup.
        1. JOIN worker cooperative với grace TRƯỚC → cho `finally` cleanup chạy.
        2. terminate() worker còn sống (non-cooperative / hang).
        3. kill() stragglers cuối.
        """
        deadline = time.monotonic() + self.shutdown_grace_s

        if self._shutdown_event is not None:
            self._shutdown_event.set()

        coop_ids = {s.worker_id for s in self.workers if s.uses_shutdown_event}
        for wid, p in list(self._procs.items()):
            if wid in coop_ids:
                remaining = max(0.0, deadline - time.monotonic())
                p.join(timeout=remaining)

        for wid, p in self._procs.items():
            if p.is_alive():
                logger.debug("sending_sigterm", worker_id=wid)
                p.terminate()

        for wid, p in list(self._procs.items()):
            p.join(timeout=1.0)
            if p.is_alive():
                logger.warning("sigkill_straggler", worker_id=wid)
                p.kill()
                p.join(timeout=1.0)

        logger.info("supervisor_shutdown_complete")
