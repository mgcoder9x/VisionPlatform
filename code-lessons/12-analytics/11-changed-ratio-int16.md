# 12.11 — `domain/motion.py::changed_ratio` — cast `int16` chống uint8 UNDERFLOW (bẫy sáng→tối)

## 1. Thuộc về đâu
Layer **domain** — `domain/motion.py`. Python thuần + numpy (luật cho phép numpy ở domain; cấm cv2/torch). Đo "2 khung khác nhau bao nhiêu".

## 2. Cần biết trước
frame ảnh = numpy array dtype `uint8` (giá trị 0..255). `uint8` KHÔNG âm được → phép trừ có thể WRAP (underflow).

## 3. Code thật (quote nguyên văn — `domain/motion.py`)
```python
    if prev.shape != curr.shape:
        raise ValueError(f"changed_ratio cần cùng shape, got {prev.shape} vs {curr.shape}")
    a = prev.astype(np.int16)
    b = curr.astype(np.int16)
    ...
    diff = np.abs(b - a)
    changed = int(np.count_nonzero(diff > pixel_diff_threshold))
    return changed / diff.size
```

## 4. Giải thích từng mẩu nhỏ nhất
- `a = prev.astype(np.int16)` / `b = curr.astype(np.int16)` — **cast sang int16 TRƯỚC khi trừ**. int16 chứa được
  số ÂM (-32768..32767) → hiệu đúng dấu.
- `diff = np.abs(b - a)` — độ lệch tuyệt đối từng pixel.
- `changed = count_nonzero(diff > pixel_diff_threshold)` — số pixel đổi "đáng kể" (vượt ngưỡng).
- `return changed / diff.size` — tỉ lệ pixel đổi ∈ [0,1].

## 5. Là gì
Đo tỉ lệ pixel thay đổi giữa 2 khung — thước đo "có chuyển động không".

## 6. Tại sao cast int16 (bẫy CỐT LÕI)
Nếu trừ THẲNG uint8: `10 - 250` (pixel sáng→tối) KHÔNG ra `-240` mà WRAP thành `16` (underflow: 10-250 mod 256).
→ `abs(16)=16` < ngưỡng → coi là "KHÔNG đổi" → **nuốt chuyển động sáng→tối** (vd đèn tắt, vật tối che nền sáng).
Cast int16 trước → `10-250 = -240` → `abs=240` > ngưỡng → bắt đúng. Đây là bug thầm lặng kinh điển khi xử ảnh uint8.

## 7. Dùng ở đâu
`MotionGateStage._do_process` (mẩu 13): `ratio = changed_ratio(prev, curr, threshold, ...)`; `ratio < min_area_ratio` → skip khung (tĩnh).

## 8. Không có nó thì sao
Trừ thẳng uint8 → underflow nuốt nửa số chuyển động (mọi thay đổi sáng→tối) → motion-gate bỏ nhầm khung CÓ vật
(sáng→tối) → SÓT phát hiện. Cast int16 = fix GỐC ở phép toán.

## 9. Ví von
Đo chênh lệch nhiệt độ mà dùng thước chỉ đo số dương → "−240 độ" hiện thành "+16 độ" → tưởng không đổi. Phải dùng thước có số âm (int16).

## 10. Liên kết bức tranh lớn
Nền cho motion-gate (cắt tải detector). Nguyên tắc: xử ảnh uint8 → luôn cast lên kiểu có dấu/rộng hơn trước phép trừ.

## 11. Cạm bẫy
- Quên cast → underflow (bug này). numpy KHÔNG cảnh báo, chạy "bình thường" nhưng SAI → phải test ca sáng→tối.
- `prev.shape != curr.shape` → raise (caller/Stage xử khung đổi-shape TRƯỚC khi gọi — mẩu 13).

## 12. Tự kiểm (Feynman)
- `uint8`: `10 - 250` ra bao nhiêu? Vì sao? Nó gây bug gì cho motion-gate?
- Vì sao cast `int16` sửa được? Cast xảy ra TRƯỚC hay SAU phép trừ?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/motion.py::changed_ratio` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp). uint8 underflow wrap = hành vi numpy chuẩn [độ chắc: cao].
