"""tools/web_concurrent_probe.py — probe TẢI SONG SONG (READ-ONLY) cho web app, kiểm thread-safety đa-client.

§3.1: script CỐ ĐỊNH, CHỈ-ĐỌC (HTTP GET) — an toàn Trust. Bắn N thread song song vào /overlay + /stats trong
`duration` giây (Basic Auth từ env VP_WEB_USER/VP_WEB_PASS nếu có) → in histogram status + số lỗi. Dùng verify
web phục vụ nhiều client đồng thời dưới waitress KHÔNG race/crash (spec web-production-hardening).

KHÔNG ghi gì ra repo/mạng ngoài; KHÔNG sửa server. Chạy:
  python -m tools.web_concurrent_probe --port 8025 --threads 12 --duration 6
"""
from __future__ import annotations

import argparse
import base64
import os
import threading
import time
import urllib.error
import urllib.request
from collections import Counter


def _auth_header() -> dict:
    u, p = os.environ.get("VP_WEB_USER"), os.environ.get("VP_WEB_PASS")
    if u and p:
        return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}
    return {}


def _worker(base: str, paths, headers, stop_ns: int, counter: Counter, lock: threading.Lock) -> None:
    local: Counter = Counter()
    while time.monotonic_ns() < stop_ns:
        for path in paths:
            req = urllib.request.Request(base + path, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    local[str(r.status)] += 1
            except urllib.error.HTTPError as e:
                local[f"HTTP_{e.code}"] += 1
            except Exception as e:  # noqa: BLE001 — lỗi mạng/timeout = tín hiệu (đếm, không crash probe)
                local[f"ERR_{type(e).__name__}"] += 1
    with lock:
        counter.update(local)


def main() -> int:
    ap = argparse.ArgumentParser(prog="tools.web_concurrent_probe")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8025)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--paths", default="/overlay,/stats")
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"
    paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    headers = _auth_header()
    counter: Counter = Counter()
    lock = threading.Lock()
    stop_ns = time.monotonic_ns() + int(args.duration * 1e9)

    ts = [threading.Thread(target=_worker, args=(base, paths, headers, stop_ns, counter, lock))
          for _ in range(args.threads)]
    t0 = time.monotonic()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    elapsed = time.monotonic() - t0

    total = sum(counter.values())
    ok = counter.get("200", 0)
    bad = {k: v for k, v in counter.items() if k != "200"}
    print(f"[probe] base={base} threads={args.threads} duration={args.duration}s paths={paths} auth={'yes' if headers else 'no'}")
    print(f"[probe] total_requests={total} in {elapsed:.2f}s (~{total/elapsed:.0f} req/s) · 200_OK={ok}")
    print(f"[probe] non_200={bad if bad else 'NONE'}")
    print(f"[probe] VERDICT={'PASS (mọi request 200, không race/crash)' if total > 0 and not bad else 'CHECK non-200'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
