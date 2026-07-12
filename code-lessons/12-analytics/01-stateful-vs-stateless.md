# 12.01 — Analytics STATEFUL vs detect/count STATELESS — vì sao đếm-không-trùng cần NHỚ

## 1. Thuộc về đâu
runtime/stages. So `TrackingStage` (stateful) với `CountStage`/`DetectStage` (stateless). Đây là mẩu KHÁI NIỆM mở đầu #12.

## 2. Cần biết trước
bài #04 (stage/pipeline), #06 (detection trả list[Detection] mỗi khung). "State" = dữ liệu NHỚ giữa các lần gọi.

## 3. Code thật (quote — `runtime/stages/tracking_stage.py`)
```python
class TrackingStage(BaseStage):
    def __init__(self, tracker: ITracker):
        super().__init__("track")
        self._tracker = tracker          # <-- STATE nằm trong tracker (nhớ xuyên khung)
        self._source_id: Optional[str] = None
    ...
    def teardown(self) -> None:
        self._tracker.reset()            # <-- giải phóng state khi hết luồng
```
(so với `count_stage.py`: `CountStage` chỉ đếm số detection TRONG khung hiện tại → không nhớ gì.)

## 4. Giải thích từng mẩu nhỏ nhất
- `DetectStage`/`CountStage` = **stateless**: xử 1 khung độc lập (khung này có mấy vật) → gọi lại với khung khác
  không phụ thuộc khung trước.
- `TrackingStage` = **stateful**: giữ `self._tracker` (nhớ các track đang sống + `track_id` đã cấp) → mới biết
  "vật khung này CÓ PHẢI vật khung trước".
- `teardown()` gọi `tracker.reset()` — xoá state khi kết thúc (đổi camera/dừng luồng).

## 5. Là gì
Phân biệt 2 loại stage: không-nhớ (detect/count) vs có-nhớ (tracking/line-crossing).

## 6. Tại sao tồn tại / vấn đề nó giải
"Đếm không trùng" (nhịp 2 cau-chuyen) BẮT BUỘC nhớ xuyên khung: 1 xe ở 30 khung/giây, đếm thô = 30. Muốn đếm 1
lần phải NHỚ "đã thấy xe này (track_id=7)". Không có state → không thể đếm-không-trùng.

## 7. Dùng ở đâu
Chuỗi analytics: `detect`(stateless) → `track`(stateful, gán id) → `line_crossing`(stateful, nhớ tâm khung trước).
`unique_count` chỉ có nghĩa vì tracker nhớ đã cấp bao nhiêu id.

## 8. Không có nó thì sao
Không stateful → chỉ đếm-theo-khung (đúng cho "mật độ tức thời" nhưng SAI cho "tổng lượt qua"). Khách hỏi "bao
nhiêu xe qua cổng hôm nay" → phải stateful.

## 9. Ví von
Bảo vệ đếm khách: stateless = đếm số người ĐANG đứng trước cửa mỗi lần nhìn (cùng người đếm nhiều lần); stateful =
ghi sổ ai đã vào (mỗi người 1 lần).

## 10. Liên kết bức tranh lớn
State đặt trong `tracker` (runtime) chứ không trong domain (domain thuần, không state) — tách "thuật toán thuần"
khỏi "bộ nhớ chạy". Nối mẩu 02 (domain association thuần) + 04 (IouTracker giữ state).

## 11. Cạm bẫy
- State + đa camera = nguy hiểm: 1 tracker phục vụ 2 camera → trộn id → đếm loạn. → camera-affinity (mẩu 06).
- Quên `reset()` lúc teardown → state cũ rò sang lần chạy sau (nếu tái dùng instance).

## 12. Tự kiểm (Feynman)
- Vì sao `CountStage` stateless nhưng `TrackingStage` phải stateful?
- State của tracking nằm ở đâu (object nào)? Vì sao KHÔNG đặt ở domain?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/stages/tracking_stage.py`/`count_stage.py` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp).
