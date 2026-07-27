"""tools/web_sse_capacity_probe.py — probe TRẦN THREAD (READ-ONLY): kết nối DÀI (`/events` SSE · `/stream` MJPEG)
chiếm thread WSGI vĩnh viễn → đo khi nào request NGẮN (`/stats`) bị starve.

VÌ SAO (rủi ro thật của spec overlay-sse-transport §Kịch bản 5): waitress là WSGI **sync** — mỗi kết nối được
1 thread trong pool `--threads`. `/stream` (MJPEG multipart) và `/events` (SSE) KHÔNG bao giờ kết thúc → mỗi
viewer web giữ **2 thread dài**. Với `threads=8`, ~4 viewer là cạn pool → `/stats`, `/overlay`, `/` (và viewer
mới) bị CHỜ vô hạn = tự-DoS bằng cách dùng bình thường. Đây là số phải ĐO, không được suy đoán.

CÁCH ĐO (không cần browser — browser bị giới hạn ~6 kết nối/origin nên KHÔNG đủ để chạm trần):
  1. Mở lần lượt N kết nối dài (`--long-paths`, mặc định `/events,/stream` xen kẽ = mô hình 1 viewer = 2 kết nối).
  2. Sau MỖI kết nối, đo request NGẮN `--probe-path` với `--timeout` → thời điểm ĐẦU TIÊN timeout = TRẦN thực tế.
  3. In bảng: mở được bao nhiêu · latency probe · mốc starve. Đóng hết socket khi xong.

§3.1: script CỐ ĐỊNH, CHỈ-ĐỌC (HTTP GET), không ghi repo/không sửa server. Chạy:
  python -m tools.web_sse_capacity_probe --port 8035 --max-long 12 --threads-hint 8
"""
from __future__ import annotations

import argparse
import base64
import os
import time
import urllib.error
import urllib.request


def _auth_header() -> dict:
    u, p = os.environ.get("VP_WEB_USER"), os.environ.get("VP_WEB_PASS")
    if u and p:
        return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}
    return {}


def _open_long(base: str, path: str, headers: dict, timeout: float):
    """Mở 1 kết nối DÀI và GIỮ mở (đọc 1 chunk để chắc server đã phục vụ, KHÔNG close)."""
    req = urllib.request.Request(base + path, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout)   # noqa: S310 — localhost, probe chỉ-đọc
    resp.read(1)                                          # chờ byte đầu = server ĐÃ cấp thread cho kết nối này
    return resp


def _probe_short(base: str, path: str, headers: dict, timeout: float):
    """1 request NGẮN → (ok, latency_ms | lý do lỗi). Timeout = dấu hiệu STARVE (không còn thread rảnh)."""
    req = urllib.request.Request(base + path, headers=headers)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            r.read()
            return True, (time.monotonic() - t0) * 1000.0
    except Exception as e:  # noqa: BLE001 — timeout/lỗi = TÍN HIỆU cần đo, không phải crash probe
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="tools.web_sse_capacity_probe")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8035)
    ap.add_argument("--long-paths", default="/events,/stream",
                    help="các path kết nối DÀI, dùng xen kẽ (mặc định = mô hình 1 viewer: SSE + MJPEG)")
    ap.add_argument("--max-long", type=int, default=12, help="số kết nối dài tối đa sẽ mở")
    ap.add_argument("--probe-path", default="/stats", help="request NGẮN dùng để phát hiện starve")
    ap.add_argument("--timeout", type=float, default=4.0, help="timeout coi là STARVE (giây)")
    ap.add_argument("--threads-hint", type=int, default=None, help="chỉ để in đối chiếu (--threads của server)")
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"
    long_paths = [p.strip() for p in args.long_paths.split(",") if p.strip()]
    headers = _auth_header()
    held: list = []
    starve_at = None

    print(f"[cap] base={base} · long_paths={long_paths} · max_long={args.max_long} · probe={args.probe_path} "
          f"· timeout={args.timeout}s · auth={'yes' if headers else 'no'}"
          + (f" · server_threads={args.threads_hint}" if args.threads_hint else ""))
    ok0, r0 = _probe_short(base, args.probe_path, headers, args.timeout)
    print(f"  {'#long':<6} {'mở path':<9} {'mở được':<9} {'probe ngắn':<12} chi tiết")
    print(f"  {0:<6} {'-':<9} {'-':<9} {'OK' if ok0 else 'STARVE':<12} "
          f"{f'{r0:.1f}ms' if ok0 else r0}")
    try:
        for i in range(1, args.max_long + 1):
            path = long_paths[(i - 1) % len(long_paths)]
            opened, detail = True, ""
            try:
                held.append(_open_long(base, path, headers, args.timeout))
            except Exception as e:  # noqa: BLE001
                opened, detail = False, f"{type(e).__name__}"
            ok, res = _probe_short(base, args.probe_path, headers, args.timeout)
            if not ok and starve_at is None:
                starve_at = i
            print(f"  {i:<6} {path:<9} {('yes' if opened else 'NO ' + detail):<9} "
                  f"{'OK' if ok else 'STARVE':<12} {f'{res:.1f}ms' if ok else res}")
            if not ok:
                break
    finally:
        for r in held:
            try:
                r.close()
            except Exception:  # noqa: BLE001,S110 — dọn best-effort
                pass

    print(f"  KẾT LUẬN: kết nối dài giữ được = {len(held)} · STARVE bắt đầu tại #{starve_at if starve_at else '-'}"
          + (f" (server --threads={args.threads_hint} → 1 viewer = {len(long_paths)} kết nối dài "
             f"⇒ trần ≈ {args.threads_hint // len(long_paths) if args.threads_hint else '?'} viewer)"
             if args.threads_hint else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
