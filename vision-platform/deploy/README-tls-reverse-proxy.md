# Deploy web app an toàn qua TLS reverse-proxy (production)

> Spec `web-production-hardening` Wave 3. Áp dụng SAU khi đã bật Wave 1 (WSGI waitress) + Wave 2 (Basic Auth).

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
  --rtsp 'rtsp://user:pass@camera-ip:554/stream'   # hoặc --video/--camera
```

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

## 3) Checklist an toàn production (bản chất, không hình thức)

- [ ] App bind `127.0.0.1` (không phơi cổng app ra ngoài — chỉ proxy vào).
- [ ] `VP_WEB_USER`/`VP_WEB_PASS` đặt qua **secret manager / biến môi trường**, KHÔNG hard-code / commit.
- [ ] Mật khẩu mạnh (Basic Auth không có khoá-tài-khoản mặc định — cân nhắc rate-limit ở proxy chống brute-force).
- [ ] TLS bật (Caddy tự / nginx + Let's Encrypt) + HSTS header.
- [ ] Security headers `X-Frame-Options: DENY` / `X-Content-Type-Options: nosniff` / `Referrer-Policy` — **app đã
      tự thêm** (SecurityHeadersMiddleware, Wave 3) → proxy chuyển tiếp; không cần cấu hình lại.
- [ ] RTSP URL chứa credential camera → coi là secret (không log; app đã `mask_rtsp` khi in).
- [ ] Giám sát: (tuỳ) bật `--metrics-port` sau proxy nội bộ để Prometheus scrape.

## Ngoài phạm vi (chưa làm — cân nhắc theo nhu cầu thương mại)

- Rate-limiting / khoá brute-force Basic Auth (nên cấu hình ở proxy: nginx `limit_req`).
- Đăng nhập nhiều-người / RBAC / OIDC (Basic Auth 1 credential dùng chung — đủ cho nội bộ, không cho multi-tenant).
- WebRTC/WebSocket thay MJPEG (giảm băng thông + độ trễ — spec riêng nếu cần).
