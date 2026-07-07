# Design Document

> **Trạng thái:** PHA 1 (design ĐỊNH HƯỚNG) — CHỜ user đọc-lại-valid. KHÔNG code.
> **Gắn với:** `requirements.md` cùng thư mục · K-040 (lỗ hổng) · K-041 (công suất) · C-014/C-015.
> **Cập nhật lúc:** 2026-07-06.

## Overview

Đưa base "1 node" (known-good) lên **cụm ~100 camera** trên phần cứng tương lai. Tư tưởng cốt lõi:
**công suất mỗi node là THAM SỐ ĐO ĐƯỢC (C)**, hệ scale ngang = nhân node; tải mỗi camera **cấu hình được** và
hệ **luôn chạy trong ngân sách + shed có kiểm soát**. Base = viên gạch "1 node"; ta THÊM 3 mặt phẳng bao quanh:
**data plane** (frame → inference → analytics → sink), **control plane** (config + scheduler + registry),
**observability plane** (metric/log tập trung). KHÔNG đập lõi (bám nguyên tắc chống-rebuild của user).

**Vì sao gốc, không ngọn:** 100 camera không phải "chạy nhanh hơn" mà là **bài toán phân bổ tài nguyên hữu hạn**
(K-041: 1 GPU có trần vật lý). Thiết kế đúng phải đặt **ngân sách + shed + config** làm hạng-nhất, không phải vá
thêm khi nghẽn. Đó là lý do tài liệu này đi từ MÔ HÌNH CÔNG SUẤT trước, topology sau.

## Capacity Model (đặt trước — mọi thứ khác suy từ đây)

Ký hiệu (đo per-node, 1 GPU):
- `C_inf` = inference/giây 1 GPU chịu (đo batch tối ưu). `C_dec` = frame/giây decode được (NVDEC + CPU).
- `V` = VRAM khả dụng; `m_i` = VRAM model tầng i. `A` = số lượt model/frame (fan-out: detect + classify + …).
- `g` = tỉ lệ gate (motion) lọt tới inference (0..1). `f` = fps inference/camera (config).

Số camera 1 node gánh (xấp xỉ, ràng buộc bởi min của 3 trần):
```
N_infer  ≈ C_inf / (f · g · A)          # trần inference
N_decode ≈ C_dec / f_decode             # trần decode (dùng sub-stream để hạ f_decode)
N_vram   ≈ (V − Σ m_i) / vram_per_stream
N_node   = floor( min(N_infer, N_decode, N_vram) )
Số node cho 100 cam = ceil( 100 / N_node )
```
**Ý nghĩa thiết kế:** muốn tăng N_node → giảm `f` (fps), tăng `g` hiệu quả (motion-gate), giảm `A` (bớt analytics
đắt), dùng sub-stream (hạ `f_decode` + vram_per_stream), tăng batch (tăng `C_inf`). Đây chính là 5 trụ (dưới).
Các con số C_* là [PHẢI BENCHMARK] — R6.1; tài liệu này giữ chúng là biến, không bịa giá trị.

**GIỚI HẠN CỦA MÔ HÌNH (self-review — đây là mô hình BẬC-1, không chính xác tuyệt đối):**
- `A` KHÔNG hằng: fan-out (số đối tượng/frame) phụ thuộc dữ liệu → tải classify/OCR là **phân phối**, phải
  dùng percentile (p95/p99) + worst-case, không trung bình. Cảnh đông = bùng nổ tầng sau.
- Mô hình chặn THROUGHPUT, **chưa có LATENCY**: hệ real-time cần **SLA độ trễ end-to-end**. Batching tăng
  throughput nhưng **tăng latency** (chờ gom batch) → phải thêm ràng buộc `latency_p99 ≤ SLA` + `batch_timeout`.
- `min(C_dec, C_inf)` giả định decode/inference ĐỘC LẬP — SAI trên cùng 1 GPU: **NVDEC + CUDA tranh tài nguyên**
  → công suất kết hợp < min. Benchmark PHẢI đo **đồng thời decode+infer**, không đo tách rời.
→ Kết luận: capacity model chỉ để **định cỡ sơ bộ + hướng benchmark**, KHÔNG phải công thức cam kết.

## Architecture

