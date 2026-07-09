# 00 — INDEX (bảng rà kiểm chứng 1 trang)

> Rà nhanh: lọc mọi dòng **🔴 / 🟡** → đó là danh sách "chưa chắc chắn / rủi ro mở" cần đối chiếu.
> Chi tiết + `Nguồn`/`Evidence` của mỗi ID nằm trong file tương ứng. Trạng thái nguồn: xem `README.md` §4.
> **Cập nhật lúc:** 2026-07-09 (máy `k.nguyen.manh.toan` — FIX GỐC hook drift-check PORTABLE: launcher `tests/drift_check.cmd` capability-test interpreter, đóng lỗ hook EXIT 9009 do `python` Store-alias; +D-056/T-022/K-057). Bản đã-commit #253 RE-VERIFY XANH tại máy này (465/1 · lint 5/0 · drift-check PASS). **Hook agentStop tự chạy launcher = PASS/EXIT 0 (VERIFIED #255).** **Dev-env launcher `scripts/vp.cmd` (cross-machine, #256).** **CI server-side `.github/workflows/verify.yml` (#257, 🔵 chờ run CI đầu): pytest+lint+drift trên windows-latest sau mỗi push.** Log canonical tới **Entry #257**. Baseline test: **465 passed/1 skipped · lint 5 kept/0 broken**. **Drift-check (`cmd /c tests\drift_check.cmd` hoặc `py tests/drift_check.py`): PASS.** Tổng **161 entry** (D58·C20·T24·K59). Review-hardened backpressure: F1 (đua drain) + D-055 (bất biến vô điều kiện); F3 = hợp đồng dùng (K-056). Còn nợ: R3 chưa wire end-to-end · POSIX chưa verify · git K-007 (máy này CÓ .git, up-to-date `origin/main` — cần user xác nhận `origin` là backup thật).

