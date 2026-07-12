# 14.02 — `resolve_device` — HÀM THUẦN quyết định device; fail-fast khi ép cuda thiếu GPU

## 1. Thuộc về đâu
kernel — `kernel/capabilities.py::resolve_device`. HÀM THUẦN (không I/O, không probe): (requested, caps) → device thật HOẶC raise.

## 2. Cần biết trước
mẩu 01 (MachineCapabilities). "hàm thuần" = cùng input → cùng output, không tác dụng phụ. `CapabilityError` (RuntimeError con).

## 3. Code thật (quote nguyên văn — `kernel/capabilities.py`)
```python
def resolve_device(requested: str, caps: MachineCapabilities) -> str:
    r = (requested or "auto").strip().lower()
    if r == "cpu":
        return "cpu"
    if r == "auto":
        return "cuda" if caps.has_cuda else "cpu"
    if r in _CUDA_BARE or r.startswith("cuda:"):
        if not caps.has_cuda:
            raise CapabilityError(f"device={requested!r} yêu cầu CUDA nhưng máy này KHÔNG có CUDA khả dụng ...")
        if r.startswith("cuda:"):
            idx = _parse_ordinal(r)
            if idx >= caps.cuda_device_count:
                raise CapabilityError(f"device={requested!r} nhưng máy chỉ có {caps.cuda_device_count} GPU ...")
            return r
        return "cuda"
    raise CapabilityError(f"device không hợp lệ: {requested!r} (hợp lệ: auto | cpu | cuda | cuda:N).")
```

## 4. Giải thích từng mẩu nhỏ nhất
- `"cpu"` → `"cpu"` (luôn được).
- `"auto"` → `"cuda"` nếu `caps.has_cuda`, ngược lại `"cpu"` (fallback ÊM — nơi gọi nên LOG device thật).
- `"cuda"`/`"gpu"`/`"cuda:N"` → nếu KHÔNG có CUDA → **CapabilityError fail-fast** (user ÉP cuda nhưng máy thiếu → báo RÕ, không chạy nhầm CPU im lặng).
- device lạ → CapabilityError.
- **THUẦN**: chỉ nhận `caps` (DTO), KHÔNG tự `import torch`/probe → cùng caps → cùng kết quả.

## 5. Là gì
Hàm quyết định "device thực tế sẽ dùng" từ yêu cầu + năng lực máy, hoặc từ chối rõ ràng.

## 6. Tại sao tồn tại / auto (fallback êm) vs cuda (fail-fast) — điểm cốt lõi
- `auto` = "tuỳ máy": có GPU dùng GPU, không thì CPU (fallback ÊM — hợp cho chạy-được-mọi-máy).
- `cuda` (ÉP) = "tôi MUỐN GPU": nếu máy thiếu → **fail-fast CapabilityError**, KHÔNG âm thầm về CPU. Vì sao: user ép
  cuda là có chủ đích (cần tốc độ GPU); âm thầm chạy CPU = chậm 10-100× mà user KHÔNG BIẾT → tệ hơn báo lỗi.
  "Không kiểm được thì báo, đừng đoán" — fail-fast > fallback im lặng khi user ép.

## 7. Dùng ở đâu
`pipeline_factory._det_pt` (mẩu 08): `resolve_device(params.get("device","cpu"), probe_capabilities())`. Test tiêm
`MachineCapabilities(...)` giả → kiểm mọi nhánh (auto/cpu/cuda/cuda:N) KHÔNG cần GPU.

## 8. Không có nó thì sao
Rải `if torch.cuda.is_available()` → khó test + không fail-fast (ép cuda thiếu GPU chạy nhầm CPU im lặng). Hàm thuần
gom logic + fail-fast + test tiêm.

## 9. Ví von
Lễ tân xếp phòng: "tuỳ" (auto) → phòng tốt nhất còn trống; "phòng VIP" (cuda) → nếu hết VIP thì BÁO NGAY (không tự
xếp phòng thường mà không nói).

## 10. Liên kết bức tranh lớn
QUYẾT-ĐỊNH (thuần, kernel) tách khỏi DÒ (probe, adapters — mẩu 04/05). Nền test-không-cần-GPU. `CapabilityError` → main bắt → exit 2 (mẩu 08).

## 11. Cạm bẫy
- `auto` fallback êm nhưng nơi gọi PHẢI LOG device thật (mẩu 08 `_det_pt` in `[device]`) — chống "tưởng GPU mà chạy CPU".
- `cuda:N` phải kiểm ordinal (mẩu 03) — `cuda:5` trên máy 1 GPU → fail-fast.

## 12. Tự kiểm (Feynman)
- `auto` vs `cuda` khác gì khi máy KHÔNG có GPU? Vì sao cuda fail-fast, auto fallback?
- Vì sao `resolve_device` THUẦN (không tự probe)? Lợi test gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/capabilities.py::resolve_device` (đọc thật phiên này) · D-072/D-073. Độ chắc: cao (quote trực tiếp).
