# 12.06 — `TrackingStage` — đọc artifacts['detections'], camera-affinity fail-fast, ghi tracks

## 1. Thuộc về đâu
runtime/stages — `tracking_stage.py`. Cầu nối detector → tracker → downstream (line-crossing).

## 2. Cần biết trước
mẩu 01 (stateful), 04 (IouTracker), bài #04 (artifacts trên MediaPacket, `.with_artifact`). "Camera-affinity" (K-042) = 1 instance phục vụ 1 camera.

## 3. Code thật (quote nguyên văn — `tracking_stage.py`)
```python
    def _do_process(self, packet: MediaPacket) -> MediaPacket:
        dets = packet.artifacts.get("detections")
        if dets is None:
            raise ValueError("TrackingStage cần artifacts['detections'] — chạy DetectStage trước (sai thứ tự pipeline)")
        if self._source_id is None:
            self._source_id = packet.source_id
        elif packet.source_id != self._source_id:
            raise ValueError(f"TrackingStage nhận 2 source_id ('{self._source_id}' rồi '{packet.source_id}') — "
                             "1 instance/1 camera (K-042); trộn state = đếm loạn")
        tracks = self._tracker.update(dets)
        return (packet
                .with_artifact("tracks", tracks)
                .with_artifact("unique_count", self._tracker.unique_count)
                .with_artifact("active_count", self._tracker.active_count))
```

## 4. Giải thích từng mẩu nhỏ nhất
- `dets = packet.artifacts.get("detections")` — đọc kết quả DetectStage (fan-out: cả CountStage lẫn TrackingStage đọc chung).
- `if dets is None: raise` — sai thứ tự pipeline (track trước detect) → fail-fast, thông điệp chỉ rõ.
- **Camera-affinity**: lần đầu ghi `_source_id`; khung sau nếu `source_id` KHÁC → raise (1 tracker chỉ 1 camera; trộn state = đếm loạn).
- `tracks = self._tracker.update(dets)` — gọi tracker (mẩu 04).
- Ghi `tracks` + `unique_count` + `active_count` vào artifacts (CoW `.with_artifact`) cho stage sau + summary.

## 5. Là gì
Stage bọc `ITracker`: đọc detections → cập nhật tracker → ghi tracks + số đếm ra artifacts.

## 6. Tại sao tồn tại / vấn đề nó giải
Tách "thuật toán tracking" (tracker, port) khỏi "vị trí trong pipeline + đọc/ghi artifacts + guard camera" (stage).
Camera-affinity fail-fast chống bug ẩn: nếu lỡ dùng 1 TrackingStage cho 2 camera (state chung) → id/đếm loạn → raise NGAY thay vì đếm sai âm thầm.

## 7. Dùng ở đâu
Registry `_stage_track` (mẩu #11.08) dựng `TrackingStage(IouTracker(...))`. Trong chuỗi: sau detect/count, trước line_crossing (đọc `artifacts["tracks"]`).

## 8. Không có nó thì sao
Không guard thứ tự → track không có detections → crash mơ hồ sâu trong tracker. Không camera-affinity → deploy sai
(1 stage 2 cam) đếm loạn mà không báo. Guard = fail-fast rõ ràng.

## 9. Ví von
Thư ký ghi sổ theo dõi cho MỘT quầy: nếu ai đó đưa khách quầy KHÁC vào cùng sổ → từ chối ngay (kẻo lẫn số).

## 10. Liên kết bức tranh lớn
"artifacts fan-out" (mẩu 14): DetectStage ghi `detections` 1 lần → Count + Track cùng đọc. Stateful stage + guard = mẫu chung (giống LineCrossingStage mẩu 09).

## 11. Cạm bẫy
- Thứ tự pipeline: `detect` PHẢI trước `track` (guard bắt nếu sai).
- 1 TrackingStage / 1 camera (camera-affinity). Nhiều camera → nhiều instance.
- `teardown` gọi `tracker.reset()` → đọc `unique_count` sau run() ra 0; phải đọc từ artifacts khung cuối (xem `_TrackSummarySink`, #11.15).

## 12. Tự kiểm (Feynman)
- Vì sao camera-affinity fail-fast thay vì cho chạy? Bug gì nếu 1 stage 2 camera?
- Vì sao đọc `unique_count` từ artifacts chứ không từ tracker sau `run()`?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`runtime/stages/tracking_stage.py` (đọc thật phiên này) · K-042 (camera-affinity). Độ chắc: cao (quote trực tiếp).
