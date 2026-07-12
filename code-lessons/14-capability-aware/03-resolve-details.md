# 14.03 — Chi tiết resolve: `has_cuda` gate · `cuda:N` kiểm ordinal · chuẩn hoá lower

## 1. Thuộc về đâu
kernel — `kernel/capabilities.py` (`resolve_device` + `_parse_ordinal`). Đi sâu 3 chi tiết chống-lỗi.

## 2. Cần biết trước
mẩu 02 (resolve_device tổng quan). "ordinal" = số thứ tự GPU (cuda:0, cuda:1...).

## 3. Code thật (quote nguyên văn — `kernel/capabilities.py`)
```python
_CUDA_BARE = frozenset({"cuda", "gpu"})

def _parse_ordinal(dev_lower: str) -> int:
    """'cuda:N' → int N (≥0). Không phải số nguyên ≥0 → CapabilityError."""
    suffix = dev_lower.split(":", 1)[1]
    if not suffix.isdigit():   # isdigit → chỉ [0-9]+ (loại '-1', 'x', rỗng)
        raise CapabilityError(f"device {dev_lower!r} không hợp lệ: ordinal sau 'cuda:' phải là số nguyên ≥0.")
    return int(suffix)
```
```python
    r = (requested or "auto").strip().lower()      # chuẩn hoá lower + strip + None→auto
    ...
        if r.startswith("cuda:"):
            idx = _parse_ordinal(r)
            if idx >= caps.cuda_device_count:      # cuda:N nhưng N >= số GPU → fail
                raise CapabilityError(...)
            return r                               # "cuda:0" (đã lower)
        return "cuda"                              # bare cuda/gpu → "cuda" (adapter map → cuda:0)
```

## 4. Giải thích từng chi tiết
- **Chuẩn hoá lower**: `(requested or "auto").strip().lower()` → `"CUDA"`, `" cuda "`, `None` đều về dạng chuẩn.
  Trả về LUÔN lower ("cpu"/"cuda"/"cuda:0") → 1 dạng chuẩn duy nhất xuống adapter (adapter tự map "cuda"→"cuda:0").
- **has_cuda gate**: mọi nhánh cuda kiểm `if not caps.has_cuda: raise` TRƯỚC → không đụng `cuda_device_count` khi không có CUDA.
- **cuda:N ordinal**: `_parse_ordinal` dùng `isdigit()` (chỉ `[0-9]+`) → loại `cuda:-1`/`cuda:x`/`cuda:` (rỗng). Rồi
  `if idx >= caps.cuda_device_count: raise` → `cuda:5` trên máy 2 GPU (hợp lệ 0..1) → fail-fast RÕ (không fail mù torch).
- `gpu`/`cuda` trần → trả `"cuda"` (adapter tự map cuda:0).

## 5. Là gì
Các quy tắc chuẩn-hoá + kiểm-biên để resolve device đúng và báo lỗi rõ ở mọi ca xấu.

## 6. Tại sao tồn tại / vấn đề nó giải
Ép `cuda:5` trên máy 1 GPU nếu không kiểm → lỗi mù sâu trong torch ("invalid device ordinal") khó hiểu. Kiểm ordinal
ở đây → CapabilityError nói RÕ "máy chỉ có N GPU (hợp lệ cuda:0..cuda:N-1)". Chuẩn hoá lower → tránh "CUDA" vs "cuda"
lệch. has_cuda gate → không truy count khi không CUDA.

## 7. Dùng ở đâu
Bên trong `resolve_device` (mẩu 02), gọi từ `_det_pt` (mẩu 08). Test tiêm caps `cuda_device_count=2` → kiểm `cuda:5` raise.

## 8. Không có nó thì sao
Không kiểm ordinal → lỗi torch mù. Không chuẩn hoá → "GPU"/"cuda" xử khác nhau. Không has_cuda gate → truy `cuda_device_count` vô nghĩa khi không CUDA.

## 9. Ví von
Kiểm vé: ghế "C5" nhưng rạp chỉ có ghế C0–C1 → báo NGAY "ghế không tồn tại, hợp lệ C0–C1" thay vì để khách vào mò rồi lỗi.

## 10. Liên kết bức tranh lớn
Làm resolve_device (mẩu 02) ROBUST ở mọi ca biên. Fail-fast + thông điệp rõ = triết lý xuyên repo (giống ConfigError #11).

## 11. Cạm bẫy
- `isdigit()` loại số âm/rỗng/chữ — đúng ý "ordinal ≥0". Đừng dùng `int()` trần (nuốt `-1`).
- Luôn trả LOWER — adapter kỳ vọng dạng chuẩn.

## 12. Tự kiểm (Feynman)
- `cuda:5` trên máy 2 GPU → điều gì xảy ra, thông điệp gì? Vì sao tốt hơn để torch báo?
- Vì sao chuẩn hoá `.lower()` + trả lower?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/capabilities.py` (đọc thật phiên này) · D-073 (Property 8/9, K-069). Độ chắc: cao (quote trực tiếp).
