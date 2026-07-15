# end.md — HANDOFF chuyển máy / phiên sau (đọc TRƯỚC khi làm gì)

> **Mục đích:** phiên sau (hoặc máy khác) đọc file này để hiểu trạng thái + tiếp tục CHÍNH XÁC.
> **Cập nhật:** 2026-07-14 — frontier **LOG #382** · máy `k.nguyen.manh.toan` (**KHÔNG GPU · CÓ Docker**).
> ⚠️ File này thay cho mọi transcript cũ (bản trước bị dán nhầm chat — đã dọn).

---

## 0. ĐẦU PHIÊN — chạy TRỌN (bắt buộc, chống drift)
1. `git status` + `git log -n 3 --oneline` — xác lập frontier THẬT (đừng tin số dán).
2. `scripts\vp.cmd check` — drift-check 3 khối (memory C1–C9 + RULES 5-file + self-test). PHẢI `DRIFT-CHECK: PASS`.
   - Nếu FAIL → SỬA bản ghi cho khớp thực tế TRƯỚC khi làm tiếp.
   - **C9 mới (bản-ghi↔GIT):** nếu báo "local SAU upstream N commit" → `git pull` + reconcile TRƯỚC (nền stale).
3. Đọc: `memory-bank/activeContext.md` (block mới nhất) + `progress.md` + 5 entry cuối `AI-IMPLEMENTATION-LOG.md` + `ai-decision-journal/00-INDEX.md` (bảng D/C/T/K + canonical).
4. Python: dùng `scripts\vp.cmd <verb>` hoặc `vision-platform\.venv\Scripts\python.exe` — **KHÔNG** alias `python`/`py` trần.

