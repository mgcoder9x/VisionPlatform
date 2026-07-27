# Deploy web app an toàn qua TLS reverse-proxy (production)

> Spec `web-production-hardening` Wave 3. Áp dụng SAU khi đã bật Wave 1 (WSGI waitress) + Wave 2 (Basic Auth).
>
> ## ⚠️ TRẠNG THÁI KIỂM CHỨNG của tài liệu này (cập nhật 2026-07-27, LOG #461 — đọc trước khi tin)
>
> Tài liệu KHÔNG được coi là "đã chạy được". Phân loại tường minh để nó không trở thành nguồn drift:
>
> | Phần | Trạng thái |
> |---|---|
> | Hành vi **app** (waitress không buffer stream · SSE flush 3.7ms/gap 50ms · auth phủ `/events` 401→200 · bulkhead 503 + reserve · `streams=a/b` · release slot) | ✅ **ĐÃ ĐO THẬT** (#427, #454, #456-#459) — có số trong LOG |
> | Hành vi **nginx** (`proxy_buffering` mặc định on · tắt được bằng header `X-Accel-Buffering` · `proxy_read_timeout` 60s · `proxy_ignore_client_abort` off · nginx ẩn header `X-Accel-*`) | 📗 **Dựa tài liệu nginx CHÍNH CHỦ đã đọc** (`ngx_http_proxy_module`) — chưa chạy nginx thật trong repo này |
> | **Toàn chuỗi qua proxy thật** (nginx/Caddy → waitress: SSE live, MJPEG live, trần bulkhead khi proxy giữ kết nối, TLS/HSTS, Basic Auth qua proxy) | 🔴 **[chưa kiểm]** — cần dựng nginx/Caddy (vd Docker) rồi đo lại bằng `tools/web_sse_capacity_probe.py` + Playwright |
> | Path-prefix (`location /camera1/`) | 🔴 **KHÔNG hỗ trợ** (xem cảnh báo §2d) |
>
> Khi ai đó dựng được proxy thật: đo theo §2c/§2d rồi **cập nhật bảng này** + ghi LOG entry mới.

## Vì sao cần reverse-proxy cho TLS (không nhúng TLS vào app)

- **Basic Auth gửi credential dạng base64 KHÔNG mã hoá** → nếu chạy HTTP trần, ai bắt gói trong mạng đọc được
  user/pass + xem được feed camera. **Basic Auth chỉ an toàn khi có TLS (HTTPS).**
- **waitress KHÔNG tự làm TLS** (theo tài liệu waitress — nó là WSGI server thuần, khuyến nghị đặt sau reverse-proxy
  cho TLS). Đây là kiến trúc chuẩn: proxy (nginx/caddy) **kết thúc TLS** rồi chuyển tiếp HTTP nội bộ tới waitress.
- Tách TLS ra proxy = single-responsibility: app lo logic + auth, proxy lo TLS + chứng chỉ + HSTS. Đổi chứng chỉ
  không phải sửa/deploy lại app.

## Kiến trúc deploy

```
Internet/LAN ──HTTPS(443, TLS)──►  reverse-proxy (nginx/caddy)  ──HTTP(loopback)──►  waitress :8000
                                    • kết thúc TLS (cert)              (app bind 127.0.0.1 — KHÔNG phơi trực tiếp)
                                    • thêm HSTS
                                    • (tuỳ) rate-limit /  brute-force Basic Auth
```

- **App bind loopback** (`--host 127.0.0.1`) → chỉ proxy trên cùng máy gọi được; KHÔNG mở cổng app ra ngoài.
- Chạy app: `--server waitress` + đặt `VP_WEB_USER`/`VP_WEB_PASS` (Basic Auth vẫn bật — phòng thủ theo lớp; proxy
  chuyển tiếp header `Authorization` xuống app).

## 1) Chạy app (behind proxy)

```bash
export VP_WEB_USER=admin
export VP_WEB_PASS='<mật-khẩu-mạnh>'
python -m vision_platform.profiles.vision_web_app \
  --server waitress --host 127.0.0.1 --port 8000 \
  --threads 22 \
  --rtsp 'rtsp://user:pass@camera-ip:554/stream'   # hoặc --video/--camera
```

> **`--threads` KHÔNG được để mặc định khi deploy thật.** Mặc định `8` chỉ phục vụ **~3 viewer** đồng thời (mỗi
> viewer giữ 2 kết nối dài `/stream` + `/events`). Công thức: **`--threads >= 2N + 2`** cho N viewer (ví dụ trên:
> 22 → 10 viewer). Chi tiết + cách quan sát bão hoà: **§2d**.

## 2a) Caddy (khuyến nghị — TLS tự động, cấu hình ngắn nhất)

`Caddyfile`:
```
vision.example.com {
    reverse_proxy 127.0.0.1:8000
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }
}
```
- Caddy tự xin + gia hạn chứng chỉ Let's Encrypt (cần domain trỏ về máy + mở 80/443).
- MJPEG stream (`multipart/x-mixed-replace`) chạy qua `reverse_proxy` của Caddy không buffer mặc định → video LIVE.

## 2b) nginx (nếu đã có hạ tầng nginx)

```nginx
server {
    listen 443 ssl;
    server_name vision.example.com;

    ssl_certificate     /etc/letsencrypt/live/vision.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vision.example.com/privkey.pem;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        # QUAN TRỌNG cho MJPEG stream LIVE (không đứng hình):
        proxy_buffering off;          # không gom buffer response (stream đẩy thẳng)
        proxy_read_timeout 3600s;     # stream dài, không timeout giữa chừng
        proxy_http_version 1.1;
    }
}
# (tuỳ) chuyển hướng 80 → 443
server { listen 80; server_name vision.example.com; return 301 https://$host$request_uri; }
```

> **Lưu ý MJPEG + nginx:** PHẢI đặt `proxy_buffering off` — nếu bật (mặc định), nginx gom buffer làm video
> `/stream` bị trễ/đứng. (waitress đã được verify không buffer stream — #427; nginx là mắt xích cần chỉnh riêng.)

## 2c) HAI kênh streaming (không chỉ MJPEG!) — bổ sung sau spec `overlay-sse-transport` (#454-#459)

> Mục này thêm vì bản đầu của tài liệu viết ở #428 — **trước khi có SSE**. Ai deploy theo bản cũ mà chỉ nghĩ tới
> MJPEG sẽ thấy **overlay (box) không cập nhật** mà không hiểu vì sao.

App có **2 kết nối DÀI** cho mỗi viewer:

| Endpoint | Content-Type | Vai trò |
|---|---|---|
| `/stream` | `multipart/x-mixed-replace` | video MJPEG |
| `/events` | `text/event-stream` (SSE) | **overlay push** — thay vòng poll `/overlay` (fix console-flood K-119) |

**Cả hai đều cần no-buffering + timeout dài.** Cấu hình nginx ở §2b (`proxy_buffering off` · `proxy_read_timeout 3600s`
· `proxy_http_version 1.1`) đặt trong `location /` nên phủ cả `/events` — **không cần block riêng**; nhưng nếu bạn
tách `location` theo endpoint thì PHẢI lặp lại 3 directive đó cho `/events`.

### Vì sao (dữ kiện lấy từ tài liệu nginx chính chủ — `ngx_http_proxy_module`)

- `proxy_buffering` **mặc định `on`**: nginx gom response vào buffer (tràn thì ghi file tạm) → stream bị trễ. Khi
  tắt, response được đẩy tới client **ngay khi nhận được**.
- **Phòng thủ lớp 2 (app đã làm sẵn):** nginx cho phép bật/tắt buffering bằng **header response `X-Accel-Buffering`**
  (`no` = tắt). App **tự đặt `X-Accel-Buffering: no`** trên `/events` ⇒ **kể cả khi operator QUÊN `proxy_buffering off`,
  SSE vẫn không bị gom buffer**. nginx cũng **không chuyển tiếp** header `X-Accel-...` xuống client (mặc định của
  `proxy_hide_header`) nên đây là chuyện nội bộ app↔proxy. *(Muốn nginx bỏ qua header này thì phải cố ý khai
  `proxy_ignore_headers X-Accel-Buffering` — ĐỪNG làm.)*
- `proxy_read_timeout` **mặc định `60s`**, tính **giữa hai lần đọc liên tiếp**: upstream không truyền gì trong khoảng
  đó → nginx **đóng kết nối**. Hệ quả cụ thể:
  - **SSE sống được với mặc định** vì app phát **heartbeat `: ping` mỗi 15s** (15s < 60s) — vẫn nên nâng
    `proxy_read_timeout` để tránh bị cắt oan khi máy tải cao.
  - **MJPEG khi NGUỒN CHẾT** (camera/RTSP mất) thì app không ghi frame nào → nginx cắt sau `proxy_read_timeout` →
    client `<img>` nhận `error` → **tự reconnect có backoff** (500ms→cap 5s, #436). Hành vi ĐÚNG, không phải lỗi.

### ⚠️ Cấu hình làm RÒ RỈ dung lượng (đừng bật)

`proxy_ignore_client_abort` **mặc định `off`** = client ngắt thì nginx **đóng luôn kết nối tới upstream** → app chạy
`finally` → **trả slot bulkhead** (§2d). Nếu bật `proxy_ignore_client_abort on`, nginx **giữ** kết nối upstream dù
viewer đã rời ⇒ slot bị giữ tới khi waitress tự dọn (`channel_timeout` **120s**, quét mỗi `cleanup_interval` **30s**)
⇒ **mất dung lượng viewer ~2 phút mỗi lần ai đó đóng tab**. → **GIỮ mặc định `off`.**

## 2d) SIZING bắt buộc: mỗi viewer chiếm 2 thread WSGI (đo được, #456)

waitress là WSGI **sync**: **1 thread / 1 kết nối**, và `/stream` + `/events` **không bao giờ kết thúc** ⇒

```
trần kết nối streaming = --threads  −  --stream-reserve-threads   (mặc định reserve 2, chừa cho /stats,/overlay,/)
số viewer ≈ trần / 2                ⇒   muốn N viewer:  --threads >= 2N + 2
```

- Số ĐO THẬT (#456): `--threads 8` **không có** bulkhead → mở 8 kết nối dài là **mọi request ngắn treo vô hạn**
  (`/stats` timeout, trang mới không vào được). **Có** bulkhead → trần 6, kết nối thứ 7 trở đi nhận **`503 + Retry-After`
  ngay**, `/stats` vẫn trả trong 0–16ms.
- Client tự **suy giảm**: SSE bị 503 → rơi về poll `/overlay` (overlay vẫn cập nhật, chỉ tốn request hơn).
- **Quan sát bão hoà:** `GET /stats` in `streams=<đang dùng>/<trần>` (#458). `đang dùng` không về 0 khi không còn
  viewer = dấu hiệu rò rỉ cần điều tra (đã đo 240 chu kỳ connect/disconnect: luôn về 0).
- Ví dụ: cần **10 viewer** đồng thời → `--threads 22` (=2×10+2), hoặc đặt tường minh `--max-stream-conns 20`.

> **Cảnh báo path-prefix:** client dựng mọi URL từ `location.origin` (D-153 — chống bẫy URL-có-credential K-124).
> Vì vậy app hiện **chỉ chạy đúng khi được proxy ở gốc `/`** của một host/subdomain. **KHÔNG** đặt sau prefix kiểu
> `location /camera1/ { proxy_pass ... }` — client sẽ gọi thiếu `/camera1`. Nhiều camera → dùng **subdomain riêng**
> (`cam1.example.com`) cho mỗi app. *(Hỗ trợ path-prefix là việc CHƯA làm.)*

## 3) Checklist an toàn production (bản chất, không hình thức)

- [ ] App bind `127.0.0.1` (không phơi cổng app ra ngoài — chỉ proxy vào).
- [ ] `VP_WEB_USER`/`VP_WEB_PASS` đặt qua **secret manager / biến môi trường**, KHÔNG hard-code / commit.
- [ ] Mật khẩu mạnh (Basic Auth không có khoá-tài-khoản mặc định — cân nhắc rate-limit ở proxy chống brute-force).
- [ ] TLS bật (Caddy tự / nginx + Let's Encrypt) + HSTS header.
- [ ] Security headers `X-Frame-Options: DENY` / `X-Content-Type-Options: nosniff` / `Referrer-Policy` — **app đã
      tự thêm** (SecurityHeadersMiddleware, Wave 3) → proxy chuyển tiếp; không cần cấu hình lại.
- [ ] RTSP URL chứa credential camera → coi là secret (không log; app đã `mask_rtsp` khi in).
- [ ] Giám sát: (tuỳ) bật `--metrics-port` sau proxy nội bộ để Prometheus scrape.
- [ ] **`--threads >= 2N + 2`** cho N viewer đồng thời (mặc định 8 = ~3 viewer). Xem §2d.
- [ ] **`proxy_buffering off` + `proxy_read_timeout` dài** áp cho CẢ `/stream` (MJPEG) **và `/events` (SSE)** — §2c.
- [ ] **KHÔNG bật `proxy_ignore_client_abort`** (giữ mặc định `off`) — nếu bật, slot streaming bị giữ ~2 phút sau
      khi viewer đóng tab → mất dung lượng. Cũng KHÔNG khai `proxy_ignore_headers X-Accel-Buffering`.
- [ ] App phải được proxy ở **gốc `/`** của host/subdomain — **không** dùng path-prefix (`/camera1/`). Nhiều camera
      → subdomain riêng cho mỗi app. Xem cảnh báo §2d.
- [ ] Sau khi deploy: `GET /stats` xem `streams=<đang dùng>/<trần>` để biết mức bão hoà (và phát hiện rò rỉ slot).

## Ngoài phạm vi (chưa làm — cân nhắc theo nhu cầu thương mại)

- Rate-limiting / khoá brute-force Basic Auth (nên cấu hình ở proxy: nginx `limit_req`).
- Đăng nhập nhiều-người / RBAC / OIDC (Basic Auth 1 credential dùng chung — đủ cho nội bộ, không cho multi-tenant).
- WebRTC/WebSocket thay MJPEG (giảm băng thông + độ trễ — spec riêng nếu cần).
