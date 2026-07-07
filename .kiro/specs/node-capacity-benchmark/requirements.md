# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — sub-spec ĐO công suất 1 node. CHỜ user đọc-lại-valid. KHÔNG code.
> **Gắn với:** `scale-architecture` (Roadmap bước 2 + R6.1 + Capacity Model C_inf/C_dec/V) · K-041 (công suất) ·
> C-015 (2060 = dev/benchmark).
> **Cập nhật lúc:** 2026-07-06.

## Introduction

`scale-architecture` đặt **capacity model per-node** (C_inf/C_dec/V + latency SLA) làm gốc, nhưng các con số ấy
là **[PHẢI BENCHMARK]** — không được bịa. Sub-spec này định nghĩa **CÁCH ĐO** các tham số đó một cách **trung
thực, tái lập được, đo trên hệ THẬT** (tái dùng `Yolov5PtDetector` + nguồn frame thật), để điền vào capacity model
trước khi thiết kế bất kỳ mảnh scale nào (batch-mux/scheduler/…).

**Ràng buộc TRUNG THỰC nền (chi phối toàn bộ spec này):**
- **KHÔNG có số nào được bịa.** Tài liệu này chỉ định nghĩa phương pháp + mẫu bảng kết quả RỖNG. Số thật chỉ điền
  sau khi CHẠY harness trên **máy GPU** (WSL/RTX2060). Máy dev hiện tại (`endgame`) **no-GPU/no-torch → KHÔNG chạy
  được benchmark ở đây** (K-047); harness chỉ verify được LOGIC đo (trên fake/CPU) ở máy này, số capacity thật ở máy GPU.
- **Đo hệ THẬT, không proxy:** dùng `Yolov5PtDetector` (đã chứng minh chạy WSL — K-034) + nguồn frame thật, không
  dựng detector giả rồi suy ra công suất.
- **Đo phải phản ánh vận hành thật:** steady-state (bỏ warmup), percentile (p50/p95/p99) không chỉ trung bình,
  và **đo decode + inference ĐỒNG THỜI** (chúng tranh GPU — scale-architecture Lỗ 1/Lỗ 2).

## Requirements

### Requirement 1: Đo throughput inference per-node (C_inf) theo batch size
**User Story:** Là kiến trúc sư, tôi muốn biết 1 GPU chạy được bao nhiêu inference/giây ở các batch size, để suy ra số camera 1 node gánh (N_infer) và lượng lợi ích của batching (trụ A1).
#### Acceptance Criteria
- 1.1 — Harness PHẢI đo inference throughput (infer/s) của `Yolov5PtDetector` ở **batch size {1, 8, 16}** trên GPU thật, steady-state.
- 1.2 — VÌ `IDetector.detect(frame)` là **theo-từng-frame** (đọc code: `kernel/ports/detector.py`), đo batch>1 PHẢI gọi model nền (`Yolov5PtDetector._model([frames])`, AutoShape nhận list) — kết quả PHẢI ghi rõ "đo dưới tầng port" + coi đây là bằng chứng lỗ **A1 (batch chưa expose qua port)**, KHÔNG giả vờ port hỗ trợ batch.
- 1.3 — Kết quả PHẢI kèm: batch size, infer/s, throughput scaling (batch8 vs batch1), thiết bị/model/độ phân giải input.

### Requirement 2: Đo throughput decode (C_dec) + đo ĐỒNG THỜI decode+inference (tranh GPU)
**User Story:** Là kỹ sư, tôi muốn biết trần decode và công suất KẾT HỢP thực tế khi decode+infer chạy cùng lúc trên 1 GPU, để không định cỡ sai vì giả định chúng độc lập.
#### Acceptance Criteria
- 2.1 — Harness PHẢI đo decode fps (frame/s) qua nguồn thật (`VideoFileFrameSource`/`RtspFrameSource`, cv2) làm **baseline**; ghi rõ đây là cv2-per-process (KHÔNG phải hardware decode NVDEC — scale-architecture Lỗ 2).
- 2.2 — Harness PHẢI đo **công suất KẾT HỢP** khi decode + inference chạy đồng thời (cùng GPU) — số này (không phải `min(C_dec,C_inf)`) mới là trần thực (GPU contention). Kết quả PHẢI so sánh combined vs riêng-lẻ.
- 2.3 — Kết quả PHẢI ghi cơ chế decode đã dùng (cv2/ffmpeg/NVDEC) + độ phân giải (main-stream vs sub-stream).

### Requirement 3: Đo VRAM (V + m_i + per-stream)
**User Story:** Là kỹ sư, tôi muốn biết model chiếm bao nhiêu VRAM và mỗi stream tốn thêm bao nhiêu, để suy N_vram.
#### Acceptance Criteria
- 3.1 — Harness PHẢI đo VRAM model lúc load (`torch.cuda.max_memory_allocated` và/hoặc `nvidia-smi`) + tổng VRAM khả dụng (V).
- 3.2 — Kết quả PHẢI ghi VRAM theo batch size (batch lớn tốn VRAM hơn) để cân trade-off batch↔VRAM.

