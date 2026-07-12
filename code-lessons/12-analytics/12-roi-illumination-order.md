# 12.12 — ROI + illumination-robust: THỨ TỰ thu-ROI-trước-rồi-mean; `validate_roi` vs `roi_mask`

## 1. Thuộc về đâu
domain — `domain/motion.py` (`changed_ratio` phần mask/illumination + `validate_roi` + `roi_mask`).

## 2. Cần biết trước
mẩu 11 (`changed_ratio` int16). ROI = Region Of Interest (vùng quan tâm, chữ nhật chuẩn-hoá [0,1]). "Illumination-robust" = bền với đổi-sáng-ĐỀU (đèn/mây).

## 3. Code thật (quote nguyên văn — `domain/motion.py`)
```python
    # 1) Thu về vùng ROI TRƯỚC (nếu có mask).
    if mask is not None:
        a = a[mask]
        b = b[mask]
    if a.size == 0:
        return 0.0
    # 2) RỒI mean-subtraction TRÊN VÙNG ĐANG XÉT (triệt uniform-shift: curr=prev+c → d=0).
    if illumination_robust:
        a = a - a.mean()
        b = b - b.mean()
    diff = np.abs(b - a)
```
```python
def validate_roi(x, y, w, h) -> None:   # THUẦN SỐ → config-time (fail-fast SỚM)
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and w > 0.0 and h > 0.0
            and x + w <= 1.0 + _ROI_EPS and y + h <= 1.0 + _ROI_EPS):
        raise ValueError(...)

def roi_mask(height, width, x, y, w, h) -> np.ndarray:   # CẦN shape → runtime (frame đầu)
    validate_roi(x, y, w, h)
    ...
    if px1 <= px0 or py1 <= py0:
        raise ValueError("ROI rỗng sau khi quy về pixel ...")
    m = np.zeros((height, width), dtype=bool); m[py0:py1, px0:px1] = True; return m
```

## 4. Giải thích từng mẩu nhỏ nhất
- `mask` = bool array (H,W) đánh dấu vùng ROI. `a[mask]` → chỉ lấy pixel TRONG ROI.
- `if a.size == 0: return 0.0` — vùng rỗng (mask toàn False) → không gì để đo → 0 (guard TRƯỚC mean để tránh chia/nan).
- `illumination_robust`: trừ trung-bình-vùng mỗi khung → nếu `curr = prev + c` (sáng đều lên c) thì sau khi trừ mean, hiệu = 0 → KHÔNG trigger oan.
- **THỨ TỰ: thu ROI (1) TRƯỚC, mean (2) SAU** — để mean là mean TRONG ROI. Nếu tính mean toàn-khung trước, đổi-sáng NGOÀI ROI kéo mean → trừ sai → tạo chuyển động GIẢ trong ROI.
- `validate_roi` (thuần số) vs `roi_mask` (cần shape): tách 2 tầng kiểm.

## 5. Là gì
2 tính năng chống nhiễu cho motion-gate (chỉ đo trong vùng + triệt đổi-sáng-đều) + 2 hàm kiểm ROI ở 2 thời điểm.

## 6. Tại sao tồn tại / vấn đề nó giải
- ROI: camera nhìn cả trời/cây (gió lay) → chuyển động NGOÀI vùng quan tâm trigger oan. Chỉ đo trong ROI (làn đường).
- illumination-robust: đèn bật/mây che → cả khung sáng đều → hiệu pixel lớn → tưởng có chuyển động (oan). Mean-subtraction triệt uniform-shift.
- THỨ TỰ: đây là bẫy tinh vi — sai thứ tự (mean toàn-khung trước) thì đổi-sáng ngoài ROI vẫn tạo chuyển động giả trong ROI (có test `test_roi_x_illum_order` bảo vệ).
- `validate_roi` config-time: bắt ROI sai (x+w>1) NGAY khi parse config (fail-fast sớm), không cần chờ frame; `roi_mask` runtime: bắt "ROI rỗng sau quy pixel" (cần biết shape).

## 7. Dùng ở đâu
`MotionGateStage`: dựng `roi_mask` LAZY ở frame đầu (biết shape) → truyền `mask`+`illumination_robust` vào `changed_ratio`.
`pipeline_factory._parse_roi` gọi `validate_roi` lúc dựng config (config-time).

## 8. Không có nó thì sao
Không ROI → cây/trời lay trigger detector liên tục (phí tải). Không illumination-robust → đổi đèn = chạy detector oan.
Sai thứ tự → chuyển động giả trong ROI. Thiếu validate_roi config-time → ROI sai lộ muộn (runtime).

## 9. Ví von
Chỉ dán "mắt thần" vào KHUNG CỬA (ROI), bỏ qua sân; và biết phân biệt "đèn hành lang bật" (sáng đều, không phải người) với "người đi qua".

## 10. Liên kết bức tranh lớn
Bền-nhiễu cho cắt-tải. `validate_roi` (config-time) nối chuỗi config-declarative (#11 mẩu 05: fail-fast sớm). Nối mẩu 13 (Stage dựng mask lazy).

## 11. Cạm bẫy
- Đảo thứ tự (mean trước ROI) → chuyển động giả (bug tinh vi, có test riêng bảo vệ).
- `a.size==0` guard PHẢI trước `mean()` (mean của rỗng = nan). 
- `validate_roi` KHÔNG bắt "rỗng sau quy pixel" (cần shape) → đó là việc `roi_mask` runtime.

## 12. Tự kiểm (Feynman)
- Vì sao thu ROI TRƯỚC rồi mới mean? Sai thứ tự ra bug gì?
- `validate_roi` (config-time) vs `roi_mask` (runtime) — cái nào bắt lỗi gì, VÌ SAO tách?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`domain/motion.py` (đọc thật phiên này) · spec motion-gate-roi (K-063). Độ chắc: cao (quote trực tiếp).
