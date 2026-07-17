# end.md — HANDOFF chuyển máy (VisionPlatform) · frontier LOG #432 / Σ313

> ⚠️ CẢNH BÁO BẢN CHẤT (K-064/K-098): FILE NÀY LÀ HANDOFF, **KHÔNG phải nguồn trạng thái**.
> Trạng thái THẬT chỉ xác định qua `scripts\vp.cmd check` + `git status` + `git log`. Nếu end.md
> nói khác `vp check` → TIN `vp check`. (File này từng bị dán transcript máy khác về dự án FUXA — đã dọn.)
>
> ⚠️ BÀI HỌC PHIÊN NÀY (K-098 tái diễn): frontier NHẢY #422→#432 GIỮA phiên (máy `toann` đẩy tiếp +
> workspace này auto-sync lên HEAD mới) → mọi giả định "tiếp nối #422" thành SAI. LUÔN chạy §0 lại khi
> nghi ngờ; đừng append lên bản ghi cũ (gây dup entry). Đã xảy ra append dup #423 → đã revert sạch.

---

## 0. ĐẦU PHIÊN — BẮT BUỘC (chống drift, làm TRỌN trước khi động gì)
1. `git status` + `git log -n 3 --oneline` → HEAD, nhánh, thay đổi chưa commit.
2. `scripts\vp.cmd check` → **cổng khách quan**, PHẢI `DRIFT-CHECK: PASS`. Đọc: `C1-LOG max #N`
   (frontier THẬT), `C4 total (D..K..=ΣM)`, `C9-GIT` (behind/ahead so origin).