### Requirement 4: Đo độ trễ end-to-end (latency) theo percentile
**User Story:** Là kỹ sư real-time, tôi muốn biết độ trễ ingest→detections ở p50/p95/p99, để đặt ràng buộc SLA và thấy cái giá của batching (chờ gom batch).
#### Acceptance Criteria
- 4.1 — Harness PHẢI đo latency mỗi frame (từ lúc có frame → có detections) và báo cáo **p50/p95/p99 + max**, KHÔNG chỉ trung bình.
- 4.2 — VÌ `RunStats` (đọc code: `runtime/pipeline_runner.py`) **không có field thời gian**, harness PHẢI TỰ đo (đóng dấu clock quanh inference/execute) — ghi rõ instrument ở đâu; KHÔNG suy latency từ throughput.
- 4.3 — Kết quả PHẢI kèm latency ở batch {1,8,16} để lộ đánh đổi throughput↑ ↔ latency↑.

### Requirement 5: Tái lập được + trung thực (chống bịa)
**User Story:** Là người kiểm chứng, tôi muốn mỗi số đo tái lập được và gắn môi trường, để tin và so sánh về sau.
#### Acceptance Criteria
- 5.1 — Mỗi lần chạy PHẢI ghi header môi trường: GPU model, driver/CUDA, torch version, yolov5 version, weight file + kích thước input, OS.
- 5.2 — Phương pháp PHẢI: bỏ **warmup** (N frame đầu), đo **steady-state** trong cửa sổ thời gian/số-frame cố định, lặp R lần, báo cáo median + percentile (không lấy 1 lần).
- 5.3 — Bảng kết quả trong tài liệu là **RỖNG (template)** cho tới khi có số đo thật trên máy GPU; ô chưa đo ghi `[chưa đo]`, TUYỆT ĐỐI không điền số phỏng đoán.
- 5.4 — Harness PHẢI in cả **cảnh báo** khi điều kiện đo không lý tưởng (vd chạy song song tải khác → K-035), để số không bị hiểu nhầm.

### Requirement 6: Tái dùng base + không đụng lõi (additive)
**User Story:** Là kiến trúc sư, tôi muốn harness benchmark đo đúng hệ hiện có mà không sửa lõi, để số phản ánh sản phẩm thật.
#### Acceptance Criteria
- 6.1 — Harness PHẢI tái dùng `Yolov5PtDetector` + `VideoFileFrameSource`/`RtspFrameSource` (+ tùy chọn `PipelineRunner`) — KHÔNG viết detector/decode riêng để đo.
- 6.2 — Harness sống NGOÀI `src/vision_platform` runtime (là công cụ dev, không phải runtime dep — như ranh giới K-022 của `build`) → đặt ở thư mục `benchmarks/`; KHÔNG thêm dependency runtime; KHÔNG sửa `src/`.
- 6.3 — Chạy full `pytest` + lint sau khi thêm harness PHẢI giữ **baseline xanh** (427/1 · lint 5/0 hiện tại) — harness không được phá test/contract.

## Non-Goals (giai đoạn này)
- KHÔNG xây batch-mux/scheduler/motion-gate (các trụ scale — sub-spec riêng sau khi có số).
- KHÔNG tối ưu model/tốc độ; chỉ ĐO hiện trạng.
- KHÔNG đo đa-node (chỉ 1 node); đa-node đo ở nấc 1→10→N sau (scale-architecture R6.2).
- KHÔNG chốt cơ chế decode production (cv2 vs ffmpeg/NVDEC) — đo baseline cv2 + ghi nhận hardware-decode là hướng.
- KHÔNG code harness trong PHA này (design-first: chốt phương pháp trước).

## Definition of Done (của PHA thiết kế này)
`design.md` có: phương pháp đo từng tham số (C_inf/C_dec/combined/V/latency) + vị trí instrument (bù cho RunStats
thiếu timing) + thiết kế harness (tái dùng component nào, đặt đâu) + **bảng kết quả RỖNG có đơn vị** + mục trung
thực (đo được gì ở máy nào). 0 diagnostic. User valid → mới sang PHA 2 (code harness + chạy trên máy GPU).

## Glossary
- **C_inf / C_dec / V** — công suất inference/decode/VRAM đo per-node (tham số điền vào capacity model scale-arch).
- **steady-state** — giai đoạn ổn định sau warmup (JIT/cache/allocator đã ấm) — chỉ đo ở đây.
- **combined throughput** — công suất khi decode + inference chạy ĐỒNG THỜI trên 1 GPU (< min riêng lẻ vì tranh tài nguyên).
- **warmup** — số frame/giây đầu bị bỏ (chưa ổn định) — KHÔNG tính vào số đo.
- **percentile (p95/p99)** — mốc mà 95%/99% mẫu nằm dưới; phản ánh đuôi độ trễ (quan trọng hơn trung bình cho real-time).
