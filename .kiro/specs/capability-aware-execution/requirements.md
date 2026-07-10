# Requirements Document

> **Spec:** capability-aware-execution (chạy đúng trên máy hỗn tạp GPU/CPU/CUDA — no-GPU verify được)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Vấn đề gốc (user nêu, tái diễn nhiều):** đổi máy GIỮA có-GPU và không-GPU (kể cả không cài CUDA) là ma sát
> lặp lại. Hiện `device` là CHUỖI thủ công ("cpu"/"cuda") user truyền qua CLI/config; KHÔNG có
> `torch.cuda.is_available()` nào trong `src` → đặt `device=cuda` trên máy không-CUDA sẽ **fail lúc runtime**
> (torch báo lỗi khó hiểu), hoặc chạy CPU trong khi tưởng dùng GPU = mismatch NGẦM.
> **Nền tảng (đã ĐỌC CODE thật):**
> - `profiles/pipeline_factory.py::_det_pt`: `Yolov5PtDetector(params["weights"], device=params.get("device","cpu"))`.
> - `adapters/yolov5_pt_detector.py::setup()`: lazy `import torch` + `import yolov5`; chuẩn hoá "cuda"/"gpu"→"cuda:0"; `yolov5.load(..., device=dev)`.
> - CLI `--device cpu` mặc định (`vision_slice_app`/`vision_demo_app`/`vision_web_app`).
> - `profiles/pipeline_factory.py::validate_config`: kiểm config KHÔNG dựng object (không import torch) — đã có.
> - `scripts/vp.cmd env`: dò GPU qua `nvidia-smi` **chỉ INFORM, tầng shell** — code Python KHÔNG đọc.
> - grep toàn `src`: KHÔNG có `is_available`/probe năng lực nào ở tầng Python.
> **Cập nhật lúc:** 2026-07-10.

## Introduction

Sản phẩm ~100 camera thương mại sẽ deploy trên **node hỗn tạp** (máy có GPU, máy CPU-only, CUDA khác version,
có/không camera). Vòng phát triển CŨNG trải nhiều máy (chính việc đổi máy GPU↔không-GPU đang gây ma sát). Cả hai
cần MỘT nguyên tắc: **năng lực máy phải được DÒ → làm TƯỜNG MINH (DTO) → và MỌI quyết định phụ-thuộc-năng-lực tra
về một nguồn đó**, với 3 hành vi sạch:
1. **auto** — chọn tốt-nhất-sẵn-có (có CUDA → GPU; không → CPU), không bắt user nhớ máy nào có gì.
2. **fail-fast** — khi yêu cầu năng lực BẮT BUỘC (vd `device=cuda` tường minh) mà máy thiếu → báo lỗi RÕ RÀNG
   NGAY (không fail mù trong torch), gợi ý cách xử.
3. **skip/hoãn êm** — thứ tuỳ chọn (test/benchmark cần GPU) tự bỏ qua trên máy thiếu, KHÔNG làm đỏ CI.

Đây là fix BẢN CHẤT (thay vì vá từng chỗ `--device`): biến năng lực thành khái niệm hạng nhất + một chính sách
resolve device thuần + gate test. Kiểm chứng **hoàn toàn no-GPU** (tiêm capabilities giả → xác định).

**Ranh giới với env-layer đã có (không trùng):** `scripts/vp.cmd`/`env.local.cmd` lo SETUP tầng shell (chọn
interpreter, dựng venv, chọn extras, INFORM GPU). Spec này lo RUNTIME tầng Python (code tra năng lực để CHỌN
device / GATE test / báo lỗi rõ). Bổ trợ nhau: shell dựng môi trường ⟂ Python quyết hành vi theo năng lực.

**Ranh giới layer (bám luật §4):** `MachineCapabilities` (DTO thuần) + `resolve_device` (chính sách thuần) +
`CapabilityError` ở `kernel` (không import torch/cv2). Việc DÒ thật (`import torch; torch.cuda.is_available()`)
ở `adapters` (leaf, được phép import torch) — bọc an toàn, KHÔNG BAO GIỜ raise khi torch vắng. Composition (dò 1
lần → resolve → truyền device) ở `profiles`. KHÔNG đưa torch vào kernel/domain.

**Chống bịa:** mọi tham chiếu (device là chuỗi, `_det_pt`, `yolov5_pt_detector.setup`, `--device cpu`, không có
`is_available` trong src, `nvidia-smi` chỉ ở vp.cmd) ĐÃ đọc code/grep thật. Khẳng định về torch API
(`torch.cuda.is_available()`, `device_count()`) gắn độ-chắc-chắn CAO (API ổn định) — đối chiếu docs lúc code.

