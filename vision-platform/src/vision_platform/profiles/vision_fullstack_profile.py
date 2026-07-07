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


def _write_result(path: Optional[str], frames_ok: int, infer_ok: int, infer_err: int, dets_total: int = 0) -> None:
    """Ghi artifact số liệu để test/CLI đọc cross-process (design QĐ-4). Không có path → bỏ qua."""
    if path is None:
        return
    with contextlib.suppress(Exception):
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"frames_ok={frames_ok}\ninfer_ok={infer_ok}\ninfer_err={infer_err}\ndets_total={dets_total}\n"
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
    """Process camera: NoiseFrameSource → WriterEpochCoordinator.write(SHM, switchover-aware) →
    ZmqInferenceClient.infer → InferenceResponse. Cooperative (poll shutdown_event #09) + heartbeat (#09b).
    Ghi frames_ok/infer_ok/infer_err ra artifact lúc `finally` (design QĐ-4, R2.3).

    Backpressure TỰ NHIÊN (design QĐ-3, Q3=hoãn BoundedQueue): `write()` trả None khi ring đầy → skip + sleep.
    """
    # Import adapter transport ở đây (leaf) — giữ import module gọn ở tầng profile.
    from vision_platform.adapters.zmq_inference_client import ZmqInferenceClient

    import structlog

    setup_logging()
    logger = structlog.get_logger("camera_worker")
    metrics = InMemoryMetrics()
    frames_ok = infer_ok = infer_err = dets_total = 0
    _logged_sample = False

    cp = RingControlPlane(cp_name, create=False)
    opener = make_pool_opener(locks_map, n_slots, h, w, c)
    wcoord = WriterEpochCoordinator(cp, opener)
    client = ZmqInferenceClient(endpoint, timeout_s=5.0)
    source = NoiseFrameSource(width=w, height=h, max_frames=1_000_000, seed=7)

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
            ref = wcoord.write(r.data)             # None nếu ring đầy (backpressure tự nhiên)
            if ref is None:
                time.sleep(0.01)
                continue
            frames_ok += 1
            req_id = uuid.uuid4().hex
            with log_context(camera_id="cam1", request_id=req_id):
                resp = client.infer(InferenceRequest(req_id, "cam1", ref))
            if resp.is_success:
                infer_ok += 1
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
                infer_err += 1
                metrics.counter("camera_infer_total", result="err")
            time.sleep(0.02)                       # pace: cho server kịp đọc (tránh cycle-đè slot)
    finally:
        _write_result(result_path, frames_ok, infer_ok, infer_err, dets_total)
        with contextlib.suppress(Exception):
            client.teardown()
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