## 1. TRẠNG THÁI HIỆN TẠI (frontier #382)
- **Nhánh:** `chore/dev-env-launcher-portable-hooks`. **HEAD = origin =** `3201d29` ("update" — commit gộp #377–#382, đã push). Tree sạch.
- **Baseline code:** **654 passed / 2 skipped · lint 5 kept/0 broken · drift PASS** (verify thật).
- **Journal:** **Σ264** = D107·C22·T35·K100. **LOG canonical tới #382.**
- **Máy:** **KHÔNG GPU · CÓ Docker** · CÓ webcam. onnxruntime CPU-only, torch vắng. Deploy GPU (nếu có máy khác) phải NATIVE.

## 2. ĐÃ LÀM GẦN NHẤT (#377 → #382)
- **#377 (D-105):** Web UI xem webcam LIVE — adapter `WebcamFrameSource` (DI capture, self-heal, `is_finite=False`) + wire `--camera`. Verify 654/2 + `/stats` detect live. **NHƯNG** user thấy bbox **nhấp nháy**.
- **#378 (D-106/T-034/K-100):** Mở sub-spec `web-live-overlay-sync` design-first V3 — fix GỐC flicker: tách **raw inference truth ⊥ display projection**, atomic `OverlayStateStore` + epoch/lease/frame-identity, `/overlay` additive giữ `/boxes` legacy. 3 vòng adversarial → tự reconcile. `HOLD_MS=500` = mitigation SAI TẦNG (K-100), KHÔNG phải fix.
- **#379–#381 (D-107/T-035/C-022):** Thêm **C9 "git-reality gate"** vào drift-check — đóng lớp drift DUY NHẤT C1–C8 không phủ (local behind upstream = nền stale, K-064/K-085/K-098). Verify empiric lệnh git (#380 bắt+sửa lỗi hướng behind/ahead) → CODE TDD (#381): `_collect_git_facts` (read-only/offline/tiêm-được) + C9 FAIL hẹp khi behind>0 + 3 self_test case. **654/2 · drift PASS · C9-GIT PASS.**
- **#382:** Audit design overlay bằng CODE THẬT `vision_web_app.py` — **6/6 static-evidence đúng** → tạo `requirements.md` (5 EARS ↔ đúng 14 property) + `tasks.md` (13 task/7 waves TDD). Bộ spec HOÀN CHỈNH, tất cả 0-diag. **CHƯA code.**

## 3. TRỌNG TÂM KẾ TIẾP (chờ user quyết)
**Thi công `web-live-overlay-sync` (fix gốc bbox flicker) — bộ spec đã sẵn, CHƯA code.**
- Đọc `.kiro/specs/web-live-overlay-sync/{design,requirements,tasks}.md`.
- Thứ tự (Task Dependency Graph): **wave 1 = Task 1 (DTO frozen @kernel) + Task 2 (matching/EMA thuần @domain)** → Task 3 stabilizer → Task 4 OverlayStateStore authority → 5 scheduler → 6 health / 7 reconnect → 8 `/overlay` endpoint (+contract import-linter cấm display DTO↮analytics) + 9 video-independence → 10 browser lease + 11 legacy `/boxes` → 12 verify tổng + webcam E2E.
- **TDD nghiêm:** test (fake clock, tiêm event) TRƯỚC → code GREEN → `vp verify` giữ 654/2.
- **Task 0 (diagnostic behind-flag):** đo cadence p50/p95/p99 THẬT trước khi chốt policy default (lease/ghostSla) — KHÔNG bịa "tối ưu".
- **Giới hạn trung thực:** MJPEG `<img>` không cho JS biết frame đang hiển thị → V1 chỉ freshness/stability, KHÔNG pixel-perfect.

## 4. HƯỚNG KHÁC (parked — có điều kiện)
- **batch-mux** (`.kiro/specs/batch-mux/`): bộ spec đủ (3 vòng review). Task 0 = spike bench = CỔNG. **CHẶN: cần GPU + network re-export model dynamic** (máy khác) — KHÔNG chạy trên máy no-GPU này.
- **GPU/torch:** chặn bởi network install (máy này no-GPU dù sao).
- **RTSP IP-camera** (K-030): ffmpeg-opencv vs Dahua digest 401 — cần hướng khác (snapshot HTTP / GStreamer / clip).
- **K-035 flaky residual:** supervisor/step_09 hiếm khi flaky dưới tải cực đại (đã giảm-thiểu-mạnh, chưa đóng tuyệt đối — cần máy mạnh/CI).

## 5. CHỐNG DRIFT — CƠ CHẾ (dùng, đừng phá)
- **1 lệnh:** `scripts\vp.cmd check` (hoặc `verify` = test+lint+drift). Đầu phiên + trước khi tuyên bố "xong".
- **9 tầng máy-kiểm** (`tests/test_memory_consistency.py`): C1 LOG liên tục · C2 INDEX↔LOG max · C3 journal liên tục · C4 total đếm-thật · C5 ID⇄INDEX · C6 activeContext freshness · C7 phantom-cite · C8 doc↔code (Verify-Symbol) · **C9 git-reality (behind upstream)**. + RULES_VERSION 16 khớp 5 file + self-test guard-the-guard 14 case.
- **Sổ 4 việc** `ai-decision-journal/` (D=quyết định · C=đổi so yêu cầu · T=trade-off · K=điều-nên-biết) + `00-INDEX.md` (bảng 1 trang). Mọi lần triển khai → append LOG + cập nhật journal/INDEX/activeContext → `vp check` PASS.
- **Bài học đắt:** K-085 (soi `git diff --stat` trước commit, KHÔNG `git add -A` mù) · K-098 (RESUME phải chạy TRỌN §0, không chỉ `git status`) · K-064 (không tin output dán).

## 6. FILE QUAN TRỌNG
- `.kiro/specs/web-live-overlay-sync/{design,requirements,tasks}.md` — **spec trọng tâm hiện tại** (fix flicker).
- `.kiro/specs/drift-check-git-reality/design.md` — thiết kế C9 (đã code).
- `tests/test_memory_consistency.py` — 9 tầng drift-check + self-test. `tests/drift_check.py` — entry point.
- `vision-platform/src/vision_platform/profiles/vision_web_app.py` — web UI hiện tại (còn `HOLD_MS=500` mitigation, sẽ thay khi làm overlay spec).
- `memory-bank/activeContext.md` (con trỏ) · `progress.md` (chân lý hiện tại) · `ai-decision-journal/00-INDEX.md` (D/C/T/K + canonical #382).
- `AGENTS.md` — luật đầy đủ (RULES_VERSION 16). `scripts/vp.cmd` — launcher lệnh.

## 7. CHẶN / LƯU Ý
- Máy no-GPU → không làm được batch-mux Task 0 / GPU benchmark ở đây.
- Bảo mật (K-031): secret production từng lộ ngoài repo → user nên rotate. Không commit secret/`.env`.
- Git: commit từng mốc message rõ; KHÔNG force/reset-hard/xóa nhánh; push nhánh (không push thẳng main).
