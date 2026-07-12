# 14.01 — `MachineCapabilities` DTO (@kernel, frozen) — năng-lực-máy là khái niệm HẠNG NHẤT

## 1. Thuộc về đâu
Layer **kernel** — `kernel/capabilities.py`. DTO thuần frozen mô tả "máy hiện tại có gì". KHÔNG import torch/cv2.

## 2. Cần biết trước
frozen dataclass (#02). "hạng nhất" (first-class) = biến 1 khái niệm mơ hồ thành 1 KIỂU rõ ràng, truyền/test được.

## 3. Code thật (quote nguyên văn — `kernel/capabilities.py`)
```python
@dataclass(frozen=True)
class MachineCapabilities:
    """Năng lực TÍNH TOÁN của máy hiện tại (kết quả probe). Immutable, thuần — tiêm được để test."""
    has_torch: bool
    has_cuda: bool
    cuda_device_count: int = 0
    gpu_name: str | None = None
    has_cv2: bool = False
```

## 4. Giải thích từng mẩu nhỏ nhất
- `has_torch`/`has_cuda`/`has_cv2` — có torch? có CUDA khả dụng? có cv2?
- `cuda_device_count` — số GPU (0 nếu không).
- `gpu_name` — tên GPU (None nếu không).
- `frozen=True` — bất biến (ảnh chụp năng lực; probe 1 lần rồi truyền đi).

## 5. Là gì
Bản ghi kiểu-hoá về năng lực tính toán máy — 1 NGUỒN sự thật "máy có gì".

## 6. Tại sao tồn tại / vấn đề nó giải
Trước: "máy có GPU không" là kiến thức rải rác (`torch.cuda.is_available()` gọi khắp nơi). Biến thành DTO hạng
nhất → dò 1 lần, truyền DI xuống, và QUAN TRỌNG: **tiêm DTO giả để test** logic chọn device mà KHÔNG cần GPU thật
(mẩu 02/05). Đặt @kernel (thuần) → resolve_device (cũng kernel) dùng được mà không kéo torch.

## 7. Dùng ở đâu
`probe_capabilities` (@adapters, mẩu 04) TẠO ra nó (dò máy thật). `resolve_device(requested, caps)` (mẩu 02) TIÊU
THỤ. `--capabilities` (mẩu 07) in nó ra JSON. conftest (mẩu 06) đọc `caps.has_cuda` để gate test.

## 8. Không có nó thì sao
Không DTO → `if torch.cuda.is_available()` rải khắp nơi (khó test, tầng thấp kéo torch). DTO gom "máy có gì" về 1
kiểu → tách DÒ khỏi DÙNG.

## 9. Ví von
Phiếu khám sức khoẻ máy: ghi rõ có GPU không, mấy cái, tên gì — 1 tờ, ai cần thì đọc, không phải tự khám lại mỗi lần.

## 10. Liên kết bức tranh lớn
Trung tâm capability-aware: DÒ (adapters) → DTO này (kernel) → QUYẾT ĐỊNH (kernel resolve). Giống các DTO kernel
khác (Detection/Track/MetricSample) — danh từ chia sẻ, thuần, tiêm được.

## 11. Cạm bẫy
- `has_cuda` KHÁC `has_torch`: có torch chưa chắc có CUDA (torch CPU-only). `has_cuda` = CUDA khả dụng thật (mẩu 04).
- Đừng đặt logic dò (`import torch`) vào DTO này (nó @kernel, cấm torch) — dò ở adapters (mẩu 04).

## 12. Tự kiểm (Feynman)
- Vì sao biến "máy có gì" thành DTO thay vì gọi `torch.cuda.is_available()` khắp nơi?
- `has_torch` vs `has_cuda` khác gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/capabilities.py` (đọc thật phiên này) · D-072. Độ chắc: cao (quote trực tiếp).
