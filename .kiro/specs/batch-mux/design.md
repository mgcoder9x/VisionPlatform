# Design Document — Batch-Mux Inference (nâng `C_inf` per-GPU)

> **Trạng thái:** PHA 1 (design DESIGN-FIRST) — CHỜ user đọc-lại-valid. KHÔNG code.
> **Là sub-spec của:** `.kiro/specs/scale-architecture/` (roadmap #3 "Batch-mux + GPU pool", trụ #3, A1/K-040).
> **Gắn số đo THẬT:** K-089 (60 infer/s @batch=1) · K-090 (e2e 720p 47.77fps) · **K-092 (đa-luồng K-session rời: K=4 → 104.7 infer/s aggregate, per-stream p95 49.5ms)** — baseline batch-mux PHẢI vượt mới đáng.
> **Cập nhật lúc:** 2026-07-13 (REVIEW #369 đọc-lại-valid: +mục "Batch-mux ↔ analytics stateful" + Property 6 thứ-tự-per-camera + siết Property 2 latency + Lỗ 7 — phát hiện bằng đọc `TrackingStage`/`IouTracker` thật).

## Overview

**Batch-mux = gộp frame của NHIỀU camera thành 1 tensor `[B,3,640,640]` chạy 1 lần `session.run` trên GPU**, thay vì
mỗi camera 1 lần `run` batch=1. Mục tiêu DUY NHẤT: **nâng trần inference per-GPU `C_inf`** — đòn bẩy throughput lớn
nhất trong capacity model (`N_infer ≈ C_inf/(f·g·A)`), để 1 RTX 2060 gánh nhiều camera hơn ~8-13 hiện tại.

**Đây KHÔNG phải "chạy nhanh hơn" mà là "dùng GPU hiệu quả hơn":** GPU là bộ xử-lý song song hàng nghìn lõi; batch=1
để phần lớn SM (streaming multiprocessor) NHÀN + trả giá overhead cố định mỗi lần `run` (launch kernel, đồng bộ
host↔device). Gộp batch **khấu hao** overhead đó và **lấp đầy** SM → throughput/GPU-giây tăng. Đây là cơ chế
DeepStream `nvstreammux` và Triton `dynamic_batching` dùng.

## Vấn đề & TẠI SAO (Forces — đặt trước giải pháp)

**Force 1 — throughput vs latency (mâu thuẫn cốt lõi):** để gộp batch phải CHỜ đủ frame từ nhiều camera. Chờ =
thêm độ trễ. Batch lớn → throughput cao nhưng latency cao (frame đến sớm phải đợi frame đến muộn). Đây là đánh đổi
KHÔNG thể tránh, phải tham-số-hoá (`max_batch`, `batch_timeout_ms`) + đo.

**Force 2 — batch-mux có THẬT SỰ thắng K-session-rời không? (nghi vấn sống-còn, chưa kiểm):** K-092 đã đo K session
CUDA rời đồng-thời = 104.7 infer/s @K=4 — nghĩa là **GPU ĐÃ được lấp khá đầy** bởi chồng-lấp compute giữa các
session (aggregate 2.25x khi K=4). Câu hỏi: batching THẬT (1 session, B-dim) có vượt 104.7/s không, hay GPU đã gần
bão hoà với yolov8n (model NHỎ)? → **Không được giả định batch-mux thắng.** Tiêu chí nghiệm thu = **ĐO** batched
throughput > 104.7/s @ latency chấp nhận được. Nếu KHÔNG vượt → batch-mux KHÔNG đáng cho model+GPU này (kết luận
hợp lệ, phải trung thực ghi nhận).

**Force 3 — VRAM hữu hạn (6GB):** batch B → activation memory ~B lần. Phải chọn B sao cho không OOM. Trần VRAM là
ràng buộc cứng, khác throughput (mềm).

**Force 4 — CPU preprocess trở thành nút khi batch lớn (K-084 áp dụng):** batch-mux làm GPU-infer/frame RẤT nhỏ
(khấu hao) → preprocess-CPU (letterbox+normalize) tương đối LỚN lên. K-084 cảnh báo đúng ca này: phải preprocess
song song / trên GPU, không tuần tự 1 lõi.

## Ràng buộc ĐÃ VERIFY (bằng đọc code + chạy thật — KHÔNG suy đoán)

| # | Ràng buộc | Bằng chứng | Hệ quả thiết kế |
|---|---|---|---|
| RB-1 | Model `yolov8n.onnx` hiện tại input **cố định `[1,3,640,640]`**; `run` batch=2/4 → `InvalidArgument: Got 2 Expected 1` | Chạy `_tmp_probe_batch.py` (describe_onnx + run thật batch 1/2/4) | **Tiên quyết:** phải RE-EXPORT model với trục batch ĐỘNG (`dynamic=True`) trước khi batch-mux chạy được |
| RB-2 | Port `IDetector.detect(frame)->list[Detection]` là **single-frame** | Đọc `kernel/ports/detector.py` | Thêm khả năng batch KHÔNG được phá port cũ (backward-compat) → port/adapter batch RIÊNG |
| RB-3 | `OnnxDetector.detect`: `preprocess(frame)`→`session.run(None,{name:tensor})`→`postprocess`; `chw_float_normalize` tạo NCHW **batch=1 cứng** (`arr[np.newaxis]`) | Đọc `adapters/onnx_detector.py` | preprocess/postprocess batch = hàm MỚI (stack B / split B), không sửa hàm cũ |
| RB-4 | `postprocess_fn` trả **list[Detection] phẳng** cho 1 sample | Đọc `onnx_detector.py` + `yolov8_decode` | postprocess batch phải tách output theo trục batch → list[list[Detection]] |
| RB-5 | `DetectorPipeline.detect(frame)` letterbox per-frame + inverse per-frame | Đọc `adapters/detector_pipeline.py` | coordinate-transform per-camera (mỗi cam kích thước gốc khác nhau) phải giữ per-sample trong batch |

**RB-1 là chặn cứng:** nếu không re-export model dynamic-batch, toàn bộ design này BẤT ĐỘNG. Đây là task #0 của pha thi công.

## Architecture

```
  N camera-worker (mỗi cam 1 luồng/process)          BATCH-MUX (1 cho mỗi GPU session)              GPU
  ┌───────────┐  submit(cam_id, frame_id, frame)   ┌────────────────────────────────────┐
  │ cam A ────┼──────────────┐                      │  inbound queue (bounded, có shed)   │
  │ cam B ────┼──────────────┼───────────────────▶ │        │                            │
  │  ...      │               │                      │  GATHER loop:                       │
  │ cam N ────┼──────────────┘                      │   gom tới max_batch HOẶC             │
  └───────────┘                                      │   batch_timeout_ms (cái nào trước) │
        ▲                                            │        │                            │
        │ future(result) ◀── scatter theo request_id │   preprocess_batch → stack [B,3,H,W]│──run──▶ [B,84,8400]
        │                                            │        │                            │◀──────┘
        └────────────────────────────────────────────  postprocess_batch → split B →       │
                                                       │   route list[Detection] về đúng cam│
                                                       └────────────────────────────────────┘
```

**Luồng 1 chu kỳ (gather→infer→scatter):**
1. Camera-worker `submit(request)` → đẩy vào inbound queue (bounded; đầy → shed + đếm metric, KHÔNG chặn vô hạn).
2. Gather loop lấy items tới khi đủ `max_batch` HOẶC quá `batch_timeout_ms` kể từ item đầu tiên (cái nào tới trước).
3. `preprocess_batch`: mỗi frame → letterbox→model-size + CHW/float → **stack** thành `[B,3,640,640]`.
4. **1 lần** `session.run(None, {input: batch_tensor})` → `[B,84,8400]`.
5. `postprocess_batch`: **tách** theo trục batch → decode+NMS mỗi sample → inverse-letterbox per-sample (mỗi cam kích thước gốc riêng, RB-5).
6. Scatter: route `list[Detection]` sample i về đúng camera qua `request_id` (Property 1 = không lẫn cam).

## Components and Interfaces

### Bản đồ TÁI DÙNG vs THÊM MỚI (chống rebuild — bám nguyên tắc không đập lõi)
| Thành phần | Trạng thái | Vai trò |
|---|---|---|
| `IDetector.detect(frame)` (port) | ✅ GIỮ NGUYÊN | đường single-frame cũ không đổi (backward-compat RB-2) |
| `OnnxDetector` (session, providers CUDA, cuda_dll_path) | ✅ tái dùng phần setup/session | chia sẻ cơ chế nạp session GPU đã có (D-097/098) |
| `yolov8_decode` / NMS / `LetterboxTransform` | ✅ tái dùng per-sample | decode + inverse mỗi sample trong batch |
| `BoundedQueue` (4 policy, K-016) | ✅ tái dùng | inbound queue có shed — KHÔNG viết mới |
| `InMemoryMetrics` + observability | ✅ tái dùng | đếm batch_size, shed, latency (Property 2/5) |
| **`preprocess_batch` / `postprocess_batch`** | ❌ MỚI (thuần, @adapters/domain) | stack B / split B — hàm thuần, test không cần GPU |
| **`BatchOnnxDetector`** (hoặc mở rộng OnnxDetector) | ❌ MỚI @adapters | nhận `list[frame]` → `[B,...]` run → `list[list[Detection]]` |
| **`BatchMuxer`** | ❌ MỚI @application | gather-scatter loop + batch_timeout + queue + route theo request_id |
| **`IBatchDetector` port** (tuỳ chọn) | ❌ MỚI @kernel | `detect_batch(frames)->list[list[Detection]]` — hợp đồng batch |

### Quyết định interface (nêu rõ, chờ valid)
- **KHÔNG sửa `IDetector`** (giữ single-frame). Thêm port RIÊNG `IBatchDetector.detect_batch(frames: list[np.ndarray]) -> list[list[Detection]]`
  (song song, không kế thừa) → adapter có thể thoả CẢ HAI. Lý do: batch là quan-tâm KHÁC (nhiều frame + định danh),
  ép vào port cũ sẽ bẻ cong hợp đồng single-frame mà mọi chỗ đang dùng.
- **`BatchMuxer` ở application** (composition): nhận `IBatchDetector` + `BoundedQueue` qua DI → thuần điều-phối,
  không biết onnx cụ thể (giữ hexagonal: application phụ thuộc kernel+runtime, không adapter).
- **`preprocess_batch`/`postprocess_batch` thuần** (domain/adapters, numpy-only) → test tính-đúng KHÔNG cần GPU/model thật.

### Batch-mux ↔ analytics CÓ TRẠNG THÁI (REVIEW #369 — đọc `TrackingStage`/`IouTracker` THẬT)
**Phát hiện khi đọc-lại-valid:** batch-mux gộp frame NHIỀU camera → mâu thuẫn BỀ MẶT với camera-affinity (scale-arch
Lỗ 3: `TrackingStage._source_id` guard K-042 — 1 instance/1 camera, nhận 2 source_id → raise "đếm loạn"). Giải quyết
BẢN CHẤT (không vá ngọn):
- **Ranh giới mux = tại `IDetector`/`IBatchDetector` (STATELESS per-frame)** → gộp cross-camera AN TOÀN cho inference
  (mỗi frame độc lập, không state). Mux nằm **THƯỢNG NGUỒN** mọi stage stateful.
- **Scatter trả detections về ĐÚNG pipeline từng camera** (theo `request_id`) → `TrackingStage` per-camera giữ nguyên
  affinity K-042 (không bao giờ thấy 2 source_id). Batch-mux KHÔNG đụng stage stateful.
- **INVARIANT THỨ TỰ (sống-còn, đã VERIFY bằng đọc code):** `IouTracker.update()` PHỤ THUỘC THỨ TỰ (mỗi lần `age += 1`
  toàn bộ track + associate frame-trước) → detections của cùng camera PHẢI trả downstream theo ĐÚNG thứ tự `frame_id`.
  Gather-infer loop TUẦN TỰ (1 session/1 thread) + queue FIFO ⇒ thứ tự bảo toàn tự nhiên. NẾU nhiều mux-worker song song
  → BẮT BUỘC re-order theo `frame_id` per-camera trước khi feed stateful stage (Property 6).

## Data Models
_(kernel — thuần dữ liệu)_
- `BatchRequest{ request_id: str, camera_id: str, frame_id: int, frame: np.ndarray }` — 1 frame chờ infer (định danh để scatter).
- `BatchItem{ request_id, orig_h, orig_w }` — metadata per-sample để inverse-letterbox đúng (RB-5).
- Tái dùng `Detection` (kernel/inference_protocol) nguyên trạng.
- KHÔNG DTO thừa: latency/batch_size là metric (không DTO).

## Correctness Properties
_(executable — cho PBT)_

### Property 1: Không lẫn camera (identity qua mux/demux)
Với batch gồm frame từ các request `[r0..r_{B-1}]`, kết quả trả về request `r_i` PHẢI là detections của ĐÚNG frame
`r_i` (không của `r_j`, j≠i). Kiểm bằng model-tí-hon tạo output phụ-thuộc-sample (marker) → assert route đúng.
**Validates: Requirements 1.1** (không trộn dữ liệu camera).

### Property 2: Latency bị chặn (không frame nào chờ vô hạn)
Gather loop PHẢI flush khi hết `batch_timeout_ms` dù batch chưa đầy → không deadlock "chờ batch đầy mãi". Latency
end-to-end 1 frame = `queue_wait + gather_wait(≤batch_timeout_ms) + t_preprocess_batch + t_infer + t_postprocess`
(KHÔNG chỉ `timeout + t_infer` — phải kể queue-wait khi tải cao + pre/postprocess); tổng có TRẦN hữu hạn theo tải,
đo per-camera (Lỗ 6). SLA kiểm bằng p95/p99 dưới tải mục tiêu, không trung bình.
**Validates: Requirements 2.1** (SLA latency bị chặn).

### Property 3: Bất biến bảo toàn frame (shed quan-sát-được)
`submitted == processed + shed_queue_full + error`. Frame bị bỏ khi queue đầy PHẢI tăng counter (không mất im lặng).
**Validates: Requirements 2.2** (shed có kiểm soát — kế thừa scale-arch Property 2).

### Property 4: Tương đương kết quả single vs batch (đúng-đắn số học)
Với cùng model dynamic-batch, `detect_batch([f0,f1])[i]` cho detections TƯƠNG ĐƯƠNG `detect(f_i)` đơn lẻ (sai khác chỉ
do thứ tự float, trong dung sai). Batching KHÔNG được đổi KẾT QUẢ, chỉ đổi throughput.
**Validates: Requirements 1.2** (batch không sai lệch phát hiện).

### Property 5: Thiết kế đặt trên số ĐO (nghiệm thu = benchmark)
Batch-mux chỉ được coi "đáng dùng" khi ĐO được batched-throughput > baseline K-092 (104.7/s @K4) ở latency-SLA. Số đo
phải ghi lại (bench). Nếu không vượt → ghi nhận trung thực "không đáng cho model+GPU này".
**Validates: Requirements 3.1** (nghiệm thu = benchmark vượt baseline; kế thừa R6.1 scale-arch).

### Property 6: Thứ tự frame per-camera được bảo toàn qua mux
WHEN nhiều frame của CÙNG một camera đi qua mux, THE detections trả downstream PHẢI theo ĐÚNG thứ tự `frame_id` gốc
(không đảo). Lý do đã VERIFY: `IouTracker.update()` phụ thuộc thứ tự (age++ + associate frame-trước mỗi lần gọi) →
đảo thứ tự = hỏng tracking/đếm. (Cross-camera KHÔNG cần thứ tự; chỉ intra-camera.) Kiểm bằng submit xen kẽ nhiều camera
+ nhiều frame/camera → assert thứ tự trả về mỗi camera đơn điệu theo `frame_id`.
**Validates: Requirements 1.4** (thứ tự frame per-camera cho analytics stateful).

## Error Handling
- **Model batch cố định (RB-1):** `BatchOnnxDetector.setup()` PHẢI dò input shape; nếu trục 0 cố định >1 hoặc ==1
  (không động) → **fail-fast** thông báo rõ: "model input batch axis cố định; re-export dynamic batch (ultralytics
  `export(dynamic=True)`)". KHÔNG chạy ngầm rồi nổ khó hiểu ở `run`.
- **Batch một phần (timeout, B < max_batch):** model dynamic chấp nhận mọi B ≤ max → chạy với B thật. Không pad giả
  (pad = tính lãng phí + có thể lẫn kết quả nếu quên loại).
- **Lỗi postprocess 1 sample:** bulkhead per-sample — 1 sample decode lỗi KHÔNG giết cả batch; sample đó trả lỗi/rỗng
  + đếm metric, các sample khác vẫn route bình thường (kế thừa tinh thần K-024 bulkhead).
- **Queue đầy:** shed theo policy BoundedQueue (drop-oldest/newest) + counter (Property 3), KHÔNG chặn vô hạn.
- **VRAM OOM:** chọn `max_batch` dưới trần VRAM đo được; nếu `run` ném OOM → giảm batch + log (không sập process).

## Testing Strategy
_(TDD, phần lớn KHÔNG cần GPU)_
- **Model-tí-hon dynamic-batch tự tạo** (license sạch, như test OnnxDetector hiện có): input `[N,3,h,w]` động, output
  phụ-thuộc-sample (vd trả tổng pixel) → verify **Property 1 (identity)** + **Property 4 (tương đương)** + mux/demux
  KHÔNG cần YOLO/GPU. Đây là cột sống test.
- **`preprocess_batch`/`postprocess_batch` thuần numpy:** property test stack/split đúng shape + thứ tự (B frame kích
  thước khác nhau → letterbox riêng → stack đồng shape model → split trả đúng số detections/sample).
- **`BatchMuxer` gather loop:** test **Property 2 (timeout flush)** bằng fake clock/detector chậm — submit 1 frame,
  không đủ batch, assert vẫn được xử lý sau `batch_timeout_ms` (event-driven, không sleep-cứng — bài học K-035/D-077).
- **Property 3 (shed):** queue nhỏ + submit dồn → assert `submitted == processed + shed`.
- **Bench GPU (Property 5, cần model re-export + GPU):** đo batched-throughput B=1/2/4/8 vs K-092 baseline → điền
  capacity model bản-3. Đây là VERIFY nghiệm thu, chạy trên RTX 2060 hiện có.
- Giữ **647/2 + lint 5/0 + drift PASS** ở mọi bước (chỉ THÊM, không phá base).

## Self-Review (doubt-driven — tự PHÁ thiết kế này)
Đã cố tìm lỗ, nêu trung thực:
- **Lỗ 1 (batch-mux có thể KHÔNG thắng — nghi vấn lớn nhất, [chưa kiểm]):** K-092 cho thấy K-session-rời ĐÃ đạt
  104.7/s @K4 (GPU chồng-lấp compute tốt). yolov8n NHỎ → có thể GPU gần bão-hoà ở batch=1, batching cho lợi ÍT.
  → Không giả định thắng; nghiệm thu = ĐO (Property 5). Nếu thua/hoà → kết luận "không đáng", vẫn là kết quả hợp lệ
  (tránh sunk-cost). **Đây là lý do design-first + bench TRƯỚC khi build đầy đủ.**
- **Lỗ 2 (RB-1 model cố định — đã VERIFY):** thiết kế bất động nếu không re-export dynamic-batch → đưa thành task #0.
- **Lỗ 3 (batch_timeout khó chỉnh):** quá dài = latency spike; quá ngắn = batch tí hon (vô ích). Phải đo đường cong
  throughput↔latency theo timeout, chọn theo SLA — không hard-code.
- **Lỗ 4 (CPU preprocess nút — K-084):** stack B frame = B lần letterbox+normalize tuần tự trên CPU → khi B lớn +
  GPU-infer/frame nhỏ, CPU preprocess vượt lên thành nút. Cần preprocess song song (thread-pool) hoặc GPU-preprocess.
  Ghi nhận là rủi ro thi công, đo `t_pre_batch` khi bench.
- **Lỗ 5 (chi phí copy stack):** gộp B frame vào mảng liền kề = B lần copy bộ nhớ. Nhỏ so infer nhưng phải đo, không bỏ qua.
- **Lỗ 6 (interleave latency không đều):** camera fps khác nhau → frame đến lệch pha; gather có thể gom lệch → 1 số cam
  latency cao hơn. Cần đo per-camera latency, không chỉ aggregate.
- **Lỗ 7 (batch-mux vs stateful analytics + THỨ TỰ — phát hiện REVIEW #369, đọc code thật):** gộp cross-camera mâu thuẫn
  BỀ MẶT với camera-affinity K-042 (`TrackingStage._source_id`) + `IouTracker.update` phụ thuộc thứ tự frame. Đã vá:
  mục "Batch-mux ↔ analytics CÓ TRẠNG THÁI" (mux ở ranh giới stateless IDetector, thượng nguồn stage stateful; scatter
  giữ affinity) + Property 6 (thứ tự per-camera) + siết Property 2 (latency đủ chuỗi). Đây là lỗ BẢN CHẤT (không phải
  ngọn): nếu bỏ qua, batch-mux sẽ làm hỏng tracking/đếm khi bật analytics stateful downstream.

**Còn mở có chủ đích (chốt khi tới):** self-viết mux vs nhúng **Triton** (Triton làm dynamic-batching sẵn, ops nặng
hơn nhưng khỏi tự-viết); thread vs process vs asyncio cho gather loop; batch-mux có nên tích hợp ZMQ inference-server
hiện có (DEALER/ROUTER) hay đứng riêng.

**Phán quyết:** ĐỦ làm **design-first PHA-1** (trung thực về nghi vấn thắng-thua + ràng buộc đã-verify + lỗ). CHƯA đủ
thi công đầy đủ — nhưng ĐỦ để làm **spike đo bench trước** (task #0 re-export + task bench) nhằm trả lời Force-2/Lỗ-1
TRƯỚC khi đầu tư BatchMuxer đầy đủ. Đây là cách rẻ nhất để biết batch-mux có đáng không.

## Open Decisions (để-ngỏ, chốt ở sub-quyết định khi tới)
- **Self-viết BatchMuxer vs Triton Inference Server:** tự-viết = kiểm soát + học + nhẹ; Triton = dynamic-batching +
  model-repo + metrics sẵn nhưng ops nặng (container — mà máy này KHÔNG docker → Triton native khó). → nghiêng tự-viết.
- **Concurrency của gather loop:** thread (GIL nhả khi `session.run` C-level — khả thi) vs process (copy frame đắt) vs
  asyncio. → nghiêng thread (1 GPU session 1 thread mux, preprocess thread-pool).
- **Re-export model:** ultralytics `export(format=onnx, dynamic=True, ...)` trong venv throwaway (repro K-083/K-087) —
  cần đèn xanh network. HOẶC dùng model tí-hon dynamic tự tạo để verify logic mux TRƯỚC (không cần network).
- **max_batch / batch_timeout_ms mặc định:** chốt bằng đường cong đo, không đặt bừa.

## Glossary
- **batch-mux** — gộp frame nhiều camera thành 1 tensor `[B,...]` chạy 1 `session.run` (tăng `C_inf`).
- **dynamic batch axis** — model ONNX có trục 0 (batch) = 'N' động, chấp nhận B bất kỳ (khác `[1,...]` cố định — RB-1).
- **gather-scatter** — gom frame vào batch (gather) rồi phân kết quả về đúng camera (scatter) theo `request_id`.
- **batch_timeout** — thời gian tối đa chờ gom batch trước khi flush batch chưa đầy (đánh đổi throughput↔latency).
- **C_inf** — inference/giây trần per-GPU (capacity model scale-architecture); batch-mux nhằm nâng số này.
- **K-session-rời** — K session CUDA độc lập chạy song song (baseline K-092: K=4→104.7/s) — khác batch THẬT (1 session B-dim).
