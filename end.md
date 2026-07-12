# end.md — Handoff chuyển máy/phiên (đọc TRƯỚC khi làm tiếp)

> **Cập nhật lúc:** 2026-07-12 · máy `toann` · nhánh git `chore/dev-env-launcher-portable-hooks`
> · commit đầu-mút (đã push): **`494bc10`** (LOG canonical **#346**).
> Đây là ảnh-chụp bàn-giao. **Nguồn sự thật SỐNG** = code + `memory-bank/activeContext.md` + `ai-decision-journal/` + `vp verify`.

## 0. LÀM GÌ NGAY ĐẦU PHIÊN (bắt buộc, theo AGENTS.md §0)
1. `git status` + `git log -n 3` — xác nhận sạch, khớp `494bc10` (hoặc mới hơn nếu máy khác đã push).
2. `cmd /c scripts\vp.cmd check` — drift-check (phải PASS; nếu FAIL = có drift bản ghi → SỬA trước).
3. Đọc: `memory-bank/activeContext.md` (block mới nhất) + `ai-decision-journal/00-INDEX.md` (header) + 5 entry cuối `AI-IMPLEMENTATION-LOG.md`.
4. Trước khi ghi sổ: **grep max ID THẬT** (`### Entry #`, `### D-`, ...) — repo sync đa-máy, KHÔNG tin số dán.

## 1. TRẠNG THÁI SẢN PHẨM (verified #346)
- **Test:** `630 passed / 2 skipped` · **lint:** `5 kept / 0 broken` (import-linter 6 layer) · **drift:** PASS.
- **RULES_VERSION:** 16 (5 mirror: AGENTS.md · GEMINI.md · .github/copilot-instructions.md · .kiro/steering/00-core-rules.md · ai-learning-os-kit/AGENTS.template.md).
- **Journal:** `Σ226` = D92 · C21 · T32 · K81.
- **Kiến trúc:** hexagonal 6 layer (domain/kernel/runtime/application/adapters/profiles). Sản phẩm: pipeline runner · config TOML · analytics (tracking/line-crossing/motion-gate/count) · observability (đo→Prometheus→/metrics) · capability-aware · SHM IPC + epoch · backpressure · supervisor.

## 2. CƠ CHẾ VẬN HÀNH (LẶP MỖI LƯỢT)
- **Verify:** `cmd /c scripts\vp.cmd verify` (pytest + lint + drift). Chỉ drift: `vp check`. Đã Trust → chạy không hỏi. Chạy 1 file test: `vp.cmd test tests/<file>.py`.
- **Ghi sổ MỖI lượt đổi trạng thái:** LOG entry (`AI-IMPLEMENTATION-LOG.md`, 4 mục) + journal D/C/T/K (`ai-decision-journal/`) + INDEX (header canonical #N + `Tổng Σ(D..C..T..K..)` + dòng ID) + `activeContext.md` (block + mốc "Cập nhật lúc"). Rồi `vp check` PASS.
- **PowerShell nuốt/mangle output** (git progress, lệnh dài → Exit -1 GIẢ). Workaround: xác nhận push bằng so `git rev-parse HEAD` == `git rev-parse @{u}` (in "PUSHED-OK"); ghi output ra `_tmp.txt` rồi `Get-Content` nếu cần.
- **§3.1:** lệnh qua launcher tên-cố-định (`vp.cmd`). CẤM `python -c` ad-hoc lặp. `py` KHÔNG có trên máy toann (scoop python) → dùng `vp.cmd` (tự dò venv).
- Kết mỗi output: "Đã verify / Chưa verify". Trả lời tiếng Việt.

## 3. CƠ CHẾ CHỐNG-DRIFT "CỰC MẠNH" (4 lớp — yêu cầu user)
`tests/drift_check.py` (qua `vp check`):
1. **C1–C7** — nhất quán bản-ghi↔bản-ghi (LOG↔INDEX↔journal↔activeContext liên tục/khớp/tươi).
2. **C8 (mới #341)** — bản-ghi↔**CODE**: trường opt-in `Verify-Symbol: <relpath>::<symbol>` trong journal → symbol phải còn ĐỊNH NGHĨA trong code (hiện 7 symbol khớp). Đóng drift class doc↔code. Khi mục ✅-code bị đảo/gỡ code → GỠ luôn dòng Verify-Symbol.
3. **RULES_VERSION sync** 5 file.
4. **self_test 11/11** — guard chống regex-rot (checker phải BẮT được drift).
Thư mục 4-việc user yêu cầu = `ai-decision-journal/` (01-decisions D · 02-requirement-changes C · 03-tradeoffs T · 04-things-to-know K + 00-INDEX + README).

## 4. ĐÃ LÀM PHIÊN NÀY (#339 → #346)
- **#339** — HOÀN TẤT deep-dive `code-lessons/` (lấp khoảng-trống sau #10): **#11 config (15) · #12 analytics (14) · #13 observability (10) · #14 capability (8)** — tất cả "đã viết đủ", **CHƯA qua cổng Feynman** (người học tự giải thích lại — chưa làm).
- **#340–#341** — thiết kế + hiện thực **C8 doc↔code** (D-089, T-031) + `review/C8-doc-code-drift-check-design.md`.
- **#342** — sửa GỐC staleness `docs/ARCHITECTURE.md` §0/§10 (bỏ liệt-kê-số-đếm-được, trỏ `vp check`).
- **#343** — FIX review **F3** (D-090): gom magic `5.0s` observe-default → 1 hằng `_DEFAULT_OBSERVE_INTERVAL_S`.
- **#344** — **D.2** đọc-lại-valid: recovery lock-poison lần-1 THỰC TẾ đã WIRE (quarantine+lease+reap) → sửa docstring STALE `shm_frame_ring.py` + defer residual (K-081, cần stress production, KHÔNG vá speculative).
- **#345** — FIX săn-bug **Z1** (D-091, T-032): bulkhead io-thread `ZmqInferenceClient` (đối xứng server K-024). TDD, 5/5 không-flaky.
- **#346** — FIX săn-bug **R1** (D-092): `_default_cv2_capture` set OPEN_TIMEOUT TRƯỚC open (construct rỗng→set→`cap.open`). TDD fake-cv2 (không cần camera).

## 5. BUG-HUNTING (review đối kháng — trạng thái)
- ✅ **Z1** (client io-thread bulkhead) — FIXED #345.
- ✅ **R1** (rtsp OPEN_TIMEOUT vô hiệu) — FIXED #346 (*order-contract tested; hang-thực chờ field-verify RTSP host*).
- 🟡 **Z2** [Low, MỞ] — `ZmqInferenceClient._responses` unbounded nếu caller ngừng poll (an toàn theo giả định camera-poll-mỗi-vòng).
- 🟡 **D.2 residual** (K-081) — lock-poison lần-2 + owner-CÒN-SỐNG (degraded an toàn, không mất data) → cần stress đa-process production.
- SOUND (đã đọc kỹ, KHÔNG bug): `nms` · `letterbox inverse_box` · `yolo v5/v8 decode` · `InferenceServer` (bulkhead K-024) · `rtsp reconnect/mask` · `onnx_detector`.
- Findings review cũ còn MỞ (Low): **E.2** (torch.load patch global — gắn nhánh GPU, chặn K-079) · **F4** (guard BLOCK+RTSP chưa wire — cần quyết định thiết kế) · **F5/F6/F7** (tổ chức code, Low). Chi tiết: `review/2026-07-11-architecture-review.md` + `docs/ARCHITECTURE.md` §12.

## 6. HƯỚNG TIẾP (chọn 1)
- **Săn bug tiếp** (user đang muốn hướng này): vùng chưa soi kỹ = `video_file_frame_source` (EOF/loop) · `dark_filter`+`brightness` stages · `supervisor` cascade race.
- **Cổng Feynman** #11–#14 (biến tài-liệu→hiểu-thật; cần user tự giải thích — CHƯA làm cái nào).
- **F4** design-first (wire guard vs future-API — cần user quyết).
- **Dừng mốc sạch.**

## 7. CHẶN / RÀNG BUỘC
- **GPU/CUDA** (nhánh `pt-cuda`, E.2, benchmark số thật): cần cài **torch** = op NẶNG-mạng → **chờ đèn xanh user** (K-078/K-079: torch VẮNG mọi interpreter máy toann; GPU-HW CÓ). KHÔNG tự cài lúc remote.
- **DB server** (Postgres sink), **máy CI mạnh** (đóng K-035 tuyệt đối / stress D.2): chờ hạ tầng.
- **Git-safety:** commit từng task, KHÔNG secret/.env; push nhẹ OK (K-078); KHÔNG force-push/reset --hard/xóa nhánh trừ khi được phép rõ.

## 8. FILE QUAN TRỌNG
- `docs/ARCHITECTURE.md` — 1 CỬA review kiến trúc (§1–11 hiểu + §12 đánh giá/findings).
- `review/2026-07-11-architecture-review.md` — findings chi tiết (F1–F7 / D.1–D.4 / E.2 / Z1 / Z2 / R1).
- `ai-decision-journal/00-INDEX.md` — bảng rà 1 trang mọi quyết định + rủi ro 🔴/🟡.
- `AGENTS.md` — luật đầy đủ (RULES_VERSION 16).
- `code-lessons/00-INDEX.md` — bản đồ bài giảng code (#01–#14).
