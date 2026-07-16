# end.md — HANDOFF chuyển máy (frontier LOG #422 · Σ304)

> ⚠️ **File này là GHI CHÚ BÀN GIAO, KHÔNG phải nguồn sự thật (K-064/K-098).** Phiên/máy sau BẮT BUỘC
> chạy §0 TRƯỚC khi tin bất cứ dòng nào ở đây:
> ```
> git status && git log -n 3 --oneline
> scripts\vp.cmd check
> ```
> Frontier THẬT do `vp check` xác định. Nếu số ở đây lệch `vp check` → tin `vp check`, sửa memory trước.

---

## 0. TRẠNG THÁI CHỐT (tại thời điểm viết — 2026-07-16)

- **Frontier:** LOG **#422** · Σ**304** (D131·C23·T35·**K115**) · `vp check` **PASS** (9 tầng memory + RULES_VERSION 16 sync 5 mirror + 14 self-test).
- **Branch:** `chore/dev-env-launcher-portable-hooks`. Trước khi push phiên này: HEAD == origin == `61560b8`, behind=0 ahead=0. **CÓ nhiều thay đổi CHƯA COMMIT** (toàn bộ việc #415→#422 + records) — phiên này sẽ commit + push (user duyệt rõ "push hết lên").
- **Máy hiện tại:** `k.nguyen.manh.toan` — **CÓ Docker · CÓ webcam · KHÔNG GPU**. (Máy `toann` có GPU+RTSP, không Docker — nhiều máy đẩy chéo, luôn làm ở frontier thật.)
- **Baseline test:** **837 passed / 2 skipped · lint 6 kept / 0 broken · drift PASS**. (Phiên #422 KHÔNG đổi code sản phẩm → baseline giữ, không cần chạy lại full verify.)

---

## 1. CHỈ THỊ THƯỜNG TRỰC (mỗi lượt, chống drift cực mạnh)

- Trả lời **tiếng Việt**, dòng đầu `→ Chế độ: <X>`.
- **Cadence:** thiết kế rõ → đọc-lại-valid nhiều lần → chính xác kiểm-chứng-được → MỚI code. Fix **bản chất, KHÔNG vá ngọn**. KHÔNG bịa/suy đoán. Kết luận kèm **"Đã verify / Chưa verify"**. "Xong" = CHẠY thật + đọc output.
- **KHÔNG tiết kiệm token.** Hướng **sản phẩm thương mại, lâu dài**. Khuyến nghị phải NÊU LÝ DO chính xác.
- **Chống phức tạp vô ích (R3.2):** đọc code xem cơ-chế-sẵn-có TRƯỚC khi đẻ config/lever mới (đã bắt: maxAgeMs trùng lease #417, updatedAtMs sai clock #416, thread-tuning vô ích #422).
- **Ghi sổ mỗi lần triển khai:** append LOG (`AI-IMPLEMENTATION-LOG.md`) + journal (`ai-decision-journal/`) + INDEX (bump ID/total Σ/logref `Log canonical tới **Entry #N**` + `Tổng **M entry** (D..·C..·T..·K..)` + stamp) + `activeContext.md` → `vp check` PASS.
- **Lệnh routine QUA LAUNCHER cố định** (`scripts\vp.cmd verify|check`); tránh `python -c` lặp. Shell nuốt `$`/`&`-chaining → dùng lệnh đơn / browser-MCP.
- **DỪNG server nền TRƯỚC `vp verify`** (đốt CPU → flaky K-035 giả). Port TIME_WAIT → đổi port (8011/8012...).
- Verify browser bằng **Playwright MCP** trên **webcam thật** (`mcp_playwright_browser_*`). Nguồn synthetic moving-square BỆNH LÝ, không dùng đánh giá tracking (K-112).
- Python qua `vision-platform\.venv\Scripts\python.exe` hoặc `scripts\vp.cmd`. Không `git add -A` (K-085); không force/reset; push chỉ khi user cho rõ.

---

## 2. VIỆC ĐÃ XONG PHIÊN NÀY (#415 → #422) — spec `overlay-tracking-refactor`

Bối cảnh: user "mở web browser phát hiện cực nhiều lỗi + mất bbox + tắt chậm". Đã fix 6 bug + đo perf, verify browser MCP webcam THẬT:

- **#415 / D-127** — pile-up 193 lỗi `ERR_INSUFFICIENT_RESOURCES`: gốc `setInterval(tick,80)` fire-and-forget chồng fetch. Fix = **poll self-rescheduling** (1 in-flight, setTimeout finally) ⊥ **render requestAnimationFrame**. Verify 193→0.
- **#416 / D-128** — S1 "box không sát": server phơi `vx/vy` (chuẩn-hoá/giây) ra `/overlay` → client ngoại suy `pos+vel*dt`. **BỎ updatedAtMs** (clock server monotonic_ns ≠ client performance.now).
- **#417 / D-129** — S2 "tắt chậm": phát hiện `maxAgeMs` TRÙNG `displayLeaseMs` → BỎ. Fix = expose CLI `--overlay-display-lease-ms` / `--overlay-candidate-lease-ms`. Verify lease 350 → box 25/25 không flicker.
- **#418 / D-130** — lệch 1px canvas↔video: border `#v`→`#wrap` + `font-size:0`. Aligned=true, network 748/748 200 OK.
- **#419 / D-131** — video ĐEN khi tab nền: MJPEG stall → `visibilitychange`→visible `img.src='/stream?t='+now` + `img.onerror`→reconnect.
- **#420** — VERIFY robustness (resize responsive + reconnect-stress 8× + 2-client), KHÔNG bug mới.
- **#421 / K-114** — churn "mất bbox nhiều" GỐC = **detection thứ-3+ spurious conf 0.25–0.33** sinh displayId mới liên tục. FIX verify 5+→2 ID: hysteresis `--overlay-create-conf 0.45 --overlay-sustain-conf 0.30`. Removal miss-based ~350ms; "~1s" ≈ detector-tail lúc rời khung.
- **#422 / K-115** — đo `intra_op_num_threads` (câu hỏi "còn nhanh hơn không"): **default 30.61fps GẦN TỐI ƯU** (intra=8=32.85 trong nhiễu; intra=1/16 tệ) → **KHÔNG hard-code** (hại máy ít-core) → **0 đổi code**. Nhanh hơn NỮA cần deploy-time (input416/INT8/GPU), không phải runtime tuning.

**Lệnh chạy web (config thương mại tốt):**
```
vision-platform\.venv\Scripts\python.exe -m vision_platform.profiles.vision_web_app ^
  --camera 0 --onnx models/yolov8n.onnx --yolo v8 --model-size 640 --coco-labels ^
  --overlay-motion --overlay-display-lease-ms 350 ^
  --overlay-create-conf 0.45 --overlay-sustain-conf 0.30 --host 127.0.0.1 --port 8012
```

**FILE đụng:** `vision-platform/src/vision_platform/profiles/vision_web_app.py` (client `_PAGE` JS + CLI + `_detect_loop`) · `runtime/overlay_projection.py` · `runtime/display_stabilizer.py` · `kernel/overlay_view.py` (DisplayTrack +vx/vy) · `kernel/overlay_config.py` · `tests/test_overlay_projection.py` · spec `.kiro/specs/overlay-tracking-refactor/{design,requirements,tasks}.md`.

---

## 3. BƯỚC KẾ (chờ user chốt hướng — đều là commit LỚN cho sản phẩm thương mại)

1. **(B) Production-hardening (K-101) — KHUYẾN NGHỊ TRƯỚC nếu sắp deploy.** Lý do chính xác: web đang chạy **Flask dev-server** (tài liệu Flask nói KHÔNG dùng production: đơn luồng, không bảo mật). Cần **WSGI (waitress)** + **auth endpoint**. Gap best-practice THẬT, không speculative.
2. **(A) Wave C — hợp nhất `domain/tracker`** (1 nguồn track cho analytics+display) = nền nghiệp vụ (đếm/vạch/zone). Refactor LỚN đụng analytics → **GATED**, chờ user duyệt rõ. Làm khi cần tính năng đếm.
3. **(C) Đưa hysteresis #421 thành DEFAULT** (đổi `OverlayConfig` default create0.45/sustain0.30 thay cờ CLI) — vì churn-by-default là lỗi thương mại rõ. Quyết định riêng (đổi hệ đã verify).
4. (tuỳ) Deploy-time perf: re-export input 416 (~2×) hoặc INT8 — cần ultralytics/mạng; hoặc GPU trên máy `toann`.

---

## 4. ĐIỂM MỞ / RỦI RO CÒN LẠI (đọc journal `04-things-to-know.md` để đầy đủ)

- **K-101** 🟡 — Flask dev-server chưa production-ready (WSGI+auth) — xem mục 3(B).
- **K-029** 🟡 — LICENSE: yolov8n là **AGPL-3.0**; sản phẩm đóng cần đổi model Apache (RTMDet/RT-DETR/YOLOX) hoặc mua Enterprise. `OnnxDetector` model-agnostic → đổi 2 hàm DI + file .onnx.
- **K-035** 🟡 — flaky supervisor ~2/5 full-run dưới tải cực đại (giảm-thiểu-mạnh, chưa đóng tuyệt đối); chạy riêng 5/5 ổn.
- **K-115** ✅ — thread-tuning KHÔNG là lever (kết luận âm tính, đừng đo lại). Mở tiếp nếu muốn đo live-under-contention (khác đo cô lập).
- Verify browser: chỉ webcam thật; synthetic moving-square không đại diện tracking (K-112).

---

## 5. FILE ĐỌC KHI KHỞI TẠO PHIÊN MỚI

- `memory-bank/activeContext.md` (block #422 = mới nhất, đọc top ~50 dòng)
- `AI-IMPLEMENTATION-LOG.md` (tail #415→#422)
- `ai-decision-journal/00-INDEX.md` (header stamp + logref canonical + bảng D/K) · `04-things-to-know.md` (K mới nhất)
- `.kiro/specs/overlay-tracking-refactor/{design,requirements,tasks}.md`
- `vision-platform/src/vision_platform/profiles/vision_web_app.py` (web app + client JS)

---

## 6. TÓM 1 DÒNG
Overlay web ĐÃ mượt + sạch lỗi (6 bug fix + verify webcam MCP); perf detect đã chạm trần hợp-lý trên CPU (không tuning runtime thêm được — #422); bước kế thương mại = **WSGI+auth (K-101)** hoặc **Wave C hợp-nhất-tracker (GATED)** — CHỜ user chốt. Chạy §0 (`vp check`) trước khi tin file này.
