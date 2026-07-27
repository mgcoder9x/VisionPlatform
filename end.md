# end.md — HANDOFF sang MÁY CÓ GPU (không phải trạng thái; frontier THẬT xác định qua `scripts\vp.cmd check`)

> ⚠️ K-064: file này là handoff người-đọc. Nguồn sự thật = `vp check` + `AI-IMPLEMENTATION-LOG.md` +
> `ai-decision-journal/00-INDEX.md` + `memory-bank/activeContext.md`.
> ⚠️ K-098: frontier **có thể NHẢY giữa phiên** (đa máy đẩy chéo + workspace auto-sync). LUÔN `git status` +
> `vp check` TRƯỚC; nghi ngờ → `git fetch` + đối chiếu; **KHÔNG append lên base cũ** (đã từng gây trùng số, #433/#453).
> 🔒 K-126 (v18): **tường lửa/kiểm soát mạng công ty — CẤM VƯỢT.** Bị chặn → DỪNG + BÁO user. Không đổi/tắt
> VPN·firewall·AV·proxy·DNS·hosts, không tunnel, không `--insecure`, không mirror lách. Chặn = kết quả đo hợp lệ.

## 0. ĐẦU PHIÊN BẮT BUỘC
```
git status
scripts\vp.cmd check
```
Đọc 5 entry cuối LOG + block trên cùng `activeContext.md`. FAIL drift → SỬA trước khi làm. Behind upstream →
`git pull --ff-only` rồi đối chiếu lại.

## 1. FRONTIER THẬT (lúc viết handoff)
- **LOG #463 · Σ343 (D156 · C24 · T35 · K128) · RULES_VERSION 18 (7 file) · nhánh `chore/dev-env-launcher-portable-hooks`**
- baseline: **`vp verify` 919 passed / 2 skipped · import-linter 7 kept/0 broken · drift PASS · C8 = 46 Verify-Symbol**
- Máy vừa làm: `k.nguyen.manh.toan` — **CPU only**, có webcam, có Docker **(daemon CHƯA bật)**.

## 2. LÀM GÌ NGAY TRÊN MÁY GPU (thứ tự ưu tiên, kèm LÝ DO)

### (A) Verify SSE + bulkhead trên GPU/RTSP thật — cao nhất, vì mọi số hiện có đều từ CPU
Toàn bộ spec `overlay-sse-transport` (#454-#462) được đo trên **CPU + webcam**. Trên GPU, detect nhanh hơn ~2×
(#452: 36 vs 17 infer/s) ⇒ **`eventRevision` đổi nhanh hơn ⇒ SSE phát event dày hơn** ⇒ cần đo lại:
```
:: 1) chạy web app (GPU + RTSP thật; đổi <PORT>, giữ --threads đủ cho số viewer: >= 2N+2)
vision-platform\.venv\Scripts\python.exe -m vision_platform.profiles.vision_web_app ^
  --rtsp "<RTSP_URL>" --onnx models/yolov8n.onnx --yolo v8 --model-size 640 --coco-labels ^
  --device auto --overlay-motion --overlay-display-lease-ms 350 --overlay-create-conf 0.45 ^
  --overlay-sustain-conf 0.30 --server waitress --threads 8 --host 127.0.0.1 --port <PORT>
:: kỳ vọng dòng log: [device] onnx yêu cầu='auto' → dùng='cuda...'  (nếu ra 'cpu' → GPU chưa dùng được, DỪNG điều tra)

:: 2) trần thread + starve (kỳ vọng: trần 6, #7+ = 503, /stats luôn OK 0-16ms)
vision-platform\.venv\Scripts\python.exe -m tools.web_sse_capacity_probe --port <PORT> --max-long 12 --threads-hint 8

:: 3) rò rỉ slot (kỳ vọng: mọi chu kỳ active -> 0/N, verdict KHÔNG RÒ RỈ)
vision-platform\.venv\Scripts\python.exe -m tools.web_sse_capacity_probe --port <PORT> --churn 10 --churn-conns 12
```
Rồi **browser (Playwright MCP)** trên URL SẠCH: kỳ vọng `sseFails=0` · `degraded=false` · box vẽ · 0 console error;
đo lại **gap giữa các event SSE** (CPU cho median ~50.8ms = đúng tick) xem GPU có làm dày hơn/nặng CPU hơn.
> ⚠️ K-124: **KHÔNG** verify bằng URL `http://user:pass@host/` (làm chết mọi `fetch` trong trang) → dùng
> `page.route` tiêm header `Authorization` với URL sạch.

### (B) Đo end-to-end fps trên GPU (nợ tự nêu ở #452)
#452 chỉ đo **detector-throughput** (36 infer/s). Chưa có **fps đầu-cuối** (decode + letterbox + NMS + overlay).
Ghép với #453 (drop@fps của SHM ring: `drop% ≈ 1 − consumer/producer`) sẽ ra **SLA đầu-cuối định lượng** —
đây là số khách hàng hỏi ("chạy được mấy cam?").

### (C) Nếu bật được Docker trên máy đó → đóng 🔴 reverse-proxy
`vision-platform/deploy/README-tls-reverse-proxy.md` có **bảng TRẠNG THÁI KIỂM CHỨNG**: phần "toàn chuỗi qua proxy
thật" vẫn 🔴. Cần dựng nginx → đo: SSE qua proxy còn live? MJPEG live? trần bulkhead khi proxy giữ kết nối riêng?
`proxy_ignore_client_abort` để mặc định off có trả slot đúng? Rồi **cập nhật bảng đó + ghi LOG mới**.

### (D) ANPR `.pt` (nếu là hướng nghiệp vụ bạn muốn): cài torch CUDA hoặc export sang ONNX.

## 3. VIỆC KHÔNG CẦN GPU (làm được ở bất kỳ máy nào — nếu muốn tiếp trên máy CPU)
- **Cưỡng chế secret bằng máy** (liên quan 🔴 K-031 + sự cố in biến môi trường #457): quét secret ở pre-commit
  thay vì trông vào kỷ luật. **CHƯA làm** — tôi đã đề xuất, chờ bạn duyệt.
- `--log-file` / `/metrics` cho **web app** (K-128: hiện web app chỉ có stdout, bất đối xứng với slice app). CHƯA làm.
- Soak 24/7 · network-partition thật (cần 2 máy/firewall drop, xem K-125).

## 4. TRẠNG THÁI CÁC 🔴 CÒN MỞ
| Mục | Vì sao còn mở |
|---|---|
| K-001 (ARM/Jetson chưa verify HW atomicity) | cần hardware Jetson |
| K-031 (rotate secret) | user thao tác; **thêm lý do**: #457 có lệnh sai cú pháp làm `cmd set` in TOÀN BỘ biến môi trường vào log phiên, gồm 3 biến chứa API key (`OPENAI_API_KEY`, `openAI_key`, `HUNGNGUYEN_API_KEY`) → **nên rotate** |
| Toàn chuỗi qua reverse-proxy thật | chờ Docker/nginx (chặn bởi tiền đề, KHÔNG phải mạng) |
| `print()` block khi stdout không ai đọc (K-128) | chưa dựng thí nghiệm pipe-không-đọc |

## 5. RÀNG BUỘC VẬN HÀNH (để máy sau khỏi vấp)
- Python qua `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd`; lệnh routine qua launcher cố định (§3.1).
- LOG entry heading phải là **`### Entry #N`** (3 dấu `#`) — drift C1 mới nhận.
- **Shell — ĐỌC KỸ, đây là bẫy gây SỰ CỐ THẬT (K-129, #464):** shell của agent là **PowerShell 7**, trong đó `&`
  là **toán tử BACKGROUND JOB**. `A & B & C` **KHÔNG bị "nuốt"** — mỗi đoạn **ĐƯỢC THỰC THI, tách rời, ÂM THẦM**
  (output nằm trong job, agent chỉ thấy bảng `Id/Name/State`). Đã gây: một `git commit` chạy **ngoài ý muốn** và
  **thoát khỏi pre-commit hook** (#464). ⇒ **TUYỆT ĐỐI dùng lệnh ĐƠN**, mỗi tool-call một lệnh. Nghi ngờ có job
  chạy ngầm → `Get-Job` (rồi `Remove-Job -Force`). PowerShell cũng cắt chuỗi ở `$`/`;`/`|` khi nội suy.
- `set VAR=v && ...` (cmd) **nhồi khoảng trắng** vào giá trị (đã gây 401 giả ở #457) → viết `set VAR=v&&...` không space.
- **DỪNG server nền TRƯỚC `vp verify`** (đốt CPU → flaky giả). Port TIME_WAIT → đổi port.
- git: không `add -A` (chọn file cụ thể), không force/reset, push nhánh hiện tại.
- Đo trạng-thái-sau-sự-kiện-có-độ-trễ-phụ-thuộc-tải → **KHÔNG sleep cố định**, dùng poll-tới-điều-kiện + deadline (K-127).