```
         CONTROL PLANE                         DATA PLANE (mỗi "node" = base hiện tại)                 OBSERVABILITY
 ┌────────────────────────┐        ┌───────────────────────────────────────────────┐          ┌──────────────────┐
 │ config (khai báo N cam, │        │  Ingest/Decode worker  (1 cam = 1 writer/ring) │          │ metric/log gom    │
 │  model, roi, fps, sink) │──────▶ │    RTSP sub-stream → decode → SHM ring          │─push──▶ │ tập trung         │
 │ scheduler (ngân sách,   │        │        │ (motion-gate rẻ, CPU)                  │          │ (Prometheus/OTel  │
 │  shed policy, ưu tiên)  │◀─stats─│        ▼                                        │          │  — chốt sau)      │
 │ registry (node/health)  │        │  Inference worker (GPU pool + BATCH-mux N cam) │          └──────────────────┘
 └────────────────────────┘        │        │ detect → (fan-out) crop → classify →   │
        (supervisor/heartbeat        │        ▼        đếm/track                       │
         hiện có mở rộng)            │  Sink (ISink): event/DB/queue/none (optional)  │
                                     └───────────────────────────────────────────────┘
                          scale ngang: nhiều Ingest + nhiều Inference-node, sharded theo camera
```

**5 trụ (nguyên tắc thiết kế, từ K-041 — mỗi trụ có lý do):**
1. **Motion-gating** — detect chuyển động rẻ (CPU) chặn trước inference đắt. Lý do: `g` nhỏ → N_infer lớn; phần
   lớn frame tĩnh không đáng chạy GPU.
2. **Sub-stream cho detect** — decode luồng thấp (D1/CIF); main-stream chỉ khi cần crop/record. Lý do: hạ `C_dec`
   cần + `vram_per_stream` → tăng N_decode/N_vram.
3. **Batching** — gộp frame nhiều camera thành batch → 1 lần inference. Lý do: tăng `C_inf` (GPU thích batch).
   Đây là A1 (K-040). Kiểu DeepStream nvstreammux / Triton dynamic-batch.
4. **Budget scheduler** — tổng inference ≤ C_inf; chia theo camera + arbitrate giữa analytics (R2.2/R3.2). Lý do:
   ngân sách hữu hạn → phải phân bổ tường minh, không để tranh chấp ngẫu nhiên.
5. **Shed quan-sát-được** — cầu > cung → bỏ frame có chủ đích + đếm metric (R2.3). Lý do: mất frame là tất yếu khi
   quá tải; phải HIỂN THỊ, không im lặng (A2 K-040).

## Components and Interfaces

### Bản đồ TÁI DÙNG vs THÊM MỚI (cốt lõi — chống rebuild)
| Thành phần | Trạng thái | Vai trò trong cụm |
|---|---|---|
| ports `IFrameSource`/`IDetector` + `IMediaRef` (D-038) | ✅ tái dùng | inbound + backend frame (in-mem/SHM) |
| `MediaPacket`/`Stage`/`SyncLinearExecutor` | ✅ tái dùng | 1 chuỗi analytics trong 1 node |
| SHM ring 1-writer + switchover/lease | ✅ tái dùng | frame cam → inference trong node (INVARIANT 1cam=1writer giữ nguyên) |
| ZMQ inference (DEALER/ROUTER) | ✅ tái dùng (mở rộng) | transport request; **cần batch + HWM (A1/A3)** |
| `Supervisor`/heartbeat | ✅ tái dùng (mở rộng) | vòng đời process trong node + node health |
| `ISink` + `PipelineRunner` (spec pipeline-runner) | 🔵 design-ready | engine + đích kết quả (storage optional) |
| **Batch-mux inference + GPU pool** | ❌ MỚI (A1) | gộp N-cam → batch → GPU |
| **Config khai báo + loader/validate** | ❌ MỚI (C2) | khai N cam/model/fps/roi/sink |
| **Budget scheduler + shed** | ❌ MỚI (A2/R2) | phân bổ ngân sách + bỏ tải có kiểm soát |
| **Metric aggregation (push)** | ❌ MỚI (C1/R5) | quan sát fleet |
| **Motion-gate stage** | ❌ MỚI (R2.4) | chặn inference rẻ |
| **Fan-out model + crop stage** | ❌ MỚI (R3) | detect→classify→count đa tầng |

### Cross-node transport (để-ngỏ, so sánh ở design sau)
ZMQ hiện tại đủ cho trong-host/vài-host. Ở ~100 cam nhiều-host, cân nhắc broker (NATS/Redis-stream/Kafka) cho
fan-out + durability + backpressure. **KHÔNG chốt bây giờ** — nêu tiêu chí chọn (độ trễ, durability, ops).

### Cơ chế DECODE (self-review Lỗ 2 — driver công suất, KHÔNG được bỏ trống)
Decode là trần ngang inference. **1 cam = 1 Python-process cv2 KHÔNG scale tới ~100** (overhead process + copy).
Phải chốt (benchmark so sánh, chưa quyết): **hardware decode** — ffmpeg + NVDEC (như Frigate: ffmpeg subprocess),
hoặc GStreamer + nvv4l2decoder (như DeepStream) — GPU giải mã, xuất frame vào SHM. Sub-stream (D1/CIF) cho detect,
main-stream chỉ khi crop/record. → capacity model phải nạp `C_dec` **đo trên cơ chế decode đã chọn**, không phải cv2.

