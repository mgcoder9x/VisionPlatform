"""vision_fullstack_profile — CAPSTONE composition-root: WIRE toàn chuỗi end-to-end.

Layer: profiles (composition-root ở rim) — được phép import mọi layer (kernel/runtime/application/adapters).
KHÔNG có layer nào được import ngược lên profiles (contract import-linter "... khong import ... profiles").

VÌ SAO FILE NÀY (sub-spec full-stack-integration-profile, capstone): tới giờ mỗi thành phần
(SHM #05, switchover #05b, inference ZMQ, supervisor+liveness #09/#09b, backpressure #07, observability #08)
được test RIÊNG LẺ. File này là artifact "product-shaped" đầu tiên: dựng 1 hệ 2-process (bulkhead) dưới
`Supervisor`, chứng minh frame chảy THẬT: camera → SHM → (ZMQ) inference → detections, rồi shutdown sạch.

⚠️ QĐ KIẾN TRÚC (điều chỉnh so với design PHA-1, ghi C-011): worker-entry (`camera_worker`,
`inference_server_entry`) đặt NGAY trong profile module này — KHÔNG ở `tests/`. Lý do:
  (a) profiles là composition-root SHIPPABLE; module `tests/` không ship + `src` không được import `tests`;
  (b) Windows spawn re-import module chứa `target` ở process con → module-level function ở đây picklable +
      import được (khác hàm trong test-file). Profile tự chứa = nền sản phẩm thật.

⚠️ Windows spawn (verify #05b T-B / zmq): `mp.Lock` KHÔNG mở theo tên → truyền `slot_locks_map()` +
`cp.name` + `endpoint` qua `Process(args=)` (thừa kế). `RingPool` (H2, K-012) né cấp-phát-động lúc switchover.

QĐ v1 (design QĐ-1): 1 camera + 1 inference server (1 RingPool) — giữ bất biến 1-writer/ring (#05 F-4).
Multi-camera = N pool (Non-goal v1). Verify qua ARTIFACT FILE (design QĐ-4): metrics per-process không gộp
cross-process được → camera ghi frames_ok/infer_ok/infer_err ra file lúc `finally`; test đọc sau shutdown.
"""
from __future__ import annotations

import contextlib
import socket
import time
import uuid
from typing import Optional

from vision_platform.kernel.inference_protocol import InferenceRequest
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.runtime.observability import setup_logging, log_context, InMemoryMetrics
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator
from vision_platform.application.inference_server import InferenceServer
from vision_platform.application.supervisor import Supervisor, WorkerSpec
from vision_platform.adapters.fake_detector import FakeDetector
from vision_platform.adapters.detector_pipeline import DetectorPipeline
from vision_platform.adapters.noise_frame_source import NoiseFrameSource


# ------------------------------------------------------------------ helpers

