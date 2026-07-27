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


def _stats_streams(base: str, headers: dict, timeout: float):
    """Đọc `streams=a/b` từ `/stats` → (active, max) hoặc None nếu server chưa phơi (bản cũ)."""
    req = urllib.request.Request(base + "/stats", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            txt = r.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    for part in txt.split("·"):
        part = part.strip()
        if part.startswith("streams="):
            a, _, b = part[len("streams="):].partition("/")
            try:
                return int(a), int(b)
            except ValueError:
                return None
    return None


def _wait_active(base: str, headers: dict, timeout: float, target: int, deadline_s: float):
    """CHỜ-THEO-SỰ-KIỆN tới khi `active` về `target` (hoặc hết `deadline_s`) → trả `active` cuối cùng đọc được.

    VÌ SAO KHÔNG `sleep()` CỐ ĐỊNH (bài học #462): release chỉ xảy ra khi server ghi chunk kế và phát hiện
    broken pipe — độ trễ này PHỤ THUỘC TẢI. Sleep cố định 0.3s dưới churn nặng cho **BÁO ĐỘNG GIẢ "RÒ RỈ SLOT"**
    (đo lại sau đó: `active` về 0). Tool báo-động-giả còn tệ hơn không có tool (đuổi bóng + mất tin vào checker).
    Cùng tiền lệ `wait_until` đã dùng để đóng flaky test #288/#430.
    """
    end = time.monotonic() + deadline_s
    last = None
    while True:
        st = _stats_streams(base, headers, timeout)
        last = st[0] if st else last
        if st and st[0] == target:
            return st
        if time.monotonic() >= end:
            return st
        time.sleep(0.1)


def _run_churn(args) -> int:
    """Đo RÒ RỈ SLOT: lặp mở-rồi-đóng kết nối dài, kiểm `active` có về 0 (bulkhead D-152 release đúng chưa)."""
    base = f"http://{args.host}:{args.port}"
    long_paths = [p.strip() for p in args.long_paths.split(",") if p.strip()]
    headers = _auth_header()
    print(f"[churn] base={base} · cycles={args.churn} · conns/cycle={args.churn_conns} · long_paths={long_paths}")
    before = _stats_streams(base, headers, args.timeout)
    if before is None:
        print("  [churn] /stats KHÔNG phơi `streams=a/b` → server bản cũ hoặc không bật bulkhead; KHÔNG kết luận được.")
        return 1
    print(f"  {'chu kỳ':<8} {'mở được':<9} {'active khi mở':<15} {'active sau đóng':<16}")
    leaked = None
    peak = 0
    for c in range(1, args.churn + 1):
        held = []
        for i in range(args.churn_conns):
            try:
                held.append(_open_long(base, long_paths[i % len(long_paths)], headers, args.timeout))
            except Exception:  # noqa: BLE001 — 503 khi đạt trần là hợp lệ, không phải lỗi
                pass
        at_open = _stats_streams(base, headers, args.timeout)
        for r in held:
            try:
                r.close()
            except Exception:  # noqa: BLE001,S110
                pass
        # CHỜ-THEO-SỰ-KIỆN (không sleep cố định — chống báo động giả, #462): release phụ thuộc lúc server ghi
        # chunk kế và phát hiện broken pipe → độ trễ thay đổi theo tải.
        after = _wait_active(base, headers, args.timeout, target=before[0], deadline_s=args.release_deadline_s)
        peak = max(peak, at_open[0] if at_open else 0)
        leaked = after[0] if after else None
        print(f"  {c:<8} {len(held):<9} {str(at_open[0]) + '/' + str(at_open[1]) if at_open else '?':<15} "
              f"{str(after[0]) + '/' + str(after[1]) if after else '?':<16}")
    print(f"  KẾT LUẬN: active ban đầu={before[0]} · peak={peak} · active cuối={leaked} → "
          f"{'KHÔNG RÒ RỈ (release đúng)' if leaked == before[0] else 'RÒ RỈ SLOT — release thiếu!'}")
    return 0 if leaked == before[0] else 1


def _run_hold(args) -> int:
    """Mở N kết nối dài rồi GIỮ + ngủ, để bên ngoài KILL (mô phỏng viewer tắt máy/mất mạng đột ngột).

    Ca biên QUAN TRỌNG: client không đóng socket tử tế → nếu server không phát hiện được thì `finally` KHÔNG
    chạy → slot bulkhead rò rỉ → sau vài lần là khoá hết hệ. Kill process này rồi đọc `/stats` để có bằng chứng.
    """
    base = f"http://{args.host}:{args.port}"
    long_paths = [p.strip() for p in args.long_paths.split(",") if p.strip()]
    headers = _auth_header()
    held = []
    for i in range(args.hold_conns):
        try:
            held.append(_open_long(base, long_paths[i % len(long_paths)], headers, args.timeout))
        except Exception as e:  # noqa: BLE001
            print(f"  [hold] mở #{i+1} THẤT BẠI: {type(e).__name__}")
    st = _stats_streams(base, headers, args.timeout)
    print(f"[hold] base={base} · giữ {len(held)} kết nối dài · /stats streams="
          f"{str(st[0]) + '/' + str(st[1]) if st else '?'} · ngủ {args.hold_seconds}s (KILL process này để test)")
    time.sleep(args.hold_seconds)
    print("[hold] hết thời gian ngủ (không bị kill) — đóng bình thường")
    for r in held:
        try:
            r.close()
        except Exception:  # noqa: BLE001,S110
            pass
    return 0


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
    ap.add_argument("--churn", type=int, default=0,
                    help="CHẾ ĐỘ RÒ RỈ SLOT: số chu kỳ mở-rồi-đóng kết nối dài; đọc `streams=a/b` ở /stats mỗi "
                         "chu kỳ. Rò rỉ = `a` KHÔNG về 0 sau khi đóng hết (hệ chết dần trong soak 24/7).")
    ap.add_argument("--churn-conns", type=int, default=4, help="số kết nối dài mở trong mỗi chu kỳ churn")
    ap.add_argument("--release-deadline-s", type=float, default=5.0,
                    help="chờ TỐI ĐA bao lâu để slot được trả sau khi đóng kết nối (chờ-theo-sự-kiện, không sleep "
                         "cố định). Quá hạn mà chưa về mốc đầu → mới kết luận RÒ RỈ (chống báo động giả #462).")
    ap.add_argument("--hold-seconds", type=float, default=0.0,
                    help="CHẾ ĐỘ GIỮ: mở `--hold-conns` kết nối dài rồi NGỦ, để bên ngoài KILL process này "
                         "(mô phỏng viewer tắt máy/rút mạng) → sau đó đọc `/stats` xem slot có được trả.")
    ap.add_argument("--hold-conns", type=int, default=4, help="số kết nối dài giữ trong chế độ --hold-seconds")
    args = ap.parse_args()

    if args.churn > 0:
        return _run_churn(args)
    if args.hold_seconds > 0:
        return _run_hold(args)

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