### Analytics CÓ TRẠNG THÁI (self-review Lỗ 3 — lỗ kiến trúc THẬT, nặng nhất)
`count`/`track` cần **trạng thái xuyên-frame theo từng camera** (liên kết đối tượng qua thời gian để không đếm
trùng). Nhưng `Stage` hiện tại **stateless-per-frame** (`MediaPacket` vào→ra, không giữ state). → KHÔNG khớp.
Phương án (chốt ở sub-spec fan-out, chưa quyết): (a) **StatefulStage per-camera** (mỗi camera 1 instance stage giữ
state tracker) — buộc affinity: 1 camera xử cố định 1 worker/thread (không round-robin tuỳ tiện); (b) tách **state
store** (tracker state ngoài) — phức tạp hơn. Hệ quả kiến trúc: **sharding phải giữ camera-affinity** cho analytics
có trạng thái (khác với inference stateless có thể batch tự do). Đây là ràng buộc mới, phải phản ánh vào scheduler.

## Data Models
- **Không DTO mới bắt buộc trong PHA định hướng.** Khi triển khai: `CameraConfig` (id/url/substream/fps/roi/
  analytics/sink), `NodeCapacity` (C_inf/C_dec/V đo được), `ScheduleDecision` (cam→slot/priority), `ShedEvent`
  (đếm). Các DTO này thiết kế chi tiết ở sub-spec tương ứng, giữ ở kernel (thuần dữ liệu).
- Tái dùng `MediaPacket`/`ExecutionResult`/`ShmFrameRefData`/`InferenceRequest` nguyên trạng.

## Correctness Properties

### Property 1: Không vượt ngân sách tài nguyên
Tổng inference/giây thực tế ≤ C_inf đo được của node (scheduler chặn); VRAM sử dụng ≤ V. Khi cầu vượt → shed,
KHÔNG phải OOM/sập.
**Validates: Requirements 2.2, 2.3**

### Property 2: Mất frame luôn quan-sát-được
Mọi frame bị bỏ (motion-gate cố ý / shed quá tải / ring overwrite) PHẢI tăng đúng 1 counter phân loại; tổng
(processed + gated + shed + dropped) == frames_ingested. Không có "mất tích im lặng".
**Validates: Requirements 2.3, 2.4, 5.1**

### Property 3: Scale ngang tuyến tính theo node (tới trần I/O chung)
Thêm 1 node công suất C → tổng camera phục vụ tăng ~N_node, tới khi chạm trần dùng chung (mạng/broker/config).
Camera được shard xác định (1 cam thuộc đúng 1 node tại 1 thời điểm — giữ INVARIANT 1writer/ring).
**Validates: Requirements 1.1, 1.2**

### Property 4: Bật/tắt analytics & storage không đổi lõi
Thêm/bớt 1 tầng analytics hoặc đổi sink CHỈ đổi config + composition, KHÔNG sửa `MediaPacket`/executor/SHM.
**Validates: Requirements 3.3, 4.1, 4.2**

### Property 5: Thiết kế đặt trên số ĐO, không phỏng đoán
Trước khi chốt số node/độ-phủ, có benchmark 1-node (C_inf/C_dec/V) + đo lại tại mỗi nấc 1→10→N.
**Validates: Requirements 6.1, 6.2**

## Error Handling
- **Quá tải:** shed theo policy (drop-oldest/priority) + metric — KHÔNG chặn vô hạn, KHÔNG OOM (Property 1/2).
- **Node chết → re-shard (self-review Lỗ 4 — RỦI RO CAO, KHÔNG phải "chi tiết nhỏ sau"):** camera của node chết
  phải chuyển sang node khác. Đây là **bài toán phân tán KHÓ**: phải tránh **split-brain** (2 node cùng tưởng
  mình sở hữu camera → 2 writer/1 logic-camera → vỡ INVARIANT 1writer/ring + ABA generation). Cần **cơ chế
  ownership/lease phân tán** (fencing token / leader election / lease hết hạn trước khi cấp lại) — KHÔNG tự sinh
  ra được, phải thiết kế riêng (có thể mượn lease pattern đã có trong SHM, nâng lên mức cụm). PHA này ghi nhận
  là **hạng mục rủi ro cao cần sub-spec riêng**, không xem nhẹ.
- **Model lỗi 1 tầng:** bulkhead per-request (K-024) đã có → 1 analytics lỗi không giết node.
- **Backpressure cross-node:** thiết kế transport phải có bound + shed (không dựa HWM mặc định — A3).
- **Config sai:** loader PHẢI validate fail-fast (không khởi động với config hỏng).

