# 12 — Analytics (tracking → đếm-qua-vạch → motion-gate) — CÂU CHUYỆN

> Bám code THẬT (đã đọc): `domain/tracking.py`·`domain/geometry.py`·`domain/motion.py` · `runtime/iou_tracker.py`·
> `runtime/stages/{tracking_stage,line_crossing_stage,motion_gate_stage,count_stage}.py` · `kernel/{tracking_protocol,crossing_event}.py`·`kernel/ports/tracker.py`.
> Người học: đã qua #04 (pipeline/stage) + #06 (detection). Thuật ngữ lạ → `knowledge-base/00-GLOSSARY.md`.

---

## Nhịp 1 — Tổng quan (analytics nằm ĐÂU, phục vụ GÌ)

Detector (bài #06) trả "khung này có 3 xe" — nhưng khách hàng hỏi câu KHÁC: *"hôm nay có bao nhiêu xe ĐI QUA
cổng?"*. Đó là **analytics**: biến "phát hiện từng-khung" thành "sự kiện có ý nghĩa nghiệp vụ" (đếm không trùng,
đếm qua vạch theo hướng). Vị trí trong pipeline:

```
frame → [motion_gate] → detect → count → [track] → [line_crossing] → sink
          (cắt tải)              (đếm/khung) (định danh) (đếm QUA vạch + CrossingEvent)
```
- **motion_gate** (`runtime/stages`) — CẮT TẢI: bỏ frame tĩnh TRƯỚC detector (detector đắt nhất).
- **track** — gán *định danh ổn định* (`track_id`) cho mỗi vật xuyên khung → đếm KHÔNG trùng.
- **line_crossing** — 1 vật đi qua vạch → +1 theo hướng (in/out) + phát `CrossingEvent`.

Ba tầng lại tách: **toán thuần @domain** (association, hình học, motion) · **stateful engine @runtime** (tracker) ·
**DTO @kernel** (Track, CrossingEvent). Đây là điểm mấu chốt của bài.

---

## Nhịp 2 — VẤN ĐỀ & tại sao (Forces)

**Vấn đề 1 — đếm không trùng:** detector chạy MỖI khung, cùng 1 chiếc xe xuất hiện ở 30 khung/giây → đếm thô =
đếm 30 lần 1 xe. Cần biết "xe khung này CÙNG xe khung trước" → cần *định danh xuyên khung* (tracking).
- *Forces:* chính xác (khớp đúng vật) ↔ đơn giản/nhanh (real-time, không ML nặng); xác định (test được) ↔ tối ưu toàn cục.

**Vấn đề 2 — đếm qua vạch có HƯỚNG:** "vào bãi" khác "ra bãi". Cần biết vật băng qua 1 đoạn thẳng theo chiều nào.
- *Forces:* bắt đúng lượt qua ↔ không đếm nhầm khi vật đi DỌC vạch / đứng yên trên vạch.

**Vấn đề 3 — detector quá tải:** camera nhìn cảnh TĨNH phần lớn thời gian (bãi xe đêm) → chạy detector mỗi khung
= phí GPU. Nhưng bỏ khung sai → sót vật.
- *Forces:* tiết kiệm tải ↔ không bỏ sót; đổi-sáng-đèn/mây ≠ chuyển-động-thật (đừng trigger oan).

> ✋ Đoán thử: làm sao "biết xe khung này là xe khung trước" mà KHÔNG cần model nặng? (đáp nhịp 3–4)

---

## Nhịp 3 — Khám phá NHIỀU hướng

**Tracking:** (a) so tâm gần nhất — rẻ nhưng lẫn khi đông; (b) **IoU-greedy** (độ chồng hộp) — rẻ, đủ tốt, xác
định; (c) Kalman/DeepSORT (ML) — chính xác cao, nặng + phức tạp. → v1 chọn **(b) IoU-greedy** (đủ + xác định +
test không cần GPU); (c) để sau qua **port `ITracker`** (thay impl không đụng stage).