### Goals
- Một **capability probe** an toàn: báo `has_torch`/`has_cuda`/`has_cv2`/`gpu_name`/`cuda_device_count` — KHÔNG
  raise dù torch/cv2 vắng (máy no-GPU/no-CUDA vẫn dò được, chỉ trả False).
- Một **chính sách resolve device THUẦN**: `auto` → chọn theo năng lực; `cuda` tường minh + thiếu → **fail-fast**
  thông báo rõ; `cpu` → luôn được. Kiểm chứng xác định (tiêm capabilities).
- **Gate test theo năng lực**: test cần GPU tự SKIP khi máy không-CUDA (CI xanh mọi máy), không xoá test.
- Ghi RÕ device đã chọn (nối observability) — không "chạy CPU mà tưởng GPU".
- KHÔNG đổi hành vi hiện tại khi không dùng tính năng (backward-compat: default giữ như cũ trừ khi opt-in `auto`).

### Non-Goals
- KHÔNG tự CÀI torch/CUDA (giữ nguyên tắc vp.cmd K-049 — cài là việc setup có chủ đích của user, không tự động).
- KHÔNG chọn GPU-nào trong nhiều-GPU / affinity / MPS (v1 chỉ có/không CUDA + device_count; multi-GPU sched = tầng cụm sau).
- KHÔNG benchmark năng lực (đo capacity = spec `node-capacity-benchmark` đã có, cần GPU thật).
- KHÔNG probe camera/RTSP liveness (khác trục; camera là I/O runtime, không phải năng lực tính toán).
- KHÔNG đổi env-layer shell (`vp.cmd`) — chỉ THÊM tuỳ chọn in capability probe (follow-on nhỏ).

## Glossary
- **Capability (năng lực)** — thứ máy CÓ THỂ làm về mặt tính toán: có torch, có CUDA, có cv2, số GPU, tên GPU.
- **Capability probe** — hàm dò năng lực THẬT lúc chạy (an toàn: torch vắng → has_cuda=False, không raise).
- **`MachineCapabilities`** — DTO thuần (frozen) chứa kết quả probe; tiêm được để test xác định no-GPU.
- **resolve device** — chính sách thuần: (requested, capabilities) → device dùng thật HOẶC raise CapabilityError.
- **auto** — giá trị device đặc biệt: "chọn tốt-nhất-sẵn-có" (cuda nếu có, không thì cpu).
- **fail-fast** — phát hiện thiếu năng lực bắt buộc → raise lỗi RÕ NGAY, không để fail mù sâu trong torch.

## Requirements

### Requirement 1: Capability probe an toàn (dò được trên mọi máy, không raise)
**User Story:** Là kỹ sư đổi máy liên tục, tôi muốn biết CHẮC máy hiện tại có gì (torch/CUDA/cv2/GPU) mà lệnh dò KHÔNG BAO GIỜ crash, để mọi quyết định sau dựa trên sự thật thay vì đoán.
#### Acceptance Criteria
- 1.1 — WHEN gọi probe trên máy KHÔNG cài torch, THE probe SHALL trả `has_torch=False`, `has_cuda=False`, `cuda_device_count=0`, `gpu_name=None` mà KHÔNG raise (bắt ImportError).
- 1.2 — WHERE torch cài được, THE probe SHALL báo `has_cuda` = `torch.cuda.is_available()` và `cuda_device_count`/`gpu_name` tương ứng (bọc an toàn nếu truy vấn lỗi → coi như không có).
- 1.3 — THE probe SHALL báo `has_cv2` theo import cv2 được hay không (bọc ImportError).
- 1.4 — THE kết quả probe SHALL là `MachineCapabilities` (frozen DTO thuần) — tiêm được ở nơi tiêu thụ để test xác định.

