# 12.05 — `Track` DTO (frozen) — `track_id`/`age`/`hits`; box giữ `space`

## 1. Thuộc về đâu
Layer **kernel** — `kernel/tracking_protocol.py`. DTO thuần frozen, đối xứng `Detection`. Import `BBox`@domain (kernel↠domain hợp lệ).

## 2. Cần biết trước
mẩu 04 (IouTracker tạo Track), bài #02 (frozen dataclass, CoordinateSpace `space`).

## 3. Code thật (quote nguyên văn — `kernel/tracking_protocol.py`)
```python
@dataclass(frozen=True)
class Track:
    track_id: int
    label: str
    box: BBox
    age: int
    hits: int
```

## 4. Giải thích từng mẩu nhỏ nhất
- `track_id: int` — định danh ổn định xuyên khung (đơn điệu, không tái dùng — mẩu 04).
- `label: str` — nhãn lớp (từ detection khớp).
- `box: BBox` — box MỚI NHẤT của vật; giữ nguyên `space` tag (invariant Step 02 — không đổi hệ toạ độ ngầm).
- `age: int` — số khung LIÊN TIẾP chưa khớp (0 khi vừa khớp/vừa tạo).
- `hits: int` — tổng khung track đã được khớp (>= 1).
- `frozen=True` — bất biến (kết quả trả ra ngoài không sửa được; state mutable ẩn trong `_TrackState` runtime).

## 5. Là gì
Bản ghi bất biến mô tả 1 vật đang theo dõi tại 1 khung.

## 6. Tại sao tồn tại
Cần "kết quả tracking" có kiểu, bất biến, để stage sau (line_crossing) đọc an toàn. Frozen → downstream không sửa
nhầm. `age`/`hits` cho phép lọc track "non" (hits thấp = mới, chưa chắc) nếu cần (v1 chưa dùng nhưng sẵn).

## 7. Dùng ở đâu
`IouTracker.update` trả `tuple[Track, ...]` → `TrackingStage` ghi `artifacts["tracks"]` → `LineCrossingStage`
(mẩu 09) đọc `tr.box`, `tr.track_id`, `tr.label`.

## 8. Không có nó thì sao
Trả tuple thô/dict → downstream đoán cấu trúc, dễ sai key, không kiểu, mutable. DTO frozen = hợp đồng rõ + an toàn.

## 9. Ví von
Thẻ theo dõi 1 đối tượng: mã số (track_id), loại, vị trí mới nhất, "vắng mấy khung" (age), "điểm danh mấy lần" (hits).

## 10. Liên kết bức tranh lớn
Đối xứng `Detection` (bài #06). kernel DTO = danh từ chia sẻ giữa runtime (tạo) và stage (đọc). Giữ `space` = kỷ luật toạ độ xuyên hệ.

## 11. Cạm bẫy
- `box.space` phải khớp không-gian khi so với vạch (mẩu 09 fail-fast nếu lệch space).
- `age`/`hits` là số khung, KHÔNG phải thời gian — phụ thuộc fps.

## 12. Tự kiểm (Feynman)
- `age` vs `hits` khác nhau gì? Khi nào `age=0`?
- Vì sao `Track` frozen nhưng state tracker (`_TrackState`) mutable? (nối mẩu 04)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/tracking_protocol.py` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp).
