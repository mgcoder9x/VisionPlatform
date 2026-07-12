# 12 — Analytics — MỤC LỤC (các mẩu nhỏ nhất)

> Đọc `00-cau-chuyen.md` trước. Mỗi mẩu = 1 ý nhỏ nhất, quote code thật + cite path. Tạo DẦN (không hàng loạt).
> Trạng thái: ⬜ chưa · 🔵 đang · ✅ đã viết đủ.

| # | Mẩu (ý nhỏ nhất) | File code thật | Trạng thái |
|---|---|---|---|
| 01 | Analytics STATEFUL vs detect STATELESS — vì sao đếm-không-trùng cần định-danh-xuyên-khung | `runtime/stages/tracking_stage.py` vs `count_stage.py` | ✅ `01-stateful-vs-stateless.md` |
| 02 | `domain/tracking.py::greedy_associate` — vì sao INDEX-based (domain cấm import kernel `Detection`) | `domain/tracking.py` | ✅ `02-greedy-associate-index-based.md` |
| 03 | IoU-greedy + tie-break XÁC ĐỊNH `sort(-iou, ni, pi)` — test lặp-lại-được | `domain/tracking.py` | ✅ `03-tie-break-xac-dinh.md` |
| 04 | `runtime/iou_tracker.py` — `_TrackState` mutable, `update()` 6 bước, `unique_count=_next_id` đơn điệu | `runtime/iou_tracker.py` | ✅ `04-iou-tracker.md` |
| 05 | `Track` DTO (frozen) — `track_id`/`age`/`hits`; box giữ `space` (invariant Step 02) | `kernel/tracking_protocol.py` | ✅ `05-track-dto.md` |
| 06 | `TrackingStage` — đọc artifacts['detections'], camera-affinity fail-fast, ghi tracks/unique/active | `runtime/stages/tracking_stage.py` | ✅ `06-tracking-stage.md` |
| 07 | `domain/geometry.py::orient` — cross-product dấu = "phía nào của đường" | `domain/geometry.py` | ✅ `07-orient-cross-product.md` |
| 08 | `segments_intersect` — proper intersection; collinear/điểm-suy-biến = False (vì sao) | `domain/geometry.py` | ✅ `08-segments-intersect.md` |
| 09 | `LineCrossingStage` — tâm prev↔curr cắt vạch → +1; `direction` từ dấu orient; bounded-memory prune | `runtime/stages/line_crossing_stage.py` | ✅ `09-line-crossing-stage.md` |
| 10 | `CrossingEvent` DTO — wall-clock ISO-8601 "Z", vì sao KHÔNG giữ BBox (chỉ cx,cy) | `kernel/crossing_event.py` | ✅ `10-crossing-event-dto.md` |
| 11 | `domain/motion.py::changed_ratio` — cast `int16` chống uint8 underflow (bẫy sáng→tối) | `domain/motion.py` | ✅ `11-changed-ratio-int16.md` |
| 12 | ROI + illumination-robust — THỨ TỰ thu-ROI-trước-rồi-mean; `validate_roi` (config-time) vs `roi_mask` (runtime) | `domain/motion.py` | ✅ `12-roi-illumination-order.md` |
| 13 | `MotionGateStage` — skip frame tĩnh, frame-đầu cho-đi-tiếp, `max_consecutive_skip` ép chạy định kỳ | `runtime/stages/motion_gate_stage.py` | ✅ `13-motion-gate-stage.md` |
| 14 | Wiring: thứ tự stage motion_gate→detect→count→track→line + artifacts fan-out (SkipFrameSignal) | `sync_linear_executor` + stages | ✅ `14-wiring-stage-order-artifacts.md` |

**Ghi chú:** #12 = analytics (spec object-tracking-count · line-crossing-count · crossing-event · motion-gate/-roi),
làm sau #10 (không có folder `implement/12`). Đọc kèm bài #04 (pipeline/stage) + #06 (detection).
