# Requirements Document

_Batch-Mux Inference_

> **Trạng thái:** PHA 1 (requirements — DẪN XUẤT TỪ design-first). CHỜ user đọc-lại-valid.
> **Là sub-spec của:** `.kiro/specs/scale-architecture/` (roadmap #3, A1/K-040). Đọc kèm `design.md` cùng thư mục.
> **Mục đích:** nâng trần inference per-GPU `C_inf` bằng gộp N-camera → 1 `session.run`, để 1 node gánh nhiều camera hơn.
> **Cập nhật lúc:** 2026-07-13.

## Introduction

`design.md` (đã valid) đề xuất `BatchMuxer` gộp frame nhiều camera thành 1 tensor `[B,3,640,640]` chạy 1 lần
inference (thay mỗi camera 1 lần batch=1). Tài liệu này chốt **YÊU CẦU** mà mọi hiện thực batch-mux PHẢI thoả —
đặc biệt các yêu cầu ĐÚNG-ĐẮN (không trộn/không sai kết quả) vì batch trộn dữ liệu nhiều camera là vùng dễ sai nhất.

**Nối đất thực tế (đã VERIFY, không bịa — xem `design.md` RB-1..5):**
- Model `yolov8n.onnx` hiện tại input CỐ ĐỊNH `[1,3,640,640]` → batch>1 nổ `InvalidArgument` (chạy probe thật) →
  cần re-export dynamic-batch (Requirement 5).
- Port `IDetector.detect(frame)` + `OnnxDetector` là single-frame / batch=1 cứng → batch phải THÊM, không phá (Requirement 4).
- Baseline so sánh = K-092 (K-session-rời: **104.7 infer/s @ K=4**, per-stream p95 49.5ms) — nghiệm thu batch-mux phải đối chiếu số này (Requirement 3).

**Chống bịa / trung thực:** batch-mux CHƯA chắc thắng baseline (yolov8n nhỏ, GPU đã lấp khá đầy ở K-session) →
yêu cầu nghiệm thu là **ĐO**, và kết quả "không vượt baseline" vẫn là kết quả HỢP LỆ (kết luận không-đáng).

## Requirements

### Requirement 1: Đúng-đắn của batch (không trộn camera, không sai kết quả)
**User Story:** Là kỹ sư, tôi muốn gộp nhiều camera vào 1 batch mà kết quả mỗi camera vẫn đúng của chính nó, để batch-mux không âm thầm trộn/sai dữ liệu giám sát.
#### Acceptance Criteria
- 1.1 — WHEN một batch gồm frame từ nhiều request `[r0..r_{B-1}]` được chạy, THE hệ thống SHALL trả về cho request `r_i` ĐÚNG detections của frame `r_i` (route theo `request_id`, KHÔNG lẫn sang `r_j` với j≠i).
- 1.2 — WHEN chạy `detect_batch([f0..f_{B-1}])` với model dynamic-batch, THE kết quả sample `i` SHALL tương đương (trong dung sai float) với `detect(f_i)` chạy đơn lẻ — batching KHÔNG được đổi KẾT QUẢ phát hiện, chỉ đổi throughput.
- 1.3 — WHEN các frame trong batch có kích thước gốc KHÁC nhau (camera khác độ phân giải), THE hệ thống SHALL letterbox + inverse-transform per-sample đúng theo `orig_h/orig_w` của từng frame (giữ hợp đồng coordinate-transform hiện có).
- 1.4 — WHEN nhiều frame của CÙNG một camera đi qua mux, THE hệ thống SHALL trả detections về downstream theo ĐÚNG thứ tự `frame_id` gốc (không đảo) — vì analytics stateful downstream (`IouTracker.update`, đã VERIFY) phụ thuộc thứ tự frame; đảo = hỏng tracking/đếm. Ranh giới mux PHẢI ở tầng detector STATELESS (thượng nguồn stage stateful), scatter giữ camera-affinity K-042.

### Requirement 2: Latency bị chặn + backpressure quan-sát-được
**User Story:** Là kỹ sư vận hành, tôi muốn frame không chờ vô hạn để gom batch và frame bị bỏ khi quá tải được đếm, để hệ real-time không treo/không mất frame im lặng.
#### Acceptance Criteria
- 2.1 — WHEN batch chưa đủ `max_batch` mà đã quá `batch_timeout_ms` kể từ frame đầu tiên, THE hệ thống SHALL flush batch hiện có (chạy với B thật) — mọi frame submit SHALL được xử lý trong ≤ `batch_timeout_ms + t_infer` (KHÔNG chờ batch đầy mãi).
- 2.2 — IF inbound queue đầy khi submit, THEN hệ thống SHALL shed frame theo policy (drop-oldest/newest) VÀ tăng đúng 1 counter shed (bất biến: `submitted == processed + shed + error`), KHÔNG chặn vô hạn.
- 2.3 — `max_batch` và `batch_timeout_ms` PHẢI cấu hình được (không hard-code) để chỉnh đánh đổi throughput↔latency theo SLA.
- 2.4 — WHEN postprocess 1 sample trong batch lỗi, THE hệ thống SHALL cô lập lỗi sample đó (đếm + trả rỗng/lỗi cho riêng nó) mà KHÔNG giết cả batch (bulkhead per-sample).

### Requirement 3: Nghiệm thu bằng SỐ ĐO (vượt baseline mới đáng)
**User Story:** Là kiến trúc sư, tôi muốn quyết định batch-mux dựa trên đo thật so với baseline, để không đầu tư vào tối ưu không mang lại lợi.
#### Acceptance Criteria
- 3.1 — TRƯỚC khi coi batch-mux "đáng dùng", PHẢI ĐO batched-throughput (B=1/2/4/8) trên GPU thật VÀ so với baseline K-092 (104.7/s @K4) ở latency-SLA; số đo PHẢI ghi lại (bench + journal).
- 3.2 — IF batched-throughput KHÔNG vượt baseline ở latency chấp nhận được, THEN kết luận "không đáng cho model+GPU này" SHALL được ghi nhận trung thực (không tiếp tục build vì sunk-cost).
- 3.3 — Số đo PHẢI cập nhật vào capacity model scale-architecture (bản-3) để định cỡ `N_node` chính xác hơn.

### Requirement 4: Không phá lõi single-frame (backward-compat)
**User Story:** Là kỹ sư, tôi muốn thêm khả năng batch mà không làm hỏng đường single-frame đang chạy, để mọi thứ hiện có (demo/config/test) không vỡ.
#### Acceptance Criteria
- 4.1 — Port `IDetector.detect(frame)->list[Detection]` PHẢI GIỮ NGUYÊN; khả năng batch thêm qua port RIÊNG `IBatchDetector.detect_batch(frames)->list[list[Detection]]` (song song, không sửa port cũ).
- 4.2 — Batch-mux PHẢI tái dùng thành phần đã có (`BoundedQueue`, session GPU của `OnnxDetector`, `yolov8_decode`, metrics) — KHÔNG viết lại lõi (bám nguyên tắc chống-rebuild).
- 4.3 — WHEN batch-mux được thêm, THE baseline test hiện tại (647/2 · lint 5/0 · drift PASS) SHALL giữ nguyên (chỉ THÊM, không phá).

### Requirement 5: Điều-kiện-tiên-quyết model dynamic-batch (fail-fast rõ ràng)
**User Story:** Là kỹ sư, tôi muốn hệ báo lỗi rõ ngay khi model không hỗ trợ batch, để không gặp lỗi khó hiểu lúc chạy.
#### Acceptance Criteria
- 5.1 — WHEN `BatchOnnxDetector.setup()` phát hiện trục batch (index 0) của input model là CỐ ĐỊNH (không động, vd `[1,3,640,640]`), THE hệ thống SHALL fail-fast với thông báo rõ: cần re-export model dynamic-batch (`export(dynamic=True)`).
- 5.2 — Logic gather/scatter (Property 1/2) PHẢI verify được bằng **model ONNX tí-hon dynamic-batch tự tạo** (license sạch), KHÔNG cần re-export YOLO / KHÔNG cần GPU — để test tính-đúng độc lập với network. **✅ VERIFIED KHẢ THI (#370/K-095):** `onnx` builder sẵn → model `ReduceSum` input `['N',3,4,4]` chạy batch=1/2/4 + identity đúng qua onnxruntime.

## Non-Goals (giai đoạn này)
- KHÔNG chốt self-viết BatchMuxer vs nhúng Triton (để design so sánh; máy no-docker → Triton native khó).
- KHÔNG chốt concurrency model (thread/process/asyncio) cứng — nêu ở design, chốt khi thi công.
- KHÔNG re-export model / KHÔNG chạy bench GPU trong PHA requirements (cần đèn xanh network; thuộc pha thi công).
- KHÔNG tối ưu riêng RTX 2060 (chỉ dùng đo nghiệm thu).

## Tiêu chí ĐẬU (Definition of Done — PHA requirements)
`requirements.md` phủ đủ: đúng-đắn batch (identity + tương đương + coordinate per-sample) + latency-bounded + shed +
nghiệm-thu-bằng-đo + backward-compat + tiên-quyết-dynamic-batch. 0 diagnostic. Mọi acceptance criteria có số khớp
`Validates` trong `design.md`. User đọc-lại-valid → sang `tasks.md` (chia task thi công, TDD).

## Glossary
- **batch-mux** — gộp frame nhiều camera thành 1 tensor `[B,...]` chạy 1 `session.run` (tăng `C_inf`).
- **dynamic batch axis** — trục 0 (batch) của input model = 'N' động; model hiện tại `[1,...]` cố định (RB-1).
- **gather-scatter** — gom frame vào batch (gather) rồi phân kết quả về đúng camera theo `request_id` (scatter).
- **batch_timeout_ms** — thời gian tối đa chờ gom batch trước khi flush (đánh đổi throughput↔latency).
- **K-session-rời** — K session CUDA độc lập song song (baseline K-092: K=4→104.7/s) — khác batch THẬT 1 session B-dim.
- **bulkhead per-sample** — lỗi 1 sample trong batch không giết cả batch (cô lập + đếm).
