# Requirements Document

> **Adaptive Detection Performance** — dẫn xuất từ `design.md` (design-first). CHƯA code — chờ user valid.

## Introduction
Hệ web-live (webcam→YOLO→overlay) chạy trên máy **KHÔNG-GPU**. Trần throughput = CPU inference (`yolov8n@640` đo THẬT máy này #395 = **8.52 infer/s**, p50 111ms). `_detect_loop` hiện chạy detector hết-sức-có-thể trên mọi frame-version → đốt 100% một lõi CPU liên tục kể cả khi cảnh tĩnh. Overlay lease (`web-live-overlay-sync`) đã làm mượt khoảng trống giữa 2 lần detect ⇒ **detect thưa hơn là chấp nhận được** trong ràng buộc lease.

Verify empiric #392: `yolov8n.onnx` input `[1,3,640,640]` **CỐ ĐỊNH** ⇒ đổi input-size là **deploy-time** (chọn/đổi .onnx), KHÔNG phải nút runtime. Spec tách hai nhóm đòn bẩy: **runtime** (giảm TẦN SUẤT detect — motion-gate + cadence, an toàn, không re-export) và **deploy-time** (input-size/INT8 artifact + fail-fast an toàn). Mọi thay đổi **additive**, mặc định = hành vi hiện tại. Nghiệm thu bằng **ĐO** (không tuyên bố "nhanh hơn" nếu chưa đo).

Nguồn thiết kế: `.kiro/specs/adaptive-detection-perf/design.md`. Mỗi Acceptance Criteria được một Correctness Property trong design đối chiếu qua `**Validates: Requirements X.Y**`.

## Glossary
- **Detect-cadence:** tần suất THỰC SỰ gọi detector (`min-interval` ns tối thiểu giữa 2 detect + `every-N` frame). Có thể < FPS video.
- **Motion-gate:** bỏ detect khi frame gần như không đổi (`domain.motion.changed_ratio < min_area_ratio`); ép detect định kỳ sau `maxConsecutiveSkip` để chống bỏ sót.
- **Runtime lever / Deploy-time lever:** đổi được lúc chạy/qua config ↔ quyết định lúc chọn model artifact/khởi động (xem design §Architecture).
- **displayLeaseMs:** hạn hiển thị box của overlay (`web-live-overlay-sync` OverlayConfig) — ràng buộc chống giật.
- **should_detect:** hàm thuần @domain quyết định frame này có chạy detector không (clock tiêm, test xác định).

## Requirements

### Requirement 1: Điều tiết nhịp detect (runtime) — tiết kiệm CPU mà không giật
**User Story:** Là người vận hành hệ no-GPU, tôi muốn detector chỉ chạy khi cần (bỏ frame tĩnh, giới hạn nhịp) để tiết kiệm CPU, nhưng box vẫn không giật và không bỏ sót vật, để hệ đáp ứng tốt lâu dài.

#### Acceptance Criteria
1. WHEN cấu hình `detectMinIntervalMs > 0` hoặc `detectEveryN > 1`, THE system SHALL giảm số lần `session.run` một cách ĐO ĐƯỢC so với baseline, VÀ SHALL KHÔNG ảnh hưởng tiến trình publish video/JPEG (video count vẫn tăng như trước).
2. WHILE motion-gate bật và cảnh tĩnh (`changed_ratio < motionMinAreaRatio`), THE system SHALL bỏ qua detect cho frame đó; WHEN số frame bỏ liên tiếp đạt `motionMaxConsecutiveSkip`, THE system SHALL ép chạy detect đúng một frame (chống bỏ sót vật đứng-yên); WHEN frame đầu hoặc đổi shape, THE system SHALL cho detect đi tiếp (thiếu mốc so sánh).
3. WHERE overlay lease đang dùng, THE system SHALL cưỡng chế `detectMinIntervalMs <= displayLeaseMs` (và `detectMaxIntervalMs <= displayLeaseMs` khi max>0) lúc khởi tạo (fail-fast `DetectionConfigError`), để box không hết hạn trước lần detect kế (chống giật/mất box).
4. WHERE `detectMaxIntervalMs > 0` (heartbeat), WHEN `now - last_detect >= detectMaxIntervalMs`, THE system SHALL ép chạy detect bất kể motion-gate/every-N/min-interval, để vật đứng-yên không mất box khi cảnh tĩnh lâu (đóng K-103). WHEN `detectMaxIntervalMs = 0`, THE system SHALL tắt heartbeat (hành vi hiện tại).

### Requirement 2: An toàn model artifact (deploy-time) — fail-fast input-size
**User Story:** Là kỹ sư triển khai, tôi muốn hệ báo lỗi rõ ràng ngay khi cấu hình input-size không khớp model thật, để không gặp crash khó hiểu lúc chạy và không chạy ngầm sai.

#### Acceptance Criteria
1. WHEN `OnnxDetector.setup` với model có input H/W cố định KHÁC `model_size` cấu hình (và không phải dynamic axis), THE system SHALL raise lỗi rõ ràng lúc setup (nêu size model thật vs cấu hình), KHÔNG để lỗi phát sinh mù lúc `session.run`.
2. WHEN nạp một model artifact khác (input-size khác hoặc INT8-quantized), THE system SHALL dùng cùng đường `OnnxDetector`/`DetectorPipeline` không đổi code detector (chỉ đổi file .onnx được trỏ tới).

### Requirement 3: Nghiệm thu bằng ĐO (anti-sunk-cost)
**User Story:** Là người ra quyết định, tôi muốn mỗi đòn bẩy tốc độ được chứng minh bằng số đo thật, để không giữ lại phức tạp không mang lại lợi ích.

#### Acceptance Criteria
1. WHEN đánh giá một lever (cadence/motion-gate/session-options/INT8), THE system SHALL có số đo baseline vs sau-lever (session.run/s, CPU, độ trễ bắt vật mới, và với INT8 thêm accuracy drop) trước khi tuyên bố cải thiện.
2. IF một lever KHÔNG cho cải thiện đo được, THEN THE decision SHALL là KHÔNG giữ lever đó (hoặc để tắt mặc định) và ghi lý do — KHÔNG thêm phức tạp vô ích.

### Requirement 4: Tương thích ngược / additive
**User Story:** Là người đang vận hành hệ hiện tại, tôi muốn thay đổi này không phá hành vi sẵn có, để nâng cấp an toàn.

#### Acceptance Criteria
1. WHEN chạy với cấu hình mặc định (`detectMinIntervalMs=0`, `detectEveryN=1`, `motionGate=off`), THE system SHALL cho hành vi detect y hệt hiện tại, VÀ baseline test SHALL giữ 761 passed/2 skipped (không giảm).
2. WHEN thêm khoá cấu hình mới (CLI/TOML), THE system SHALL merge với precedence CLI > TOML (theo tiền lệ observability D-086) và validate fail-fast giá trị sai.