## 1. Quyết định tự ra — `01-decisions.md`
| ID | Trạng thái | Tóm tắt | Nguồn (LOG Entry) |
|---|---|---|---|
| D-001 | ✅ | Control-plane = segment tên-cố-định {epoch, ring_name} | #119,#121,#122 |
| D-002 | ✅ authority · ↩️ "tạo ring" | Authority switchover ở application; phần tạo-ring đảo bởi D-013 | #124 |
| D-003 | ✅ | Wave 3 additive, không sửa Writer/Reader | #125 |
| D-004 | ✅ | Teardown = OS handle ref-count; bỏ attach_count (fix gốc) | #126,#127 |
| D-005 | ✅ | Tiêm liveness_fn + obs vào ShmRingBuffer | #106,#109 |
| D-006 | ✅ | register_writer() explicit, không auto __init__ | #110 |
| D-007 | ✅ | ring_epoch default 0 + read() optional (backward-compat) | #111 |
| D-008 | ✅ | WriterEpochCoordinator additive + check-on-write + DI | #129 |
| D-009 | ✅ | ReaderEpochCoordinator additive + check-on-read (đối xứng) | #130 |
| D-010 | ↩️ đảo bởi D-013 | Supervisor close ring cũ (teardown B) — H2 bỏ | #131 |
| D-011 | ✅ | Chốt H2 ring-pool + reset_for_reuse() (K-012) | #134 |
| D-012 | ✅ | RingPool + make_pool_opener (H2 bước 1) | #135 |
| D-013 | ✅ | RingSupervisor H2 (pool.activate) — đảo D-002/D-010 | #136 |
| D-014 | ✅ | Test tích hợp in-process toàn hệ switchover + cyclic reuse | #137 |
| D-015 | ✅ | T-B cross-process spawn — giải K-012 cross-process (5/5) | #138 |
| D-016 | ✅ | Task 8 PBT (Hypothesis) Property 1-5 + dep hypothesis | #139 |
| D-017 | ✅ | Task 9 observability taxonomy end-to-end + catalog + regression | #140 |
| D-018 | ✅(win) 🔴(posix/Q2) | Task 7 T-C no-leak (bounded reuse) + Q2 bound ≤ n_slots → sub-spec đóng (Windows) | #141 |
| D-019 | ✅ | Bài dạy switchover `code-lessons/05b` — 12/12 mẩu + 2 sơ đồ | #142,#149,#150 |
| D-020 | ✅ | Fix A K-015: cưỡng chế drain (reset refuse + switchover defer) | #153 |
| D-021 | ✅ | Stress đa-process reader cross-process (đóng K-006) | #154 |
| D-022 | 🟡 | Q2 bound frame-drop xác nhận thực nghiệm ≤ n_slots (K-014 phần bound) | #155 |
| D-023 | ✅ | #06: dời InlineClient adapters→application + InferenceRequest nhúng ShmFrameRefData (9 test pass) | #157,#158 |
| D-024 | ✅ | #07: BoundedQueue 4 policy — giữ nguyên thiết kế Design (valid sạch) + docstring K-016 (11 test) | #160 |
| D-025 | ✅ | #08: observability (structlog + log_context + InMemoryMetrics) — giữ nguyên + style cleanup (12 test) | #162 |
| D-026 | ✅ | #09: Supervisor + cascade cooperative-first (giữ nguyên, đã fix E-10) — verify E-10 thật (6 test) | #164 |
| D-027 | ✅ | #10: package+ship+re-run — số THẬT 290/1 (không blueprint 110); wheel build + fresh-install 0.1.0 | #166 |
| D-028 | ✅ | Sub-spec zmq-inference HOÀN TẤT (đóng K-023) — codec/port/client(adapters)/server(application) + 10 test cross-process | #169,#170,#171 |
| D-029 | ✅ | Sub-spec supervisor-liveness HOÀN TẤT (đóng K-020 heartbeat + K-021 backoff) — additive #09, 4 test | #173,#174 |
| D-030 | ✅ | Sub-spec full-stack-integration-profile HOÀN TẤT (capstone) — code profile self-contained + full-stack test infer_ok≥1 cross-process, shutdown sạch (307/1, lint 5/0) | #179,#180 |
| D-031 | ✅ (A+B+C) · C chờ weight | real-detector-integration: A (coordinate-transform) + B (OnnxDetector) + C (yolov8_decode + describe_onnx, verify tensor tổng hợp + ONNX-stub) — 32 test (339/1, lint 5/0). Chặn cuối: cần user đưa path weight thật (QC-1/2) | #182,#183,#184,#187 |
| D-032 | ✅ | App demo trực quan `vision_demo_app` (xem luồng + vẽ box cv2, --save/--show/--camera/--rtsp/--onnx swap-ready) + `BrightBlobDetector` + opencv-python — 6 test, chạy tạo 12 PNG có box (345/1, lint 5/0) | #188 |
| D-033 | ✅ adapter · ⏳ cam/weight | RtspFrameSource (IFrameSource tự reconnect, DI capture, 7 test) + wire --rtsp + copy 3 weight .pt (Ultralytics YOLO 640) vào models/. Cam thật chặn K-030; weight chờ export .onnx | #189 |
| D-034 | ✅ | yolov5_decode ([1,N,5+nc] objectness, weight=YOLOv5) + VideoFileFrameSource (file video, fail-fast+EOF+loop, DI) + wire --video — 10 test (362/1, lint 5/0). Sẵn cho .onnx + validate footage | #192,#193 |
| D-035 | ✅ web · ⏳ docker | Web UI Flask MJPEG (`vision_web_app`, verify / 200 + /stats) + Dockerfile/compose (Linux, chưa verify K-032) + cờ --yolo v5/v8 + dep flask | #196 |
| D-036 | ✅ | Yolov5PtDetector (chạy thẳng .pt YOLOv5, yolov5 pkg + patch torch weights_only, box ORIGINAL_FRAME) + --pt + optional dep pt — VERIFY WSL: names car/moto/truck, detect chạy. Windows 364/1 lint 5/0 | #198 |
| D-037 | ✅ | Web UI TÁCH LUỒNG (video ⊥ detect, browser canvas overlay /boxes JSON) theo đề xuất user — verify WSL GPU ~15fps | #201 |
| D-038 | ✅ | Sub-spec media-ref-port: port `IMediaRef` (kernel) + nới `MediaPacket.media_ref` → đóng seam K-038 phần 1. Verify 369/1 · lint 5/0 | #206,#207 |
| D-039 | ✅ | pipeline-runner (engine source→executor→sink + ISink) — ĐÃ HIỆN THỰC trong PHA2 slice (D-041): PipelineRunner+RunStats+ISink code + test thật (379/1) | #208,#216,#218 |
| D-040 | 🔵 | Mở spec `scale-architecture` (PHA1 design định hướng cụm ~100 cam): capacity-model per-node + 3 mặt phẳng + bản đồ tái-dùng(base=1node)/thêm-mới + 5 trụ + lộ trình 1→10→N. 0-diag, chờ valid, chưa code | #214 |
| D-041 | ✅ | `vision-vertical-slice` HOÀN TẤT (PHA1 design-sâu + PHA2 code TDD 8 task): ISink+PipelineRunner+RunStats+CompositeSink+CollectingSink+DetectStage(Gap-2)+CountStage(stateless)+JsonlEventSink+profile+10 test. **VERIFY 379/1 · lint 5/0**. Đóng Gap-2 + hiện thực pipeline-runner (D-039). v1 stateless (né Lỗ3) | #216,#217,#218 |
| D-042 | ✅ | Spec `config-declarative` HOÀN TẤT (đóng K-040 **C2** no-config): design+req+tasks 0-diag → code TDD 4 task. `kernel/config.py`(frozen schema) + `application/config_loader.py`(parse/validate/tomllib) + `profiles/pipeline_factory.py`(registry+build_runner) + 25 test (7+12+6+2 PBT). **VERIFY 406/1 · lint 5/0** (lint qua `importlinter.api` né AV). `tomllib` stdlib, additive, no-GPU | #219–#223 |
| D-043 | ✅ parse/validate/wire · 🔴 GPU e2e | Config dùng được end-to-end: `--config` wire (`_run_from_config`, tuần tự) + `configs/` GPU-ready (3 .toml + README) + `validate_config`/`--validate` (đóng lỗ review #1). **VERIFY 421/1 · lint 5/0** (parse+validate+fake). ⚠️ YOLO/RTSP end-to-end CHƯA chạy (máy no-GPU) — nghiệm thu máy GPU. Còn nợ K-046 | #224–#226 |
| D-044 | ✅ | Bulkhead per-pipeline trong `_run_from_config` (đóng K-045): try/except Exception mỗi pipeline (chừa BaseException) → 1 pipeline lỗi BUILD/RUN KHÔNG kéo sập cả loop + log rõ + return 0/1 (C-016) + DI `build` để test. **VERIFY TDD 423/1 · lint 5/0** (2 test bulkhead) | #229 |
| D-045 | ✅ | Strict-key params (đóng K-046): mỗi builder khai báo `allowed_params` + `_check_params` từ chối key lạ (ConfigError fail-fast) ở CẢ validate_config LẪN build_runner (trước lazy-import torch). Builder chưa khai báo→lenient. **VERIFY TDD 427/1 · lint 5/0** (4 test) | #230 |
| D-046 | 🔵 design-only | Mở sub-spec `node-capacity-benchmark` (PHA1 phương pháp đo C_inf/C_dec/combined/VRAM/latency cho scale-arch R6.1). 0-diag. Bám code thật (batch dưới port=bằng chứng lỗ A1; RunStats thiếu timing→tự đo). → PHA2 = D-047 | #231 |
| D-047 | ✅ logic · 🔴 số GPU | PHA2 harness `benchmarks/` (_stats/_env/bench_capacity, DI-friendly, ngoài src K-022) + 9 test verify LOGIC (fake/CPU) — full **436/1 · lint 5/0**. CPU=cảnh báo "không phải capacity"; cuda-thiếu-torch→exit3 không số giả. Số capacity thật chờ `.[pt]` (K-048) | #232 |
| D-048 | 🔵 design/tasks | Spec `backpressure-cross-process` chốt **Mô hình A (bound-before-send)** — design + tasks (đóng A2/A3). 3 file spec 0-diag; tái dùng BoundedQueue + Metric_DTO@kernel + submit/poll async + HWM-trước-connect + FakeDetector.delay_s + PushFrameSource + cấm BLOCK+RTSP@config. Code: Wave1/2/3.1 xong (D-049) | #237–#244 |
| D-049 | ✅ | Wave 3.1 `camera_worker` async submit + drain (poll tới outbound_size==0 & in_flight==0) + hạch toán 2-tầng backpressure + property `outbound_size`. **VERIFY THẬT máy toann: fullstack 1 passed (4.09s) + full 456/1 + lint 5/0** | #244 |
| D-050 | ✅ | Wave 3.2 (cấm BLOCK+RTSP, R3/P7): làm HÀM GUARD THUẦN `assert_policy_allowed_for_source` (config_loader), KHÔNG bơm field policy vào schema (config chưa tiêu thụ → tránh over-engineer). **VERIFY: 8 test guard + full 464/1 + lint 5/0** | #245 |
| D-051 | ✅ | Wave 4+5: test overload cross-process (`detector_kind=slow` + harness n_slots/client_kwargs + window=1/queue=1) assert bất biến 2-tầng `submitted+client_drop+shm_drop==M` + dropped>0 + in_flight==0. **Spec HOÀN TẤT (đóng A2+A3). VERIFY: overload 4x không flaky + full 465/1 + lint 5/0** | #246,#247 |
| D-052 | ✅ | Cơ chế chống-drift "cực mạnh" = LINTER nhất quán bộ nhớ `tests/test_memory_consistency.py` (6 check: LOG liên tục · INDEX↔LOG · journal liên tục · total đếm-thật · ID⇄INDEX · activeContext freshness). Dogfood BẮT drift thật (LOG dup + thiếu D-036). Wire §0/§2 + hook | #248 |
| D-053 | ✅ | Củng cố chống-drift 3 tầng: hook **agentStop** `auto-drift-check` (tự chạy linter sau mỗi lượt, runCommand không loop) + PORT cơ chế vào kit (`test_memory_consistency.template.py` + §2 rule + bump AGENTS.template 15). "Cực mạnh" = máy-kiểm + tự-chạy + tái-dùng, không dựa kỷ luật | #249 |
| D-054 | ✅ | Review đối kháng code backpressure + FIX GỐC F1 (đua drain): reorder io_loop step 1b — set pending/in_flight/_sent TRƯỚC send() → đóng cửa sổ (outbound=0 & in_flight=0) frame cuối. **VERIFY: 14 test đích + overload 3/3 không flaky + full 465/1 + lint 5/0** | #252 |
| D-055 | ✅ | Bất biến bảo toàn ĐÚNG VÔ ĐIỀU KIỆN: `camera_worker.finally` teardown-trước → đếm `frames_dropped_shutdown`=leftover-van + snapshot-sau-quiesce; `_write_result` gộp 3 tầng drop (client+shm+shutdown). Đóng biên "server chết+van đầy" + F2(K-056). **VERIFY: fullstack + full 465/1 + lint 5/0** | #253 |
| D-056 | ✅ | Hook drift-check dùng LAUNCHER `tests/drift_check.cmd` capability-test interpreter (py→venv→python) thay hardcode `python` → đóng lỗ hook EXIT 9009 (Store-alias). Fix gốc portable, KHÔNG đụng rule/RULES_VERSION. Port kit. **VERIFY: launcher EXIT 0 + drift_check PASS** | #254 |
| D-057 | ✅ | Lớp trừu tượng môi trường = dev-env launcher `scripts/vp.cmd` (`env/setup/test/lint/check/verify`) auto-detect interpreter/GPU + ghi đè `VP_PYTHON`/`VP_EXTRAS` qua `env.local.cmd` (per-máy, gitignored). Gộp venv/pytest/lint(K-044)/drift → 1 giao diện cross-machine. **VERIFY: env/setup/verify EXIT 0 · 465/1·5/0·drift PASS** | #256 |
| D-058 | 🔵 | CI server-side `.github/workflows/verify.yml` (windows-latest, parity `win32`): checkout→setup-python 3.11→install→pytest→lint(importlinter.api)→drift_check. Anti-drift PHÍA-SERVER (không phụ thuộc dev chạy Kiro). CHƯA verify run CI (không chạy Actions cục bộ) | #257 |
## 2. Chỗ phải đổi — `02-requirement-changes.md`
| ID | Trạng thái | Đổi gì | Nguồn |
|---|---|---|---|
| C-001 | ✅ | Q1: publish-epoch-suy-tên → segment tên cố định | #119 |
| C-002 | ✅↩️ | Task 2: (A) lock+attach_count → (B) OS ref-count (đảo) | #123→#126 |
| C-003 | ✅ | slot header 32→256B; ring ctrl 16→64B | #103/#104,#110 |
| C-004 | ✅ | lock acquire timeout 2.0s → 0.1s | #106 |
| C-005 | ✅ | 3 test Task 4 chỉnh do đổi semantics multi-reader | #108 |
| C-006 | 🟡 | Chốt H2: switchover tái dùng pool ring (đảo một phần D-002/D-010) | #132-134 |
| C-007 | ✅ | #06: InlineClient adapters→application + InferenceRequest nhúng ShmFrameRefData (Design ERRATA E-06-1/2) | #157,#158 |
| C-008 | ✅ | #08: thêm dependency structlog>=24.1 vào [project] (cài 26.1.0) | #162 |
| C-009 | ✅ | #10: README/DoD dùng số test THẬT 290/1 (không blueprint 110) | #166 |
| C-010 | ✅ | zmq-inference: correlation THREADING (socket-owner-thread) thay asyncio.Future (step-06) | #170,#171 |
| C-011 | ✅ | full-stack profile: worker-entry đặt TRONG profile module (self-contained, shippable) thay `tests/` — src không import tests | #180 |
| C-012 | ✅ | real-detector B: thêm dep onnxruntime+onnx (optional group `.[onnx]`, cấm domain+kernel) | #184 |
| C-013 | ✅ | 4 scope user: lưu trữ HOÃN · camera user tự lắp · detector=YOLO (⚠️AGPL K-029) · bảo mật từ từ. + CLI "chạy lên xem" | #186 |
| C-014 | ✅ | CHỐT đích = MULTI-CAMERA **~100 con** (không bao giờ 1) → bài toán PHÂN TÁN nhiều-GPU/nhiều-host; K-040 A1/A2/C2/C1 thành BẮT BUỘC; base=1-node tái dùng, cần THÊM tầng cụm | #212 |
| C-015 | ✅ | Máy 1×RTX2060 = CHỈ DEV/benchmark; đích chạy phần cứng TƯƠNG LAI (scale được) → gỡ chặn K-041; kiến trúc phần-cứng-bất-khả-tri, công suất/node=tham-số-đo | #214 |
| C-016 | ✅ | `_run_from_config` đổi return code LUÔN-0 → 0 (mọi pipeline ok) / 1 (có ≥1 lỗi) — chống giấu lỗi cho vận hành nhiều-cam. 3 test cũ (toàn-ok) vẫn 0 | #229 |
| C-017 | ✅ | `build_runner`+`validate_config` giờ TỪ CHỐI key params lạ (ConfigError) thay vì bỏ qua im lặng — chống typo cấu hình chạy sai. Config/test cũ dùng key hợp lệ nên không phá | #230 |
| C-018 | ✅ | `backpressure-cross-process` R2.2 đổi ngữ nghĩa "in-flight cũ nhất" → "frame chờ-gửi (CHƯA gửi) cũ nhất" + tách R1 (4→5 AC) + Glossary 2-van. User duyệt hướng (Mô hình A) trước khi sửa requirement | #238 |
| C-019 | ✅ | `frames_dropped_backpressure` (artifact profile) = drop client-window + drop SHM-ring (2 tầng) — design §4.5 không xử lý nhánh write→None; gộp để giữ R4.1 + bất biến. **Bất biến ASSERT cross-process ở Wave 4 (D-051)** | #244,#246 |
| C-020 | ✅ | Khôi phục detail `D-036` bị thiếu trong 01-decisions.md (INDEX có dòng, file thiếu heading — nghi mất khi sync đa-máy) từ nguồn LOG #198. Phát hiện bởi linter D-052 | #248 |

## 3. Trade-off — `03-tradeoffs.md`
| ID | Trạng thái | A vs B → chọn | Nguồn |
|---|---|---|---|
| T-001 | ✅ | segment riêng vs nhúng ctrl → segment riêng | #119,#121 |
| T-002 | ✅ | OS ref-count vs attach_count RMW → OS ref-count | #126 |
| T-003 | ✅ | explicit+additive vs auto → explicit | #110,#125 |
| T-004 | ✅ | DI vs hard-code → DI (liveness/obs) | #106,#109 |
| T-005 | 🟡 | test in-process vs đa-process → in-process (tạm) | #108 |
| T-006 | 🔴 | threshold default vs đo SLA → default (chờ benchmark) | #111 |
| T-007 | ✅ | dựng lại venv (gốc) vs vá shim (ngọn) → dựng lại | #129 |
| T-008 | ✅ | nới type media_ref→Protocol (mở đa-impl) vs concrete (type chặt) → Protocol (verify 369/1 không phá) | #207 |
| T-009 | 🔵 | ISink là PORT vs callback → port (lifecycle + điểm mở nghiệp vụ) | #208 |
| T-010 | 🔵 | runner nhận executor concrete vs IExecutor port → concrete (YAGNI, chỉ 1 executor) | #208 |
| T-011 | 🔵 | vertical slice TRƯỚC vs scale-out hạ tầng trước → slice trước (giá trị thật, tránh hạ tầng rỗng) | #214 |
| T-012 | 🔵 | để-ngỏ công nghệ (transport/config/metrics) vs chốt ngay → để-ngỏ + tiêu chí (tránh đoán liều) | #214 |
| T-013 | ✅ | `tomllib` stdlib vs config lib ngoài (PyYAML/pydantic) → tomllib (zero-dep, base lean; cái mất: TOML-only + py≥3.11 + validate tay) | #219,#222 |
| T-014 | ✅ | `validate_config` KHÔNG dựng object vs dựng-thật → không-dựng (chạy validate GPU-config trên máy no-GPU; cái mất: không bắt lỗi runtime builder) | #226 |
| T-015 | ✅ | đa-pipeline TUẦN TỰ (v1) vs song song → tuần tự (additive+đúng; song song→scale-architecture khi có benchmark) | #224 |
| T-016 | ✅ | bulkhead bắt `except Exception` (rộng) vs loại cụ thể (hẹp) → rộng (chừa BaseException; kiểu lỗi camera đa dạng, hẹp sẽ thủng vách; log rõ để không nuốt bug) | #229 |
| T-017 | ✅ | key lạ fail-fast ConfigError (siết) vs cảnh báo-log (lỏng) → fail-fast (sai config báo NGAY > chạy sai âm thầm); builder chưa khai báo allowed_params → lenient (không siết registry bên thứ 3) | #230 |
| T-018 | ✅ chốt | Mô hình A (bound TRƯỚC gửi, 2 van) vs B (bound in-flight đã gửi, đúng câu chữ cũ) → **A** (server ROUTER không hủy được request đã nhận → B không giảm tải = fix ngọn) | #238 |
| T-019 | ✅ | Tái dùng `BoundedQueue` kernel vs viết mới → tái dùng (client 1 process, thread⊥thread → thỏa K-016 thread-safe; có sẵn 4 policy + đếm) | #238 |
| T-020 | ✅ | SHM-ring-đầy tính DROP (gộp `frames_dropped_backpressure` + counter riêng) vs `frames_captured`=chỉ-frame-ghi-SHM-OK → chọn gộp (giữ R4.1 + không giấu mất-frame tầng SHM = đúng mục tiêu A2). Assert Wave 4 (D-051) | #244,#246 |
| T-021 | ✅ | R3 cấm BLOCK+RTSP: hàm guard THUẦN sẵn-sàng-wire vs bơm field policy vào schema+parse+wire ngay → guard thuần (config chưa tiêu thụ policy → schema = over-engineer; guard+test nắm bản chất R3, P7) | #245 |
| T-022 | ✅ | Hook interpreter: launcher capability-test vs swap `python`→`py` vs chỉ-venv → **launcher** (2 máy setup khác nhau, không tên đơn nào đúng cả hai; py-swap=ngọn vỡ scoop; venv-only vỡ fresh-clone) | #254 |
| T-023 | ✅ | Dev-env: dispatcher `.cmd` tự-viết vs Makefile/just/nox vs lệnh tay → **`.cmd` thuần** (chạy ngay mọi Windows sạch, zero-dep; Make/just cần cài thêm = trái mục tiêu; lệnh tay = fix ngọn không xóa ma sát). Cross-OS `.sh` = mở rộng sau | #256 |
| T-024 | ✅ | CI runner: windows-latest vs ubuntu-latest → **windows-latest** (parity test `win32` cross-process; ubuntu skip chúng = cổng yếu/tự-lừa). Đổi lấy: tốn Actions-minutes hơn. Ép ngân sách → ubuntu + ghi rõ skip | #257 |

## 4. Điều nên biết / rủi ro — `04-things-to-know.md`
| ID | Trạng thái | Nội dung | Đóng khi |
|---|---|---|---|
| K-001 | 🔴 | ARM atomicity chưa test HW thật | test trên ARM |
| K-002 | ✅ | (ĐÓNG) Switchover cross-process thật — T-B 5/5 pass (D-015) | đã đóng #138 |
| K-003 | 🔴 | Teardown Linux resource_tracker chưa verify | T-C trên Linux |
| K-004 | 🔴 | REBUILD_THRESHOLD chưa tuning SLA | có benchmark |
| K-005 | 🔴 | AccessDenied cross-privilege Windows dùng fake | test quyền khác thật |
| K-006 | ✅ | (ĐÓNG win) Đa-process reader stress cross-process — 2 test 5/5 (D-021) | đã đóng #154 |
| K-007 | 🔴 | Push BỊ CHẶN QUYỀN 403 (`toannmWeb` thiếu write `mgcoder9x/VisionPlatform`) — **43 commit chưa push + 82 thay đổi working-tree chưa commit** (verify #209/#210, git on-hold) → chưa backup, rủi ro mất việc | user cấp quyền / tự push |
| K-008 | 🟡 | 2 bản memory-bank (kit là template placeholder) | luôn đọc bản gốc-repo |
| K-009 | ℹ️✅ | Log tới #127, khớp git — không lệch pha | (đã đóng) |
| K-010 | ℹ️ | Bước kế: WriterEpochCoordinator→Reader→teardown→T-B | cập nhật theo tiến độ |
| K-011 | ✅ | (ĐÓNG) tasks.md 4.1/4.2/4.3 sửa khớp QĐ B (bỏ detach/attach_register) | đã đóng #129 |
| K-012 | ✅ | (GIẢI XONG win) Lock cross-process → H2 pool + T-B 5/5 (D-011..015) | đã đóng #138 |
| K-013 | 🔴 | venv dựng lại đổi phiên bản (py3.13/numpy2.5/il2.13) | (truy vết) |
| K-014 | 🔴 | Q2 frame-drop dưới tải thật chưa đo (chỉ bound ≤ n_slots) | kịch bản tải |
| K-015 | ✅ | (ĐÓNG) reset_for_reuse cưỡng chế drain (Fix A) — refuse+defer nếu còn reader; +6 test | đã đóng #153 |
| K-016 | 🟡 | BoundedQueue THREAD-safe (threading.Lock), KHÔNG process-safe → chỉ dùng in-process | ranh giới thiết kế |
| K-017 | 🟡 | Backpressure metrics chưa wire vào sink obs (#08 đã dựng sink; wiring nguồn→sink là bước sau) | wire counter→InMemoryMetrics |
| K-018 | 🟡 | Observability #08 bỏ production log handlers (non-blocking/rotation/flush) | sub-spec production handlers |
| K-019 | 🟡 | Cardinality budget — label metric phải bounded (không packet_id/coords) | quy tắc vận hành |
| K-020 | ✅ | (ĐÓNG) Heartbeat liveness — phát hiện hang (mp.Value wall-clock); test hang→restart | đã đóng #174 |
| K-021 | ✅ | (ĐÓNG) Restart exponential backoff non-blocking (`_backoff_for` base·2^(n-1) cap) | đã đóng #174 |
| K-022 | 🟡 | `build` là dev/ship tool, không phải runtime dep (không vào [project] deps) | ranh giới dep |
| K-023 | ✅ | (ĐÓNG) InlineClient không switchover-aware → giải ở ZmqInferenceServer (ReaderEpochCoordinator) + retryable đúng | đã đóng #171 |
| K-024 | ✅ | (PHÁT HIỆN+FIX audit) InferenceServer chết vì 1 request rác → bọc per-request try/except + guard frame | đã đóng #176 |
| K-025 | ℹ️✅ | (AUDIT) BoundedQueue #07 + control-plane read_current verify SẠCH (không bug) + stress test | #177 |
| K-026 | ℹ️✅ | (AUDIT) SHM ring core SOUND; invariant reset_for_reuse (pool_size≥2, không reset ring hiện hành) làm explicit | #178 |
| K-027 | ℹ️✅ | (full-stack) Timing chống-flaky: heartbeat_timeout & shutdown_grace PHẢI > client infer timeout (tránh false-hang + kịp ghi artifact lúc finally) | #180 |
| K-028 | ℹ️✅ | NMS/thuật toán ở domain PHẢI index-based/BBox-based (domain↛kernel, không import Detection); pipeline@adapters ghép index→Detection | #183 |
| K-029 | 🟡 | LICENSE: YOLOv8/v11 = AGPL-3.0 (sản phẩm đóng phải mua license); chọn RTMDet/RT-DETR/YOLOX (Apache-2.0). OnnxDetector model-agnostic để không khoá AGPL | #184 |
| K-030 | ✅ ĐÓNG | RTSP 401 = **SAI MẬT KHẨU** (URL ban đầu `L2B40AD07` dư '0'; đúng `L2B40AD7`). KHÔNG phải ffmpeg/lockout (mọi phân tích đó sai tiền đề). Mật khẩu đúng → opened=True, frame 1080p, detect OK | #189,#197,#199 |
| K-031 | 🔴 | BẢO MẬT: config syn/resources chứa secret production thật (API/web/CIFS/RTSP nhiều cam) — lộ trong chat → user NÊN ĐỔI. AI không copy config/không echo secret | #189 |
| K-032 | 🟡 | Docker artifact (deploy/) CHƯA build/verify — máy dev không có docker; user build trên Linux | #196 |
| K-033 | ✅ (một phần đính chính) | .pt YOLOv5 chạy = yolov5 pkg + patch torch weights_only (root cause đúng). Phần RTSP-lockout trong K-033 = SAI (thật ra sai mật khẩu — xem K-034) | #198,#199 |
| K-034 | ✅ | 🎯 HỆ CHẠY THẬT: RTSP live+YOLOv5+WebUI (~5fps, 84% frame có box, detect truck thật). RTSP 401 = SAI MẬT KHẨU (dư '0'), KHÔNG phải ffmpeg. Bài học: 401-dù-creds-đúng → nghi sai-pass sớm | #199 |
| K-035 | 🟡 | Web/full-stack flaky dưới tải GPU song song (timeout tune máy rảnh, KHÔNG regression) | tload-test riêng |
| K-036 | ✅ | Web bbox "đứng yên" = detect thread chết CUDA + orphan giữ port → bulkhead try/except + reload + version-counter + pkill orphan trước restart | #203 |
| K-037 | ℹ️✅ | AUDIT base extensibility: lõi generic TỐT; 5 gap vision-layer (no PipelineRunner, no vision Stages, 1 executor, no fan-out, stringly artifacts) | audit |
| K-038 | ℹ️✅→phần 1 đóng | AUDIT: 2 world rời (World-A Stage/in-mem ⊥ World-B SHM cross-proc) do media_ref concrete. Phần 1 đóng bởi D-038 (port IMediaRef) | #206,#207 |
| K-039 | ✅ | Seam K-038 đóng PHẦN 1: port IMediaRef (mở chỗ cắm). Còn ShmMediaRef+PipelineRunner+wiring-SHM (Non-Goal, sub-spec sau) | #207 |
| K-040 | ℹ️ | SỔ LỖ HỔNG KIẾN TRÚC (audit vs DeepStream/Frigate/Triton): A1 no-batching🔴 · A2 no-backpressure-cross-proc🔴 · C2 no-config🔴 · C1 metrics-per-proc🟠 · B2 retry-trùng🟠 · D2 SHM-leak-crash🟠 · C4 zmq-plaintext🟠 · D1 copy-hot-path🟡 · A3 no-HWM🟡. KHÔNG phải bug — trục CHƯA có cho scale; đóng khi vào production thật | #211 |
| K-041 | ⚠️ | CÔNG SUẤT: 100cam@max trên 1×RTX2060(6GB) KHÔNG khả thi (~10–40× vật lý: decode 2500fps + infer 5–10k/s + VRAM). Phải thiết kế NGÂN SÁCH GPU + config-giảm + motion-gate + sub-stream + batch + shed. Bước đúng: BENCHMARK 2060 thật trước, rồi design | #213 |
| K-042 | ℹ️✅ | SELF-REVIEW scale-arch: 4 lỗ (1 capacity thiếu latency/fan-out-biến-thiên/GPU-contention · 2 decode bỏ trống · 3 **analytics-CÓ-STATE vs Stage-stateless → camera-affinity** · 4 failover split-brain rủi-ro-cao) — đã vá vào design; đủ định-hướng, chưa đủ thi-công | #215 |
| K-043 | ℹ️✅ | ĐÀO SÂU slice design: 5 lỗ (A–E) tìm khi đọc code thật + đã đưa vào design | #217 |
| K-044 | ℹ️✅ | AV chặn `lint-imports.exe` → lint qua `importlinter.api`; `.venv` per-machine (K-013 lặp) → dựng lại mỗi máy | #219,#223 |
| K-045 | ✅ | **LỖ REVIEW #2 ĐÓNG (D-044):** ĐÃ có bulkhead per-pipeline trong `_run_from_config` (try/except Exception + return 0/1 + DI build). 1 pipeline lỗi KHÔNG còn kéo sập loop. VERIFY 423/1 | #226,#229 |
| K-046 | ✅ | **LỖ REVIEW #3 ĐÓNG (D-045):** strict-key — mỗi builder khai `allowed_params`, `_check_params` từ chối key lạ (fail-fast) ở validate_config + build_runner. Typo không còn nuốt im lặng. VERIFY 427/1 | #226,#230 |
| K-047 | ✅ | **MÔI TRƯỜNG máy-3 `endgame`:** venv trỏ máy `k.nguyen.manh.toan` (hỏng) → ĐÃ dựng lại (scoop py3.13.12) + **VERIFY THẬT 421/1 · lint 5/0** (khớp #226). Version drift py3.11.9→3.13.12 ghi để truy vết (K-013) | #228 |
| K-048 | 🟡 | **ĐÍNH CHÍNH:** máy `endgame` CÓ **RTX 2060** (nvidia-smi) — nói "no-GPU" (#219–#231) là SAI (chưa kiểm nvidia-smi); bản chất = GPU có, torch/yolov5 chưa cài. → đã cài `.[pt]` nhưng ra torch CPU-only (K-049) | #232 |
| K-049 | 🔴 | `.[pt]` trên Windows kéo **torch 2.12.1+cpu** (cuda_available=False) → benchmark GPU CHƯA chạy dù có 2060; cần CUDA wheel (~2.5GB, index cu124). Version drift numpy→2.4.6/opencv→headless; baseline **436/1 idle** OK; full-stack flaky = load-induced (K-035, không regression) | #233 |
| K-050 | 🟢 cứu · 🔴 lặp | SỰ CỐ `.git` bị tiến trình NGOÀI xoá giữa phiên (máy `k.nguyen.manh.toan`, 09:47) — ĐÃ restore từ Recycle Bin + `git fsck` sạch + bundle backup ngoài folder (43 commit an toàn). Công cụ xoá [chưa xác định]; working-tree chưa commit + rủi ro xoá lại VẪN mở | #235,#236 |
| K-051 | 🔵 | BẤT BIẾN: `frames_submitted` đếm TẠI LÚC GỬI (không lúc enqueue) — nếu sai, DROP_OLDEST đếm trùng → vỡ `submitted+dropped==captured`. Phải verify khi code (wave 2.4/2.5, PBT) | #238 |
| K-052 | 🟢 baseline · 🔴 .git | Máy `toann` KHÔNG có `.git` (drift-check dùng file-state+diagnostics). **Baseline ĐÃ tự-verify tại đây (#241):** rebuild venv scoop py3.13.12 → `pytest` **436/1 (45.92s)** + lint `importlinter.api` **5/0** (khớp #232/#234, không torch) | #240,#241 |
| K-053 | ✅ | `camera_worker` có 2 tầng backpressure độc lập (SHM ring `write()→None` ⊥ client submission-window). `metrics_snapshot()` CHỈ đếm tầng client → camera_worker phải cộng `frames_dropped_shm` khi ghi artifact (nếu không bất biến vỡ âm thầm = lỗ A2). **ASSERT bất biến cross-process Wave 4 (D-051)** | #244,#246 |
| K-054 | ✅ | Drift TỒN ĐỌNG bị linter D-052 bắt: LOG dup legacy #90/91/95/96 (2 AI append cùng ngày → allowlist, không renumber vì append-only) + thiếu detail D-036 (khôi phục từ LOG #198, C-020) | #248 |
| K-055 | ✅ | Hook `runCommand` KHÔNG hiểu `;` separator (dán vào argv → "No such file") → fix gốc: 1-script entry `tests/drift_check.py` gọi cả 2 linter; hook + §0 dùng 1 lệnh. Bài học: hook KHÔNG ghép lệnh bằng `;`/`&&` | #250 |
| K-056 | 🟡 | Ranh giới client backpressure (KHÔNG bug — hợp đồng dùng): F2 `metrics_snapshot` đọc-sau-quiesce (io idle); F3 không trộn `infer()` sync + `submit()` async nặng (sync bỏ qua flow-control window) | #252 |
| K-057 | ✅ | Interpreter Python KHÔNG portable giữa máy Windows (python.org có `py` · scoop có `python` · Store-alias `python` tồn-tại-mà-hỏng-9009) → hook/CI dò CAPABILITY (`--version` exit 0), KHÔNG hardcode tên/không presence-test. Đóng bằng launcher D-056 | #254 |
| K-058 | ✅ | Dev-env launcher: đổi máy chỉ cần `scripts\vp.cmd setup` → `vp verify`; auto-detect sai thì tạo `scripts\env.local.cmd` (gitignored) đặt `VP_PYTHON`/`VP_EXTRAS`; máy GPU thêm `pt` vào extras (nhớ K-049 torch-CPU). `vp lint` né AV sẵn (K-044) | #256 |
| K-059 | 🔵 | CI `verify.yml`: KHÔNG verify được cục bộ → chỉ biết xanh/đỏ khi push (dán log Actions); flaky risk K-035 (đỏ-flaky≠regression); actions checkout@v4/setup-python@v5 [chưa kiểm trên CI]; PAT-URL không ảnh hưởng Actions (GITHUB_TOKEN). Đóng ✅ khi CI xanh lần đầu | #257 |

## Tổng quan trạng thái (cập nhật 2026-07-06 — phiên máy-3 `endgame`, sync đầy đủ config-declarative + môi trường)
- **Tổng 127 entry:** D 47 (D-001..047) · C 17 (C-001..017) · T 17 (T-001..017) · K 49 (K-001..049). Baseline **436 passed/1 skipped · lint 5/0** — ✅ **ĐÃ TỰ VERIFY phiên này** (máy `endgame`, scoop py3.13.12, LOG #232: pytest 48.70s EXIT 0 + `importlinter.api` LINT_OK True). K-047+K-045+K-046 đóng; +9 test bench.
- **🔧 benchmark harness (D-047, #232):** `benchmarks/` (ngoài src) code xong + verify LOGIC (9 test fake/CPU). Số capacity THẬT chờ `.[pt]`.
- **⚠️ ĐÍNH CHÍNH K-048:** máy `endgame` CÓ **RTX 2060** (nvidia-smi) — "no-GPU" ở #219–#231 là SAI (chưa kiểm). Bản chất: GPU có, torch/yolov5 chưa cài → benchmark THẬT + config GPU end-to-end CÓ THỂ chạy ngay tại đây sau `pip install -e .[pt]`.
- **🔵 MỞ spec `node-capacity-benchmark` (D-046, design-only, #231):** phương pháp ĐO capacity per-node (C_inf batch 1/8/16 · C_dec + combined decode+infer · VRAM · latency p50/p95/p99) cho `scale-architecture` R6.1. 0-diag. Trung thực K-047: máy `endgame` no-GPU → template `[chưa đo]`, số thật CHỈ ở máy GPU. Bám code thật (batch dưới port = lỗ A1; RunStats thiếu timing → harness tự đo; cuda.synchronize; đo combined decode+infer). Chờ user valid → PHA2 code harness (verify logic máy dev + chạy số máy GPU).
- **✅ CẢ 2 LỖ REVIEW CONFIG ĐÓNG (doubt-driven #226 → vá #229/#230):** **K-045 bulkhead** (D-044): `_run_from_config` bọc mỗi pipeline try/except Exception (chừa BaseException) → 1 pipeline lỗi BUILD/RUN không kéo sập loop + return 0/1 (C-016). **K-046 strict-key** (D-045): mỗi builder khai `allowed_params` + `_check_params` từ chối key lạ (fail-fast) ở validate_config + build_runner (trước lazy-import torch) → typo config không nuốt im lặng (C-017). TDD, verify **427/1 · lint 5/0**.
- **🔴 CÒN NỢ (không phải lỗ config):** GPU end-to-end (pt/cuda/rtsp) chưa chạy (máy no-GPU, nghiệm thu máy GPU) · git on-hold K-007 · hướng scale (launcher song song T-015 / benchmark 1-node K-041).
- **🥇 config-declarative HOÀN TẤT + dùng được end-to-end (D-042 #219–#223 + D-043 #224–#226):** đóng lỗ hổng **C2 no-config** (K-040). Chuỗi giá trị: file `.toml` → `config_loader`(tomllib, T-013) → `pipeline_factory`(registry + `build_runner` + `validate_config`, T-014) → `PipelineRunner` chạy thật. Wire `--config`/`--validate` vào `vision_slice_app` (additive, tuần tự T-015) + `configs/` GPU-ready. **VERIFY parse+validate+fake = 421/1** (LOG #226). 🔴 YOLO/RTSP end-to-end CHƯA chạy (máy no-GPU) → nghiệm thu máy GPU.
- **🔴 CÒN NỢ config (2 lỗ review doubt-driven, CHƯA vá):** **K-045** bulkhead per-pipeline (1 pipeline lỗi kéo sập cả — nguy hiểm ~100 cam, đề xuất làm KẾ) · **K-046** params typo nuốt im lặng (validate strict-key).
- **🔴 MÔI TRƯỜNG (K-047):** phiên này ở máy thứ 3 (`endgame`) — venv trỏ máy cũ + không Python đăng ký (có scoop py3.13) → **KHÔNG tự chạy lại pytest/lint được**. Cần dựng lại venv (py3.11.9→3.13) mới verify được baseline thật.
- **🥇 vision-vertical-slice HOÀN TẤT (D-041, #218):** lát cắt dọc CHẠY THẬT: source→DetectStage(Gap-2)→CountStage(stateless)→sink qua PipelineRunner. Hiện thực nền pipeline-runner+ISink (D-039✅). 8 file mới + 10 test, **379/1 · lint 5/0**. Bước 1 roadmap scale xong.
- **🥇 SPEC vision-vertical-slice (D-041, PHA1 design-only):** lát cắt dọc đầu tiên chạy thật (source→DetectStage→CountStage-stateless→sink qua PipelineRunner). Đóng Gap-2 (detector-as-Stage) + hiện thực pipeline-runner (D-039 kích hoạt). v1 STATELESS né Lỗ3. CHỜ user valid → PHA2 code. Đây là bước ĐẦU của roadmap scale (T-011 slice-trước).
- **🔬 SELF-REVIEW scale-arch (K-042):** doubt-driven tìm 4 lỗ trong design + đã vá (capacity thiếu latency/fan-out/GPU-contention · decode bỏ trống · analytics-CÓ-STATE cần camera-affinity · failover split-brain). Đủ ĐỊNH-HƯỚNG, chưa đủ THI-CÔNG.
- **🏗️ SPEC scale-architecture (D-040, PHA1 design-only):** kiến trúc cụm ~100 cam, phần-cứng-tương-lai (2060=dev). Capacity-model per-node (tham-số-đo) + 3 mặt phẳng + tái-dùng base=1node + 5 trụ (motion-gate/sub-stream/batch/budget/shed) + lộ trình vertical-slice→1→10→N. CHỜ user valid, CHƯA code.
- **⚠️ CÔNG SUẤT (K-041):** cấu hình user = 1 máy/1 GPU (RTX 2060)/max fps/nhiều analytics/lưu tùy. 100cam@max trên 1×2060 KHÔNG khả thi (~10–40× vật lý). → thiết kế NGÂN SÁCH-GPU + config-giảm + motion-gate + sub-stream + batch + shed. Bước đúng: BENCHMARK 2060 thật TRƯỚC khi viết capacity design. CHỜ user duyệt benchmark + chốt phần cứng (giữ 2060 → N chục cam; hay tăng GPU → 100).
- **🎯 ĐÍCH CHỐT (C-014):** ~100 camera → hệ PHÂN TÁN nhiều-GPU/nhiều-host. K-040 (A1/A2/C2/C1) = BẮT BUỘC (hết "suy đoán"). Base = "1 node" tái dùng; cần THÊM tầng cụm (shard/batch/config/metrics/fan-out). Bước kế: chốt 4 fork (phần cứng/fps/nghiệp vụ/lưu trữ) → design-first tài liệu capacity+cụm, validate 1→10→100.
- **📋 SỔ LỖ HỔNG KIẾN TRÚC (K-040):** audit đối kháng vs hệ lớn — 9 trục CHƯA có cho scale (A1 batching · A2 backpressure cross-proc · C2 config · C1 metrics · B2 idempotency · D2 crash-cleanup · C4 security · D1 copy · A3 HWM). KHÔNG phải bug; đóng khi vào production thật.
- **⏸️ MỐC DỪNG hiện tại:** media-ref-port ✅ (port IMediaRef, D-038). pipeline-runner ⏸️ DESIGN-ONLY (D-039, chưa code — hoãn theo phản biện phạm vi user, "để nghiệp vụ thật dẫn dắt"). Base known-good, an toàn dừng.
- **🔴 rủi ro vận hành lớn nhất:** git on-hold → **43 commit chưa push + 82 working-tree chưa commit** = chưa backup (K-007). + K-031 secret production nên rotate.
- **UI:** Web MJPEG (`vision_web_app`, verify `/`+`/stats` chạy máy dev — mở browser localhost:8000) thay cv2 window. cv2 window vẫn còn (`--show`).
- **Docker:** `deploy/` Dockerfile+compose+README (Linux, giải RTSP-401 + ONNX) — CHƯA verify (dev không docker, K-032).
- **Detector chọn version:** `--yolo v5`(mặc định, weight user)/`v8`. Full **362/1 · lint 5/0**.
- **CHẶN CUỐI:** user export .pt(YOLOv5)→.onnx ở env syn → mount + `--onnx --yolo v5` → detect thật.
- **Nguồn frame:** synthetic · camera · RTSP (tự reconnect) · **video-file** (mới) — demo app cờ `--video`/`--rtsp`/`--camera`/`--onnx`.
- **Detector:** BrightBlobDetector · FakeDetector · OnnxDetector + **yolov5_decode & yolov8_decode** (chọn theo describe_onnx). Full **362/1 · lint 5/0**.
- **CHẶN CUỐI:** user export .pt→.onnx (env syn) → AI wire chạy YOLO thật.
- **RTSP:** RtspFrameSource (tự reconnect, 7 test) + --rtsp. Camera thật reachable nhưng ffmpeg-Windows 401 (K-030); chạy Linux sẽ ổn.
- **Weight:** 3 file .pt YOLO (imgsz 640, vehicle car/moto/truck) copy vào models/ (gitignore). CẦN export .pt→.onnx (ultralytics+torch) → khuyến nghị user export ở env syn (Linux, version-compat).
- **⚠️ K-031 bảo mật:** secret production lộ trong config → user rotate.
- **▶️ APP DEMO XEM LUỒNG:** `python -m vision_platform.profiles.vision_demo_app --frames 12 --save demo_frames` → PNG có box xanh bám ô sáng (BrightBlobDetector). `--show` live · `--camera 0`/`--rtsp URL` khi có camera · `--onnx path --labels` khi có YOLO (swap-ready). Full **345 passed/1 skipped · lint 5/0**.
- **▶️ CHẠY ĐƯỢC:** `python -m vision_platform.profiles.vision_fullstack_profile --duration 5` → chuỗi camera→SHM→ZMQ→DetectorPipeline(FakeDetector)→box ORIGINAL_FRAME cross-process. Chạy thật: 70–71 frame, infer_ok=100%, 0 restart, detection_sample box=[4,4,8,8] (transform đúng). Swap Noise→RTSP + Fake→YOLO khi có camera/weight.
- **Scope user (C-013):** lưu trữ HOÃN · camera user tự lắp · detector=YOLO (⚠️AGPL) · bảo mật từ từ.
- **🎯 SUB-SPEC real-detector-integration HOÀN TẤT (A+B):** Phần A `domain/letterbox_transform.py` + `domain/nms.py` (index-based, K-028) + `adapters/detector_pipeline.py` (Decorator, resize DI, NMS) — đóng BUG toạ độ sau letterbox. Phần B `adapters/onnx_detector.py` (model-agnostic, preprocess/postprocess DI, lazy import) + optional dep `.[onnx]` (C-012) + verify onnxruntime 1.27.0/onnx 1.22.0 chạy THẬT (Identity model). 24 test mới (property 300 + unit + 4 onnx guard). Full **331 passed/1 skipped · lint 5/0** (contract onnx negative-test có răng). ⚠️ K-029 license YOLO AGPL — adapter model-agnostic để không khoá.
- **🎯 SUB-SPEC full-stack-integration-profile HOÀN TẤT (CAPSTONE):** `profiles/vision_fullstack_profile.py` self-contained (run_profile + camera_worker + inference_server_entry) + `tests/test_fullstack_integration.py`. Chứng minh THẬT cross-process camera→SHM→(ZMQ)inference→detections + shutdown sạch. Full **307 passed/1 skipped · lint 5 kept/0 broken**. Tái dùng component (không viết lại). Điều chỉnh worker-placement C-011; timing chống-flaky K-027.
- **🎯 SUB-SPEC zmq-inference-service HOÀN TẤT (đóng K-023):** codec@kernel + IInferenceClient@kernel/ports + ZmqInferenceClient@adapters + InferenceServer@application + 10 test (5 codec/port + 5 cross-process/switchover). Full **300 passed/1 skipped · lint 5 kept/0 broken** · pyzmq 27.1.0/msgpack 1.2.1. Switchover-aware verify thật (test_zmq_switchover).
- **🎯 MODULE 03 #01–#10 HOÀN TẤT** (code + bài học code-lessons #01–#10): full **290 passed/1 skipped · lint 5 kept/0 broken** · wheel 0.1.0 shippable. #06 inference · #07 backpressure · #08 observability · #09 supervisor · #10 package đều ✅ verify thật.
- **SUB-SPEC SWITCHOVER: Task 1–9 ✅ TRÊN WINDOWS** (full 242 passed/1 skipped · lint 5 kept/0 broken · T-B 5/5). K-002 + K-012 đã đóng (H2 + T-B). Dạy học 05b 12/12 mẩu + 2 sơ đồ ✅.
- **✅ đã đóng/verify:** K-002, K-009, K-011, K-012 + hầu hết D/C/T.
- **🟡 một phần:** K-007 (43 commit chưa push + 82 working-tree chưa commit) · K-008 (2 bản memory-bank).
- **🔴 rủi ro MỞ (ranh giới trung thực — cần môi trường/quyền ngoài Windows, KHÔNG claim xong):**
  K-001 (ARM HW) · K-003 (POSIX teardown) · K-004 (REBUILD_THRESHOLD SLA) · K-005 (AccessDenied cross-privilege) · K-007 (push chặn quyền 403, 43 commit chưa push) · K-013 (venv version) · K-014 (throughput tải fps thật).
- **✅ đã đóng thêm (2026-07-04):** K-006(D-021) · K-015(D-020) · **K-020+K-021 heartbeat/backoff (D-029)** · **K-023 zmq switchover-aware (D-028)**.
- **🟡 ranh giới thiết kế (ghi nhận, không phải lỗi):** K-016 (BoundedQueue thread-only) · K-017 (backpressure metrics chưa wire sink) · K-018 (log handlers production) · K-019 (cardinality) · K-022 (build là dev tool).
- **✅ K-015 ĐÃ FIX (Fix A, D-020):** reset_for_reuse cưỡng chế drain (refuse+defer nếu còn reader) — lỗ hổng torn-frame doubt-driven đã đóng, +6 test.
- **Chờ NGƯỜI HỌC:** cổng Feynman 05b (đã hỏi 3 câu) + Feynman #05 gốc. AI KHÔNG tự đánh "hiểu".
- Bước kế AI-làm-được: đều cần môi trường khác (POSIX/ARM) hoặc tải thật (Q2) → không verify trên Windows.
