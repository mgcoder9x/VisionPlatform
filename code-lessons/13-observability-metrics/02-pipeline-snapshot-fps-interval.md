# 13.02 — `PipelineSnapshot` (frozen) — fps INTERVAL (không che sự cố) vs trung-bình-tích-luỹ

## 1. Thuộc về đâu
kernel — `kernel/observability_port.py`. DTO frozen mang số liệu 1 camera tại 1 thời điểm.

## 2. Cần biết trước
mẩu 01 (port). "interval fps" = số frame kể từ lần đo trước / thời gian trôi (nhịp GẦN ĐÂY). "tích luỹ" = tổng frame / tổng thời gian.

## 3. Code thật (quote nguyên văn — `kernel/observability_port.py`)
```python
@dataclass(frozen=True)
class PipelineSnapshot:
    source_id: str
    frames_read: int
    processed: int
    skipped: int
    stage_errors: int
    frames_per_second: float
    skip_rate: float
    is_final: bool = False
```
Docstring:
```python
"""- `frames_per_second`: throughput INTERVAL (frame kể từ lần emit trước / thời gian trôi) — phản ánh nhịp
      GẦN ĐÂY, KHÔNG che sự cố (khác trung bình tích luỹ)."""
```

## 4. Giải thích từng mẩu nhỏ nhất
- `source_id` — camera nào (nhãn phân biệt khi nhiều camera).
- `frames_read/processed/skipped/stage_errors` — số đếm tích luỹ của luồng.
- `frames_per_second` — fps **INTERVAL** (tính trong `PipelineRunner._emit`, xem mẩu 03): `d_frames/dt` giữa 2 lần emit.
- `skip_rate` — `skipped/frames_read` (tỉ lệ motion-gate bỏ).
- `is_final` — snapshot CHỐT lúc `run()` kết thúc.
- `frozen=True` — bất biến (ảnh chụp, không sửa).

## 5. Là gì
Ảnh chụp số liệu vận hành 1 camera để phát cho observer.

## 6. Tại sao fps INTERVAL (không tích luỹ)
Camera chạy 1 giờ ở 30fps rồi RỚT (0 fps 5 phút gần đây). **Trung bình tích luỹ** vẫn ~30fps (đẹp) → CHE sự cố.
**Interval** = fps 5 phút gần đây ~0 → lộ ngay "camera đang chết". Vận hành cần thấy sự-cố-hiện-tại, không phải
trung-bình-quá-khứ. → chọn interval.

## 7. Dùng ở đâu
`PipelineRunner._emit` dựng `PipelineSnapshot` (fps interval) → `observer.on_snapshot(snap)`. `LoggingObserver`/
`MetricsObserver` (mẩu 04) đọc các field này.

## 8. Không có nó thì sao (nếu dùng tích luỹ)
Dashboard "xanh" trong khi camera đã chết → phát hiện sự cố muộn. Interval + emit-định-kỳ = cảnh báo sớm.

## 9. Ví von
Đồng hồ tốc độ xe: hiện tốc độ HIỆN TẠI (interval), không hiện "tốc độ trung bình cả chuyến" — để tài xế biết đang chạy nhanh/chậm/dừng.

## 10. Liên kết bức tranh lớn
DTO của khâu ĐO. `is_final` + emit-theo-giờ (mẩu 03) đảm bảo luôn có snapshot cuối + phát cả khi mất-camera.

## 11. Cạm bẫy
- Nhầm interval với tích luỹ → che sự cố. Công thức interval nằm ở `_emit` (mẩu 03), không ở DTO.
- `skip_rate` là tích luỹ (skipped/frames_read) — khác fps (interval); đọc đúng ngữ nghĩa từng field.

## 12. Tự kiểm (Feynman)
- Camera rớt 5 phút: fps tích-luỹ vs interval hiện gì? Cái nào lộ sự cố?
- `is_final` để làm gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/observability_port.py` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp).
