# Design Document — web-production-hardening (WSGI production + access-control cho web app, hướng thương mại)

## Overview

Web app hiện phục vụ bằng **werkzeug development server** (`app.run(..., threaded=True)`) và **KHÔNG có
kiểm soát truy cập** trên mọi endpoint (kể cả `/stream` = MJPEG camera trực tiếp). Đây là 2 lỗ **bản chất**
chặn deploy thương mại 24/7:

- **(P1 — robustness)** werkzeug dev-server tự cảnh báo "không dùng cho production" — không được thiết kế cho
  tải liên tục/nhiều viewer/slow-client. Cần một **WSGI server production-grade** phục vụ chính app Flask đó.
- **(P2 — an toàn)** mọi endpoint mở → bất kỳ ai tới được `host:port` đều xem được camera + thống kê. Cần
  **access-control** (xác thực) + **secure-by-default binding** (không vô tình phơi ra mạng).

**Nguyên tắc gốc (fix TẬN GỐC, không vá ngọn):** KHÔNG viết lại app; KHÔNG đổi hành vi endpoint. Chỉ (a) thay
LỚP-PHỤC-VỤ (serving layer) ở composition root, (b) bọc app bằng LỚP-XÁC-THỰC (WSGI middleware) — cả hai đều là
mối lo của `profiles`/`adapters`, KHÔNG rò vào domain/kernel/runtime. Bảo toàn toàn bộ overlay đã verify (#415–423).

## Bằng chứng code đã đọc (chống bịa — verify TỒN TẠI trước khi thiết kế)

- `profiles/vision_web_app.py:488` → `app.run(host=args.host, port=args.port, threaded=True)` — **werkzeug dev server**.
- `profiles/vision_web_app.py` routes (grep `@app.route`): `/` (index), `/favicon.ico`, `/stream` (MJPEG),
  `/overlay`, `/boxes`, `/stats` — **KHÔNG endpoint nào có** `Authorization`/`token`/`Bearer`/`check_auth`/`login`
  (grep rỗng) → hiện **0 access-control**.
- `vision-platform/pyproject.toml:25` → `web = ["flask>=3.0"]` — **CHỈ flask**; `waitress`/`gunicorn` CHƯA khai báo.
- Máy hiện tại (`toann`): **Windows, KHÔNG Docker** (memory-bank/activeContext + AGENTS system_information: OS Windows).
- Tiền lệ secure-by-default TRONG REPO: `metrics-http-endpoint` (#289/#290) — bind `127.0.0.1` mặc định, `0.0.0.0`
  = opt-in + LOG cảnh báo không-auth. Tái dùng đúng khuôn này cho web app.
- Kiến trúc 6 layer (AGENTS §4): `profiles` = composition root (phụ thuộc mọi thứ); `adapters` = leaf (phụ thuộc
  kernel). Serving + auth-middleware KHÔNG được đặt ở domain/kernel/runtime.

## Nguồn chuẩn (kiến thức — ghi rõ độ chắc chắn, xác nhận lại lúc code)

- **werkzeug dev-server KHÔNG cho production:** khi chạy `app.run()`, werkzeug in
  "WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server
  instead." — **độ chắc chắn CAO** (hành vi mặc định werkzeug, sẽ xác nhận bằng log khi chạy).
- **waitress** = WSGI server thuần-Python, **chạy đa nền tảng gồm Windows**; API `waitress.serve(app, host=, port=,
  threads=N)` (blocking) — **độ chắc chắn CAO** (waitress docs). Đây là lý do chọn waitress (xem §Lựa chọn).
- **gunicorn** = WSGI server chỉ chạy trên **Unix** (dựa `fork`/module Unix) → **KHÔNG chạy trên Windows** máy này —
  **độ chắc chắn CAO**. ⇒ loại gunicorn cho môi trường hiện tại.
- **waitress KHÔNG tự làm TLS/HTTPS**; khuyến nghị TLS qua reverse-proxy (nginx/caddy) phía trước — **độ chắc chắn
  CAO** (waitress docs). ⇒ TLS = ngoài phạm vi lõi, chỉ tài liệu hoá (xem Non-Goals + Wave 3).
- **HTTP Basic Auth + MJPEG trong `<img>`:** trình duyệt tự đính kèm credential đã lưu cho subresource cùng-origin
  (gồm `<img src=/stream>`) sau khi có credential → Basic Auth phủ được cả stream — **độ chắc chắn VỪA**, **BẮT BUỘC
  verify bằng browser MCP lúc triển khai** (fetch `/overlay` cần `credentials:'same-origin'`; điểm này [chưa kiểm]
  cho tới khi đo thật — KHÔNG khẳng định suông).

## Architecture

KHÔNG thêm layer mới, KHÔNG đảo hướng phụ thuộc. Thêm 1 serving-adapter + 1 auth-middleware; wire ở `profiles`.

```
                 ┌─────────────────────────── profiles/vision_web_app.py (composition root) ───────────────────────────┐
client (browser) │                                                                                                     │
   │  GET /stream │   [Wave 1] serving:  serve_wsgi(app, host, port, threads)  ──►  waitress.serve  (production)         │
   │  GET /overlay│                       (fallback: app.run dev khi waitress vắng / --server dev)                      │
   ▼  GET /stats  │                                   │ phục vụ                                                          │
 ┌───────────┐    │   [Wave 2] auth:      app = BasicAuthMiddleware(app, realm, verify_credential)  ◄── bọc NGOÀI app    │
 │ 401 nếu   │◄───┼───────────────────────────────────┘  (WSGI middleware @adapters, leaf)                              │
 │ thiếu/sai │    │                                       verify_credential: (user,pw)->bool  (TIÊM; nguồn = env/CLI)    │
 │ Basic Auth│    │   secure-by-default: host mặc định 127.0.0.1; 0.0.0.0 ⇒ BẮT BUỘC có credential + LOG cảnh báo        │
 └───────────┘    └─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │ (app Flask + routes GIỮ NGUYÊN — không đụng /overlay,/stream…)
                                                        ▼
                            runtime OverlayStateStore / detect-loop / video-loop  (KHÔNG đổi)
```

- **Hướng phụ thuộc:** `adapters/wsgi_server.py` (serve_wsgi) + `adapters/auth_middleware.py` (BasicAuthMiddleware)
  → chỉ import stdlib + `waitress` (optional). `verify_credential` là callable TIÊM (thuần) → adapters=leaf giữ
  (không import runtime/application/profiles). `profiles` wire: dựng verify từ env/CLI, bọc app, gọi serve_wsgi.
- **Vì sao WSGI middleware (không dùng `@app.before_request` của Flask):** middleware bọc NGOÀI ⇒ phủ **mọi** phản
  hồi kể cả `/stream` (generator MJPEG dài) TRƯỚC khi vào Flask ⇒ không sót đường nào; và tách khỏi app (test riêng
  bằng WSGI env giả, không cần Flask/pipeline). (Nếu Flask before_request: vẫn chạy trong app, khó test cô lập hơn.)
- **Vì sao serve tách adapter:** để `profiles` chọn serving (dev/prod) tại composition; adapter chỉ biết "nhận app
  WSGI + host/port + threads → phục vụ". Test bằng app WSGI tí hon.

## Lựa chọn công cụ (nêu lý do CHÍNH XÁC — yêu cầu của user)

| Vấn đề | Lựa chọn | LÝ DO (đã kiểm) | Đã loại | Vì sao loại |
|---|---|---|---|---|
| WSGI server production | **waitress** | thuần-Python, **chạy Windows** (máy `toann`), API `serve()` đơn giản, threads pool | gunicorn | **Unix-only** — KHÔNG chạy Windows (fork) |
| | | | uWSGI | nặng, build C, khó trên Windows |
| Xác thực | **HTTP Basic Auth** (Wave 2) | phủ được `<img src=/stream>` MJPEG (browser tự gửi lại credential cùng-origin); zero-dep; đủ cho LAN thương mại | token query `?token=` | rò credential vào access-log/URL |
| | | | session-cookie+form | thêm state/CSRF/route login — over-engineer cho 1 viewer-app nội bộ (cân nhắc Wave 3 nếu cần multi-user) |
| Nguồn credential | **env var** `VP_WEB_USER`/`VP_WEB_PASS` (+ CLI trỏ tên biến) | KHÔNG hard-code secret trong code/log (git-safety §8); so sánh hằng-thời-gian | CLI `--password` trực tiếp | lộ trong `ps`/history/log |
| TLS/HTTPS | **reverse-proxy** (tài liệu, Wave 3) | waitress KHÔNG tự TLS (docs); nginx/caddy termination là chuẩn | tự nhúng ssl vào waitress | không phải cách khuyến nghị; dễ sai cấu hình an toàn |

## Components and Interfaces

### Wave 1 — adapters/wsgi_server.py :: serve_wsgi (serving production)
```
def serve_wsgi(app, host: str, port: int, *, threads: int = 8, server: str = "auto") -> None:
    # server="auto": dùng waitress nếu import được, else fallback dev + LOG cảnh báo.
    # server="waitress": bắt buộc waitress (thiếu → raise rõ ràng, fail-fast).
    # server="dev": ép werkzeug dev (chỉ dev/local) — giữ đường lui.
    # BLOCKING (thay chỗ app.run hiện tại). KHÔNG nuốt lỗi bind (cổng bận → raise).
```
- Chỉ import `waitress` BÊN TRONG nhánh (optional-dep; vắng vẫn chạy dev). Không import ở top-module.

### Wave 2 — adapters/auth_middleware.py :: BasicAuthMiddleware (WSGI middleware, leaf)
```
class BasicAuthMiddleware:
    def __init__(self, app, verify_credential, *, realm="VisionPlatform", exempt_paths=("/healthz",)):
        # verify_credential: (username, password) -> bool  (TIÊM; hằng-thời-gian ở nơi cấp)
    def __call__(self, environ, start_response):
        # đọc HTTP_AUTHORIZATION "Basic base64(user:pass)"; thiếu/sai → 401 + WWW-Authenticate: Basic realm=...
        #   (KHÔNG tiết lộ user tồn tại hay không); path ∈ exempt_paths → cho qua (health-check)
        #   hợp lệ → self._app(environ, start_response)
```
- Trả 401 với header `WWW-Authenticate: Basic realm="..."` để browser hiện prompt / gửi lại credential cho `<img>`.

### profiles/vision_web_app.py — wire (composition, thay dòng 488)
```
verify = make_env_verifier("VP_WEB_USER", "VP_WEB_PASS")   # None nếu chưa đặt biến
wsgi_app = app
if verify is not None:
    wsgi_app = BasicAuthMiddleware(app.wsgi_app, verify)   # bọc WSGI app của Flask
    app.wsgi_app = wsgi_app                                # để dev-fallback (app.run) cũng qua middleware
elif not _is_loopback(args.host):
    # secure-by-default: phơi mạng mà KHÔNG có credential → TỪ CHỐI start (fail-fast) hoặc bắt buộc --insecure
    raise SystemExit("Từ chối: bind non-loopback nhưng chưa đặt VP_WEB_USER/PASS (dùng --insecure để bỏ qua)")
serve_wsgi(app, args.host, args.port, threads=args.threads, server=args.server)
```
- CLI thêm: `--server {auto,waitress,dev}` (default `auto`), `--threads N` (default 8), `--insecure` (cho phép
  phơi mạng không-auth, PHẢI tường minh + LOG cảnh báo to). `--host` giữ nguyên.

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `serve_wsgi` | fn | server∈{auto,waitress,dev}; blocking; không nuốt lỗi bind | adapters | composition (thay app.run) |
| `BasicAuthMiddleware` | class WSGI | verify tiêm; 401+WWW-Authenticate; exempt health | adapters (leaf) | bọc app |
| `verify_credential` | `(str,str)->bool` | so sánh hằng-thời-gian; nguồn env | (tiêm) | middleware |
| bind host | str | default `127.0.0.1`; non-loopback ⇒ cần auth hoặc `--insecure` | profiles | serve |
| `--server/--threads/--insecure` | CLI | default auto/8/False | profiles | composition |

- KHÔNG đổi routes, OverlayStateStore, detect/video-loop, `_PAGE`. Chỉ thêm serving + middleware + CLI.

## Error Handling

| Tình huống | Xử lý | Wave |
|---|---|---|
| `server=waitress` nhưng waitress chưa cài | `serve_wsgi` raise ImportError rõ ("pip install ...[web-prod]") — fail-fast | 1 |
| `server=auto`, waitress vắng | fallback dev + LOG cảnh báo "đang dùng dev-server, KHÔNG cho production" | 1 |
| cổng đã bị dùng | lỗi bind raise (không nuốt) — thông báo cổng bận | 1 |
| thiếu/sai Basic Auth | 401 + `WWW-Authenticate: Basic` (không phân biệt user-sai/pass-sai) | 2 |
| path health-check | `exempt_paths` cho qua (để reverse-proxy/monitor kiểm sống mà không cần credential) | 2 |
| bind non-loopback + chưa đặt credential | TỪ CHỐI start (SystemExit) trừ khi `--insecure` (tường minh) | 2 |
| credential trong env rỗng/không đặt | verify=None → chỉ chạy được khi loopback; non-loopback bị chặn | 2 |

## Correctness Properties

### Property 1: serve_wsgi dùng waitress khi có, fallback dev khi vắng
`server="auto"` + waitress import được → gọi `waitress.serve` (không gọi `app.run`); waitress vắng → gọi dev + phát
cảnh báo. `server="waitress"` + vắng → raise. **Validates: Requirements 1.1**

### Property 2: middleware CHẶN khi thiếu/sai credential
WSGI env không header Authorization → 401 + `WWW-Authenticate: Basic`; sai user:pass → 401; đúng → gọi app (200).
**Validates: Requirements 2.1**

### Property 3: middleware phủ MỌI path (kể cả /stream)
Env path `/stream`,`/overlay`,`/stats`,`/` khi thiếu credential → tất cả 401 (không sót). `exempt_paths` (health)
→ qua. **Validates: Requirements 2.2**

### Property 4: secure-by-default binding
Default host == `127.0.0.1`. Bind non-loopback mà không có credential và không `--insecure` → TỪ CHỐI start.
`--insecure` → cho phép + LOG cảnh báo. **Validates: Requirements 3.1**

### Property 5: so sánh credential hằng-thời-gian + không hard-code
verify đọc từ env (không literal trong code); dùng `hmac.compare_digest` (chống timing). **Validates: Requirements 2.3**

### Property 6: layer + additive + hành vi endpoint KHÔNG đổi
adapters(serve/middleware) chỉ import stdlib + waitress(optional) + callable tiêm — import-linter kept/0 broken;
routes/overlay/stream GIỮ NGUYÊN; khi KHÔNG đặt credential + loopback → hành vi = hệt hiện tại (tương thích ngược).
**Validates: Requirements 4.1**

### Property 7: Basic Auth hoạt động với MJPEG + fetch thật (verify-browser BẮT BUỘC)
Trên browser MCP: sau khi nhập credential → `<img src=/stream>` load được (200) + `fetch('/overlay')` 200; thiếu →
401 (img không load). **Validates: Requirements 2.4** — điểm [chưa kiểm] tới khi đo browser (KHÔNG khẳng định trước).

## Testing Strategy

- **Wave 1 (P1):** `serve_wsgi` với monkeypatch: giả `waitress` module có/không (sys.modules) → assert nhánh gọi
  đúng (waitress.serve vs app.run) + cảnh báo fallback; `server="waitress"` thiếu → pytest.raises.
- **Wave 2 (P2,P3,P5):** gọi `BasicAuthMiddleware` bằng **WSGI env giả** (dict) + `start_response` bắt status →
  no-header→401 (+WWW-Authenticate), sai→401, đúng→app-called; path /stream thiếu→401; exempt health→qua;
  verify dùng compare_digest (kiểm bằng cặp đúng/sai).
- **Wave 2 (P4):** hàm `_is_loopback` + logic từ-chối: non-loopback+no-cred+no-insecure → SystemExit; --insecure→qua+warn.
- **Wave 1/2 (P6):** import-linter kept/0 broken; test tương thích ngược: no-credential + loopback → app phục vụ như cũ.
- **Wave 2 (P7) — browser MCP THẬT:** chạy server (waitress, có credential, người-thật people-detection.mp4) → nhập
  Basic Auth → verify `<img>` stream + `/overlay` 200; bỏ credential → 401. (đúng kỷ luật verify-by-browser #415–423.)
- **Không cần GPU.** Unit chạy máy dev ngay; browser MCP cho E2E.

## Waves (ưu tiên, GATED rõ)

- **Wave 1 — WSGI production serving (waitress).** Rủi ro thấp, KHÔNG đổi hành vi endpoint, giá trị deploy tức thì.
  Thêm `web-prod = [..., "waitress>=3.0"]` vào pyproject (optional-extra, không ép cài).
- **Wave 2 — access-control (Basic Auth + secure-by-default).** Đóng lỗ an toàn. Cần verify browser (P7).
- **Wave 3 — GATED (chờ user, ngoài lõi):** tài liệu TLS reverse-proxy + (tuỳ) security headers/rate-limit. KHÔNG
  code TLS vào app. Chỉ làm khi user xác nhận cần deploy qua mạng không tin cậy.

## Doubt-driven review (tự phản biện — KHẮT KHE, trước khi user valid)

- **Forces:** production-robust (WSGI) ⟂ an-toàn (auth + bind) ⟂ KHÔNG hồi quy overlay đã verify ⟂ layer sạch ⟂
  chạy Windows (máy này) ⟂ tương thích ngược (dev vẫn chạy). Cân được: adapter serving + WSGI middleware tiêm +
  secure-default + optional-dep.
- **What varies?** SERVER phục vụ (dev/waitress/…tương lai gunicorn trên Linux) → `serve_wsgi(server=)` trừu tượng.
  CƠ CHẾ auth (Basic giờ; token/OIDC sau) → `verify_credential` callable + middleware thay được. NGUỒN credential
  (env giờ; secret-manager sau) → tiêm.
- **Which way deps point?** adapters(serve/middleware) → stdlib + waitress(optional) + callable; profiles wire.
  adapters KHÔNG import runtime → leaf giữ. App Flask KHÔNG biết mình bị bọc.
- **Cái GIÁ:** +2 module nhỏ + vài CLI + 1 optional-dep (waitress). Đổi lấy: deploy production thật + đóng lỗ camera-mở.
- **An toàn (nhấn):** Basic Auth over HTTP = credential base64 (KHÔNG mã hoá) → **chỉ an toàn sau TLS**. Vì vậy
  secure-default = bind loopback; phơi mạng bắt buộc credential; và TLS (reverse-proxy) là điều kiện cho môi trường
  không tin cậy (Wave 3). KHÔNG khẳng định "đã an toàn" chỉ với Basic Auth trần.
- **Khi nào KHÔNG dùng cái này:** (a) đã có API-gateway/ingress lo auth+TLS toàn cụm → chỉ cần Wave 1 (WSGI) +
  bind loopback sau proxy; (b) multi-user/RBAC thật → cần OIDC/session (vượt Basic Auth, sub-spec riêng).
- **Recognize:** "web chạy được nhưng werkzeug cảnh báo dev-server + ai cũng xem được camera" = thiếu 2 wave này.

## Non-Goals (ranh giới rõ — chống over-engineer)

TLS/HTTPS nhúng-trong-app (dùng reverse-proxy) · session/login-form/RBAC/multi-user · rate-limiting/WAF ·
đổi hành vi bất kỳ endpoint hiện có (overlay/stream/stats) · gunicorn/uWSGI (Unix, không phù hợp máy Windows này) ·
đổi kiến trúc overlay/tracking (đã verify #415–423) · secret-manager (env là đủ cho giai đoạn này).

## CHỜ USER VALID (4 câu — rồi mới requirements → tasks → code TDD)

1. **WSGI server = waitress** (vì máy `toann` là Windows, gunicorn Unix-only không chạy) — đồng ý? Hay bạn deploy
   lên Linux/Docker riêng và muốn để ngỏ gunicorn?
2. **Xác thực = HTTP Basic Auth + credential từ env var** (phủ được MJPEG `<img>`, zero-dep) — đủ cho nhu cầu
   thương mại của bạn chưa, hay cần login-form/multi-user (sẽ thành sub-spec lớn hơn)?
3. **Secure-by-default = bind 127.0.0.1; phơi 0.0.0.0 bắt buộc có credential** (trừ khi `--insecure` tường minh) —
   đồng ý mức chặt này?
4. **TLS để Wave 3 (tài liệu reverse-proxy, không nhúng vào app)** — chấp nhận, hay bạn cần HTTPS ngay trong lõi?

→ Ưu tiên đề xuất: **Wave 1 trước** (WSGI, rủi ro thấp, deploy được ngay) → **Wave 2** (auth) → Wave 3 GATED.
