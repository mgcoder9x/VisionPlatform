# Requirements Document

## Introduction

Web app (`profiles/vision_web_app.py`) đang phục vụ bằng werkzeug **development server** (`app.run`) và **không có
kiểm soát truy cập** trên mọi endpoint (kể cả `/stream` MJPEG camera). Spec này đưa web app đạt mức deploy thương
mại: (1) phục vụ bằng **WSGI production server** (waitress), (2) **xác thực truy cập** + **secure-by-default
binding**, mà KHÔNG đổi hành vi endpoint hiện có (bảo toàn overlay đã verify #415–423). Ánh xạ Correctness
Properties P1–P7 trong `design.md`.

## Glossary

- **WSGI**: giao diện chuẩn giữa web server và app Python (PEP 3333).
- **werkzeug dev-server**: server tích hợp của Flask khi gọi `app.run()`; Flask tự cảnh báo không dùng production.
- **waitress**: WSGI server thuần-Python, production-grade, chạy đa nền tảng gồm Windows.
- **Basic Auth**: xác thực HTTP gửi `Authorization: Basic base64(user:pass)`.
- **loopback**: địa chỉ chỉ máy cục bộ (`127.0.0.1`, `::1`, `localhost`).

## Requirements

### Requirement 1: Phục vụ bằng WSGI production server

**User Story:** Là người vận hành, tôi muốn web app phục vụ bằng WSGI server production, để deploy 24/7 chịu tải
mà không dính cảnh báo/giới hạn của dev-server.

#### Acceptance Criteria

1. WHEN web app khởi động ở chế độ production, THE system SHALL phục vụ qua **waitress** (KHÔNG gọi werkzeug
   `app.run`).
2. IF `server="waitress"` mà waitress chưa cài, THEN THE system SHALL báo lỗi rõ ràng (fail-fast) chỉ dẫn cách cài.
3. WHEN `server="auto"` và waitress không import được, THE system SHALL fallback werkzeug dev-server VÀ phát cảnh
   báo "đang dùng dev-server, không cho production".
4. IF cổng bind đã bị dùng, THEN THE system SHALL báo lỗi bind (không nuốt lỗi).

### Requirement 2: Kiểm soát truy cập mọi endpoint

**User Story:** Là chủ hệ thống camera, tôi muốn mọi endpoint (đặc biệt `/stream`) yêu cầu xác thực, để người lạ
trong mạng không xem được camera.

#### Acceptance Criteria

1. IF một request thiếu hoặc sai credential, THEN THE system SHALL trả `401` kèm header `WWW-Authenticate: Basic`
   (không tiết lộ user tồn tại hay không).
2. THE system SHALL áp xác thực cho **mọi** route (`/`, `/stream`, `/overlay`, `/boxes`, `/stats`); path health-check
   (`/healthz`) được miễn.
3. THE system SHALL so sánh credential **hằng-thời-gian** (`hmac.compare_digest`) VÀ đọc credential từ **biến môi
   trường** (`VP_WEB_USER`/`VP_WEB_PASS`) — KHÔNG hard-code trong code/log.
4. WHEN client đã xác thực trên trình duyệt, THE system SHALL cho `<img src=/stream>` (MJPEG) load được VÀ
   `fetch('/overlay')` trả 200; khi chưa xác thực SHALL bị chặn (verify browser MCP — Property 7).

### Requirement 3: Secure-by-default binding

**User Story:** Là người vận hành, tôi muốn mặc định an toàn, để không vô tình phơi web ra mạng mà không xác thực.

#### Acceptance Criteria

1. THE system SHALL bind `127.0.0.1` mặc định.
2. IF bind địa chỉ non-loopback mà chưa đặt credential và không có cờ `--insecure`, THEN THE system SHALL TỪ CHỐI
   khởi động (fail-fast).
3. WHEN chạy với `--insecure`, THE system SHALL cho phép phơi mạng không-auth VÀ phát cảnh báo to.

### Requirement 4: Không hồi quy + layer sạch

**User Story:** Là kỹ sư, tôi muốn thay đổi này không phá hành vi hiện có và không vi phạm kiến trúc.

#### Acceptance Criteria

1. THE system SHALL KHÔNG đổi hành vi bất kỳ endpoint hiện có; WHEN không đặt credential VÀ bind loopback, hành vi
   SHALL bằng hệ hiện tại (tương thích ngược).
2. THE serving-adapter VÀ auth-middleware SHALL đặt ở `adapters` (leaf) + wire ở `profiles`; import-linter kept/0
   broken (không import runtime/application/profiles từ adapters).
3. Dependency waitress SHALL là **optional-extra** (`web-prod`), không ép cài với bản base.
