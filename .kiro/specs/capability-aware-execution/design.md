# Design Document — capability-aware-execution (chạy đúng trên máy hỗn tạp GPU/CPU, no-GPU verify)

## Overview

Fix BẢN CHẤT vấn đề tái diễn "đổi máy GPU↔không-GPU": biến **năng lực máy** thành khái niệm HẠNG NHẤT được DÒ →
làm TƯỜNG MINH (DTO) → và mọi quyết định phụ-thuộc-năng-lực tra về một nguồn. Thay chuỗi `--device` thủ công
(mismatch ngầm, fail mù trong torch) bằng: (1) **probe an toàn**, (2) **chính sách resolve device thuần**
(auto/fail-fast/cpu), (3) **gate test theo năng lực**. Tất cả kiểm chứng **hoàn toàn no-GPU** (tiêm capabilities).

**Nguyên tắc gốc:** năng lực là DỮ LIỆU (DTO tiêm được), không phải hiệu ứng lề rải rác. Quyết định dựa năng lực
là HÀM THUẦN (test xác định). Việc DÒ thật (import torch) bị cô lập ở adapters (leaf) + bọc an toàn.

## Bằng chứng code đã đọc (chống bịa)
- `profiles/pipeline_factory.py::_det_pt(params)` → `Yolov5PtDetector(params["weights"], device=params.get("device","cpu"))`;
  `_det_pt.allowed_params = frozenset({"weights","device"})`.
- `adapters/yolov5_pt_detector.py::__init__(weights,*,device="cpu",...)` + `setup()`: lazy `import torch`/`import yolov5`;
  `if dev in ("cuda","gpu"): dev="cuda:0"`; `yolov5.load(weights, device=dev)`.
- CLI `--device` default `"cpu"` ở `vision_slice_app`/`vision_demo_app`/`vision_web_app`.
- `validate_config` kiểm config KHÔNG dựng object (không import torch) — giữ được ở máy no-GPU.
- grep `src`: KHÔNG có `torch.cuda.is_available()`/probe năng lực nào (device chỉ là chuỗi truyền tay).
- `scripts/vp.cmd env`: `nvidia-smi` INFORM tầng shell (Python không đọc). `env.local.cmd` override extras/interpreter.

## Nguồn chuẩn (kiến thức — độ chắc chắn CAO, xác nhận lại lúc code)
- `torch.cuda.is_available() -> bool`; `torch.cuda.device_count() -> int`; `torch.cuda.get_device_name(i) -> str`
  (pytorch docs — API ổn định nhiều năm). Gắn độ-chắc-chắn CAO; PHA2 đối chiếu docs/`import torch` thật nếu cài được.
- Quy ước device string: `"cpu"`, `"cuda"`, `"cuda:N"` (đã dùng trong adapter — khớp yolov5 select_device).

## Architecture

Thêm khái niệm năng lực THUẦN ở `kernel` + 1 probe ở `adapters` + wire ở `profiles`. KHÔNG layer mới, KHÔNG đảo hướng.

```
profiles/  (composition: probe 1 lần → resolve_device → truyền device thật cho builder + LOG)
   │ dùng
   ├───────────────► kernel/capabilities.py
   │                    • MachineCapabilities (frozen DTO thuần)
   │                    • CapabilityError (exception)
   │                    • resolve_device(requested, caps) -> str  (CHÍNH SÁCH THUẦN)
   │ gọi probe
   ▼
adapters/capability_probe.py   probe_capabilities() -> MachineCapabilities
   • import torch/cv2 trong try/except → torch vắng = has_cuda False (KHÔNG raise)
   • adapters = leaf, được phép import torch/cv2; phụ thuộc kernel (DTO) hợp lệ

tests/conftest.py   marker `gpu` + autoskip khi probe_capabilities().has_cuda False
```

- **Hướng phụ thuộc:** `kernel` (DTO+policy thuần) ← `adapters` (probe) ; `profiles` dùng cả hai. Không đảo.
  `resolve_device` THUẦN ở kernel (không I/O) → domain/kernel giữ sạch (không import torch).