### Requirement 2: Chính sách resolve device THUẦN (auto / fail-fast / cpu)
**User Story:** Là kỹ sư, tôi muốn khai `device=auto` để hệ tự chọn đúng theo máy, và nếu tôi ép `cuda` mà máy không có thì báo lỗi RÕ ngay, để không bao giờ chạy sai âm thầm.
#### Acceptance Criteria
- 2.1 — WHEN `requested == "auto"`, THE `resolve_device` SHALL trả `"cuda"` nếu `capabilities.has_cuda` là True, ngược lại `"cpu"`.
- 2.2 — IF `requested` yêu cầu CUDA tường minh (`"cuda"`/`"gpu"`/`"cuda:N"`) WHILE `capabilities.has_cuda` là False, THEN `resolve_device` SHALL raise `CapabilityError` với thông báo RÕ (máy không có CUDA + gợi ý dùng `auto`/`cpu` hoặc chạy máy GPU).
- 2.3 — WHEN `requested == "cpu"`, THE `resolve_device` SHALL luôn trả `"cpu"` (không phụ thuộc năng lực).
- 2.4 — THE `resolve_device` SHALL là hàm THUẦN (chỉ nhận requested + capabilities → trả chuỗi / raise) — không I/O, không tự probe bên trong → test xác định bằng capabilities tiêm.

### Requirement 3: Wire vào đường chạy (chọn device qua năng lực) + ghi rõ
**User Story:** Là kỹ sư vận hành, tôi muốn CLI/config chấp nhận `device=auto` và LOG rõ device thực tế đã chọn, để deploy 1 cấu hình lên nhiều node mà vẫn biết node nào chạy GPU/CPU.
#### Acceptance Criteria
- 3.1 — THE CLI/config SHALL chấp nhận `device="auto"` (ngoài "cpu"/"cuda"); đường dựng detector `pt` SHALL resolve device qua `resolve_device(requested, probe())` TRƯỚC khi tạo `Yolov5PtDetector`.
- 3.2 — WHEN device được resolve, THE hệ SHALL ghi (log/observability) device THỰC TẾ đã chọn + lý do (vd "auto→cpu vì máy không CUDA") — chống "tưởng GPU mà chạy CPU".
- 3.3 — THE thay đổi SHALL additive: default device giữ nguyên hành vi hiện tại (không opt-in `auto`/không ép `cuda` → như cũ); baseline **560 passed/1 skipped · lint 5/0** giữ (+ test mới).
- 3.4 — WHERE `validate_config` chạy trên máy dev, THE việc resolve device (fail-fast cuda) SHALL KHÔNG cản validate tĩnh (validate không dựng object — giữ được kiểm config GPU trên máy no-GPU).

### Requirement 4: Gate test theo năng lực (CI xanh mọi máy)
**User Story:** Là kỹ sư, tôi muốn test cần GPU tự bỏ qua trên máy không-CUDA để CI không đỏ oan, nhưng vẫn chạy khi có GPU.
#### Acceptance Criteria
- 4.1 — THE bộ test SHALL có cơ chế đánh dấu test "cần GPU" (marker) + tự SKIP khi `probe().has_cuda` là False (không xoá/không xoá phủ test).
- 4.2 — THE logic skip SHALL kiểm chứng được xác định (tiêm capabilities giả) — test cho cả nhánh có-CUDA và không-CUDA mà KHÔNG cần GPU thật.
- 4.3 — THE test hiện tại (no-GPU) SHALL KHÔNG bị ảnh hưởng (vẫn 560/1); marker chỉ thêm.

### Requirement 5: Ranh giới layer + kiểm chứng KHÔNG cần GPU
**User Story:** Là kiến trúc sư, tôi muốn năng lực là khái niệm sạch không kéo torch vào lõi, và test xác định trên máy dev.
#### Acceptance Criteria
- 5.1 — THE `MachineCapabilities` (DTO) + `resolve_device` + `CapabilityError` SHALL ở `kernel` (thuần, KHÔNG import torch/cv2); probe THẬT (import torch) ở `adapters` (leaf). Import-linter 5 kept/0 broken.
- 5.2 — Test `resolve_device` phủ: auto→cuda/cpu theo caps; cuda-thiếu→CapabilityError; cpu→cpu (capabilities TIÊM, no-GPU).
- 5.3 — Test probe: máy không-torch → has_cuda=False không raise (chạy được ngay trên máy này — không-CUDA).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format: Overview/Architecture/Components/Data Models/Error
Handling/Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) `MachineCapabilities`
DTO + `CapabilityError` + `resolve_device` thuần @kernel; (b) `probe_capabilities()` @adapters bọc-an-toàn (torch/cv2
vắng → False, không raise); (c) điểm wire `_det_pt`/CLI nhận `auto` + resolve + log device thực tế; (d) cơ chế
marker `gpu` + autoskip theo probe (conftest); (e) chứng minh backward-compat + ranh giới layer + no-GPU-verify.
**KHÔNG code ở PHA này** (chờ user valid thiết kế).
