"""K-014: đo FRAME-DROP @fps THẬT của SHM ring khi consumer chậm hơn producer (real-time keep-latest).

VÌ SAO (đóng K-014): `test_switchover_q2_bound.py` đã chứng minh BOUND drop ≤ n_slots (deterministic,
in-process serialize) NHƯNG chưa đo drop DƯỚI TẢI fps thật (timing-dependent). Harness này bổ sung chiều
THỜI GIAN: producer ghi ring ở `--fps`, consumer đọc ref MỚI NHẤT rồi "xử lý" (sleep `--consume-ms`, mô hình
inference) → đo tỉ lệ frame consumer NHẬN ĐƯỢC vs DROP.

MÔ HÌNH DROP (real-time "keep-latest" — đúng hệ thật): 2 nguồn drop TÁCH BẠCH, không nhập nhằng:
  - `drop_ring_full`: `wc.write()` trả None (ring đầy slot chưa đọc = backpressure source-side, = frames_dropped_shm).
  - `drop_superseded`: ref ghi được nhưng bị ref MỚI HƠN thay trong mailbox trước khi consumer kịp lấy
    (chính sách keep-latest: real-time luôn ưu tiên frame mới nhất → frame cũ bỏ).
  received = frame consumer đọc thành công (read_ref ra data). produced = received + drop_ring_full + drop_superseded.

VÌ SAO số ỔN ĐỊNH (khác probe thread #422 nhiễu): đây là số học tốc-độ (produce-rate vs consume-rate), không
phải đo CPU-contention → lặp 3 vòng để xác nhận, KHÔNG kỳ vọng variance lớn.

§3.1: dev-tool CHỈ-ĐỌC/ĐO (không ghi repo, không đổi src). Chạy:
  vision-platform\\.venv\\Scripts\\python.exe -m benchmarks.measure_ring_drop [--fps 30 --consume-ms 100 --n-slots 8 --duration-s 5 --rounds 3]
"""
from __future__ import annotations

import argparse
import statistics
import threading
import time
import uuid

import numpy as np

from vision_platform.runtime.ipc.ring_control_plane import RingControlPlane
from vision_platform.runtime.ipc.ring_pool import RingPool, make_pool_opener
from vision_platform.application.ring_supervisor import RingSupervisor
from vision_platform.application.writer_epoch_coordinator import WriterEpochCoordinator
from vision_platform.application.reader_epoch_coordinator import ReaderEpochCoordinator


def _run_once(fps: float, consume_ms: float, n_slots: int, h: int, w: int, duration_s: float) -> dict:
    cp = RingControlPlane(f"vp_cp_drop_{uuid.uuid4().hex}", create=True)
    pool = RingPool(n_slots, h, w, 3, pool_size=3, session_prefix=f"drop_{uuid.uuid4().hex[:8]}")
    sup = RingSupervisor(cp, pool)
    opener = make_pool_opener(pool.slot_locks_map(), n_slots, h, w, 3)
    wc = WriterEpochCoordinator(cp, opener)
    rc = ReaderEpochCoordinator(cp, opener)

    produced = 0
    drop_ring_full = 0
    drop_superseded = 0
    received = 0
    stop = threading.Event()
    mbox_lock = threading.Lock()
    latest_ref = [None]           # mailbox 1-slot (keep-latest)

    def producer():
        nonlocal produced, drop_ring_full, drop_superseded
        period = 1.0 / fps
        next_t = time.perf_counter()
        base = np.empty((h, w, 3), dtype=np.uint8)
        while not stop.is_set():
            frame = base            # nội dung frame không ảnh hưởng phép đo drop (đo timing/rate)
            ref = wc.write(frame)
            produced += 1
            if ref is None:
                drop_ring_full += 1
            else:
                with mbox_lock:
                    if latest_ref[0] is not None:
                        drop_superseded += 1     # ref cũ chưa consume bị thay → keep-latest bỏ
                    latest_ref[0] = ref
            next_t += period
            sl = next_t - time.perf_counter()
            if sl > 0:
                time.sleep(sl)

    def consumer():
        nonlocal received
        consume_s = consume_ms / 1000.0
        while not stop.is_set():
            with mbox_lock:
                ref = latest_ref[0]
                latest_ref[0] = None
            if ref is None:
                time.sleep(0.001)
                continue
            data = rc.read_ref(ref)
            if data is not None:
                received += 1
            if consume_s > 0:
                time.sleep(consume_s)

    try:
        assert sup.switchover() == 1
        wc.bootstrap(); rc.bootstrap()
        tp = threading.Thread(target=producer); tc = threading.Thread(target=consumer)
        tp.start(); tc.start()
        time.sleep(duration_s)
        stop.set()
        tp.join(timeout=2); tc.join(timeout=2)
    finally:
        if wc.current_ring is not None:
            wc.current_ring.close()
        if rc.current_ring is not None:
            rc.current_ring.close()
        pool.close_all()
        cp.close(); cp.unlink()

    drop = drop_ring_full + drop_superseded
    return {
        "produced": produced, "received": received,
        "drop_ring_full": drop_ring_full, "drop_superseded": drop_superseded,
        "drop_pct": round(100.0 * drop / produced, 1) if produced else 0.0,
        "consumer_fps": round(received / duration_s, 2),
        "producer_fps": round(produced / duration_s, 2),
    }


def main() -> int:
    p = argparse.ArgumentParser(prog="benchmarks.measure_ring_drop")
    p.add_argument("--fps", type=float, default=30.0, help="tốc độ producer ghi ring (frame/s)")
    p.add_argument("--consume-ms", type=float, default=100.0, help="thời gian consumer 'xử lý' mỗi frame (mô hình inference; 100ms≈10/s như YOLO-CPU)")
    p.add_argument("--n-slots", type=int, default=8)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--duration-s", type=float, default=5.0)
    p.add_argument("--rounds", type=int, default=3)
    args = p.parse_args()

    print(f"[ring-drop] fps={args.fps} · consume={args.consume_ms}ms (~{1000.0/args.consume_ms:.1f}/s) · "
          f"n_slots={args.n_slots} · {args.height}x{args.width} · {args.duration_s}s × {args.rounds} vòng")
    print(f"  {'vòng':<5} {'produced':<9} {'received':<9} {'drop_full':<10} {'drop_sup':<9} {'drop%':<7} {'cons_fps':<9}")
    drop_pcts = []
    cons_fpss = []
    for r in range(args.rounds):
        m = _run_once(args.fps, args.consume_ms, args.n_slots, args.height, args.width, args.duration_s)
        drop_pcts.append(m["drop_pct"]); cons_fpss.append(m["consumer_fps"])
        print(f"  {r+1:<5} {m['produced']:<9} {m['received']:<9} {m['drop_ring_full']:<10} "
              f"{m['drop_superseded']:<9} {m['drop_pct']:<7} {m['consumer_fps']:<9}")
    print(f"  MEDIAN drop%={statistics.median(drop_pcts)} · consumer_fps={statistics.median(cons_fpss)}")
    print("  (drop cao là ĐÚNG cho real-time keep-latest khi consumer<producer: bỏ frame cũ, giữ mới nhất — "
          "box vẫn bám frame mới; đây là số ĐO SLA nguồn, không phải lỗi.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
