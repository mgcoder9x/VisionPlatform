# Design Document

> **Trạng thái:** PHA 1 (design phương pháp đo) — CHỜ user đọc-lại-valid. KHÔNG code.
> **Gắn với:** `requirements.md` cùng thư mục · `scale-architecture` (Capacity Model) · K-041 · K-047 (máy dev no-GPU).
> **Cập nhật lúc:** 2026-07-06.

## Overview

Mục tiêu: **đo THẬT** các tham số capacity per-node để điền vào `scale-architecture` (C_inf, C_dec, combined,
V, latency), theo phương pháp **tái lập + trung thực + đo trên hệ thật**. Tài liệu này chốt PHƯƠNG PHÁP (đo cái gì,
đo thế nào, tránh sai ở đâu) + mẫu bảng kết quả RỖNG. Số thật điền sau khi chạy harness trên **máy GPU** (WSL/2060).

**Vì sao design-first (không code liền):** đo sai phương pháp → ra số sai → thiết kế capacity sai (fix ngọn). Cái
GỐC cần chốt trước là *đo thế nào cho đúng bản chất* (steady-state, percentile, đo đồng thời decode+infer). Chốt
phương pháp xong mới viết harness — đúng nguyên tắc "thiết kế rõ, valid, rồi mới triển khai".

## Ranh giới máy đo (TRUNG THỰC — K-047)

| Đo gì | Máy `endgame` (hiện tại, no-GPU/no-torch) | Máy GPU (WSL/RTX2060) |
|---|---|---|
| Logic harness (đọc frame, đóng dấu thời gian, tính percentile) | ✅ verify được bằng nguồn fake/`FakeDetector` (CPU) | ✅ |
| C_inf / C_dec / combined / VRAM / latency THẬT | ❌ KHÔNG (không có torch/GPU) → **cấm điền số** | ✅ điền số thật |

→ PHA 2: viết harness + verify logic ở máy này (fake); **chạy lấy số thật CHỈ ở máy GPU**. Mọi ô số giữ `[chưa đo]`
cho tới lúc đó. Đây là ranh giới bắt buộc theo luật §5 (không bịa, không suy đoán).

## Architecture

Kiến trúc phép đo = 4 chế độ đo (M1–M4) chạy trên hệ THẬT, mỗi chế độ cô lập đúng thứ cần đo:

```
                 nguồn frame thật                     đo (harness, ngoài src/)
 video/rtsp ──▶ VideoFileFrameSource/Rtsp… ─┐
 (cv2 decode)                               │  M2 decode-only: đếm fps đọc (không infer)
                                            ├─▶ M1 infer-only: frame dựng-sẵn → Yolov5PtDetector → infer/s (batch 1/8/16)
 GPU (1×) ◀── Yolov5PtDetector (torch) ─────┤  M4 latency: đóng dấu perf_counter quanh infer → p50/p95/p99
                                            └─▶ M3 VRAM: torch.cuda.max_memory_allocated + nvidia-smi
   M2-combined: decode + infer ĐỒNG THỜI trên cùng GPU → throughput kết hợp (số định cỡ THẬT, tính contention)
```

Nguyên tắc: **cô lập biến khi đo trần riêng** (M1 dùng frame dựng sẵn để loại nhiễu decode; M2 decode-only không
infer), NHƯNG **đo kết hợp để lấy số định cỡ** (M2-combined) — vì trên 1 GPU decode+infer tranh tài nguyên. Harness
KHÔNG đụng `src/`; chỉ import + gọi component thật.

## Phương pháp đo (cốt lõi — mỗi metric + cách tránh sai)

### Nguyên tắc chung (áp cho mọi phép đo)
1. **Warmup:** bỏ `W` frame/lần chạy đầu (JIT torch, cudnn autotune, allocator, cache model chưa ấm). Đề xuất W≥20 (chốt bằng quan sát khi đường cong phẳng).
2. **Steady-state window:** đo trong cửa sổ cố định (vd `M` frame hoặc `T` giây) sau warmup.
3. **Lặp `R` lần** (vd R=5) → báo cáo **median + p95/p99 + min/max**, KHÔNG lấy 1 lần (chống nhiễu).
4. **Đóng dấu thời gian bằng `time.perf_counter_ns`** (đồng hồ đơn điệu độ phân giải cao) — KHÔNG dùng wall-clock cho đo khoảng.
5. **Đồng bộ CUDA trước khi chốt thời gian:** GPU chạy bất đồng bộ → phải `torch.cuda.synchronize()` trước khi đọc mốc kết thúc, nếu không đo hụt (đo ra "nhanh giả"). [điểm dễ sai — bắt buộc].
6. **Cô lập tải:** máy đo phải rảnh (không chạy pytest/web song song — K-035). Harness in cảnh báo nếu phát hiện tải lạ (R5.4).

