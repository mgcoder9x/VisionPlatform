# Requirements Document

> **Spec:** pipeline-observability (quan sát vận hành cho analytics pipeline — no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Đóng:** K-017 (backpressure/pipeline metrics CHƯA wire vào observability) + K-040 C1 (metrics-per-proc,
> chưa có quan sát vận hành cho slice) — phần KHÔNG cần GPU.
> **Nền tảng (đã ĐỌC CODE thật):**
> - `runtime/pipeline_runner.py`: `RunStats(frames_read, processed, skipped, stage_errors, cancelled, eof,
>   source_errors)` — frozen, CHỈ trả về lúc KẾT THÚC `run()`. Vòng lặp `read→execute→sink.handle`.
> - `runtime/observability.py`: `InMemoryMetrics` (counter/gauge/histogram, thread-safe) + structlog.
> - `runtime/stages/motion_gate_stage.py`: phát artifact `motion_ratio` / `motion_forced`.
> - `kernel/ports/frame_source.py`: `source_id` duy nhất/camera (cho logging/metrics).
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Hệ đã ĐẾM được (detections/tracks/crossings) và trả `RunStats` tổng hợp. Nhưng để vận hành **~100 camera
thương mại**, người vận hành cần thấy **sức khỏe runtime theo thời gian, theo từng camera** — nếu không sẽ
"bay mù": không biết camera nào chết, motion-gate tiết kiệm GPU bao nhiêu, tỉ lệ lỗi/drop ra sao.

Hiện có 2 hạn chế bản chất (đã đọc code):
1. `RunStats` là **immutable, chỉ trả về khi `run()` KẾT THÚC** → với luồng RTSP chạy liên tục (is_finite=False,
   không bao giờ tự dừng) → **không có số liệu nào tới lúc dừng** = mù hoàn toàn trong lúc vận hành.
2. Số nghiệp vụ (detections/crossings đếm được) nằm trong **artifacts** của packet, KHÔNG gộp vào quan sát
   vận hành; `InMemoryMetrics` có sẵn nhưng **pipeline analytics chưa wire vào** (K-017).

Tính năng này thêm **quan sát vận hành ĐỊNH KỲ, theo camera**, phát trong lúc `run()` chạy, qua **một port
observer tiêm vào** (giữ hexagonal — runner không phụ thuộc backend cụ thể như Prometheus). **Opt-in, mặc định
no-op → hành vi hiện tại giữ nguyên (backward-compat).** Kiểm chứng hoàn toàn **không cần GPU** (fake source +
clock tiêm + observer spy).

**Ranh giới layer (bám luật):** port observer khai ở `kernel` (Protocol thuần, không phụ thuộc lib ngoài);
`PipelineRunner` (runtime) gọi port; adapter cụ thể (Prometheus/StatsD/log) ở `adapters` — **Non-Goal v1**
(v1 chỉ cần port + 1 impl in-memory/log tái dùng `InMemoryMetrics` đã có ở runtime). KHÔNG cv2/torch.

**Chống bịa:** mọi tham chiếu (RunStats fields, InMemoryMetrics API, source_id, motion artifacts, vòng lặp run)
ĐÃ đọc code thật. Con số throughput/tỉ-lệ là dẫn xuất số học từ bộ đếm sẵn có (kiểm được bằng test xác định).

### Goals
- Thấy sức khỏe runtime **theo từng camera** (source_id) **trong lúc chạy** (không đợi kết thúc).
- Đo hiệu quả motion-gate: **tỉ lệ skip** (số frame bỏ / tổng đọc) = phần trăm GPU tiết kiệm.
- Đo throughput (frames/giây) + tỉ lệ lỗi stage + drop (nếu có).
- Wire số liệu vào observability qua **port tiêm** (hexagonal), giữ v1 nguyên khi không bật.
- Kiểm chứng KHÔNG cần GPU/camera (xác định).

### Non-Goals
- KHÔNG adapter Prometheus/StatsD/OTLP cụ thể (port sẵn-sàng-cắm; adapter = sub-spec `adapters` sau).
- KHÔNG gộp metrics cross-process (~100 cam đa tiến trình) — đó là K-040 C1 tầng cụm, sub-spec scale sau.
- KHÔNG per-packet/per-detection label (cardinality bùng nổ — K-019); chỉ counter/gauge bounded theo source_id + tên cố định.
- KHÔNG đổi ngữ nghĩa `RunStats` (giữ nguyên; observability là kênh SONG SONG, additive).
- KHÔNG tracing/log-handler production (K-018 giữ nguyên phạm vi).

## Glossary
- **Observer (port)** — giao diện `kernel` nhận sự kiện số liệu định kỳ từ runner; impl cụ thể ở ngoài (DI).
- **Snapshot định kỳ** — bộ đếm tích luỹ được phát mỗi N frame HOẶC mỗi T giây (cấu hình), để thấy tiến triển live.
- **skip-rate** — `skipped / frames_read` (tỉ lệ frame motion-gate bỏ → xấp xỉ % inference tiết kiệm).
- **throughput (fps)** — `frames_read / (elapsed_seconds)`, tính từ clock tiêm.
- **Bounded cardinality (K-019)** — nhãn metric chỉ gồm giá trị hữu hạn biết trước (source_id, tên-metric); CẤM packet_id/toạ độ.

## Requirements

### Requirement 1: Quan sát định kỳ trong lúc chạy (không đợi kết thúc)
**User Story:** Là kỹ sư vận hành ~100 cam, tôi muốn thấy số liệu runtime CẬP NHẬT trong khi pipeline đang chạy (đặc biệt luồng RTSP không bao giờ tự dừng), để phát hiện sự cố sớm.
#### Acceptance Criteria
- 1.1 — WHERE observer được cấu hình, WHILE `run()` đang chạy, THE runner SHALL phát snapshot số liệu ĐỊNH KỲ (mỗi `emit_every_n` frame đọc được, hoặc mỗi `emit_interval_s` giây — theo cấu hình), KHÔNG đợi `run()` kết thúc.
- 1.2 — THE snapshot SHALL gồm tối thiểu: `source_id`, `frames_read`, `processed`, `skipped`, `stage_errors`, `frames_per_second` (throughput tích luỹ), `skip_rate`.
- 1.3 — WHEN `run()` kết thúc (EOF hoặc should_stop), THE runner SHALL phát 1 snapshot CUỐI (đảm bảo số liệu chốt được ghi nhận) rồi mới trả `RunStats`.
- 1.4 — WHERE KHÔNG cấu hình observer, THE runner SHALL hành xử Y HỆT hiện tại (observer mặc định no-op; RunStats không đổi) — backward-compat.

### Requirement 2: Số liệu theo từng camera (per-source) + hiệu quả motion-gate
**User Story:** Là kỹ sư, tôi muốn biết mỗi camera khoẻ không và motion-gate tiết kiệm GPU bao nhiêu, để cân tải + chỉnh ROI/ngưỡng.
#### Acceptance Criteria
- 2.1 — THE mọi snapshot SHALL mang `source_id` của camera (từ `IFrameSource.source_id`) — không trộn số liệu nhiều camera.
- 2.2 — THE `skip_rate` SHALL = `skipped / frames_read` (0 nếu `frames_read==0`), phản ánh tỉ lệ frame bị motion-gate bỏ (xấp xỉ % inference tiết kiệm).
- 2.3 — WHERE nhãn được gắn cho metric, THE nhãn SHALL bounded (chỉ `source_id` + tên metric cố định) — CẤM packet_id/toạ độ/nhãn không giới hạn (K-019).

### Requirement 3: Port observability (hexagonal) — tiêm được, không cột backend
**User Story:** Là kiến trúc sư, tôi muốn runner không phụ thuộc backend metrics cụ thể, để cắm Prometheus/StatsD/log sau mà không sửa runner.
#### Acceptance Criteria
- 3.1 — THE port observer SHALL khai ở `kernel` là Protocol thuần (không import structlog/prometheus/lib ngoài); ví dụ 1 method `on_snapshot(snapshot)` (+ tuỳ chọn lifecycle).
- 3.2 — THE `PipelineRunner` SHALL nhận observer qua DI (tham số optional, default no-op) — KHÔNG khởi tạo backend cụ thể bên trong.
- 3.3 — THE impl cụ thể v1 SHALL tái dùng `InMemoryMetrics`/structlog ở `runtime` (hoặc 1 observer đơn giản) — KHÔNG thêm dependency ngoài; adapter Prometheus = Non-Goal.
- 3.4 — THE ranh giới layer SHALL giữ: `kernel` (port thuần) ← `runtime` (runner + impl in-mem) ; import-linter 5 kept/0 broken.

### Requirement 4: Additive + an toàn (không phá baseline, không nuốt lỗi)
**User Story:** Là kiến trúc sư, tôi muốn quan sát KHÔNG làm hỏng pipeline đang chạy.
#### Acceptance Criteria
- 4.1 — THE thay đổi SHALL additive: KHÔNG đổi chữ ký/`RunStats`; baseline **546 passed/1 skipped · lint 5/0** giữ (+ test mới).
- 4.2 — IF observer.on_snapshot ném lỗi, THEN runner SHALL KHÔNG để lỗi quan sát làm sập vòng lặp xử lý frame (quan sát là phụ trợ — bọc an toàn + đếm/log, không nuốt im lặng kiểu che bug pipeline chính).
- 4.3 — THE việc emit định kỳ SHALL KHÔNG gọi observer mỗi frame nếu `emit_every_n>1` (tránh overhead + cardinality) — chỉ theo nhịp cấu hình.

### Requirement 5: Kiểm chứng KHÔNG cần GPU/camera (xác định)
**User Story:** Là kỹ sư, tôi muốn test observability xác định trên máy dev để CI ổn định.
#### Acceptance Criteria
- 5.1 — Test dùng FakeFrameSource + **clock tiêm** (không phụ thuộc thời gian thực) → throughput/nhịp emit xác định.
- 5.2 — Test observer SPY thu snapshot: kiểm số snapshot đúng nhịp (`emit_every_n`), snapshot cuối phát ra, các trường (skip_rate/fps/source_id) đúng số học.
- 5.3 — Test backward-compat: KHÔNG observer → RunStats + hành vi Y HỆT hiện tại (so số).
- 5.4 — Test an toàn: observer ném lỗi → vòng lặp vẫn xử lý hết frame + RunStats đúng (lỗi quan sát bị cô lập).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format: Overview/Architecture/Components/Data Models/Error
Handling/Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) port observer
`kernel` (Protocol) + DTO snapshot (immutable); (b) điểm wire trong `PipelineRunner.run` (đếm nhịp + tính
fps/skip_rate từ clock tiêm) + teardown-safe (emit cuối trong finally trước return); (c) impl v1 tái dùng
InMemoryMetrics/log; (d) chứng minh backward-compat (no-op default) + isolation lỗi observer; (e) ranh giới layer.
**KHÔNG code ở PHA này** (chờ user valid thiết kế).
