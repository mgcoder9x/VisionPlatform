# END.md — Bàn giao chuyển máy (frontier #371, 2026-07-13)

> Đọc file này ĐẦU TIÊN khi sang máy mới. Nguồn sự thật đầy đủ: `AGENTS.md` + `memory-bank/activeContext.md`
> (block mới nhất) + `ai-decision-journal/00-INDEX.md`.

## §0. LÀM GÌ ĐẦU PHIÊN (bắt buộc, theo AGENTS §0)
1. `git status` + `git log -n 3 --oneline` — xác nhận cây sạch + HEAD.
2. `cmd /c scripts\vp.cmd check` — drift-check (KHÔNG tin số dán ở đâu; tự chạy). Phải PASS.
3. Đọc `memory-bank/activeContext.md` (block #371 mới nhất) + 5 entry cuối `AI-IMPLEMENTATION-LOG.md` + `ai-decision-journal/00-INDEX.md` header.
4. Nếu drift FAIL hoặc có thay đổi chưa-commit lệch activeContext → DỪNG, đồng bộ trước.

## §1. TRẠNG THÁI HIỆN TẠI (đã verify #371)
- **Nhánh git:** `chore/dev-env-launcher-portable-hooks`. **HEAD đã push:** `26c5bec` (== upstream, tree sạch).
- **Baseline code:** **647 passed / 2 skipped · lint 5 kept/0 broken · drift PASS · RULES_VERSION 16** (khớp 5 mirror).
- **Journal:** **Σ252** = D102·C21·T33·K96. **LOG canonical tới #371.**
- **Máy:** CÓ GPU (RTX 2060 6GB) + camera + **KHÔNG cài được Docker** → deploy GPU phải NATIVE. `py` KHÔNG có → dùng `scripts\vp.cmd` hoặc `.venv\Scripts\python.exe`.
- **Venv chính** `vision-platform/.venv` (Python 3.13) đã có: onnxruntime-gpu 1.27 + 8 gói nvidia CUDA13 (~2GB) + onnx + numpy + opencv. torch VẮNG. GPU đã BẬT được (K-088, CUDA_LOADED=True).

## §2. CƠ CHẾ VẬN HÀNH (lặp mỗi lượt)
- **Verify:** `cmd /c scripts\vp.cmd verify` (pytest+lint+drift). Chỉ drift: `cmd /c scripts\vp.cmd check`. 1 file: `cmd /c "scripts\vp.cmd test tests/a.py"`.
- **Ghi sổ MỖI lượt đổi trạng thái:** LOG entry (4 mục) + journal D/C/T/K + INDEX (canonical #N + `Tổng Σ..` + dòng ID) + `activeContext.md` (block + mốc "Cập nhật lúc") → rồi `vp check` PASS.
- **Git an toàn (K-085):** LUÔN soi `git diff --cached --stat` TRƯỚC commit (số +/- bất thường = cờ đỏ). Xác nhận push bằng so `git rev-parse HEAD` == `git rev-parse @{u}` (in "PUSHED-OK").
- **PowerShell nuốt/mangle output** (git progress → Exit giả): workaround ghi ra `_tmp_*.log` rồi `type`/`Get-Content`, xóa sau. `Remove-Item` từng file một (2 tham số positional lỗi).
- **Network (tải model/pip)** = **CHỜ ĐÈN XANH RÕ** của user. Không tự chạy.
- Kết mỗi output: "Đã verify / Chưa verify". Trả lời tiếng Việt.

## §3. CHỐNG DRIFT 4 LỚP (`tests/drift_check.py`, điểm vào `vp check`)
- **C1–C7:** bản-ghi↔bản-ghi (LOG liên tục · INDEX↔LOG max · journal liên tục · total đếm-thật · ID⇄INDEX · activeContext freshness · INDEX-cites∈LOG). *Lưu ý: đừng viết "#0"/"task #0" trong INDEX — C7 hiểu là trích LOG #0 → FAIL (đã dính #366, sửa "task-0").*
- **C8 doc↔code:** trường `Verify-Symbol: relpath::symbol` → symbol phải còn trong code (hiện 11 khớp).
- **RULES_VERSION sync** 5 mirror + **self-test 11 case** (guard chống regex-rot). Tất cả PASS = frontier lành.

## §4. ĐÃ LÀM PHIÊN NÀY (#365 → #371)
- **#365:** đóng đo đa-luồng GPU (K=1/2/4 → aggregate 46.6/78/**104.7** infer/s, dưới-tuyến-tính; +K-092). Baseline so sánh cho batch-mux.
- **#366–#371: BỘ SPEC `batch-mux` (design-first) HOÀN CHỈNH + 3 vòng đọc-lại-valid** (xem §5).

## §5. TRỌNG TÂM: SUB-SPEC `batch-mux` (`.kiro/specs/batch-mux/`)
Mục tiêu: gộp N-camera → 1 `session.run` `[B,3,640,640]` nâng trần inference `C_inf` (roadmap #3 scale-architecture). **3 file design+requirements+tasks, getDiagnostics=0, CHƯA code dòng nào.**
- **#366 (D-100):** design.md. **K-093 (verify chạy thật):** model `yolov8n.onnx` hiện tại input CỐ ĐỊNH `[1,3,640,640]` → `run` batch>1 = `InvalidArgument` → **cần RE-EXPORT dynamic-batch** (task-0).
- **#367 (requirements.md):** 5 Requirement EARS (đúng-đắn/latency/nghiệm-thu-bằng-đo/backward-compat/tiên-quyết-dynamic).
- **#368 (tasks.md):** Task 0 = **SPIKE BENCH làm CỔNG** (re-export + đo B=1/2/4/8 vs 104.7/s → không vượt thì DỪNG, chống sunk-cost).
- **#369 (D-101, review 1):** đọc `TrackingStage`/`IouTracker` thật → +Property 6 (thứ tự frame per-camera, vì IouTracker phụ thuộc thứ tự) + R1.4 + mục "batch-mux ↔ analytics stateful" (mux ở tầng detector STATELESS, thượng nguồn stage stateful).
- **#370 (K-095, verify):** chứng minh chiến lược test khả thi KHÔNG-network — tạo model ONNX tí-hon dynamic (`onnx.helper` ReduceSum `['N',3,4,4]`) chạy batch>1 + identity đúng.
- **#371 (D-102, review 2):** đọc `InferenceServer.serve`/`camera_worker`/`BoundedQueue` thật → **CHỐT điểm tích hợp = `InferenceServer.serve`** (server one-at-a-time; camera=process riêng; BoundedQueue thread≠process-safe K-016 ⇒ gộp cross-camera CHỈ ở server). Scatter theo ZMQ `ident`. Backpressure camera-side (SHM+window) trực giao. +Task 4 (wire InferenceServer, additive cờ batch, batch=1=cũ).

**NGHI VẤN CỐT LÕI (Lỗ 1, [chưa kiểm]):** batch-mux có thể KHÔNG thắng K-session-rời (104.7/s@K4) vì yolov8n nhỏ + GPU đã lấp khá đầy → **nghiệm thu = ĐO** (Task 0), kết luận "không đáng" vẫn hợp lệ.

## §6. HƯỚNG TIẾP (bước kế)
- **Task 0 (spike bench) = việc kế duy nhất — CẦN ĐÈN XANH NETWORK:** re-export `yolov8n` dynamic (`ultralytics export(dynamic=True)` trong venv throwaway, repro K-083/K-087, giữ `.venv` chính) → đo B=1/2/4/8 trên GPU vs 104.7/s + latency. GATE: vượt → build Task 1-5; không vượt → DỪNG, ghi "không đáng".
- **Task 1-3** (preprocess/postprocess_batch + IBatchDetector + BatchMuxer) THUẦN logic no-GPU/no-network (dùng model tí-hon K-095) — làm được sau khi có model dynamic HOẶC để verify logic độc lập.
- **Task 4** wire vào `InferenceServer.serve` (cross-process). **Task 5** PBT + regression.
- Hoặc: hướng khác trong scale-architecture roadmap (#4 config, #5 scheduler...) — nhưng batch-mux là roadmap #3, ưu tiên.

## §7. CHẶN / RÀNG BUỘC
- **Network** (re-export model, pip) = chờ đèn xanh RÕ của user.
- **Docker KHÔNG cài được** → GPU deploy NATIVE (TOML `device=cuda`, D-097/098/099 đã sẵn).
- **Model dynamic-batch** chưa có (K-093 — model hiện tại cố định batch=1). Task 0 phải re-export trước.
- **License (K-029):** YOLOv8 Ultralytics = AGPL-3.0 → sản phẩm đóng thương mại cần license Ultralytics hoặc model Apache (RTMDet/RT-DETR/YOLOX).

## §8. FILE QUAN TRỌNG
- `.kiro/specs/batch-mux/{design,requirements,tasks}.md` — spec trọng tâm hiện tại.
- `memory-bank/activeContext.md` — con trỏ "đang làm gì" (block #371 mới nhất).
- `ai-decision-journal/00-INDEX.md` — bảng rà 1-trang (D/C/T/K + canonical #371 + Σ252).
- `AGENTS.md` — luật đầy đủ (RULES_VERSION 16). `scripts/vp.cmd` — launcher lệnh.
- `.kiro/specs/scale-architecture/design.md` — capacity model (batch-mux là roadmap #3 của nó).

**Đã verify:** end.md viết lại khớp frontier #371 (đọc activeContext/INDEX thật). **Chưa verify:** batch-mux throughput (Task 0 chờ đèn xanh).
