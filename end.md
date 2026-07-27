# end.md — HANDOFF sang máy GPU (gọn). Nguồn sự thật = `vp check` + LOG + journal + activeContext.

## 0. ĐẦU PHIÊN — chạy 3 lệnh này
```
git status
scripts\vp.cmd check           :: xem C10-HOOKS · C9-GIT · DRIFT-CHECK
scripts\vp.cmd install-hooks   :: CHỈ khi C10-HOOKS báo WARN (config local, mỗi clone 1 lần)
```
- FAIL drift → sửa trước khi làm. `behind>0` → `git pull --ff-only` rồi đối chiếu lại.
- ⚠️ **K-098:** frontier có thể NHẢY giữa phiên (đa máy) → **KHÔNG append lên base cũ** (đã gây trùng số #433/#453).
- 🔒 **K-126:** bị tường lửa/kiểm soát mạng công ty chặn → **DỪNG + BÁO user**, TUYỆT ĐỐI không vượt.
- ⚠️ **K-129:** shell là PowerShell 7, `&` = **background job** → lệnh `&`-chained **chạy ngầm, âm thầm, né cả hook**.
  **1 lệnh / 1 tool-call.** Nghi ngờ → `Get-Job`.

## 1. FRONTIER (lúc viết)
**LOG #465 · Σ346 (D158·C24·T35·K129) · RULES_VERSION 18 (7 file) · nhánh `chore/dev-env-launcher-portable-hooks`**
Baseline: `vp verify` **919 passed / 2 skipped · lint 7 kept/0 broken · drift PASS · secret-scan PASS · C8=48**.
`vp verify` = test + lint + drift + secrets · `vp check` = drift nhanh · `vp secrets` = quét secret.
Máy vừa làm: `k.nguyen.manh.toan` — **CPU only**, webcam, Docker **chưa bật**.

## 2. VIỆC TRÊN MÁY GPU (ưu tiên A → C)

**(A) Đo lại SSE + bulkhead trên GPU/RTSP thật** — mọi số hiện có đều từ CPU; GPU detect ~2× nhanh (#452: 36 vs 17 infer/s) ⇒ SSE phát event dày hơn, phải đo lại.
```
:: chạy app (đổi <RTSP_URL>, <PORT>; --threads >= 2N+2 cho N viewer)
vision-platform\.venv\Scripts\python.exe -m vision_platform.profiles.vision_web_app ^
  --rtsp "<RTSP_URL>" --onnx models/yolov8n.onnx --yolo v8 --model-size 640 --coco-labels ^
  --device auto --overlay-motion --overlay-display-lease-ms 350 --overlay-create-conf 0.45 ^
  --overlay-sustain-conf 0.30 --server waitress --threads 8 --host 127.0.0.1 --port <PORT>
:: KỲ VỌNG log: [device] onnx yêu cầu='auto' → dùng='cuda...'   (ra 'cpu' → DỪNG, điều tra GPU)

:: trần thread (kỳ vọng: trần 6 · kết nối #7+ = 503 · /stats luôn OK 0-16ms)
vision-platform\.venv\Scripts\python.exe -m tools.web_sse_capacity_probe --port <PORT> --max-long 12 --threads-hint 8
:: rò rỉ slot (kỳ vọng: mọi chu kỳ active → 0/N · verdict KHÔNG RÒ RỈ)
vision-platform\.venv\Scripts\python.exe -m tools.web_sse_capacity_probe --port <PORT> --churn 10 --churn-conns 12
```
Browser (Playwright MCP), **URL SẠCH**: kỳ vọng `sseFails=0` · `degraded=false` · box vẽ · 0 console error; đo lại gap giữa event SSE (CPU: median 50.8ms).
> ⚠️ **K-124:** KHÔNG verify bằng `http://user:pass@host/` — làm chết mọi `fetch` trong trang. Dùng `page.route` tiêm header `Authorization` với URL sạch.

**(B) Đo fps ĐẦU-CUỐI trên GPU** (nợ tự nêu #452): #452 chỉ đo detector đơn lẻ. Ghép với #453 (`drop% ≈ 1 − consumer/producer`) → SLA đầu-cuối = con số khách hàng hỏi ("chạy được mấy cam").

**(C) Nếu bật được Docker → đóng 🔴 reverse-proxy:** `vision-platform/deploy/README-tls-reverse-proxy.md` có bảng TRẠNG THÁI KIỂM CHỨNG, phần "toàn chuỗi qua proxy thật" vẫn 🔴. Dựng nginx → đo SSE/MJPEG live qua proxy · trần bulkhead khi proxy giữ kết nối · `proxy_ignore_client_abort` giữ mặc định `off` có trả slot đúng → rồi **cập nhật bảng đó + ghi LOG mới**.

## 3. 🔴 CÒN MỞ
| Mục | Vì sao |
|---|---|
| K-001 ARM/Jetson | cần hardware |
| K-031 rotate secret | user thao tác. **Thêm lý do:** #457 lệnh sai cú pháp làm `cmd set` in TOÀN BỘ biến môi trường vào log phiên, gồm 3 biến chứa API key (`OPENAI_API_KEY`, `openAI_key`, `HUNGNGUYEN_API_KEY`) → **nên rotate** |
| Toàn chuỗi qua proxy thật | chờ Docker/nginx (chặn tiền đề, KHÔNG phải mạng) |
| K-128 web app chỉ có stdout | chưa có `--log-file`/`/metrics` cho web app (YAGNI, chờ user) |
| `print()` block khi stdout không ai đọc | chưa dựng thí nghiệm pipe-không-đọc |

## 4. RÀNG BUỘC VẬN HÀNH
- Python qua `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd` (§3.1: lệnh routine qua launcher cố định).
- LOG entry heading = **`### Entry #N`** (3 dấu `#`) — drift C1 mới nhận.
- `set VAR=v && ...` (cmd) nhồi khoảng trắng vào giá trị (gây 401 giả #457) → viết `set VAR=v&&...` không space.
- **DỪNG server nền TRƯỚC `vp verify`** (đốt CPU → flaky giả). Port TIME_WAIT → đổi port.
- git: không `add -A` (chọn file cụ thể), không force/reset, push nhánh hiện tại.
- Đo trạng thái đến SAU sự-kiện-có-độ-trễ-phụ-thuộc-tải → **không sleep cố định**, dùng poll-tới-điều-kiện + deadline (K-127).
- Tài liệu **không** viết chuỗi hình-dạng-key nguyên văn (secret-scan sẽ chặn commit) → viết dạng ngắt.