- **Vì sao probe ở adapters (không kernel):** probe PHẢI `import torch`/`cv2` (I/O-ish, dep optional) → kernel
  cấm import lib ngoài (contract #2). adapters là nơi đúng (leaf, chạm dep cụ thể). Kết quả trả DTO kernel thuần.
- **Vì sao resolve_device THUẦN + tách khỏi probe:** để test xác định (tiêm caps giả, không cần GPU) + tái dùng
  (CLI/config/web đều gọi cùng chính sách) → 1 nguồn chân lý cho quyết-định-device.

## Components and Interfaces

### 1. kernel/capabilities.py (thuần — DTO + policy + error)
```
@dataclass(frozen=True)
class MachineCapabilities:
    has_torch: bool
    has_cuda: bool
    cuda_device_count: int = 0
    gpu_name: str | None = None
    has_cv2: bool = False

class CapabilityError(RuntimeError): ...

_CUDA_REQUESTS = frozenset({"cuda", "gpu"})   # "cuda:N" xử bằng startswith("cuda")

def resolve_device(requested: str, caps: MachineCapabilities) -> str:
    """(requested, caps) → device dùng thật, HOẶC raise CapabilityError. THUẦN."""
    r = (requested or "auto").strip().lower()
    if r == "cpu":
        return "cpu"
    if r == "auto":
        return "cuda" if caps.has_cuda else "cpu"
    if r in _CUDA_REQUESTS or r.startswith("cuda:"):
        if not caps.has_cuda:
            raise CapabilityError(
                f"device={requested!r} yêu cầu CUDA nhưng máy này không có CUDA "
                f"(has_torch={caps.has_torch}). Dùng device='auto' (tự về cpu) / 'cpu', "
                f"hoặc chạy trên máy GPU.")
        return requested          # giữ nguyên "cuda"/"cuda:N" (adapter tự chuẩn hoá "cuda"→"cuda:0")
    raise CapabilityError(f"device không hợp lệ: {requested!r} (hợp lệ: auto|cpu|cuda|cuda:N)")
```
- DTO immutable thuần Python → hợp `kernel`. `resolve_device` không I/O → test tiêm `MachineCapabilities(...)` xác định.

### 2. adapters/capability_probe.py (dò THẬT, bọc an toàn — leaf)
```
def probe_capabilities() -> MachineCapabilities:
    has_torch = has_cuda = False; n = 0; gpu = None; has_cv2 = False
    try:
        import torch
        has_torch = True
        try:
            has_cuda = bool(torch.cuda.is_available())
            if has_cuda:
                n = int(torch.cuda.device_count())
                gpu = torch.cuda.get_device_name(0) if n > 0 else None
        except Exception:            # truy vấn CUDA lỗi (driver/lib) → coi như không có
            has_cuda = False; n = 0; gpu = None
    except ImportError:
        pass                          # máy no-torch (như máy hiện tại) → False, KHÔNG raise
    try:
        import cv2  # noqa: F401
        has_cv2 = True
    except ImportError:
        pass
    return MachineCapabilities(has_torch, has_cuda, n, gpu, has_cv2)
```
- KHÔNG BAO GIỜ raise (mọi import/truy vấn bọc) → chạy an toàn trên máy no-GPU/no-CUDA/no-torch (chính máy hiện tại).
- Kết quả CÓ THỂ cache ở tầng gọi (probe 1 lần/tiến trình) — nhưng hàm tự nó thuần-đọc-môi-trường, không state.

### 3. profiles — wire (probe 1 lần → resolve → truyền + LOG)
- `_det_pt`/`_build_detector`/CLI: nhận `device` (thêm "auto"); trước khi tạo `Yolov5PtDetector` →
  `dev = resolve_device(requested, caps)` (caps = probe 1 lần, tiêm được để test) → log
  `"device: auto→cpu (máy không CUDA)"` → `Yolov5PtDetector(weights, device=dev)`.
- `validate_config` KHÔNG gọi resolve (giữ kiểm-tĩnh không-dựng-object — R3.4); resolve chỉ ở đường CHẠY thật.
- CLI thêm tiện ích `--capabilities` (in probe) — follow-on nhỏ, không bắt buộc v1.

### 4. tests/conftest.py — marker `gpu` + autoskip
```
# pyproject: [tool.pytest.ini_options] markers = ["gpu: cần CUDA thật"]
def pytest_collection_modifyitems(config, items):
    caps = probe_capabilities()
    if caps.has_cuda: return
    skip = pytest.mark.skip(reason="cần CUDA (máy không có) — skip tự động")
    for it in items:
        if "gpu" in it.keywords: it.add_marker(skip)
```
- Logic quyết-định-skip TÁCH riêng (hàm thuần nhận `has_cuda`) để test cả 2 nhánh KHÔNG cần GPU thật (R4.2).

## Data Models

| Tên | Kiểu | Ràng buộc | Layer | Dùng ở |
|---|---|---|---|---|
| `MachineCapabilities` | frozen dataclass | bool/int/str thuần; `cuda_device_count≥0` | kernel | probe trả + resolve nhận |
| `CapabilityError` | Exception (RuntimeError) | — | kernel | resolve_device raise |
| `resolve_device` | hàm thuần | (str, caps) → str hoặc raise; không I/O | kernel | profiles/CLI |
| `probe_capabilities` | hàm | không raise; đọc môi trường → DTO | adapters | composition (probe 1 lần) |
| `device` (config/CLI) | str | ∈ {auto, cpu, cuda, cuda:N} | profiles | resolve trước khi dựng detector |

- KHÔNG đổi chữ ký `Yolov5PtDetector` (vẫn nhận `device: str` đã-resolve). Thêm "auto" chỉ ở tầng CLI/config + resolve.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| torch KHÔNG cài (máy hiện tại) | probe bắt ImportError → `has_torch=False, has_cuda=False` (không raise) | R1.1, P4 |
| truy vấn `torch.cuda.*` lỗi (driver/lib hỏng) | probe bọc Exception → coi như không có CUDA | R1.2 |
| `device="cuda"` tường minh + máy không CUDA | `resolve_device` raise `CapabilityError` thông báo RÕ + gợi ý auto/cpu | R2.2, P2 |
| `device` chuỗi lạ (vd "gpu0") | `resolve_device` raise `CapabilityError` (liệt kê hợp lệ) | R2.4 |
| `device="auto"` máy không CUDA | trả "cpu" + LOG "auto→cpu" (không raise, không im lặng) | R2.1, R3.2, P1 |
| `validate_config` trên máy no-GPU | KHÔNG gọi resolve (kiểm tĩnh) → config GPU vẫn validate được | R3.4 |

- Nguyên tắc: **auto = êm (log rõ)**; **cuda tường minh = fail-fast (báo rõ)** — hai đường tách bạch, không nhập nhằng.

## Correctness Properties

### Property 1: auto chọn theo năng lực
`resolve_device("auto", caps(has_cuda=True))` == `"cuda"`; `resolve_device("auto", caps(has_cuda=False))` == `"cpu"`.
**Validates: Requirements 2.1**

### Property 2: cuda tường minh thiếu CUDA → fail-fast
`resolve_device("cuda", caps(has_cuda=False))` raise `CapabilityError` (thông báo chứa gợi ý auto/cpu). Tương tự "cuda:0"/"gpu".
**Validates: Requirements 2.2**

### Property 3: cpu luôn được
`resolve_device("cpu", caps_bất_kỳ)` == `"cpu"`.
**Validates: Requirements 2.3**

### Property 4: probe an toàn không raise
Trên máy không-torch (hoặc giả lập ImportError), `probe_capabilities()` trả `has_torch=False, has_cuda=False, cuda_device_count=0` mà KHÔNG raise.
**Validates: Requirements 1.1, 1.3**

### Property 5: resolve thuần (xác định, tiêm được)
`resolve_device` chỉ phụ thuộc (requested, caps) — cùng input → cùng output/raise; không I/O, không tự probe.
**Validates: Requirements 2.4, 5.2**

### Property 6: gate test skip đúng theo năng lực
Logic skip (hàm thuần nhận has_cuda): has_cuda=False → test `gpu` bị skip; has_cuda=True → chạy. Kiểm cả 2 nhánh không cần GPU thật.
**Validates: Requirements 4.1, 4.2**

### Property 7: backward-compat + ranh giới layer
Không dùng "auto"/không ép cuda → hành vi + baseline 560/1 giữ; kernel không import torch/cv2; probe ở adapters; import-linter 5 kept/0 broken.
**Validates: Requirements 3.3, 4.3, 5.1**

## Testing Strategy

- **resolve (P1,P2,P3,P5):** tiêm `MachineCapabilities` giả (has_cuda True/False) → assert auto→cuda/cpu; cuda-thiếu→CapabilityError (kiểm message có gợi ý); cpu→cpu; chuỗi lạ→raise. TẤT CẢ no-GPU.
- **probe (P4):** gọi `probe_capabilities()` trên máy hiện tại (no-torch) → has_torch=False, has_cuda=False, không raise; (tuỳ chọn) monkeypatch giả lập torch có/không để kiểm nhánh.
- **gate test (P6):** tách hàm quyết-định-skip nhận `has_cuda` → test True/False; + 1 test đánh dấu `@pytest.mark.gpu` để xác nhận cơ chế skip chạy (trên máy no-CUDA test đó bị skip — đúng ý đồ).
- **layer (P7):** lint `importlinter.api` 5 kept/0 broken; kiểm `kernel/capabilities.py` không import torch/cv2.
- **Đối chiếu chuẩn (lúc code):** nếu torch cài được (máy GPU khác) → xác nhận probe khớp `torch.cuda.is_available()`; máy này (no-torch) → xác nhận nhánh ImportError. Ghi rõ [đã kiểm]/[chưa kiểm].

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** đổi-máy-không-ma-sát (auto) ⟂ không-chạy-sai-âm-thầm (log device thực + fail-fast cuda) ⟂ CI-xanh-mọi-máy
  (gate test) ⟂ lõi-sạch (không torch vào kernel) ⟂ backward-compat (default giữ). Cân được: probe(adapters) +
  policy thuần(kernel) + auto opt-in + log.
- **What varies?** NĂNG LỰC máy (torch/CUDA/cv2, số GPU) → trừu tượng = DTO `MachineCapabilities` (thêm trường
  khi cần, vd MPS/ROCm) + probe điền. QUYẾT ĐỊNH theo năng lực = hàm thuần `resolve_device` (thêm chính sách =
  sửa 1 hàm thuần có test, không rải if torch khắp nơi).
- **Which way deps point?** kernel(DTO+policy thuần) ← adapters(probe import torch) ; profiles dùng cả hai. Không
  đảo; kernel không biết torch tồn tại (chỉ nhận bool).
- **Cái GIÁ:** thêm 1 DTO + 1 hàm thuần + 1 probe + marker. Rất nhỏ. Đổi lấy: xoá tận gốc mismatch-ngầm khi đổi
  máy + CI xanh mọi máy + product deploy đa-node an toàn.
- **fail-fast (cuda) vs auto-fallback (cuda→cpu im lặng)?** CHỌN fail-fast cho `cuda` TƯỜNG MINH (ép cuda mà máy
  không có = kỳ vọng sai của user/ops → phải BÁO, không âm thầm chạy CPU chậm rồi tưởng GPU). `auto` mới là đường
  fallback êm (+log). Hai ý định KHÁC NHAU → hai đường KHÁC NHAU (không nhập nhằng). Đây là bản chất "đừng fix ngọn".
- **default nên là "auto" hay giữ "cpu"?** (xem T-027) → giữ **"cpu"** default (backward-compat, không đổi hành vi
  ngầm); khuyến nghị đặt `device="auto"` trong config deploy. Đổi default = thay đổi hành vi ngầm → tránh.
- **Khi nào KHÔNG dùng:** (a) môi trường đồng nhất tuyệt đối (mọi node y hệt) → auto ít giá trị nhưng vô hại; (b)
  chọn GPU-nào trong multi-GPU/affinity → v1 KHÔNG lo (chỉ có/không CUDA) → tầng cụm sau; (c) đo hiệu năng năng
  lực → `node-capacity-benchmark` (khác trục).
- **Recognize (dấu hiệu cần):** "đổi máy là phải sửa tay/đoán device", "chạy CPU mà tưởng GPU", "CI đỏ vì test GPU
  trên máy không GPU" = triệu chứng thiếu capability-awareness.

## Non-Goals (nhắc lại)
Tự cài torch/CUDA (giữ K-049) · chọn GPU trong multi-GPU/affinity/MPS · benchmark năng lực (node-capacity-benchmark) ·
probe camera/RTSP · đổi env-layer shell `vp.cmd` (chỉ thêm in probe follow-on) · đổi default device sang auto (giữ cpu, T-027).
