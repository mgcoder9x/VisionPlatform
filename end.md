# end.md — HANDOFF chuyển máy (KHÔNG phải trạng thái; frontier THẬT xác định qua `scripts\vp.cmd check`)

> ⚠️ K-064: file này là HANDOFF người-đọc, KHÔNG phải nguồn sự thật. Nguồn thật = `vp check` +
> `AI-IMPLEMENTATION-LOG.md` + `ai-decision-journal/00-INDEX.md` + `memory-bank/activeContext.md`.
> ⚠️ K-098: **frontier có thể NHẢY giữa phiên** (đa máy đẩy chéo + workspace auto-sync). LUÔN chạy
> `git status` + `vp check` TRƯỚC khi làm; nghi ngờ → `git fetch` + đối chiếu, đừng append trên base cũ.

## 0. ĐẦU PHIÊN BẮT BUỘC (copy chạy ngay)
```
git status
scripts\vp.cmd check      :: drift-check nhanh (C1-C9 + RULES sync + self-test)
```
Đọc 5 entry cuối `AI-IMPLEMENTATION-LOG.md` + block trên cùng `activeContext.md` + `00-INDEX.md` header.
FAIL drift → SỬA cho khớp thực tế TRƯỚC khi làm. Behind upstream → `git pull --ff-only` rồi đối chiếu lại.

## 1. FRONTIER THẬT (chốt lúc viết handoff, đã `vp check` PASS)
- **LOG #453 · Σ329 (D149 · C24 · T35 · K121) · HEAD=origin=`8dc44ee` · nhánh `chore/dev-env-launcher-portable-hooks`**
- drift PASS · C8=40 Verify-Symbol · RULES_VERSION 16 (5 mirror khớp).
- `vp verify` = test + import-linter + drift · `vp check` = chỉ drift (nhanh) · `vp install-hooks` = đặt git pre-commit (D-148, `.githooks/`).

## 2. VIỆC VỪA XONG PHIÊN NÀY (#453, máy `k.nguyen.manh.toan` CPU)
- **Đóng K-014 🔴→✅ (D-149):** perf-harness `vision-platform/benchmarks/measure_ring_drop.py` đo FRAME-DROP@fps
  THẬT của SHM ring (in-process 2-thread keep-latest; tách `drop_ring_full` backpressure vs `drop_superseded`).
  **Số THẬT (CPU, 30fps producer, 480×640, variance≈0):** consume 33ms→drop 0.0%·30fps · 50ms→34.0%·19.8 ·
  100ms(YOLO-CPU)→66.2%·10.0. Quan hệ `drop% ≈ 1 − consumer_rate/producer_rate`; `consumer_fps=1000/consume_ms`
  bất kể producer → keep-latest **latency-bounded** (consumer full-tốc không backlog, drop=frame cũ, không tích
  luỹ trễ) = hành vi ĐÚNG real-time, SLA nguồn KHÔNG phải lỗi. Ghép #452 (detector GPU 36/s · CPU 17/s) = SLA đầu-cuối.
- **RECONCILE K-098:** phiên khởi base cũ `1b645a5` (#440); giữa phiên workspace-sync + máy `toann` GPU push
  origin tới `8dc44ee` #452 (Σ328: onnx-cuda gating / production logging / cardinality / fleet-profile spec /
  SSE-transport spec / RTSP-verify). Bookkeeping #441/D-142 tôi soạn trên base cũ TRÙNG số máy kia → `git restore`
  + `git pull --ff-only` #452 → làm lại #453/D-149 trên base mới (bài học #433: KHÔNG append trên base cũ).
- **§3.1 — đề nghị user thêm Trusted Command:** `python -m benchmarks.measure_ring_drop *` (dev-tool CHỈ-ĐỌC/đo).

## 3. TRẠNG THÁI NỀN (từ #441-#452, máy `toann` GPU + #453 máy này)
- **Web/overlay:** sạch (verify Playwright MCP nhiều lần); production-hardening Wave 1+2+3 XONG (waitress + BasicAuth + security-headers + TLS-doc).
- **Detector device policy:** hợp nhất qua `onnx_providers_for`/`resolve_device` (#437/D-139 + onnx-cuda gating D-142); GPU verify THẬT trên RTSP (#450/#451); capacity GPU 36/s vs CPU 17/s yolov8n@640 (#452/K-121).
- **Observability production:** logging non-blocking+rotating (#443/K-018) + cardinality budget (#444/K-019) + wire TOML (#445).
- **Chống-drift:** `vp check` (C1-C9 + self-test) + git pre-commit hook versioned (#449/D-148) = phòng-thủ-3-lớp agentStop→pre-commit→CI.
- **SHM ring SLA:** bound ≤ n_slots (đã CM) + drop@fps đo (#453/K-014 ✅) → SLA nguồn định lượng đầy đủ cho 1-consumer/stream.

## 4. SPEC ĐANG MỞ (design-first, CHỜ USER VALID — chưa code)
- `.kiro/specs/architecture-review/design.md` — bản đánh giá kiến trúc CỰC SÂU (Phần E = 9 câu chốt để suy requirements).
- `.kiro/specs/multicamera-fleet-profile/` (requirements+design) — profile fleet đa-cam đa-process; A2 nay có số 36 detect/s.
- `.kiro/specs/overlay-sse-transport/design.md` — khử tận gốc console-noise browser bằng SSE (thay MJPEG poll).

## 5. BƯỚC KẾ = CẦN USER CHỐT (không tự làm speculative — nguyên tắc YAGNI của user)
- **(A) ANPR .pt** (cài torch / export ONNX) — nghiệp vụ biển số.
- **(B) valid 1 trong 3 spec design-first** ở §4 → requirements → tasks → code TDD.
- **(C) soak 24/7 / đo end-to-end fps** (decode+letterbox+NMS+overlay) — nối tiếp #452/#453.
- **🔴 còn mở:** K-001 (ARM chưa verify — cần HW Jetson) · K-031 (rotate secret production).

## 6. RÀNG BUỘC VẬN HÀNH (lặp lại để máy sau khỏi vấp)
- Python qua `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd`; lệnh routine qua launcher cố định (§3.1); `python -c` chỉ thăm-dò 1-lần.
- Shell cmd nuốt `&`-chaining / PowerShell nuốt `$`/`;` → lệnh ĐƠN. LOG entry heading = **`### Entry #N`** (3 dấu #, drift C1 mới nhận).
- DỪNG server nền TRƯỚC `vp verify` (đốt CPU → flaky giả). Port TIME_WAIT → đổi port. git: không `add -A`, không force/reset, push nhánh hiện tại.
- Verify browser = Playwright MCP trên webcam/RTSP thật. Máy này: CPU, có Docker + webcam, KHÔNG GPU. Máy `toann`: GPU + RTSP cam Dahua `.106`.