### M1 — C_inf (inference throughput theo batch) [R1]
- **Chuẩn bị:** nạp `Yolov5PtDetector(weights, device="cuda")` (tái dùng, K-034). Chuẩn bị `B` frame cùng kích thước (đọc sẵn từ video → loại nhiễu decode khỏi phép đo inference).
- **batch=1:** lặp gọi `detector.detect(frame)` M lần; `infer/s = M / tổng_thời_gian` (sau warmup + cuda.synchronize).
- **batch=8/16:** gọi model NỀN `detector._model([f1..fB])` (AutoShape nhận list) — VÌ `IDetector.detect` chỉ theo-frame (đọc code `kernel/ports/detector.py` + `yolov5_pt_detector.py`). Ghi rõ trong kết quả: "đo dưới tầng port; port CHƯA hỗ trợ batch = lỗ A1" (không giả vờ port batch được).
- **Xuất:** infer/s mỗi batch + hệ số scaling (infer/s@8 ÷ infer/s@1) → cho thấy lợi ích batching (định lượng trụ A1).

### M2 — C_dec + combined (decode và tranh GPU) [R2]
- **Decode-only baseline:** chạy `VideoFileFrameSource(path)` (hoặc RTSP sub-stream) đọc liên tục, KHÔNG inference; `dec_fps = frame_đọc / thời_gian`. Ghi rõ: **cv2-per-process** (không phải NVDEC) → là baseline, không phải trần production (Lỗ 2 scale-arch).
- **Combined (QUAN TRỌNG):** chạy decode + inference ĐỒNG THỜI (2 thread/process trên cùng GPU) → đo throughput kết hợp end-to-end. So sánh với `min(C_dec, C_inf)`: nếu combined < min → định lượng GPU contention (đúng như Lỗ 1 cảnh báo). **Đây mới là số dùng để định cỡ**, không phải số riêng lẻ.
- **Sub-stream:** đo thêm ở độ phân giải thấp (D1/CIF) nếu có → cho thấy sub-stream hạ tải decode/VRAM thế nào.

### M3 — VRAM [R3]
- Trước load: `torch.cuda.reset_peak_memory_stats()`. Sau load model + sau vài inference batch B: đọc `torch.cuda.max_memory_allocated()` (+ đối chiếu `nvidia-smi` cho tổng thực gồm cả context). Ghi VRAM@load, VRAM@batch1/8/16, tổng V của card.

### M4 — Latency end-to-end theo percentile [R4]
- Đo mỗi frame: `t0 = perf_counter_ns()` khi có frame → chạy inference (+ cuda.synchronize) → `t1`; `latency = t1−t0`. Gom list latency (steady-state) → tính p50/p95/p99/max bằng `statistics.quantiles`/`numpy.percentile`.
- VÌ `RunStats` (đọc `runtime/pipeline_runner.py`) KHÔNG có field thời gian → đo NGOÀI RunStats (harness tự đóng dấu quanh bước inference). Ghi rõ điểm instrument.
- Báo cáo latency ở batch {1,8,16} cạnh nhau → lộ đánh đổi: batch↑ → throughput↑ nhưng latency↑ (chờ gom batch). Nuôi ràng buộc `latency_p99 ≤ SLA` + `batch_timeout` của scale-arch.

## Components and Interfaces

### Vị trí + ranh giới
- Đặt ở **`benchmarks/`** (gốc `vision-platform/`), NGOÀI `src/vision_platform` — là công cụ dev, không phải runtime (ranh giới K-022, giống `build`). KHÔNG thêm dependency runtime; torch/yolov5 chỉ cần khi chạy thật (đã có ở env `.[pt]`).
- KHÔNG sửa `src/` → baseline test/lint giữ nguyên (R6.3).

### Thành phần (dự kiến — chốt chi tiết ở PHA 2)
```
benchmarks/
  bench_capacity.py     # entrypoint: --mode {infer,decode,combined,latency,all} --weights --video/--rtsp
                        #   --device cuda --batch 1,8,16 --warmup 20 --measure 200 --repeat 5
  _stats.py             # gom mẫu → median/p50/p95/p99/max + in bảng + header môi trường
  _env.py               # thu thập môi trường (torch.__version__, cuda, GPU name qua nvidia-smi, weight, imgsz)
  README.md             # cách chạy trên máy GPU + cảnh báo cô lập tải
```
- Tái dùng: `Yolov5PtDetector` (infer), `VideoFileFrameSource`/`RtspFrameSource` (decode) — import từ `vision_platform` (đã cài editable). KHÔNG dựng detector/decode giả để đo (R6.1).
- Output: in ra stdout dạng bảng + tùy chọn ghi `benchmarks/results/<ngày>-<gpu>.md` (điền vào template dưới).

