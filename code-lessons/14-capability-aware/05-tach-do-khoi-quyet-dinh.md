# 14.05 — Vì sao TÁCH DÒ (probe@adapters) khỏi QUYẾT-ĐỊNH (resolve@kernel) — ranh giới + test

## 1. Thuộc về đâu
Mẩu KHÁI NIỆM: so `adapters/capability_probe.py` (DÒ, chạm torch) với `kernel/capabilities.py::resolve_device` (QUYẾT-ĐỊNH, thuần).

## 2. Cần biết trước
mẩu 02 (resolve thuần), 04 (probe không-raise). Ranh giới: kernel cấm import torch (contract #2); adapters được (contract #5).

## 3. Code thật (quote docstring — `kernel/capabilities.py`)
```python
"""Việc DÒ năng lực THẬT (`import torch`) nằm ở `adapters/capability_probe.py` (leaf, được phép chạm dep
cụ thể) và TRẢ VỀ `MachineCapabilities` (DTO này).

Vì sao tách DTO+policy (kernel) khỏi probe (adapters): quyết-định-theo-năng-lực là HÀM THUẦN
(`resolve_device`) → test xác định bằng cách TIÊM `MachineCapabilities` giả, KHÔNG cần GPU/torch. Đây là
cách xử lý BẢN CHẤT việc chạy trên máy hỗn tạp GPU/CPU (thay vì rải `if torch...` khắp nơi)."""
```

## 4. Giải thích (đây là "tại sao", không phải "dòng nào")
- **DÒ (probe @adapters)**: cần `import torch` (dep cụ thể) → PHẢI ở adapters (kernel cấm torch). Có tác dụng phụ
  (đọc trạng thái máy), không thuần.
- **QUYẾT-ĐỊNH (resolve @kernel)**: chỉ nhận `MachineCapabilities` (DTO) → HÀM THUẦN, không torch, không I/O.
- Ranh giới: nếu resolve_device tự `import torch` để dò → kernel import torch → VI PHẠM contract #2 (`lint-imports` đỏ)
  + kéo dep nặng vào kernel. Tách → kernel sạch, probe ở rìa.

## 5. Là gì
Nguyên tắc: "biết máy có gì" (DÒ, có dep, adapters) TÁCH khỏi "quyết định làm gì với năng lực đó" (thuần, kernel).

## 6. Tại sao tồn tại / vấn đề nó giải (2 lợi ích lớn)
1. **Ranh giới sạch:** kernel không kéo torch → chạy/test được máy no-torch; import-linter giữ hướng phụ thuộc.
2. **Test được KHÔNG cần GPU:** resolve thuần → test tiêm `MachineCapabilities(has_cuda=True, cuda_device_count=2)`
   giả → kiểm mọi nhánh (auto→cuda, cuda:5→raise...) trên máy CI KHÔNG GPU. Nếu trộn dò+quyết-định → phải có GPU thật
   mới test được nhánh CUDA. Đây là "cách xử lý BẢN CHẤT" (không rải if).

## 7. Dùng ở đâu
`_det_pt` (mẩu 08): `resolve_device(device, probe_capabilities())` — DÒ 1 lần (probe) rồi QUYẾT-ĐỊNH (resolve).
Test resolve: tiêm caps giả (không probe). Test probe: chạy trên máy thật (chấp nhận kết quả tuỳ máy).

## 8. Không có nó thì sao
Trộn → kernel import torch (thủng contract) + không test nhánh CUDA trên máy no-GPU. Đây đúng nỗi đau tái diễn
(cau-chuyen nhịp 2) mà tách-tầng giải.

## 9. Ví von
Y tá ĐO (probe, cần máy đo) ghi kết quả vào phiếu (DTO); bác sĩ ĐỌC PHIẾU quyết định điều trị (resolve, thuần) —
để dạy/kiểm bác sĩ, đưa phiếu GIẢ là đủ, không cần bệnh nhân thật.

## 10. Liên kết bức tranh lớn
Mẫu hexagonal áp cho "năng lực máy": adapter dò (rìa) → DTO (kernel) → policy thuần (kernel). Nền cho gate test (06)
+ wiring (08). Giống ports (IFrameSource...) nhưng cho capability.

## 11. Cạm bẫy
- Cám dỗ cho resolve tự probe "cho tiện" → thủng ranh giới + mất test-không-GPU. Giữ resolve THUẦN.
- probe kết quả tuỳ máy → test probe không nên assert cứng (assert theo máy); test LOGIC ở resolve (tiêm caps).

## 12. Tự kiểm (Feynman)
- Nếu `resolve_device` tự `import torch`, `lint-imports` báo gì? Test nhánh CUDA trên máy no-GPU còn được không?
- 2 lợi ích của tách DÒ/QUYẾT-ĐỊNH là gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/capabilities.py` (docstring) + `adapters/capability_probe.py` (đọc thật phiên này) · contract #2/#5. Độ chắc: cao.
