# 14.04 — `probe_capabilities` (@adapters) — KHÔNG BAO GIỜ raise; `has_cuda = is_available AND count>0`

## 1. Thuộc về đâu
Layer **adapters** (leaf) — `adapters/capability_probe.py`. Được phép `import torch`/`cv2` (contract chỉ cấm adapters import ngược lên).

## 2. Cần biết trước
mẩu 01 (MachineCapabilities). `torch.cuda.is_available()` / `device_count()` (API torch).

## 3. Code thật (quote nguyên văn — `adapters/capability_probe.py`)
```python
def probe_capabilities() -> MachineCapabilities:
    has_torch = False; has_cuda = False; n = 0; gpu = None; has_cv2 = False
    try:
        import torch
        has_torch = True
        try:
            n = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
            has_cuda = n > 0
            gpu = torch.cuda.get_device_name(0) if has_cuda else None
        except Exception:  # truy vấn CUDA lỗi → coi như không có
            has_cuda, n, gpu = False, 0, None
    except ImportError:
        pass  # máy không cài torch → has_torch=False (KHÔNG raise)
    try:
        import cv2  # noqa: F401
        has_cv2 = True
    except ImportError:
        pass
    return MachineCapabilities(has_torch=has_torch, has_cuda=has_cuda, cuda_device_count=n, gpu_name=gpu, has_cv2=has_cv2)
```

## 4. Giải thích từng mẩu nhỏ nhất
- `try: import torch ... except ImportError: pass` — máy KHÔNG cài torch → `has_torch=False`, KHÔNG raise (đi tiếp).
- `has_cuda = n > 0` với `n = device_count() if is_available() else 0` — **has_cuda = is_available AND count>0**:
  chống ca lạ `is_available()` True nhưng 0 GPU (driver rởm) → vẫn coi không-CUDA.
- `try: ... except Exception` (bọc trong) — truy vấn CUDA lỗi (driver/lib hỏng) → coi như không có (không raise).
- cv2 tương tự (try import).
- Trả `MachineCapabilities` (DTO kernel, mẩu 01).

## 5. Là gì
Hàm DÒ năng lực máy THẬT, an toàn tuyệt đối (không raise), trả DTO.

## 6. Tại sao KHÔNG BAO GIỜ raise (nguyên tắc cốt lõi)
Máy dev/CI KHÔNG cài torch (như máy toann — K-079). Nếu probe raise khi thiếu torch → mọi thứ dùng probe (conftest
collect, `--capabilities`, `_det_pt`) CRASH trên máy no-torch → không chạy được test/CLI. Bọc mọi import + truy vấn
trong try/except → no-torch chỉ trả `has_torch=False`, hệ vẫn chạy (đường CPU). "Dò an toàn" = nền chạy-được-mọi-máy.

## 7. Dùng ở đâu
- `conftest.py` (mẩu 06): `_CAPS = probe_capabilities()` lúc collect → gate `@pytest.mark.gpu`.
- `_det_pt` (mẩu 08): `resolve_device(device, probe_capabilities())`.
- `--capabilities` (mẩu 07): in `probe_capabilities()` ra JSON.

## 8. Không có nó thì sao (nếu probe raise)
Máy no-torch: import probe → crash → không collect test được, `--capabilities` crash, `_det_pt` crash cả khi
device=cpu. Probe-không-raise = tách "máy thiếu dep" khỏi "hệ sập".

## 9. Ví von
Bác sĩ khám: nếu máy đo huyết áp hỏng thì GHI "không đo được" (has_cuda=False) chứ KHÔNG bỏ chạy (raise) — bệnh nhân vẫn được khám phần khác.

## 10. Liên kết bức tranh lớn
DÒ (adapters, chạm torch) → DTO (kernel) → resolve (kernel thuần). probe là chỗ DUY NHẤT `import torch` trong đường
này → cô lập dep nặng ở rìa. Nối K-077/K-079 (máy toann torch vắng → probe trả has_torch=False, đúng).

## 11. Cạm bẫy
- `is_available()` True mà 0 GPU → `has_cuda` phải là `n>0` (không chỉ is_available). Code xử đúng.
- Probe NÊN gọi 1 lần/tiến trình rồi truyền DI (docstring) — gọi lại nhiều lần tốn (import torch nặng).

## 12. Tự kiểm (Feynman)
- Vì sao probe KHÔNG BAO GIỜ raise? Máy no-torch chạy `--capabilities`/test ra sao nếu probe raise?
- `has_cuda = is_available AND count>0` — vì sao không chỉ `is_available()`?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`adapters/capability_probe.py` (đọc thật phiên này) · K-077/K-079. Độ chắc: cao (quote trực tiếp).
