# 12.04 — `runtime/iou_tracker.py::IouTracker` — giữ STATE, `update()` 6 bước, `unique_count` đơn điệu

## 1. Thuộc về đâu
Layer **runtime** — `runtime/iou_tracker.py`. Impl port `ITracker` (bài port). GIỮ STATE (`_tracks`, `_next_id`). Ghép index (domain, mẩu 02) ↔ track_id.

## 2. Cần biết trước
mẩu 02 (`greedy_associate` index-based), 05 (`Track` DTO). "đơn điệu tăng" = chỉ tăng, không lùi/tái dùng.

## 3. Code thật (quote nguyên văn — `runtime/iou_tracker.py`)
```python
    def update(self, detections: Sequence[Detection]) -> tuple[Track, ...]:
        for st in self._tracks.values():
            st.age += 1                                  # 1) mọi track già đi 1 khung
        prev_ids = list(self._tracks.keys())
        prev_boxes = [self._tracks[tid].box for tid in prev_ids]
        ...
        matches = greedy_associate(prev_boxes, new_boxes, self._iou_threshold, ...)  # 2) ghép
        new_to_tid: dict[int, int] = {}
        for new_i, prev_i in matches:                    # 3) cặp khớp → cập nhật track cũ
            tid = prev_ids[prev_i]; st = self._tracks[tid]
            st.box = det.box; st.label = det.label; st.age = 0; st.hits += 1
            new_to_tid[new_i] = tid
        for new_i in range(len(detections)):             # 4) detection chưa khớp → track MỚI
            if new_i in new_to_tid: continue
            tid = self._next_id; self._next_id += 1
            self._tracks[tid] = _TrackState(...); new_to_tid[new_i] = tid
        for tid in [t for t, st in self._tracks.items() if st.age > self._max_age]:  # 5) retire già
            del self._tracks[tid]
        out = [...Track(track_id=tid, ...) for new_i...]  # 6) output 1 Track/detection
        return tuple(out)

    @property
    def unique_count(self) -> int:
        return self._next_id
```

## 4. Giải thích từng mẩu nhỏ nhất (6 bước update)
1. **Già đi**: mọi track `age += 1` (giả định chưa khớp; khớp sẽ reset age=0).
2. **Ghép**: gọi `greedy_associate` (domain thuần) → cặp `(new_i, prev_i)`.
3. **Khớp**: track cũ cập nhật box/label mới, `age=0`, `hits += 1`, nhớ `new_i→tid`.
4. **Mới**: detection chưa khớp → track MỚI, `tid = _next_id; _next_id += 1` (id **đơn điệu**, không tái dùng).
5. **Retire**: track `age > max_age` (mất dấu quá lâu) → xoá.
6. **Output**: 1 `Track` cho mỗi detection khung này (theo thứ tự detection).
- `unique_count = _next_id` — vì id chỉ tăng, `_next_id` = tổng số track ĐÃ TỪNG tạo = đếm-không-trùng.

## 5. Là gì
Bộ theo dõi giữ state: nhận detections mỗi khung → gán/khớp track_id → trả tracks.

## 6. Tại sao tồn tại / vấn đề nó giải
domain chỉ ghép index (thuần, mẩu 02); cần 1 nơi GIỮ trạng thái track qua khung + gán id ổn định + đếm-không-trùng.
IouTracker làm điều đó ở runtime (được giữ state). `unique_count` đơn điệu = câu trả lời "bao nhiêu vật khác nhau đã thấy".

## 7. Dùng ở đâu
`TrackingStage` (mẩu 06) gọi `tracker.update(dets)` mỗi khung + đọc `unique_count`/`active_count`. Thay bằng
Kalman/DeepSORT sau = impl `ITracker` khác, KHÔNG đụng stage (port).

## 8. Không có nó thì sao
Không giữ state/không id đơn điệu → không đếm-không-trùng. Nếu tái dùng id (sau retire) → 2 vật khác nhau cùng id
→ đếm sai. Đơn điệu-không-tái-dùng đảm bảo mỗi vật 1 id duy nhất suốt luồng.

## 9. Ví von
Nhân viên phát số thứ tự: mỗi khách mới 1 số MỚI (không dùng lại số cũ) → tổng số đã phát = số khách khác nhau.

## 10. Liên kết bức tranh lớn
Runtime giữ state = "động cơ" ghép index (domain) ↔ định danh. `_TrackState` mutable (cập nhật tại chỗ) nhưng
OUTPUT `Track` frozen (mẩu 05) — state nội bộ ẩn, kết quả bất biến.

## 11. Cạm bẫy
- Tái dùng id sau retire → đếm loạn. Giữ `_next_id` chỉ-tăng.
- `age`/`max_age`: mất dấu tạm (che khuất) không nên retire ngay → `max_age` cho track "sống lại" khi xuất hiện lại (trong hạn).

## 12. Tự kiểm (Feynman)
- 6 bước `update` làm gì? Bước nào cấp id mới?
- Vì sao `unique_count = _next_id` = đếm-không-trùng? Điều gì hỏng nếu tái dùng id?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/iou_tracker.py` (đọc thật phiên này). Độ chắc: cao (quote trực tiếp; excerpt có dấu `...`).