**Qua vạch:** (a) so tâm ở 2 phía vạch mỗi khung — cần định nghĩa "phía"; (b) kiểm 2 đoạn thẳng (đường-đi-tâm
giữa 2 khung) có CẮT vạch — chuẩn hình học. → chọn **(b)** + dùng **orientation (cross-product)** cho cả "cắt"
lẫn "hướng".

**Motion-gate:** (a) chạy detector luôn — phí; (b) so 2 khung, đo tỉ lệ pixel đổi, dưới ngưỡng → skip. → chọn
(b) + xử 2 bẫy: uint8 underflow (cast int16) + đổi-sáng-đều (mean-subtraction) + chỉ đo trong ROI.

---

## Nhịp 4 — CHỐT giải pháp + tại sao thắng

- **Tracking = IoU-greedy** (`domain.greedy_associate` thuần + `runtime.IouTracker` giữ state) qua port `ITracker`.
  Thắng: rẻ/xác định/test-được + thay ML sau không đụng `TrackingStage`. `track_id` **đơn điệu, không tái dùng**
  → `unique_count` = đếm-không-trùng.
- **Đếm qua vạch = orientation** (`domain.orient`/`segments_intersect`): tâm khung-trước↔khung-này cắt vạch → +1;
  **dấu orient** cho HƯỚNG (in/out). 1 nguồn `direction` cho cả đếm lẫn `CrossingEvent` (không lệch).
- **Motion-gate = changed_ratio** (`domain.motion`): int16-cast (chống underflow) + ROI-mask + illumination-robust;
  `max_consecutive_skip` ép chạy định kỳ (chống bỏ sót khi tĩnh lâu).
- **Tách tầng:** toán THUẦN @domain (không state, không kernel) · state @runtime (`IouTracker`) · DTO @kernel
  (`Track`/`CrossingEvent`). Vì sao domain index-based (không import `Detection`): domain là tầng THẤP NHẤT,
  cấm import kernel → nhận boxes/labels rời, trả cặp index (giống `nms_indices`); runtime ghép index↔track_id.

---

## Nhịp 5 — Dạy TRIỂN KHAI (qua các mẩu nhỏ nhất)
Xem `00-muc-luc.md`: domain (greedy_associate/orient/segments_intersect/changed_ratio/roi) → runtime
(IouTracker/TrackingStage/LineCrossingStage/MotionGateStage) → kernel DTO (Track/CrossingEvent) → wiring thứ-tự-stage + artifacts fan-out.

---

## Nhịp 6 — NÊN LÀM / NÊN TRÁNH
**Nên:** tie-break XÁC ĐỊNH (sort `(-iou, ni, pi)`) → test lặp-lại-được · `track_id` đơn điệu không tái dùng ·
1 nguồn `direction` · int16-cast trước khi trừ uint8 · camera-affinity (1 tracker/1 camera) · bounded-memory
(prune track vắng).
**Tránh:** state chia sẻ giữa camera (đếm loạn) · uint8-uint8 trực tiếp (underflow nuốt chuyển động) · coi đi-DỌC-vạch
là qua-vạch (collinear=False) · tính mean toàn-frame trước khi thu ROI (đổi-sáng ngoài ROI tạo chuyển động giả).

## Tự kiểm (retrieval)
1. Vì sao `domain/tracking.py` trả INDEX chứ không `Detection`? (ranh giới tầng)
2. `track_id` đơn điệu-không-tái-dùng phục vụ gì?
3. Vì sao phải cast `int16` trước khi trừ 2 frame uint8?
4. `orient` (cross-product) dùng cho 2 việc gì trong line-crossing?

**Mốc ôn:** 1 ngày / 1 tuần / 1 tháng. **Nguồn:** 10 file code trên · D (object-tracking/line-crossing/motion-gate) · `docs/ARCHITECTURE.md` §5.