def _free_port() -> int:
    """Chọn 1 cổng TCP loopback rảnh (tránh trùng khi test song song). Pattern như test_zmq_switchover."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_result(path: Optional[str], metrics, frames_dropped_shm: int = 0,
                  frames_dropped_shutdown: int = 0, dets_total: int = 0) -> None:
    """Ghi artifact số liệu để test/CLI đọc cross-process (design QĐ-4). Không có path → bỏ qua.

    `metrics` = `BackpressureMetrics` (snapshot client). Ghi CẢ key cũ (`frames_ok`/`infer_ok`/`infer_err`/
    `dets_total` — giữ test fullstack cũ không vỡ, `frames_ok`=frames_submitted) LẪN 6 field metrics mới +
    phân tách 3 tầng bỏ frame. `frames_dropped_backpressure` GỘP CẢ 3 tầng (client-window + SHM + shutdown-leftover)
    → bất biến `frames_submitted + frames_dropped_backpressure == frames_captured` đúng **VÔ ĐIỀU KIỆN**
    (kể cả khi drain bị deadline cắt lúc server chết — leftover van được đếm; xem C-019/T-020/K-053/D-055).

    3 tầng bỏ frame: (1) client-window = `metrics.frames_dropped_backpressure` (DROP_OLDEST/NEWEST/REJECT ở van);
    (2) SHM = `frames_dropped_shm` (ring đầy, write→None); (3) shutdown = `frames_dropped_shutdown` (frame CÒN
    trong van chưa gửi khi shutdown cắt drain — captured nhưng không submit/không evict).
    """
    if path is None:
        return
    dropped_total = metrics.frames_dropped_backpressure + frames_dropped_shm + frames_dropped_shutdown
    with contextlib.suppress(Exception):
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                # --- key cũ (backward-compat cho test/CLI hiện có) ---
                f"frames_ok={metrics.frames_submitted}\n"
                f"infer_ok={metrics.infer_ok}\n"
                f"infer_err={metrics.infer_err}\n"
                f"dets_total={dets_total}\n"
                # --- 6 field BackpressureMetrics + phân tách 3 tầng drop (mới) ---
                f"frames_captured={metrics.frames_captured}\n"
                f"frames_submitted={metrics.frames_submitted}\n"
                f"frames_dropped_backpressure={dropped_total}\n"
                f"frames_dropped_client_window={metrics.frames_dropped_backpressure}\n"
                f"frames_dropped_shm={frames_dropped_shm}\n"
                f"frames_dropped_shutdown={frames_dropped_shutdown}\n"
                f"infer_timeout={metrics.infer_timeout}\n"
            )


def parse_result(path: str) -> dict[str, int]:
    """Đọc + parse artifact do camera_worker ghi. Trả dict {frames_ok, infer_ok, infer_err}."""
    out: dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = int(v)
    return out


# ------------------------------------------------------------------ worker entry points (spawn-safe, module-level)

def inference_server_entry(shutdown_event, endpoint, cp_name, locks_map, n_slots, h, w, c, model_h, model_w) -> None:
    """Process inference-server: attach control-plane + pool opener (lock thừa kế) → ReaderEpochCoordinator
    (switchover-aware) + DetectorPipeline(FakeDetector) + InferenceServer.serve (ROUTER, cooperative shutdown).

    Detector = `DetectorPipeline(FakeDetector(), model_h, model_w)` → chạy CẢ CHUỖI thật: frame ORIGINAL_FRAME
    (h×w từ SHM) → letterbox về (model_h×model_w) → FakeDetector → inverse-transform box về ORIGINAL_FRAME
    (sub-spec real-detector-integration). Chứng minh coordinate-transform hoạt động cross-process trong hệ wired.
    Tái dùng nguyên InferenceServer (R3.1). bootstrap + bind CHẠY TRONG process này (SHM handle + socket per-process).
    """
    setup_logging()
    cp = RingControlPlane(cp_name, create=False)
    opener = make_pool_opener(locks_map, n_slots, h, w, c)
    coord = ReaderEpochCoordinator(cp, opener)
    detector = DetectorPipeline(FakeDetector(), model_h=model_h, model_w=model_w)
    server = InferenceServer(coord, detector, endpoint)
    try:
        server.serve(shutdown_event)   # block tới khi shutdown_event set (cooperative)
    finally:
        with contextlib.suppress(Exception):
            cp.close()


def camera_worker(shutdown_event, heartbeat, endpoint, cp_name, locks_map, n_slots, h, w, c, result_path) -> None:
    """Process camera (Mô hình A — bound-before-send, Wave 3.1): NoiseFrameSource →
    WriterEpochCoordinator.write(SHM, switchover-aware) → ZmqInferenceClient.**submit** (ASYNC, non-blocking) →
    poll_responses. Cooperative (poll shutdown_event #09) + heartbeat (#09b). Ghi BackpressureMetrics ra
    artifact lúc `finally` (design QĐ-4 / §4.5, R1/R4/R5).

    HAI tầng backpressure (K-053): (1) SHM ring `write()→None` khi đầy → `frames_dropped_shm` (bỏ, KHÔNG
    submit); (2) cửa sổ submit client (BoundedQueue DROP_OLDEST) → `metrics.frames_dropped_backpressure`.
    Artifact ghi `frames_dropped_backpressure` GỘP cả 2 tầng (C-019/T-020) → bất biến
    `frames_submitted + frames_dropped_backpressure == frames_captured` đúng SAU drain (R4.3).
    `frames_submitted` đếm TẠI LÚC GỬI trong client (K-051), KHÔNG lúc enqueue.
    """
    # Import adapter transport ở đây (leaf) — giữ import module gọn ở tầng profile.
    from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient

    import structlog

    setup_logging()
    logger = structlog.get_logger("camera_worker")
    metrics = InMemoryMetrics()
    timeout_s = 5.0
    frames_captured = 0
    frames_dropped_shm = 0
    dets_total = 0
    _logged_sample = False

    cp = RingControlPlane(cp_name, create=False)
    opener = make_pool_opener(locks_map, n_slots, h, w, c)
    wcoord = WriterEpochCoordinator(cp, opener)
    client = ZmqInferenceClient(endpoint, timeout_s=timeout_s)
    source = NoiseFrameSource(width=w, height=h, max_frames=1_000_000, seed=7)

    def _consume() -> None:
        """Rút response đã hoàn tất (non-blocking): đếm dets_total + log 1 sample. ok/err/timeout do client
        đếm nội bộ (io thread) → đọc từ metrics_snapshot lúc cuối (KHÔNG đếm lại ở đây, tránh trùng)."""
        nonlocal dets_total, _logged_sample
        for resp in client.poll_responses():
            if resp.is_success:
                dets_total += len(resp.detections)
                metrics.counter("camera_infer_total", result="ok")
                if not _logged_sample and resp.detections:
                    d = resp.detections[0]
                    logger.info(
                        "detection_sample", label=d.label, confidence=round(d.confidence, 3),
                        box_space=d.box.space.value,
                        box=[round(d.box.x, 1), round(d.box.y, 1), round(d.box.w, 1), round(d.box.h, 1)],
                    )
                    _logged_sample = True
            else:
                metrics.counter("camera_infer_total", result="err")

    try:
        wcoord.bootstrap()          # register_writer ring epoch hiện tại TRƯỚC frame đầu (1-writer/ring)
        client.setup()
        source.setup()
        while not shutdown_event.is_set():
            heartbeat.value = time.time()          # đập nhịp (#09b) — supervisor phát hiện hang
            r = source.read()
            if not r.has_data:
                if r.status == ReadStatus.EOF:
                    break
                continue
            frames_captured += 1                   # R4.1: đếm MỌI frame nhận từ source
            ref = wcoord.write(r.data)             # None nếu ring đầy → backpressure tầng SHM (K-053)
            if ref is None:
                frames_dropped_shm += 1            # bỏ vì hạ nguồn đầy (T-020) — KHÔNG submit
                _consume()                         # vẫn tiêu thụ response để in_flight giảm
                continue
            req_id = uuid.uuid4().hex
            with log_context(camera_id="cam1", request_id=req_id):
                client.submit(InferenceRequest(req_id, "cam1", ref))   # ASYNC non-blocking (R1.2) — camera KHÔNG bị chặn
            _consume()
            time.sleep(0.02)                       # pace nhẹ: cho server kịp đọc SHM (tránh cycle-đè slot)
        # DRAIN sau vòng lặp (R4.3): io thread gửi nốt frame trong van → thu kết cục, tới khi van rỗng &
        # in_flight==0. Cap an toàn: nếu server chết, timeout-scan (timeout_s) tự dọn in_flight → drain kết thúc.
        drain_deadline = time.monotonic() + timeout_s + 1.0
        while (client.outbound_size > 0 or client.in_flight > 0) and time.monotonic() < drain_deadline:
            heartbeat.value = time.time()
            _consume()
            time.sleep(0.01)
        _consume()                                 # quét nốt response cuối cùng
    finally:
        # teardown TRƯỚC (dừng io thread) → counters + van outbound ỔN ĐỊNH (quiesce) rồi mới đọc snapshot
        # (K-056 F2: snapshot phải đọc sau quiesce) + đếm leftover chính xác (D-055).
        with contextlib.suppress(Exception):
            client.teardown()
        _consume()                                 # thu nốt response còn trong _responses (dets_total chính xác)
        frames_dropped_shutdown = 0
        with contextlib.suppress(Exception):
            # Frame CÒN trong van chưa gửi khi shutdown cắt drain (vd server chết + van đầy): captured nhưng
            # KHÔNG submit/KHÔNG evict → đếm là "dropped-shutdown" để bất biến đúng VÔ ĐIỀU KIỆN (D-055).
            frames_dropped_shutdown = client.outbound_size
        snap = client.metrics_snapshot(frames_captured)
        _write_result(result_path, snap, frames_dropped_shm, frames_dropped_shutdown, dets_total)
        with contextlib.suppress(Exception):
            source.teardown()
        with contextlib.suppress(Exception):
            cp.close()


# ------------------------------------------------------------------ composition root

def run_profile(
    duration_s: float,
    *,
    n_slots: int = 8,
    height: int = 16,
    width: int = 16,
    channels: int = 3,
    model_h: int = 32,
    model_w: int = 32,
    result_path: Optional[str] = None,
) -> dict[str, int]:
    """Composition-root (R1): tạo RingPool + control-plane (publish epoch1) + endpoint ZMQ → Supervisor spawn
    2 process (inference-server + camera, bulkhead) → chạy `duration_s` → cascade shutdown sạch (#09) →
    close pool + control-plane. Trả restart_counts theo worker_id.

    KHÔNG logic nghiệp vụ (R1.3) — chỉ WIRE. Giữ pool creator-handle sống suốt phiên (R1.2).
    """
    pool = RingPool(n_slots, height, width, channels, pool_size=3)
    cp = RingControlPlane(name=f"vp_fs_cp_{uuid.uuid4().hex[:8]}", create=True)
    name1 = pool.activate(1)                    # reset pool[1%3] + bump epoch=1 → tên ring
    if name1 is None:                           # fresh pool → không thể bị chặn drain; phòng thủ
        raise RuntimeError("pool.activate(1) trả None trên pool mới — bất thường")
    cp.publish(1, name1)                        # publish TRƯỚC spawn (bootstrap cần epoch>0 — QĐ-5)
    endpoint = f"tcp://127.0.0.1:{_free_port()}"
    locks_map = pool.slot_locks_map()           # truyền qua Process args → thừa kế lock (K-012)

    workers = [
        WorkerSpec(
            worker_id="inference",
            target=inference_server_entry,
            args=(endpoint, cp.name, locks_map, n_slots, height, width, channels, model_h, model_w),
            uses_shutdown_event=True,
            max_restarts=2,
        ),
        WorkerSpec(
            worker_id="camera",
            target=camera_worker,
            args=(endpoint, cp.name, locks_map, n_slots, height, width, channels, result_path),
            uses_shutdown_event=True,
            uses_heartbeat=True,
            heartbeat_timeout_s=20.0,           # > client timeout 5s → block infer lúc startup KHÔNG bị coi hang
            max_restarts=2,
        ),
    ]
    sup = Supervisor(workers=workers, poll_interval_s=0.2, shutdown_grace_s=8.0)
    try:
        return sup.run(duration_s)
    finally:
        with contextlib.suppress(Exception):
            pool.close_all()
        with contextlib.suppress(Exception):
            cp.close()
        with contextlib.suppress(Exception):
            cp.unlink()


# ------------------------------------------------------------------ CLI ("chạy lên xem")

def main() -> int:
    """CLI demo: chạy toàn hệ + in tóm tắt số liệu để QUAN SÁT.

    Chạy: `python -m vision_platform.profiles.vision_fullstack_profile --duration 5`

    Bản demo hiện tại dùng NoiseFrameSource + DetectorPipeline(FakeDetector) — các thành phần ĐÃ verify. Khi
    có camera thật (RTSP adapter) + weight YOLO thì SWAP source/detector, phần khung giữ nguyên.
    """
    import argparse
    import tempfile
    import os

    parser = argparse.ArgumentParser(prog="vision_platform.profiles.vision_fullstack_profile")
    parser.add_argument("--duration", type=float, default=5.0, help="Số giây chạy hệ")
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--model-size", type=int, default=32, help="Kích thước input model (letterbox)")
    parser.add_argument("--n-slots", type=int, default=8)
    args = parser.parse_args()

    result_path = os.path.join(tempfile.gettempdir(), f"vp_fullstack_{uuid.uuid4().hex[:8]}.txt")
    print(f"[demo] Khởi động hệ full-stack: {args.duration}s · frame {args.height}x{args.width} · "
          f"model {args.model_size}x{args.model_size} · nguồn=Noise · detector=DetectorPipeline(FakeDetector)")
    print("[demo] (JSON log dưới đây là của supervisor + 2 process con)\n")

    counts = run_profile(
        args.duration,
        n_slots=args.n_slots,
        height=args.height,
        width=args.width,
        model_h=args.model_size,
        model_w=args.model_size,
        result_path=result_path,
    )

    data = {}
    try:
        data = parse_result(result_path)
        os.remove(result_path)
    except OSError:
        pass

    print("\n=== KẾT QUẢ (chạy lên xem) ===")
    print(f"  frames_ok   (frame ghi vào SHM)        : {data.get('frames_ok', 0)}")
    print(f"  infer_ok    (inference THÀNH CÔNG)     : {data.get('infer_ok', 0)}")
    print(f"  infer_err   (inference lỗi)            : {data.get('infer_err', 0)}")
    print(f"  dets_total  (tổng detection nhận về)   : {data.get('dets_total', 0)}")
    print(f"  restart_counts (bulkhead/supervisor)   : {counts}")
    ok = data.get("infer_ok", 0) >= 1
    print(f"\n  → Chuỗi camera→SHM→ZMQ→detector→box(ORIGINAL_FRAME) cross-process: "
          f"{'HOẠT ĐỘNG ✅' if ok else 'CHƯA có infer thành công ❌'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
