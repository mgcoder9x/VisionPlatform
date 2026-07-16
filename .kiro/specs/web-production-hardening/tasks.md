# Implementation Plan: web-production-hardening

## Overview

Design-first đã valid (user duyệt 4 câu #424). TDD: RED → GREEN → verify. Additive, không đổi hành vi endpoint.
Ánh xạ Properties P1–P7 (design.md) ↔ Requirements R1–R4. Wave 1 (WSGI) rủi ro thấp làm trước; Wave 2 (auth) sau;
Wave 3 (TLS) GATED chờ user.

## Tasks

### Wave 1 — WSGI production serving (waitress) [ưu tiên, rủi ro thấp]

- [x] 1.1 `pyproject.toml`: thêm optional-extra `web-prod = ["waitress>=3.0"]` (không đụng base). Cài vào venv. _(R4.3)_ — DONE #425 (waitress 3.x cài venv).
- [x] 1.2 `adapters/wsgi_server.py::serve_wsgi(app, host, port, *, threads=8, server="auto")` — TDD: _(R1.1, R1.2, R1.3, P1)_ — DONE #425 (6 test GREEN).
  - `server="waitress"` → gọi `waitress.serve(app, host=, port=, threads=)`; thiếu waitress → raise ImportError rõ.
  - `server="auto"` → waitress nếu import được, else werkzeug `app.run` + cảnh báo (log).
  - `server="dev"` → ép `app.run` (đường lui local).
  - import `waitress` BÊN TRONG nhánh (optional-dep, không top-import).
  - Test: monkeypatch sys.modules waitress present/absent → assert nhánh gọi đúng (spy) + raise + cảnh báo.
- [x] 1.3 `profiles/vision_web_app.py`: thêm CLI `--server {auto,waitress,dev}` (default auto) + `--threads` (default 8);
  thay `app.run(host, port, threaded=True)` bằng `serve_wsgi(app, args.host, args.port, threads=args.threads, server=args.server)`. _(R1.1)_ — DONE #425.
- [x] 1.4 Verify: `vp verify` (unit GREEN + import-linter kept/0 broken + baseline giữ) + chạy thật `--server waitress`
  → GET `/stats` 200 + log KHÔNG còn cảnh báo werkzeug-dev. _(R1.1, R4.1, R4.2)_ — DONE #425: **843/2** (+6)·lint 6/0·drift PASS; `/stats` 200 + header `Server: waitress` (bằng chứng empiric waitress phục vụ, không rơi dev).
- [x] 1.5 Ghi sổ (LOG + D + INDEX + activeContext) + `vp check` PASS. — DONE #425.

### Wave 2 — Access-control (Basic Auth + secure-default) [sau Wave 1]

- [x] 2.1 `adapters/auth_middleware.py::BasicAuthMiddleware(app, verify_credential, *, realm, exempt_paths)` — TDD:
  thiếu/sai `Authorization` → 401 + `WWW-Authenticate: Basic realm=...`; đúng → gọi app; phủ mọi path; exempt health. _(R2.1, R2.2, P2, P3)_ — DONE #426 (14 test GREEN).
- [x] 2.2 `make_env_verifier(user_var, pass_var)` — đọc env, `hmac.compare_digest`, không hard-code. _(R2.3, P5)_ — DONE #426.
- [x] 2.3 `profiles`: wire `app.wsgi_app = BasicAuthMiddleware(...)` khi có credential; secure-default non-loopback +
  no-cred + no-`--insecure` → SystemExit; `--insecure` → cho phép + cảnh báo. CLI `--insecure`. _(R3.1, R3.2, R3.3, P4)_ — DONE #426 (verify empiric `--host 0.0.0.0` no-cred → EXIT=1 TỪ CHỐI).
- [x] 2.4 Verify unit (P2–P5) + import-linter + baseline. _(R4.2)_ — DONE #426: 857/2·lint 6/0·drift PASS.
- [x] 2.5 **Verify browser MCP (BẮT BUỘC):** server waitress + credential + video người-thật → nhập Basic Auth →
  `<img>` stream + `/overlay` 200; bỏ credential → 401. _(R2.4, P7)_ — DONE #426: unauth `/overlay` 401+WWW-Authenticate; auth → img naturalWidth=768 + `/overlay`/`/stats` 200 + 0 console error. P7 đóng.
- [x] 2.6 Ghi sổ + `vp check` PASS. — DONE #426.

### Wave 3 — hardening cuối (security headers code + TLS deploy doc)

- [x] 3.1 `adapters/security_headers.py::SecurityHeadersMiddleware` (WSGI leaf, bọc NGOÀI CÙNG) — thêm
  `X-Content-Type-Options: nosniff` + `X-Frame-Options: DENY` (chống clickjacking feed camera) + `Referrer-Policy:
  no-referrer`; không đè header app đã đặt; phủ cả response 401. Wire profiles (outermost). _(R3, an toàn)_ — DONE #428 (3 test + browser header verify).
- [x] 3.2 `deploy/README-tls-reverse-proxy.md` — TLS qua reverse-proxy (Caddy tự-cert / nginx + `proxy_buffering off`
  cho MJPEG LIVE) + app bind loopback + HSTS + checklist an toàn. KHÔNG nhúng TLS vào app (waitress không tự TLS). _(R3)_ — DONE #428.
- [ ] 3.3 (GATED, ngoài phạm vi) rate-limit/brute-force Basic Auth (proxy `limit_req`) + WebRTC thay MJPEG — spec riêng nếu cần.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"], "depends_on": [] },
    { "wave": 2, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"], "depends_on": ["1.5"] },
    { "wave": 3, "tasks": ["3.1"], "depends_on": ["2.6"] }
  ]
}
```

Ghi chú: Wave 1 (WSGI) tuần tự nội bộ (1.1→1.2→1.3→1.4→1.5), rủi ro thấp, giá trị deploy ngay. Wave 2 (auth) phụ
thuộc Wave 1 xong. Wave 3 (TLS reverse-proxy doc) GATED — chỉ làm khi user xác nhận deploy qua mạng không tin cậy.

## Notes

- Wave 1 additive: khi không đặt credential + loopback → hành vi = hệ hiện tại (R4.1).
- Basic Auth trần chỉ an toàn SAU TLS → secure-default bind loopback là lớp giảm-thiểu; TLS = Wave 3 (reverse-proxy).
- P7 (Basic Auth + MJPEG/fetch) là [chưa kiểm] tới khi verify browser MCP ở task 2.5 — không khẳng định trước.
- waitress chọn vì máy Windows (gunicorn Unix-only); để ngỏ `--server` cho gunicorn nếu sau deploy Linux.
