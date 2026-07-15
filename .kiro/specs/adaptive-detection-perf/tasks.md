# Implementation Plan — Adaptive Detection Performance

> Dẫn xuất từ `design.md` + `requirements.md`. **TDD nghiêm ngặt:** mỗi task viết test (fake clock, tiêm — KHÔNG sleep cứng) TRƯỚC, rồi code tới GREEN, rồi `scripts\vp.cmd verify` giữ baseline (761/2) không vỡ.
> **Layer (import-linter):** config DTO → `kernel`; `should_detect` + reuse `changed_ratio` → `domain`; fail-fast input-size → `adapters` (OnnxDetector); wiring cadence/motion vào loop + CLI/TOML → `profiles`.
> **Cổng đo (Task 0):** đo baseline TRƯỚC khi chốt default; default giữ = hành vi hiện tại (experimental) tới khi có số. Lever không cải thiện đo được → KHÔNG giữ (R3.2).

## Overview
Thi công điều-tiết detect CPU no-GPU theo waves: đo baseline trước → config+policy thuần (kernel/domain) → motion-gate reuse (domain) → fail-fast input-size (adapters) → wire vào `_detect_loop`+CLI (profiles) → TOML surface → verify tổng + webcam E2E. Deploy-time INT8 là task gated (đo accuracy) có thể tách. Mọi thay đổi additive; mặc định = hành vi hiện tại (R4.1).

## Task Dependency Graph
```json
{
  "waves": [
    { "wave": 0, "tasks": ["0"], "depends_on": [] },
    { "wave": 1, "tasks": ["1", "3"], "depends_on": [] },
    { "wave": 2, "tasks": ["2"], "depends_on": ["1"] },
    { "wave": 3, "tasks": ["4"], "depends_on": ["1", "2", "3"] },
    { "wave": 4, "tasks": ["5"], "depends_on": ["4"] },
    { "wave": 5, "tasks": ["6"], "depends_on": ["3"] },
    { "wave": 6, "tasks": ["7"], "depends_on": ["4", "5"] }
  ]
}
```
Ghi chú: Task 6 (INT8) gated + độc lập nhánh (chỉ cần Task 3 fail-fast) — có thể tách spec riêng nếu môi trường chặn (ultralytics/calibration). Task 7 là gate cuối.

## Tasks

