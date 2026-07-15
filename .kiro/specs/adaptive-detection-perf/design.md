# Design — Adaptive Detection Performance (điều tiết detect trên CPU no-GPU)

> **TRẠNG THÁI: DESIGN-FIRST, CHƯA CODE.** Chờ user đọc-lại-valid trước khi tạo requirements/tasks/code.
> Nguồn sự thật kiến trúc: `AGENTS.md`. Spec bám CODE THẬT đã đọc (#392) — mọi khẳng định cụ thể có nhãn verify.
> **Nguyên tắc:** fix BẢN CHẤT (trần CPU-inference), không vá ngọn; tách deploy-time ⊥ runtime; đo trước khi tuyên bố "nhanh hơn".

## Glossary
- **Trần inference (C_inf):** số lần `session.run` tối đa/giây của model trên máy — nút cổ chai gốc throughput detect CPU.
- **Detect-cadence:** tần suất THỰC SỰ chạy detector (có thể < FPS video). Overlay lease "làm mượt" khoảng trống giữa 2 lần detect.
- **Deploy-time lever:** đòn bẩy quyết định lúc CHỌN model artifact / khởi động (đổi .onnx, input-size, INT8). Không đổi được khi đang chạy.
- **Runtime lever:** đòn bẩy đổi được khi đang chạy / qua config (detect mỗi N frame, motion-gate, min-interval).
- Thuật ngữ nền (letterbox, NMS, motion-gate, lease): xem `knowledge-base/00-GLOSSARY.md` + spec `web-live-overlay-sync`.

## Overview
Cho hệ web-live (webcam→YOLO→overlay) chạy trên máy **KHÔNG-GPU**, giảm tải CPU / tăng đáp ứng mà KHÔNG làm bbox giật, theo cách **cấu-hình-được** và **an toàn cho sản phẩm thương mại**. Gom các đòn bẩy tốc độ vào MỘT spec vì chúng tương tác (cadence ↔ lease ↔ accuracy ↔ model artifact). KHÔNG tối ưu overlay-wire (không phải nút cổ chai — xác định #392).

**Phi mục tiêu (Non-Goals):** GPU/CUDA (máy khác); batch-mux (spec riêng, cần GPU); đổi thuật toán tracking; production WSGI server / auth (backlog K-101); transport WebRTC (spec frontend riêng).

### Vấn đề & TẠI SAO (Forces)
**Trần thật = CPU inference.** Đo THẬT máy này (#395, `bench_capacity --mode infer --onnx yolov8n.onnx --imgsz 640`): **8.52 infer/s** (p50 110.9ms · p95 177.5ms · p99 203ms). (#352 ghi 11.72/s ở máy/điều-kiện khác — số máy này thấp hơn.) Video-loop chạy nhanh hơn detect nhiều lần (#391: video≫detect). Vậy:
- Detector KHÔNG kịp mọi frame → phần lớn frame không được detect. **Chấp nhận được** vì overlay lease (`web-live-overlay-sync`) giữ box mượt giữa 2 lần detect.
- Nhưng `_detect_loop` hiện chạy detector **hết sức có thể** trên mọi frame-version mới → **đốt 100% một lõi CPU liên tục** ngay cả khi cảnh TĨNH hoặc khi không cần nhịp detect cao.

**Forces (mâu thuẫn phải cân):**
1. CPU hữu hạn ↔ muốn detect thường xuyên để bắt vật mới nhanh.
2. Detect thưa (tiết kiệm CPU) ↔ lease phải đủ dài để không mất box giữa 2 detect ↔ lease dài → ghost lâu khi vật đã rời (mâu thuẫn 3 chiều — điểm cốt lõi).
3. Độ chính xác (model to / input 640) ↔ tốc độ (model nhỏ / input 320 / INT8).
4. Cấu-hình-được (linh hoạt vận hành) ↔ fail-fast an toàn (cấu hình sai không chạy ngầm sai).

## Architecture
### Phát hiện BẢN CHẤT (verify empiric #392) — tách deploy-time ⊥ runtime
`describe_onnx('models/yolov8n.onnx')` #392: input `images=[1,3,640,640]` **CỐ ĐỊNH** (không dynamic axis), output `[1,84,8400]`. **Hệ quả:**
- **KHÔNG THỂ đổi input-size lúc runtime** cho model shape-cố-định: feed 416 vào model-640 → `onnxruntime InvalidArgument` — **verify empiric #395** (`bench --imgsz 416` → `Got: 416 Expected: 640`). Đây cũng chứng minh nhu cầu fail-fast (lỗi hiện tối nghĩa). "Input-size cấu-hình-được" là **deploy-time** (phải có .onnx đúng input-size, hoặc model dynamic-axes).
- `DetectorPipeline` letterbox frame về `model_h×model_w` rồi feed `inner.detect`; nếu `model_h/w ≠ input model thật` → crash. Hiện KHÔNG fail-fast đối chiếu `--model-size` với input THẬT (`describe_onnx`) → cấu hình sai chỉ lộ khi crash. **Lỗ an toàn cần đóng.**
- **INT8 quantize** = file `.onnx` quantized RIÊNG (offline + calibration) → cũng **deploy-time artifact**.

⇒ **Bản chất:** đòn bẩy chia 2 nhóm rạch ròi. Máy này không re-export ngay được (cần ultralytics/mạng, K-087) → **nhóm RUNTIME (giảm tần suất detect) an toàn + sẵn-dùng ngay**; nhóm DEPLOY-TIME (input-size/INT8) cần artifact mới + fail-fast.

### Vị trí trong hệ (layer)
- **domain:** hàm THUẦN `should_detect(...)` (cadence policy) + tái dùng `domain.motion.changed_ratio`. Không I/O.
- **profiles (`vision_web_app`/`vision_slice_app`):** gọi policy trong `_detect_loop` để QUYẾT ĐỊNH có `detector.detect()` không, TRƯỚC khi feed `OverlayStateStore`. Không đụng authority/store.
- **adapters:** `OnnxDetector.setup` thêm fail-fast đối chiếu input shape (dùng `describe_onnx` sẵn có) + (tùy chọn) `SessionOptions`.
- **Không** thêm phụ thuộc ngược layer; không kéo `MotionGateStage` (runtime/stages) vào profile — chỉ dùng hàm domain.

## Components and Interfaces
### C1 — `should_detect` (domain, thuần)
Quyết định "frame này có nên chạy detector không" từ: (a) **min-interval** (ns tối thiểu giữa 2 detect — throttle), (b) **every-N** (chỉ detect mỗi N frame-version), và (c) **max-interval / HEARTBEAT** (ns TỐI ĐA được phép không detect — nếu vượt thì ÉP detect, override mọi cổng khác gồm motion-gate). Clock tiêm → test xác định. Trả `(bool, reason)` với reason ∈ {FIRST, MAX_INTERVAL, MIN_INTERVAL, EVERY_N, OK}.
- **Chọn** (vs hard-code sleep trong loop): tách policy (thuần, test được) khỏi vòng lặp I/O — đúng hexagonal; chỉnh qua config không đụng loop.
- **max-interval là FIX GỐC cho K-103** (webcam E2E #398: motion-gate/cadence bỏ detect quá lâu → vật đứng-yên hết lease → mất box). Đặt heartbeat ở TẦNG POLICY (không sửa đếm-frame của motion-gate) → tổng quát: bất kỳ cổng nào (motion-gate/every-N/min-interval) muốn skip, nếu `now - last_detect >= maxInterval` thì vẫn detect. Bất biến `detectMinIntervalMs <= detectMaxIntervalMs <= displayLeaseMs` (khi max>0) ĐẢM BẢO detect lại TRƯỚC khi lease hết → track khớp được refresh → box KHÔNG mất. `max=0` = tắt heartbeat = hành vi hiện tại (additive).

### C2 — Motion-gate tái dùng trong loop
Dùng THẲNG `domain.motion.changed_ratio(prev, curr, threshold, mask, illumination_robust)` (đã tồn tại, đã test): `ratio < min_area_ratio` → bỏ detect lần này, giữ overlay (lease lo). `max_consecutive_skip` ép detect định kỳ chống bỏ sót vật đứng-yên (ngữ nghĩa đã có ở `MotionGateStage`, tái dùng logic — không viết lại).
- **Loại hướng B** (gắn `MotionGateStage`): Stage cần `MediaPacket` + thuộc pipeline Stage → coupling thừa vào loop bespoke.
- **Loại hướng C** (refactor web-app sang PipelineRunner): đúng dài hạn nhưng blast-radius lớn → tách spec riêng nếu cần.

### C3 — Fail-fast model input-size (adapters)
`OnnxDetector.setup`: đọc `session.get_inputs()[0].shape`; nếu H/W cố định và ≠ `model_size` cấu hình (và không dynamic) → raise lỗi RÕ ("model input 640 nhưng config 416 — re-export hoặc sửa config"). Đóng lỗ §Architecture.

### C4 — Deploy-time artifacts (follow-on, có thể tách Task riêng)
- **Input-size khác:** nạp .onnx export ở size đó (deploy chọn file). Không nút runtime.
- **INT8:** pipeline quantize offline (`onnxruntime.quantization`) tạo `yolov8n.int8.onnx` + calibration nhỏ + ĐO accuracy drop. Nạp như model khác (không đổi code detector).
- **SessionOptions:** thử `intra_op_num_threads`/`graph_optimization_level`. **[chưa kiểm]** lợi ích (mặc định đã hết-core + graph-opt ALL) → **benchmark-gated**: chỉ giữ nếu Task 0 đo vượt; không cải thiện → KHÔNG thêm.

### Bề mặt cấu hình
- **CLI:** `--detect-min-interval-ms`, `--detect-every-n`, `--motion-gate` (+`--motion-threshold`/`--motion-min-area`/`--motion-max-skip`/`--motion-roi`), giữ `--model-size`.
- **TOML** `[detection]`: cùng khoá; merge precedence CLI > TOML (tiền lệ D-086).
- **Mặc định = HÀNH VI HIỆN TẠI** (min-interval=0, every-n=1, motion-gate=off) → additive.

## Data Models
- **`DetectionCadenceConfig`** (kernel, frozen, fail-fast): `detectMinIntervalMs:int>=0`, `detectMaxIntervalMs:int>=0` (0=tắt heartbeat), `detectEveryN:int>=1`, `motionGate:bool`, `motionPixelDiffThreshold`, `motionMinAreaRatio`, `motionMaxConsecutiveSkip`, `motionRoi:optional [0,1]`, `experimental:bool`. Invariants: nếu `detectMaxIntervalMs>0` thì `detectMinIntervalMs <= detectMaxIntervalMs` (throttle không được lớn hơn heartbeat) — kiểm trong `__post_init__`. Liên-spec (kiểm ở `assert_cadence_fits_lease` lúc wire): **`detectMinIntervalMs <= displayLeaseMs`** VÀ (nếu max>0) **`detectMaxIntervalMs <= displayLeaseMs`** → nếu vượt thì box hết hạn trước detect kế → giật/mất box → `DetectionConfigError`.
- Không DTO mới cho kết quả detect (đi qua `OverlayStateStore.apply_completion` như hiện tại). Motion state (prev-frame) là biến cục bộ loop (per-camera), không DTO.

## Correctness Properties
Provisional (chốt số criteria ở requirements.md):

Provisional mapping (requirements.md CHƯA tồn tại — số criteria chốt lại khi tạo requirements):

### Property 1: Additive — mặc định không đổi hành vi
Cấu hình mặc định (min-interval=0, every-n=1, motion-gate=off) → hành vi detect y hệt hiện tại; baseline 761/2 giữ.
**Validates: Requirements 4.1**

### Property 2: Motion-gate không bỏ sót quá hạn
Cảnh tĩnh → sau ≤ `motionMaxConsecutiveSkip` frame luôn có 1 detect (ép định kỳ, reuse ngữ nghĩa đã test).
**Validates: Requirements 1.2**

### Property 3: Cadence tiết kiệm CPU
Với min-interval/every-n, số `session.run` giảm ĐO ĐƯỢC vs baseline; video-loop KHÔNG bị ảnh hưởng (Property 12 overlay giữ).
**Validates: Requirements 1.1**

### Property 4: Fail-fast model-size
Model-size cấu hình ≠ input thật của .onnx → raise lỗi rõ lúc setup (không crash mù runtime).
**Validates: Requirements 2.1**

### Property 5: Không giật + không mất box (ràng buộc liên-spec + heartbeat)
`detectMinIntervalMs <= displayLeaseMs` (và `detectMaxIntervalMs <= displayLeaseMs` khi bật) cưỡng chế → box không hết hạn trước lần detect kế. **Heartbeat (max-interval):** khi bật, hệ SHALL ép detect nếu `now - last_detect >= detectMaxIntervalMs`, override motion-gate/every-N/min-interval → vật đứng-yên KHÔNG mất box (đóng K-103). `max=0` = tắt = hành vi hiện tại.
**Validates: Requirements 1.3**

### Property 6: Nghiệm thu bằng ĐO
Task 0 đo baseline vs mỗi lever; lever KHÔNG cải thiện đo được → KHÔNG giữ (chống phức tạp vô ích + sunk-cost).
**Validates: Requirements 3.1**

## Error Handling
- Cấu hình sai (interval<0, everyN<1, roi sai, interval>displayLease) → `ConfigError` fail-fast lúc dựng (không chạy ngầm sai).
- Model-size mismatch → lỗi rõ lúc `setup` (C3), KHÔNG để crash `session.run` khó hiểu.
- Motion-gate frame-đầu/đổi-shape → cho đi tiếp (thiếu mốc → thà chạy thừa hơn bỏ sót — QĐ đã có trong MotionGateStage).
- Detector exception vẫn theo `web-live-overlay-sync` (health ERROR, không bịa empty) — spec này KHÔNG đổi xử lý lỗi detect.

## Testing Strategy
- **Unit thuần (fake clock):** `should_detect` mọi biên (interval=0/every-n=1 = luôn detect; interval>0 chặn tới hạn; every-n bỏ đúng frame). Config boundary (đậu/rớt), P5 invariant.
- **Motion-gate:** tái dùng test `changed_ratio` có sẵn; thêm test loop-level (tĩnh→skip, động→detect, quá-hạn→ép detect).
- **Fail-fast model-size:** stub model input cố định + config lệch → raise; khớp → pass.
- **Task 0 (đo, script cố định — KHÔNG one-liner lặp §3.1):** `session.run`/s baseline; cadence → CPU%/detect-s/độ-trễ-bắt-vật-mới; motion-gate tĩnh vs động; [nếu INT8] accuracy drop. KHÔNG chốt default "tối ưu" nếu chưa có số (giữ experimental).
- **Regression:** `scripts\vp.cmd verify` giữ 761/2 (không tăng timeout che K-035). Webcam E2E xác nhận không giật với cadence bật (user nhìn).

## Chờ VALID
User đọc-lại-valid (đặc biệt: (a) tách deploy-time⊥runtime hợp lý? (b) ưu tiên runtime-levers trước? (c) ràng buộc cadence↔lease P5?) → mới tạo `requirements.md` (EARS) → `tasks.md` (TDD, Task 0 đo trước) → code. KHÔNG code trước valid.