3. Đọc `memory-bank/activeContext.md` (block TRÊN CÙNG) + tail `AI-IMPLEMENTATION-LOG.md` (#428→#432)
   + `ai-decision-journal/00-INDEX.md` (header + bảng D/K cuối).
4. Thay đổi chưa commit / `vp check` FAIL → DỪNG, đồng bộ trước.

**Chốt tại handoff:** frontier = **LOG #432 · Σ313 (D137·C23·T35·K118)** · drift PASS · HEAD=origin=`20934c7`
· nhánh `chore/dev-env-launcher-portable-hooks`. **Baseline test = 860 passed / 2 skipped · lint 6 kept/0 broken.**

**Máy hiện tại `k.nguyen.manh.toan`:** CÓ Docker · CÓ webcam · KHÔNG GPU. Máy `toann`: CÓ GPU · CÓ RTSP ·
KHÔNG Docker. **Đa máy đẩy chéo nhánh này** — LUÔN làm ở frontier thật (đừng theo memory máy khác).

---

## 1. CHỈ THỊ THƯỜNG TRỰC CỦA USER (áp mỗi lượt)
- Trả lời **tiếng Việt**, dòng đầu `→ Chế độ: <X>`.
- Cadence: thiết kế rõ → đọc-lại-VALID nhiều lần → chính xác kiểm-chứng-được → MỚI triển khai.
- **Fix bản chất, KHÔNG vá ngọn.** Đọc code xem cơ-chế-sẵn-có TRƯỚC khi đẻ config/lever mới (R3.2).
- **KHÔNG bịa / KHÔNG suy đoán.** Chưa kiểm → nhãn `[chưa kiểm]`/`[suy đoán]`. Code = CHẠY thật + đọc
  output mới "xong". Kết bằng "Đã verify / Chưa verify". (Bài học #429→#430: suy đoán phải sửa lại khi đọc code.)
- **KHÔNG tiết kiệm token.** Hướng sản phẩm thương mại. Khuyến nghị PHẢI nêu lý do chính xác.
- Ghi sổ MỌI triển khai: LOG + journal + INDEX (bump logref/total + stamp) + activeContext → `vp check` PASS.
- Không `git add -A`; không force/reset; push chỉ khi user yêu cầu rõ.

---

## 2. ĐÃ XONG (verify) — nền thương mại đã VỮNG
### 2a. overlay-tracking-refactor (fix bbox web) — #415→#422, ĐÓNG
Spec `.kiro/specs/overlay-tracking-refactor/`. 6 bug fix + verify browser MCP webcam THẬT:
- #415 (D-127) pile-up 193 lỗi → poll self-rescheduling ⊥ render rAF.
- #416 (D-128) S1 box-không-sát → server phơi vx/vy → client ngoại suy pos+vel*dt (bỏ updatedAtMs).
- #417 (D-129) S2 tắt-chậm → bỏ maxAgeMs (trùng displayLease) → CLI `--overlay-display-lease-ms`.
- #418 (D-130) lệch 1px canvas↔video → border `#v`→`#wrap`+`font-size:0`.
- #419 (D-131) video đen tab-nền → `visibilitychange`→reconnect `/stream?t=...` + `img.onerror`.
- #421 (K-114) churn "mất bbox" GỐC = spurious conf 0.25–0.33 → hysteresis `--overlay-create-conf 0.45
  --overlay-sustain-conf 0.30` (verify 5+→2 ID).
- #422 (K-115) perf: đo `intra_op_num_threads` (process-riêng median-of-3) → **default ≈ tối ưu, KHÔNG
  hard-code** (hại máy ít core). Nhanh hơn cần deploy-time (input416/INT8/GPU), KHÔNG runtime tuning.

### 2b. web-production-hardening — #425→#428, #432, XONG (đây là "(B) K-101" đã hoàn thành)
- **Wave 1 (#425, D-133):** `adapters/wsgi_server.py::serve_wsgi` = **waitress** thay werkzeug dev-server; CLI
  `--server {auto,waitress,dev} --threads 8`; extra `web-prod=["waitress>=3.0"]`.
- **Wave 2 (#426, D-134):** `adapters/auth_middleware.py::BasicAuthMiddleware` + `make_env_verifier` (env
  `VP_WEB_USER`/`VP_WEB_PASS`, constant-time compare) bọc MỌI route gồm /stream; **secure-default**:
  non-loopback + no-cred + không `--insecure` → SystemExit (từ chối bind). Verify browser P7: 401 khi chưa auth.
- **Wave 3 (#428, D-135):** `adapters/security_headers.py::SecurityHeadersMiddleware` (X-Frame-Options DENY +
  nosniff + Referrer-Policy) bọc NGOÀI CÙNG + `deploy/README-tls-reverse-proxy.md` (Caddy/nginx TLS termination).
- **#427/#432 verify:** waitress KHÔNG buffer MJPEG (stream live OK); **đa-client thread-safe** (tool
  `tools/web_concurrent_probe.py`: 12 thread×5s → 2844/2844 request 200, ~564 req/s, không crash) — shared
  state dưới `_lock` + OverlayStateStore snapshot immutable-swap.
- CÒN GATED (spec riêng nếu cần): rate-limit (ở proxy) · WebRTC · multi-user RBAC.

### 2c. Reliability
- Flaky **K-116** (test_direct_quarantine_on_killed_owner, race sau kill) ĐÓNG #430 (D-136): fix test-only
  event-driven `wait_until` (production đã đúng — quarantine self-heal retry). Chạy lặp 12/12 PASS.
- **Wave C (hợp nhất `domain/tracker`) HOÃN #431 (D-137, YAGNI grounded):** `IouTracker` chỉ ở
  `vision_slice_app` (analytics headless `--track`); `DisplayStabilizer` chỉ ở `vision_web_app` (web) →
  2 tracker 2 entry-point RIÊNG, KHÔNG cùng process → không xung đột runtime. Chỉ hợp nhất khi nghiệp vụ cần.

---

## 3. CẦN USER QUYẾT (2 đường tiến THẬT — còn lại là speculative, đừng tự làm)
- **(A) RTSP camera thật (K-117 — BLOCKED bởi VPN):** máy IP LAN 192.168.120.104 cùng /24 camera `.106`,
  route on-link ĐÚNG, NHƯNG **VPN `ProTUN` chặn TOÀN BỘ traffic LAN** (ping gateway .1 + camera .106 đều fail;
  chỉ self .104 OK). → User bật **"Allow LAN / local network access" trong app VPN** (GIỮ VPN bật) → tôi verify
  RTSP `.106` end-to-end qua stack production (waitress+auth). **RÀNG BUỘC TUYỆT ĐỐI: AI KHÔNG tắt/đổi VPN.**
- **(B) Nêu 1 NGHIỆP VỤ cụ thể** (vd "đếm người qua vạch hiện trên web view") → mở Wave C/Wave D design-first
  driven-by-nghiệp-vụ (lúc đó hợp nhất tracker mới có giá trị).

Ngoài 2 đường trên, việc còn lại chỉ là refactor speculative (đi ngược nguyên tắc "không phức tạp vô ích").

---

## 4. LỆNH CHẠY WEB (config thương mại production)
```
set VP_WEB_USER=admin
set VP_WEB_PASS=<mật-khẩu-mạnh>
vision-platform\.venv\Scripts\python.exe -m vision_platform.profiles.vision_web_app ^
  --camera 0 --onnx models/yolov8n.onnx --yolo v8 --model-size 640 --coco-labels ^
  --overlay-motion --overlay-display-lease-ms 350 ^
  --overlay-create-conf 0.45 --overlay-sustain-conf 0.30 ^
  --server waitress --threads 8 --host 127.0.0.1 --port <PORT>
```
- Phơi qua mạng KHÔNG tin cậy: đặt sau TLS reverse-proxy (xem `deploy/README-tls-reverse-proxy.md`); Basic
  Auth trần cần TLS trước. `--host 0.0.0.0` không cred + không `--insecure` → server TỪ CHỐI bind (secure-default).
- Port TIME_WAIT: restart nhanh cùng port → `socket forbidden` (Windows) → đổi port hoặc chờ.

---

## 5. CÁCH LÀM VIỆC (đúc kết)
- **Verify browser = Playwright MCP** trên webcam THẬT. Nguồn synthetic moving-square BỆNH LÝ — không dùng
  đánh giá tracking (K-112). Trang có Basic Auth → dialog Chrome CHẶN automation → verify header bằng
  urllib/Invoke-WebRequest gửi thẳng `Authorization: Basic ...` (K bài học #428).
- **Python qua** `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd`; KHÔNG alias.
- **cmd nuốt `&`-chaining (→ PowerShell Job rác); PowerShell nuốt `$`/`;`** → dùng lệnh ĐƠN / script cố định.
- **DỪNG background server TRƯỚC khi `vp verify`** (đốt CPU → flaky K-035/K-116 giả).
- Chống-drift = `scripts\vp.cmd check` (C1-C9 + RULES_VERSION 16 sync 5 mirror + 14 self-test).

---

## 6. FILE ĐỌC KHI KHỞI TẠO PHIÊN MỚI
- `memory-bank/activeContext.md` (block #432 trên cùng) · `progress.md`
- `AI-IMPLEMENTATION-LOG.md` (tail #428→#432) · `ai-decision-journal/00-INDEX.md` + `04-things-to-know.md`
- `.kiro/specs/overlay-tracking-refactor/` + `.kiro/specs/web-production-hardening/`
- `vision-platform/src/vision_platform/profiles/vision_web_app.py`
- `vision-platform/src/vision_platform/adapters/{wsgi_server,auth_middleware,security_headers}.py`
- `deploy/README-tls-reverse-proxy.md`