- [ ] 0. Đo baseline + cổng quyết định default (script cố định, KHÔNG one-liner lặp)
  - **ĐÃ ĐO (#395):** `session.run`/s baseline = **8.52/s** (p50 111ms) qua `bench_capacity --mode infer --onnx --imgsz 640`; verify input-size cố định (bench `--imgsz 416` → InvalidArgument 416≠640). CÒN: CPU% khi detect-loop chạy + độ trễ bắt vật mới + bảng so-sánh-cadence (chờ Task 1/2/4 để đo hiệu ứng).
  - Thêm/ mở rộng script đo (họ `bench_capacity`/tools cố định) đo: `session.run`/s baseline hiện tại trên máy này (re-verify #352); CPU% khi detect-loop chạy; độ trễ bắt vật mới.
  - Đo thử cadence `min-interval`/`every-n` + motion-gate (cảnh tĩnh vs động) → bảng so sánh.
  - Xuất số → dùng chốt default `detectMinIntervalMs`/`detectEveryN`/`motion*`; nếu chưa đủ SLA → giữ experimental (KHÔNG tuyên bố "tối ưu").
  - _Requirements: 3.1, 3.2_

- [x] 1. `DetectionCadenceConfig` @kernel (fail-fast) + `should_detect` @domain (thuần)
  - `DetectionCadenceConfig` frozen: `detectMinIntervalMs>=0`, `detectEveryN>=1`, `motionGate:bool`, `motionPixelDiffThreshold`, `motionMinAreaRatio`, `motionMaxConsecutiveSkip>=0`, `motionRoi:optional`, `experimental`. Validate fail-fast; **`detectMinIntervalMs <= displayLeaseMs`** (nhận displayLeaseMs để kiểm) → `ConfigError`.
  - `should_detect(now_ns, last_detect_ns, frame_version, last_detect_version, cfg) -> (bool, reason)` THUẦN: every-N (version % N) + min-interval (now - last >= interval). Clock/version tiêm.
  - Test: mặc định (interval=0/every-n=1) → luôn True; interval>0 chặn tới hạn; every-n bỏ đúng frame; config boundary đậu/rớt; P5 invariant.
  - _Requirements: 1.1, 1.3, 4.2_

- [x] 2. Motion-gate reuse trong loop (domain helper, KHÔNG kéo Stage)
  - Helper thuần bọc `domain.motion.changed_ratio` + trạng thái (prev-frame, consecutive_skips) cho loop bespoke: trả `(should_skip, ratio, forced)`; frame đầu/đổi-shape → không skip; `ratio<min_area` → skip trừ khi đạt `maxConsecutiveSkip` → ép đi tiếp; có chuyển động → reset đếm.
  - Tái dùng ngữ nghĩa `MotionGateStage` (đã test) NHƯNG không phụ thuộc `MediaPacket`.
  - Test (numpy nhỏ): tĩnh→skip, động→detect, quá-hạn→ép, frame-đầu→đi tiếp; ROI + illumination_robust (reuse `changed_ratio` args).
  - _Requirements: 1.2_

- [x] 3. Fail-fast model input-size @adapters (OnnxDetector.setup)
  - Trong `setup`: đọc `session.get_inputs()[0].shape`; nếu H/W là số cố định và ≠ model_size mong đợi (tiêm qua param hoặc so với DetectorPipeline model_h/w) → raise lỗi rõ (nêu model-thật vs config). Dynamic axis (None/str) → cho qua (không chặn).
  - Test: stub model input cố định 640 + config 416 → raise; khớp 640 → pass; dynamic → pass.
  - _Requirements: 2.1_

- [x] 4. Wire cadence + motion-gate vào `_detect_loop` + CLI (profiles, additive)
  - `vision_web_app._detect_loop`: trước `detector.detect`, gọi motion-gate helper + `should_detect`; skip → giữ overlay (không feed store), cập nhật last_detect khi có detect. CLI: `--detect-min-interval-ms`/`--detect-every-n`/`--motion-gate`(+params). Mặc định = hành vi hiện tại.
  - (Nếu áp cả `vision_slice_app`: cân nhắc — có thể để loop web trước, slice sau.)
  - Verify: import OK (không unit-test được loop) + webcam E2E (cadence bật → detect thưa, video vẫn mượt, box không giật).
  - _Requirements: 1.1, 1.2, 4.1_

- [x] 5. Bề mặt cấu hình TOML `[detection]` + merge precedence
  - Thêm khoá `[detection]` (cùng tên CLI) vào config loader + merge CLI > TOML (tiền lệ D-086) + validate fail-fast.
  - **ĐỔI so với câu chữ (C-023):** KHÔNG nhét vào `AppConfig` schema (buộc `[[pipelines]]` giả cho web app pipeline-less) → dùng `load_detection_config` standalone + `_parse_detection` dùng chung. Reuse `DetectionCadenceConfig` (kernel) làm đích parse (1 nguồn sự thật). Thêm `--config` cho `vision_web_app` + `_merge_detection` (default argparse→None sentinel).
  - Test (`test_config_detection_toml.py`, 14 test): parse full/empty; bad-types→ConfigError; invariant→ConfigError; TOML-only; CLI-override-TOML; motion-gate OR; roi TOML-only; template `configs/web/example_web_detection.toml`.
  - **VERIFY (#400):** `scripts\vp.cmd verify` = 819 passed/2 skipped (+14) · lint 6 kept/0 broken · drift PASS. D-121.
  - _Requirements: 4.2, 1.3_

- [ ] 6. (GATED, có thể tách) INT8 quantize artifact + đo accuracy
  - Pipeline quantize offline (`onnxruntime.quantization`) tạo `yolov8n.int8.onnx` + calibration ảnh nhỏ; nạp qua `--onnx` như model khác (Task 3 fail-fast áp dụng).
  - ĐO: speed vs accuracy drop trên tập ảnh nhỏ (vd bus.jpg + vài ảnh) so fp32. Giữ CHỈ khi cải thiện đo được (R3.2).
  - _Requirements: 2.2, 3.1, 3.2_

- [~] 7. Verify tổng + webcam E2E (gate cuối) — MỘT PHẦN xong
  - ✅ `scripts\vp.cmd verify` = 819/2 · lint 6/0 · drift PASS (#400). Unit/property should_detect/motion-gate/config/fail-fast đều xanh.
  - ✅ **ĐO CPU% ĐỊNH LƯỢNG (R3.1, #401, D-122/K-105):** `benchmarks/measure_cadence_cpu.py` (harness cô lập reuse `should_detect`) → min-interval 200ms **−60% CPU**, 500ms **−80% CPU** (onnx yolov8n CPU máy toann). Lever THẬT tiết kiệm → giữ (R3.2).
  - ⬜ CÒN: đo motion-gate CPU (cần scene TĨNH thật — synthetic không đại diện) + độ-trễ-bắt-vật-mới + **E2E RTSP/webcam user nhìn** (cần URL RTSP / webcam) + [tuỳ] GPU khi cài torch.
  - _Requirements: 1.1–4.2 (toàn bộ) · design §Testing Strategy_

## Notes
- **TDD bắt buộc:** test (fake clock/tiêm) TRƯỚC → GREEN → `scripts\vp.cmd verify` giữ 761/2.
- **Không code trước khi user valid design + requirements + tasks.**
- **Default chờ số Task 0** — không tuyên bố "tối ưu" nếu chưa đo; giữ experimental.
- **Deploy-time ⊥ runtime:** input-size/INT8 KHÔNG đổi được lúc runtime (model shape cố định `[1,3,640,640]` verify #392) — chỉ chọn artifact + fail-fast.
- **Ràng buộc liên-spec P5:** `detectMinIntervalMs <= displayLeaseMs` (overlay) cưỡng chế fail-fast — chống box hết hạn trước detect kế.
- **Anti-sunk-cost (R3.2):** lever không cải thiện đo được → KHÔNG giữ (ghi lý do vào journal).