### Verify logic harness ở máy no-GPU (máy `endgame`)
- Chạy `bench_capacity.py --mode latency --device cpu` với `FakeDetector` + nguồn fake → kiểm harness TÍNH percentile/throughput ĐÚNG (so với input dựng sẵn đã biết đáp án). Đây là test LOGIC harness (chạy được không GPU), KHÔNG phải số capacity.
- (Tùy chọn) 1-2 unit test cho `_stats.py` (percentile trên list đã biết) trong `benchmarks/` — chạy được máy dev, giữ baseline.

## Data Models

Cấu trúc dữ liệu của harness (thuần đo, KHÔNG vào `src/` — chốt chi tiết PHA 2):
- **`EnvInfo`** — header môi trường: `gpu_name`, `driver_cuda`, `torch_version`, `yolov5_version`, `weight_path`, `imgsz`, `os` (R5.1). Bắt buộc kèm mọi kết quả.
- **`MetricSample`** — 1 mẫu đo: `metric` (infer/decode/latency), `batch`, `value`, `unit` (infer/s · frame/s · ms), `t_ns`. Gom list → thống kê.
- **`Stats`** — kết quả tổng hợp 1 phép đo: `median`, `p50`, `p95`, `p99`, `min`, `max`, `n_samples`, `warmup_dropped`, `repeats` (R5.2).
- **`ResultRow`** — 1 dòng bảng kết quả (batch/fps/scaling/VRAM/latency) → render markdown template dưới.
- Tái dùng nguyên trạng `Detection`/`ReadResult` từ `vision_platform` (chỉ đọc, không đổi). KHÔNG thêm DTO vào kernel (harness là công cụ ngoài).

## Bảng kết quả (TEMPLATE RỖNG — điền trên máy GPU, KHÔNG bịa)

**Môi trường (điền lúc chạy):** GPU=`[chưa đo]` · driver/CUDA=`[chưa đo]` · torch=`[chưa đo]` · yolov5=`[chưa đo]` · weight=`[chưa đo]` · imgsz=`[chưa đo]` · OS=`[chưa đo]`

**M1 — Inference (C_inf):**
| batch | infer/s | scaling vs b1 | VRAM (MB) | latency p50/p95/p99 (ms) |
|---|---|---|---|---|
| 1 | `[chưa đo]` | 1.0× | `[chưa đo]` | `[chưa đo]` |
| 8 | `[chưa đo]` | `[chưa đo]` | `[chưa đo]` | `[chưa đo]` |
| 16 | `[chưa đo]` | `[chưa đo]` | `[chưa đo]` | `[chưa đo]` |

**M2 — Decode + combined (C_dec):**
| phép đo | fps | ghi chú (cơ chế/độ phân giải) |
|---|---|---|
| decode-only (cv2, main-stream) | `[chưa đo]` | cv2-per-process (baseline, KHÔNG NVDEC) |
| decode-only (cv2, sub-stream) | `[chưa đo]` | `[chưa đo]` |
| combined decode+infer (batch tối ưu) | `[chưa đo]` | số DÙNG ĐỂ ĐỊNH CỠ (đã tính contention) |
| min(C_dec,C_inf) tham chiếu | `[chưa đo]` | so để thấy mức contention |

**M3 — VRAM (V):** tổng V card=`[chưa đo]` MB · model@load=`[chưa đo]` · @batch8=`[chưa đo]` · @batch16=`[chưa đo]`

**Suy ra (điền công thức scale-arch sau khi có số, KHÔNG trước):** N_infer=`[chưa đo]` · N_decode=`[chưa đo]` · N_vram=`[chưa đo]` · **N_node=min(...)** = `[chưa đo]` · số node cho 100 cam = `[chưa đo]`.

## Error Handling
- **torch/yolov5 không có (máy dev no-GPU):** harness ở chế độ `--device cuda` PHẢI fail-fast với thông điệp rõ ("cần env `.[pt]` + GPU — xem K-047"), KHÔNG chạy tiếp ra số rác. Chế độ `--device cpu` (verify logic) chạy được.
- **GPU OOM khi batch lớn:** bắt `torch.cuda.OutOfMemoryError` → ghi `[OOM]` vào ô batch đó (là DỮ LIỆU hợp lệ: batch đó vượt VRAM), tiếp batch khác — KHÔNG sập harness.
- **Video/RTSP không mở được:** fail-fast (như `VideoFileFrameSource.setup` đã làm) — không đo trên nguồn hỏng.
- **Điều kiện đo không sạch (tải song song — K-035):** harness in CẢNH BÁO + đánh dấu kết quả "nghi nhiễu"; người đo quyết đo lại. Không âm thầm báo số nhiễu.
- **Phương pháp sai (combined > min):** P3 phát hiện → harness cảnh báo "có thể chưa cuda.synchronize / đo sai", không dùng số.

