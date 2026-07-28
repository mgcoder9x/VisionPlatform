# HANDOFF — đọc file này TRƯỚC khi làm (máy mới / phiên mới)

> ⚠️ Đây là HANDOFF ngắn (không phải trạng thái chân lý). **Trạng thái THẬT xác định bằng `scripts\vp.cmd check`** +
> `memory-bank/activeContext.md` (block trên cùng) + `AI-IMPLEMENTATION-LOG.md` (entry cuối). Frontier có thể NHẢY
> giữa phiên (đa máy + workspace auto-sync, K-098) → LUÔN `vp check` lại, KHÔNG append lên base cũ.

## 0. ĐẦU PHIÊN (bắt buộc, theo thứ tự)
1. `git status` + `git log -n 3` — xem có gì chưa commit / frontier ở đâu.
2. `scripts\vp.cmd check` — drift-check (phải PASS). Nếu FAIL = bản ghi lệch thực tế → SỬA trước khi làm.
3. **`git config --local --get core.hooksPath`** → nếu KHÔNG phải `.githooks` thì chạy **`scripts\vp.cmd install-hooks`**
   (cổng pre-commit drift+secret kích hoạt per-clone, C10-HOOKS sẽ WARN nếu quên — K-129/#465).
4. Đọc `memory-bank/activeContext.md` (block #476 trên cùng) + 5 entry cuối LOG + `ai-decision-journal/00-INDEX.md` (bảng D).
5. Đọc spec đang làm: `.kiro/specs/image-preprocess-and-labeling/{requirements,design,tasks}.md`.

## 1. FRONTIER THẬT (lúc viết handoff)
- **LOG #476 · Σ355 (D166·C24·T35·K130) · HEAD=`5d5ac60` · nhánh `chore/dev-env-launcher-portable-hooks`** (đã push, `0 0` với origin).
- Baseline: `vp verify` = **959 passed / 2 skipped · import-linter 7 kept/0 broken · drift PASS · secret-scan PASS · C8=56 Verify-Symbol**.
- **Workflow git CHƯA quyết** (cần user chốt): hiện `main` == nhánh `chore` (FF #468). Nếu tiếp tục commit trên `chore` mà không FF định kỳ → `main` lại cũ. Chốt main-trunk hay feature-branch+PR?

## 2. LỆNH CỐ ĐỊNH (chạy qua launcher, KHÔNG one-liner ad-hoc — §3.1)
- `scripts\vp.cmd check` = drift nhanh (memory + RULES_VERSION + self-test).
- `scripts\vp.cmd verify` = test + import-linter + drift + **secret-scan** (gate "xong").
- `scripts\vp.cmd secrets` = quét secret · `scripts\vp.cmd install-hooks` = bật core.hooksPath.
- Python trực tiếp: `vision-platform\.venv\Scripts\python.exe -m pytest tests/<file> -q` (cwd = `vision-platform`).

## 3. ĐANG LÀM: spec `image-preprocess-and-labeling` (chuẩn hoá 2 mép pipeline thị giác)
Nguyên tắc: **MODEL-định=cố-định (T1 normalize+T2 letterbox @adapter) ⊥ TRIỂN-KHAI-định=cắm-được (T3 preprocess + display-name)**.
Bộ spec HOÀN CHỈNH (design+requirements+tasks). Thi công theo `tasks.md` (13 task/2 Wave, TDD, task-tool dùng `taskList`/`taskUpdate` trên tasks.md).

### ✅ WAVE 1 — HIỂN THỊ TÊN VẬT THỂ (Label) — XONG (task 1-6, #471-#476)
- `kernel/label_map.py::LabelMap` — value-object positional, `canonical(cid)` fail-safe idx-lạ→`class_<id>` (D-162).
- `adapters/label_map_loader.py::load_label_map` — nguồn ưu tiên sidecar`.names`→metadata-ONNX(best-effort)→config→rỗng.
- `adapters/yolo_postprocess.py` — decoder thay `str(cid)` bằng `LabelMap.canonical` qua `_resolve_label_map` (param `label_map`, giữ `labels` compat) (D-163). Wire `pipeline_factory._det_onnx` + choke-point `vision_demo_app._build_detector` (phủ web app).
- `domain/display_policy.py::DisplayPolicy` — thuần: alias/i18n/gộp/ẩn/màu-ổn-định; `decide(canonical)→DisplayDecision{visible,display_name,group,color_key}`; alias>group>canonical; color_key=group-else-canonical (D-164).
- **Bất biến canonical⊥display** (D-165): `Detection.label`=canonical xuyên analytics; contract import-linter **Property 10** phủ thêm `domain.display_policy` (cưỡng chế máy).
- **Render** (D-166): `overlay_projection.project_overlay(..., policy=)` thêm `displayName`/`colorKey` + lọc `visible=false` (rawResult giữ raw → Ẩn⊥Đếm); web app `_display_policy` global (mặc định passthrough) → `/overlay`+SSE; client `_PAGE` `colorFor(colorKey)`→hue + `truncName`. Verify browser thật: canvas vẽ 1047px/9 màu, 0 console error.
- **Nợ nhỏ Label (follow-up):** chưa có CLI/config nạp `_display_policy` khác rỗng (i18n/alias/hide per-deployment) — framework sẵn, thiếu loader.

### ⬜ WAVE 2 — TIỀN XỬ LÝ ẢNH T3 (Preprocess) — CHƯA làm (task 7-13). BƯỚC KẾ = task 7.1.
- **7** `MediaPacket.with_media()` (CoW) — thay frame giữ metadata.
- **8** registry op-agnostic + `domain/preprocess_ops.py` op numpy-thuần (gamma/brightness/gray/resize-scale/ROI-crop/white-balance/sharpen).
- **9** op cần cv2 (denoise/CLAHE) → `adapters/` (GIỮ domain KHÔNG cv2 — R11.1); de-warp = điểm-cắm CHƯA hiện thực (Non-Goal v1).
- **10** ⚠️ **PHẦN KHÓ NHẤT** — op đổi hình học (crop/resize) trả kèm transform NGHỊCH; map ngược điểm ≤1px (P-A1); nối chuỗi nghịch ngược thứ tự áp → ORIGINAL_FRAME.
- **11** `runtime/preprocess_stage.py::PreprocessStage` (MediaPacket→MediaPacket, chỉ phụ thuộc kernel) + config `[preprocess]` TOML (danh sách op có thứ tự) + wire `_detect_loop` TRƯỚC detect; **no-regression: không op → bytes-identical** (P-A2).
- **12** harness `benchmarks/` đo recall/precision+CPU/op; op T3 KHÔNG tự bật mặc định.
- **13** verify + Non-Goal guards.

## 4. RÀNG BUỘC BẤT BIẾN (đọc kỹ — vi phạm = hỏng)
- **Sau MỖI task/slice:** append LOG `### Entry #N` (3 dấu #) + journal (D/C/T/K nếu có quyết định) + INDEX (bump `Log canonical tới **Entry #N**` + total `Σ` + dòng bảng + mega-stamp line 5 + Verify-Symbol nếu +D) + `activeContext.md` (block trên cùng + mốc "Cập nhật lúc") + `vp check` PASS + commit + push. **1 commit / 1 slice, message có #N.**
- **Import 6 layer:** domain thuần (numpy, KHÔNG cv2/torch) · kernel = DTO+ports · runtime chỉ kernel · adapters leaf chỉ kernel · profiles = composition root. import-linter 7 contracts phải KEPT.
- **🔒 Tường lửa/mạng công ty:** bị chặn → **DỪNG + BÁO user, TUYỆT ĐỐI KHÔNG vượt** (không đổi VPN/proxy/DNS/hosts, không `--insecure`, không mirror lách). Chặn = kết quả đo hợp lệ → `[bị chặn — chưa kiểm]`. Docker daemon chưa bật ≠ tường lửa (nêu lỗi nguyên văn). (K-126/§8)
- **⚠️ Shell = PowerShell 7:** `&` = background job chạy ngầm NÉ hook → **1 lệnh / 1 tool-call**; nghi ngờ → `Get-Job`/`Remove-Job -Force`. (K-129)
- **Verify CHẶT:** code = CHẠY lệnh + đọc output thật mới "xong"; thứ cụ thể (file/hàm/API) kiểm tồn tại; chưa kiểm → nhãn `[suy đoán]`/`[chưa kiểm]`. Kết mỗi output: "Đã verify / Chưa verify".
- **Verify browser** = Playwright MCP trên webcam/synthetic; URL SẠCH + tiêm `Authorization` qua `page.route`, KHÔNG `http://user:pass@host/` (làm chết mọi fetch — K-124). ERR_CONNECTION_REFUSED khi server down/tắt = nhiễu browser-log dự kiến, KHÔNG phải defect (K-119). DỪNG server nền TRƯỚC `vp verify`.
- **git:** không `add -A` (chọn file cụ thể) · không force/reset (trừ user duyệt) · không commit secret · push nhánh hiện tại. Trả lời tiếng Việt, dòng đầu `→ Chế độ: X`.
- **Máy hiện tại (cũ):** `k.nguyen.manh.toan` — CPU only, webcam + Docker (daemon chưa bật), KHÔNG GPU. Máy GPU = `toann`.

## 5. 🔴 Nợ mở khác (ngoài spec đang làm)
- K-031 rotate secret (3 API key lộ ở #457 do in env — cần rotate ở nhà cung cấp) · K-001 ARM (cần HW) · proxy thật nginx/Caddy (cần Docker bật) · soak 24/7 · ANPR .pt.
