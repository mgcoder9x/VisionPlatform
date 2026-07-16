# Design — Overlay/Tracking Architecture Refactor (fix "box không sát + tắt chậm" TẬN GỐC)

> **TRẠNG THÁI: DESIGN-FIRST, CHƯA CODE.** Chờ user đọc-lại-valid. Grounded trên code THẬT đã đọc (#412):
> `runtime/display_stabilizer.py`, `runtime/overlay_projection.py`, `domain/display_smoothing.py`,
> `domain/tracking.py`, browser JS trong `profiles/vision_web_app.py::_PAGE`.

## Overview
User nhìn thấy 2 lỗi VISUAL trên video thật (#411): **S1 — bbox KHÔNG SÁT người** (trễ/lệch/giật khi di chuyển); **S2 — bbox TẮT CHẬM** khi người đã đi qua (ghost). Đã vá 4 lần ở `DisplayStabilizer` (hysteresis/evict/predict-match/conf) mà chưa dứt → cần xem lại KIẾN TRÚC tận gốc, thiết kế rõ để (a) hết 2 lỗi, (b) làm NỀN cho nghiệp vụ (đếm/vạch/zone/tốc-độ). Doc này = review + đề xuất kiến trúc, CHƯA code.

## Architecture

### Gốc rễ 2 triệu chứng (từ CODE THẬT, không đoán)
**S1 "không sát" = 3 nguồn cộng dồn:**
1. Trễ detect CPU: mỗi `session.run` ~111ms (K-102) + ~5–12/s → vị trí mới nhất luôn cũ ~100–200ms.
2. EMA server (alpha 0.5, `ema_box`): box = trung bình động old↔new → CỐ Ý trễ để bớt giật → tụt sau người di chuyển.
3. **CLIENT vẽ TĨNH (sample-and-hold) — GỐC LỚN NHẤT:** `_PAGE` `tick()` vẽ box tại vị trí BÁO CUỐI (`b.x*cv.width`), poll 80ms, **KHÔNG ngoại suy theo vận tốc**; `project_overlay` KHÔNG gửi vận tốc → client không có gì để ngoại suy → box đứng chỗ cũ + nhảy khi có detect mới.

**S2 "tắt chậm" = 2 nguồn:**
1. Xoá theo ĐỒNG HỒ mù (`displayLeaseMs=600` + `maxMisses`): giữ box tới hết lease sau khớp cuối; người rời không-qua-mép (bị che/detect ngừng) → nán tới 600ms.
2. `evictPredictedOffFrame` (D-124) chỉ bắt rời-qua-MÉP, không bắt "detect ngừng giữa khung".

### Chẩn đoán kiến trúc (vì sao vá không dứt)
`DisplayStabilizer` GỘP 3 mối quan tâm: **tracking** (ID + motion), **display smoothing** (EMA/lease/render), **vòng đời** (born/confirmed/lost). Thêm: **2 tracker song song PHÂN KỲ** — `domain.tracking.greedy_associate`+`runtime/iou_tracker` (analytics đếm/vạch) VÀ `DisplayStabilizer` (display). Nghiệp vụ tương lai cần track ổn định = CÙNG thứ display cần → xây trên tracker-display ad-hoc = drift + 2 nguồn sự thật. Và smoothness là việc CLIENT nhưng client đang câm.

### Kiến trúc đề xuất (RÕ, làm nền nghiệp vụ) — layering 6-tầng
`domain/tracker` (THUẦN: motion + association + lifecycle) → `runtime` (wire + projection gửi vận tốc) → **consumers**: `analytics` (nghiệp vụ đếm/zone) + `overlay` (client render mượt). Tách **tracking (domain, dùng chung) ⊥ display (client ngoại suy)**. 1 nguồn track duy nhất (đóng phân kỳ 2-tracker).

## Components and Interfaces
- **C1 `domain` Tracker (nguồn track duy nhất):** motion model mỗi track (v1 vận tốc tuyến tính; v2 Kalman); association IoU+dự-đoán (v2 center-distance/size-aware/Hungarian); lifecycle `tentative→confirmed→lost` theo `time_since_update` (THỜI GIAN). Thuần, fake-clock test. Dùng chung analytics + display.
- **C2 `runtime/overlay_projection`:** thêm `vx,vy` (chuẩn-hoá/giây) + `updatedAtMs` mỗi track → client ngoại suy.
- **C3 client render bù chuyển động (fix S1):** `requestAnimationFrame` vẽ tại `pos + vel*(now-updatedAt)` → bám sát mượt giữa detect thưa; giảm/bỏ EMA server (mượt chuyển sang client).
- **C4 removal evidence-based (fix S2):** ~~"lost" khi `time_since_update > maxAgeMs`~~ **[REVISED #417/D-129]** — verify code: `lease_deadline = last_match + displayLeaseMs` (refresh mỗi khớp) → `displayLeaseMs` ĐÃ LÀ time-since-update timeout; `maxAgeMs` riêng = TRÙNG → BỎ. Fix S2 = **giảm `displayLeaseMs`** (expose CLI) + off-frame-evict (D-124). Đã verify lease 350 giữ box 25/25 không flicker (empiric).

## Data Models
- **Track (domain):** `{id:int, box:BBox, vx:float, vy:float, age:int, hits:int, time_since_update:int, label:str, conf:float, state:tentative|confirmed|lost}`.
- **Overlay track JSON (thêm):** `vx, vy, updatedAtMs` cạnh `x,y,width,height,displayId,label,confidence`.
- Không đổi raw truth (Property 10 giữ). Config mới: `maxAgeMs` (removal), cờ `clientExtrapolate`.

## Correctness Properties
- **P1 (client render):** box vẽ = clamp(pos+vel*dt, khung); vel=0 → đứng yên (không drift).
- **P2 (removal):** track không update quá `maxAgeMs` → biến mất ≤ maxAgeMs (độc lập lease dài).
- **P3 (additive):** cờ tắt → hành vi hiện tại; baseline test giữ.
- **P4 (1-nguồn-track):** analytics + display đọc cùng tracker (Wave C) → ID nhất quán.
- **P5 (motion clamp, đóng bug #410):** mọi vị trí dự đoán clamp [0,1] trước khi dựng BBox.

## Error Handling
- Vị trí dự đoán ra ngoài [0,1] → clamp (đã fix #411, giữ nguyên tắc).
- Vận tốc thiếu (track mới, <2 update) → vel=0 (vẽ tĩnh, không ngoại suy sai).
- Client mất kết nối/epoch đổi → giữ cơ chế epoch-rollback hiện có (`web-live-overlay-sync`).

## Testing Strategy
- **Wave A (client, thắng nhanh S1):** unit projection gửi vx/vy đúng; browser MCP đo "box sát" (so vị trí box vẽ ↔ raw detection theo thời gian). Rủi ro thấp (không đụng domain).
- **Wave B (removal S2):** unit `time_since_update>maxAgeMs → lost`; browser đo box tắt nhanh khi người rời.
- **Wave C (hợp nhất tracker):** domain Tracker TDD (fake clock: motion/association/lifecycle); analytics + display cùng đọc → ID nhất quán; giữ `web-live-overlay-sync` + `object-tracking-count` xanh. Refactor lớn → từng bước.
- **Wave D (nghiệp vụ):** đếm/zone/tốc-độ trên tracker chung.
- Regression: `scripts\vp.cmd verify` giữ xanh mỗi wave; browser MCP verify visual (không chỉ metric ID — K-111: đo box-continuity, không đếm ID).

## Câu hỏi cần user VALID (trước khi code)
1. Đồng ý tách **tracking (domain, dùng chung) ⊥ display (client render mượt)**?
2. Ưu tiên **Wave A (client ngoại suy vận tốc)** trước — thắng nhanh "box sát", rủi ro thấp?
3. **Wave C hợp nhất tracker** (đụng analytics) làm ngay hay để khi nghiệp vụ cần?
4. Chấp nhận **giảm/bỏ EMA server**, chuyển mượt sang client?
