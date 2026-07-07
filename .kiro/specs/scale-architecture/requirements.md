# Requirements Document

> **Trạng thái:** PHA 1 (requirements) — tài liệu ĐỊNH HƯỚNG kiến trúc scale. CHỜ user đọc-lại-valid.
> **Mục đích:** đưa base "1 node" (đã có, known-good 369/1) lên **kiến trúc cụm ~100 camera**, phần cứng
> tương lai (RTX 2060 hiện tại = chỉ DEV/benchmark). Đóng K-040 (lỗ hổng scale) + đặt trên K-041 (công suất).
> **Cập nhật lúc:** 2026-07-06.

## Introduction

User chốt (C-014/C-015): đích = **~100 camera**, **KHÔNG bao giờ 1**; chạy trên **phần cứng tương lai phù hợp**
(máy hiện tại 1×RTX2060/6GB chỉ để dev + benchmark 1-node). Nghiệp vụ = **nhiều analytics** (detect → classify →
đếm → …, đa tầng). Lưu trữ = **tùy chọn** (có thể có/không). "Làm max rồi giảm" → thực chất phải **thiết kế theo
NGÂN SÁCH tài nguyên + cho phép cấu hình giảm tải + degrade có kiểm soát** (K-041), vì hệ GPU-bound không thể đạt
"max tuyệt đối".

**Nguyên tắc nền (bám nguyên tắc user "fix bản chất, không rebuild"):** base hiện tại (ports IFrameSource/
IDetector, MediaPacket + IMediaRef, Stage pipeline, SHM ring 1-writer, switchover/lease, ZMQ inference,
supervisor/heartbeat) là **"1 NODE" đúng và tái dùng**. Kiến trúc cụm = **THÊM tầng bao quanh** (sharding, batch,
config, metrics tập trung, fan-out), KHÔNG đập lõi.

**Chống bịa:** mọi con số công suất là **THAM SỐ ĐO ĐƯỢC per-node** (benchmark), KHÔNG hằng số bịa. Ràng buộc
1-writer/ring là INVARIANT đã có trong code (`shm_frame_ref.py`). Thành phần tái dùng đều đã đọc code thật.

## Requirements

### Requirement 1: Scale ngang, phần-cứng-bất-khả-tri (per-node capacity là tham số đo)
**User Story:** Là kiến trúc sư, tôi muốn hệ scale theo số node/GPU, để chạy N camera trên phần cứng nào cũng được, chỉ cần đo công suất 1 node rồi nhân lên.
#### Acceptance Criteria
- 1.1 — Kiến trúc PHẢI biểu diễn "1 node" = đơn vị công suất đo được (C = inference/s/GPU) → tổng tải chia cho C ra số node cần.
- 1.2 — Thêm camera / thêm node KHÔNG đòi sửa lõi (chỉ đổi config + thêm process/host).
- 1.3 — Base hiện tại PHẢI được tái dùng làm khối "1 node" (không viết lại ports/Stage/SHM/ZMQ/supervisor).

### Requirement 2: Ngân sách tài nguyên + config giảm tải + shed quan-sát-được
**User Story:** Là kỹ sư vận hành, tôi muốn hệ chạy trong ngân sách GPU cố định và bỏ tải có kiểm soát khi quá tải, để không sập/không mất frame im lặng.
#### Acceptance Criteria
- 2.1 — fps + tập analytics MỖI camera PHẢI cấu hình được (không hard-code) → giảm tải cho vừa phần cứng.
- 2.2 — PHẢI có scheduler ngân sách: tổng inference/s không vượt công suất node (đo được), chia theo cam + ưu tiên.
- 2.3 — Khi cầu > cung → shed (bỏ frame) PHẢI **có chủ đích + đếm được** (metric), KHÔNG im lặng; policy cấu hình.
- 2.4 — Motion-gating: inference đắt CHỈ chạy khi có tín hiệu (chuyển động) — gate rẻ (CPU) đứng trước.