## Testing Strategy
- **Benchmark 1-node (bước 0, R6.1):** script đo decode fps / YOLO fps batch1-8-16 / VRAM trên GPU thật (dev
  2060 hiện tại) → điền C_* thật vào capacity model. Đây là VERIFY nền cho mọi con số.
- **Sub-spec sau (mỗi mảnh có test riêng, TDD):** batch-mux (đúng gộp/không lẫn cam) · scheduler (không vượt ngân
  sách, shed đếm đúng) · config loader (validate fail-fast) · motion-gate (chặn đúng) · fan-out (1→N tầng).
- **Scale test 1→10→N:** đo throughput/độ trễ/drop mỗi nấc; so với capacity model.
- Giữ **369/1 + lint 5/0** ở mọi bước (base bất biến; chỉ THÊM).

## Roadmap (tuần tự — mỗi mục = 1 sub-spec design-first riêng, CHỜ valid từng cái)
1. **Vertical slice (giá trị thật trước):** 1 cam → detect → (1 analytics) → event/sink (+ storage optional). Dùng
   `pipeline-runner` (đã design) + `ISink`. Chứng minh luồng nghiệp vụ chạy end-to-end.
2. **Benchmark 1-node** → điền capacity model (số thật).
3. **Batch-mux + GPU pool (A1)** — trần throughput lớn nhất.
4. **Config khai báo + loader (C2)** — vận hành N cam không sửa code.
5. **Budget scheduler + shed + motion-gate (A2/R2)** — chạy trong ngân sách.
6. **Metric aggregation (C1)** — quan sát fleet.
7. **Fan-out đa-analytics (R3)** + **re-shard khi node chết** + **transport-ở-quy-mô** (chốt công nghệ).

## Open Decisions (để-ngỏ có chủ đích — chốt ở sub-spec khi tới)
- Transport quy mô: giữ ZMQ vs thêm broker (NATS/Redis-stream/Kafka) — theo tiêu chí độ trễ/durability/ops.
- Config format: YAML/TOML + schema validate (pydantic?) — chốt khi làm C2.
- Metrics backend: Prometheus pull vs OTel push — chốt khi làm C1.
- Inference serving: tự viết batch-mux vs nhúng Triton — cân license/ops/độ-phức-tạp.

## Self-Review (doubt-driven — tự phản biện thiết kế NÀY)
Đã cố PHÁ chính thiết kế này, tìm được 4 lỗ + đã vá vào tài liệu:
- **Lỗ 1 (capacity model bậc-1):** thiếu latency-SLA + `A` biến thiên + decode/inference tranh GPU → đã thêm mục
  "GIỚI HẠN CỦA MÔ HÌNH" + yêu cầu đo đồng-thời + ràng buộc latency_p99/batch_timeout.
- **Lỗ 2 (decode bỏ trống):** đã thêm mục "Cơ chế DECODE" (hardware ffmpeg/NVDEC/GStreamer, không cv2-per-process).
- **Lỗ 3 (analytics có trạng thái — nặng nhất):** Stage stateless không khớp count/track → đã thêm mục "Analytics
  CÓ TRẠNG THÁI" (StatefulStage + **camera-affinity** ràng buộc scheduler).
- **Lỗ 4 (failover coi nhẹ):** đã nâng re-shard thành **rủi ro cao** (split-brain / fencing / lease phân tán).
**Còn mở có chủ đích (chưa vá vì thuộc sub-spec sau, không phải thiếu sót):** chọn transport quy mô · config
hot-reload (thêm/bớt camera runtime không restart fleet) · metrics backend · self-viết-batch vs Triton.
**Phán quyết:** ĐỦ TỐT làm **bản định hướng PHA-1** (đã trung thực về giới hạn + lỗ + rủi ro cao). KHÔNG đủ làm
thiết kế thi công — mỗi mảnh cần sub-spec design-first riêng (đặc biệt: batch-mux, stateful-analytics, failover).

## Glossary
- **C_inf / C_dec / V** — công suất inference/decode/VRAM đo được per-node (tham số, không hằng bịa).
- **camera-affinity** — analytics có trạng thái buộc 1 camera xử cố định 1 worker (không round-robin tự do).
- **split-brain / fencing** — 2 node cùng tưởng sở hữu 1 camera; fencing token/lease chống ghi kép.
- **data/control/observability plane** — 3 mặt phẳng: xử-lý-frame / điều-phối / quan-sát.
- **batch-mux** — gộp frame nhiều camera thành 1 batch inference (tăng C_inf).
- **re-shard** — gán lại camera của node chết sang node sống (giữ 1writer/ring).
- **vertical slice** — lát cắt dọc 1-cam-đến-sink chạy thật, làm TRƯỚC scale-out.