## Correctness Properties

### Property 1: Steady-state (không tính warmup)
Số báo cáo KHÔNG gồm warmup; nếu median các lần lặp lệch > ngưỡng → đánh dấu "chưa ổn định", đo lại (không báo số nhiễu).
**Validates: Requirements 5.2**

### Property 2: CUDA-synced trước khi chốt thời gian
Mọi mốc thời gian inference đo SAU `torch.cuda.synchronize()` — GPU async, không sync → đo hụt (nhanh giả).
**Validates: Requirements 1.1, 4.2**

### Property 3: Combined ≤ min riêng lẻ
Throughput đo khi decode+infer đồng thời PHẢI ≤ min(C_dec, C_inf) riêng lẻ; nếu > → SAI phương pháp (chưa đồng bộ) → điều tra, không dùng số.
**Validates: Requirements 2.2**

### Property 4: Mọi số gắn môi trường
Không bảng số nào thiếu header môi trường (GPU/model/imgsz/torch) — số vô nghĩa nếu không biết đo trên gì.
**Validates: Requirements 5.1**

### Property 5: Không bịa số
Ô chưa đo = `[chưa đo]`; cấm nội suy/phỏng đoán điền số. Chỉ điền sau khi chạy thật trên máy GPU.
**Validates: Requirements 5.3**

## Testing Strategy
- **Logic harness (máy dev, no-GPU):** unit test `_stats.py` (percentile/throughput trên input đã biết đáp án) + smoke `--mode latency --device cpu` (FakeDetector) → verify harness tính đúng. Giữ baseline **427/1 · lint 5/0**.
- **Số capacity thật (máy GPU):** chạy `bench_capacity.py --mode all --device cuda` → điền template. Lặp R lần. Đây là VERIFY nền cho scale-architecture.

## Open Decisions (để-ngỏ, chốt ở PHA 2 hoặc khi có số)
- Cơ chế decode để đo combined: cv2 (dễ, baseline) TRƯỚC; ffmpeg/NVDEC (đúng production) đo sau khi dựng được (Lỗ 2).
- Có đo qua `PipelineRunner` đầy đủ (gồm Stage/sink) hay chỉ detector trần: đề xuất đo detector trần cho C_inf (cô lập), + 1 lần end-to-end qua PipelineRunner cho latency thực tế.
- Format lưu kết quả (markdown table vs json) — markdown cho người đọc; json nếu cần vẽ biểu đồ sau.

## Self-Review (doubt-driven — tự phản biện spec NÀY)
- **Nguy cơ đo "nhanh giả" do async CUDA** → đã chốt P2 (cuda.synchronize bắt buộc).
- **Nguy cơ số vô nghĩa vì không gắn môi trường** → P4 + header bắt buộc.
- **Nguy cơ giả định decode/infer độc lập** → M2 combined + P3 (bắt lỗi phương pháp).
- **Nguy cơ đo batch qua port (không có)** → R1.2 + M1 ghi rõ đo dưới port = bằng chứng lỗ A1.
- **Nguy cơ bịa số khi máy không GPU** → mục "Ranh giới máy đo" + P5 + template `[chưa đo]`.
- **Còn mở có chủ đích:** NVDEC decode (đo baseline cv2 trước); đo đa-model fan-out (khi có tầng classify — thuộc R3 scale-arch). Không phải thiếu sót — ngoài phạm vi "đo 1 node cơ bản".
**Phán quyết:** ĐỦ làm phương pháp đo PHA-1 (trung thực về ranh giới + điểm dễ sai). PHA 2 = code harness + verify logic (máy dev) + chạy số thật (máy GPU).

## Glossary
- **cuda.synchronize** — chặn tới khi mọi kernel GPU xong; bắt buộc trước khi chốt mốc thời gian (GPU async).
- **combined throughput** — công suất decode+infer đồng thời trên 1 GPU (đã tính contention) — số định cỡ thật.
- **scaling factor** — infer/s@batchB ÷ infer/s@batch1; đo lợi ích batching (trụ A1).
- **p95/p99** — đuôi độ trễ; quan trọng cho SLA real-time hơn trung bình.