### Requirement 3: Analytics đa-tầng (fan-out) chia sẻ node
**User Story:** Là kỹ sư, tôi muốn chuỗi detect → classify → đếm/track chạy nhiều tầng trên cùng frame, để phục vụ nhiều nghiệp vụ.
#### Acceptance Criteria
- 3.1 — PHẢI mô hình hoá fan-out: 1 frame → N vùng/đối tượng → tầng sau (classify/OCR) theo từng vùng.
- 3.2 — Nhiều model chia CHUNG 1 GPU → scheduler PHẢI arbitrate giữa các tầng/analytics (không để 1 tầng đói).
- 3.3 — Mỗi analytics = Stage/port cắm được (tái dùng IStage/IDetector + port mới ITracker/IClassifier/… khi cần).

### Requirement 4: Sink cắm/rút (lưu trữ tùy chọn)
**User Story:** Là kỹ sư, tôi muốn kết quả đi tới đích cấu hình được (event/DB/queue/không-lưu), để bật/tắt lưu trữ không đổi lõi.
#### Acceptance Criteria
- 4.1 — Kết quả pipeline PHẢI ra qua outbound port (ISink, khớp thiết kế pipeline-runner) — storage là 1 impl optional.
- 4.2 — Tắt lưu trữ = không gắn sink lưu; bật = thêm sink DB/file. KHÔNG đổi pipeline.

### Requirement 5: Quan sát tập trung (fleet observability)
**User Story:** Là vận hành, tôi muốn thấy metric/log toàn cụm ở một chỗ, để không phải SSH từng process trong ~100 camera.
#### Acceptance Criteria
- 5.1 — Metric PHẢI gom được cross-process/host (đẩy tới backend tập trung — Prometheus/OTel là lựa chọn, chốt sau).
- 5.2 — Nhãn metric bounded (K-019 — không dùng packet_id/toạ độ làm label).

### Requirement 6: Validate tăng dần theo công suất ĐO ĐƯỢC (1 → 10 → N)
**User Story:** Là kiến trúc sư, tôi muốn mở rộng có kiểm chứng từng nấc dựa trên số đo thật, để không thiết kế trên phỏng đoán.
#### Acceptance Criteria
- 6.1 — TRƯỚC thiết kế chi tiết: benchmark 1-node (decode fps, inference fps batch1/8/16, VRAM/model) → số THẬT.
- 6.2 — Mở rộng theo nấc 1 → 10 → N, mỗi nấc đo lại (decode/GPU/RAM/độ trễ) rồi mới tăng tiếp.

## Non-Goals (giai đoạn này)
- KHÔNG chốt cứng công nghệ transport-ở-quy-mô (ZMQ hiện tại vs broker Kafka/NATS/Redis-stream) — để design so sánh.
- KHÔNG chốt config-format/metrics-backend cụ thể — nêu lựa chọn, chốt ở bước sau.
- KHÔNG code gì trong PHA này (design-first).
- KHÔNG tối ưu cho riêng RTX 2060 (chỉ dùng để đo 1-node).

## Tiêu chí ĐẬU (Definition of Done — của PHA thiết kế này)
Tài liệu `design.md` có: mô hình công suất (per-node param) + sơ đồ topology cụm + bản đồ TÁI DÙNG (base=node) vs
THÊM MỚI + 5 trụ ngân sách/shed + fan-out + lộ trình validate 1→10→N + các quyết định công nghệ để-ngỏ. 0 diagnostic.
User đọc-lại-valid → mới sang sub-spec triển khai từng mảnh (design-first tiếp).

## Glossary
- **1 node** — đơn vị công suất = base hiện tại chạy 1 nhóm camera trên 1 GPU; C = inference/s đo được.
- **budget scheduler** — bộ chia tải giữ tổng inference ≤ công suất node, arbitrate giữa camera + analytics.
- **motion-gating** — chặn inference đắt bằng phát-hiện-chuyển-động rẻ (CPU) đứng trước.
- **fan-out** — 1 frame → N đối tượng → nhiều tầng analytics (detect→classify→count/track).
- **shed** — bỏ frame có chủ đích + đếm được khi quá tải (không im lặng).
- **sub-stream** — luồng RTSP độ phân giải thấp để detect; main-stream chỉ khi cần crop/record.
