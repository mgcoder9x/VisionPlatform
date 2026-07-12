# 12.09 — `LineCrossingStage` — tâm prev↔curr cắt vạch → +1; `direction` từ dấu orient; bounded-memory

## 1. Thuộc về đâu
runtime/stages — `line_crossing_stage.py`. STATEFUL (nhớ tâm khung trước mỗi track). Đọc `artifacts["tracks"]` (từ TrackingStage).

## 2. Cần biết trước
mẩu 07 (`orient`), 08 (`segments_intersect`), 05 (`Track`), 10 (`CrossingEvent`).

## 3. Code thật (quote nguyên văn — `line_crossing_stage.py`, lõi)
```python
        for tr in tracks:
            if tr.box.space != self._space:
                raise ValueError(f"LineCrossingStage: track box space {tr.box.space} khác space vạch {self._space} ...")
            cx = tr.box.x + tr.box.w / 2.0
            cy = tr.box.y + tr.box.h / 2.0
            curr = (cx, cy)
            seen.add(tr.track_id)
            prev = self._last_center.get(tr.track_id)
            if prev is not None and segments_intersect(prev, curr, self._a, self._b):
                direction = "in" if orient(ax, ay, bx, by, cx, cy) > 0 else "out"
                if direction == "in": self._in += 1
                else: self._out += 1
                ts = self._clock().isoformat().replace("+00:00", "Z")
                events.append(CrossingEvent(track_id=tr.track_id, label=tr.label, direction=direction,
                              source_id=self._source_id, cx=cx, cy=cy, event_ts=ts))
            self._last_center[tr.track_id] = curr
        for tid in [t for t in self._last_center if t not in seen]:
            del self._last_center[tid]   # prune track vắng khung này (bounded memory)
```

## 4. Giải thích từng mẩu nhỏ nhất
- `if tr.box.space != self._space: raise` — so vị trí khác KHÔNG-GIAN là vô nghĩa → fail-fast (invariant Step 02).
- `cx, cy` = TÂM box track. `curr = (cx, cy)`.
- `prev = self._last_center.get(tr.track_id)` — tâm khung TRƯỚC của CHÍNH track này (nhớ theo track_id).
- `if prev is not None and segments_intersect(prev, curr, A, B)` — đường đi tâm `[prev,curr]` cắt vạch `[A,B]` → QUA vạch (mẩu 08).
- `direction = "in" if orient(...) > 0 else "out"` — HƯỚNG từ dấu orient của tâm hiện tại so vạch A→B (mẩu 07). **1 nguồn `direction`** dùng cho CẢ đếm (`_in`/`_out`) lẫn `CrossingEvent` → không lệch.
- `event_ts` = wall-clock UTC ISO "Z" (mẩu 10).
- `self._last_center[tr.track_id] = curr` — cập nhật mốc.
- **prune**: xoá `_last_center` của track KHÔNG có mặt khung này → RAM ~ số track sống (bounded memory, R3.4).

## 5. Là gì
Stage đếm lượt qua vạch theo hướng + phát `CrossingEvent`, nhớ tâm khung trước từng track.

## 6. Tại sao tồn tại / vấn đề nó giải
Nghiệp vụ "đếm xe VÀO/RA cổng". Dùng đường-đi-tâm cắt vạch (chuẩn hình học, mẩu 08) + dấu orient cho hướng. 1
nguồn `direction` → đếm và event không bao giờ lệch nhau. Prune → không rò RAM khi chạy dài (track cũ biến mất).

## 7. Dùng ở đâu
Registry `_stage_line_crossing` dựng từ config `--line ax,ay,bx,by`. Sau `track` trong chuỗi. Ghi
`crossings_in/out/total` + `crossing_events` vào artifacts → sink (JSONL/SQLite) + summary.

## 8. Không có nó thì sao
Không nhớ tâm trước → không biết "đã qua vạch" (cần 2 điểm để có đoạn). Không prune → `_last_center` phình vô hạn
(track đã biến mất vẫn giữ) = rò RAM khi chạy dài. Không fail-fast space → so toạ độ khác hệ = đếm rác.

## 9. Ví von
Vạch vôi giữa đường + camera: xe đi từ vị-trí-cũ tới vị-trí-mới, nếu đường nối cắt vạch vôi → tính 1 lượt; ở bên
trái hay phải vạch → vào/ra. Xe rời khung → xoá ghi chú vị-trí-cũ của nó.

## 10. Liên kết bức tranh lớn
Đỉnh chuỗi analytics: dùng geometry domain (07/08) + Track (05) → CrossingEvent (10). Stateful + bounded-memory + camera-affinity (giống TrackingStage mẩu 06).

## 11. Cạm bẫy
- Cần `--track` trước (đọc `artifacts["tracks"]`) — guard `_validate` (#11) + stage raise nếu thiếu.
- Đảo A,B → in↔out đảo (orient đổi dấu). Quy ước cố định theo config.
- Quên prune → rò RAM luồng dài.

## 12. Tự kiểm (Feynman)
- Vì sao cần NHỚ tâm khung trước (prev)? Không có prev thì sao?
- `direction` lấy từ đâu, vì sao dùng CHUNG cho cả đếm lẫn event?
- Prune giải nỗi lo gì khi chạy dài?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/stages/line_crossing_stage.py` (đọc thật phiên này) · spec line-crossing-count/crossing-event-log. Độ chắc: cao (quote trực tiếp).
