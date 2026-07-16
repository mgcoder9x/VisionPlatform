# Implementation Plan — Overlay/Tracking Architecture Refactor

> Dẫn xuất từ `design.md` (D-126) + `requirements.md`. **TDD nghiêm ngặt:** test (fake clock/tiêm) TRƯỚC → GREEN → `scripts\vp.cmd verify` giữ baseline xanh. Verify visual = **browser MCP với nguồn SYNTHETIC (moving-square)** — máy no-GPU/không cần webcam/RTSP/model.
> **Layer:** motion/association/lifecycle + extrapolation math THUẦN → `domain`; projection (thêm vx/vy/updatedAtMs) + removal → `runtime`; client rAF + cờ → `profiles`. KHÔNG để display DTO import analytics (Property 10 giữ).
> **GATE Wave C:** hợp nhất tracker ĐỤNG analytics → chỉ làm khi user duyệt RÕ (R3.3).

## Overview
Fix S1 (box không sát) + S2 (tắt chậm) tận gốc + đặt nền 1-nguồn-track cho nghiệp vụ. Thi công theo waves: A (client ngoại suy vận tốc — thắng nhanh S1, rủi ro thấp, chỉ display) → B (removal evidence-based — S2) → C (hợp nhất `domain/tracker`, GATED vì đụng analytics) → D (nghiệp vụ trên tracker chung). Mọi cờ mới mặc định TẮT (additive).

## Task Dependency Graph
```json
{
  "waves": [
    { "wave": 0, "tasks": ["1", "2"], "depends_on": [] },
    { "wave": 1, "tasks": ["3"], "depends_on": ["1"] },
    { "wave": 2, "tasks": ["4", "5"], "depends_on": ["1", "3"] },
    { "wave": 3, "tasks": ["6"], "depends_on": ["5"] }
  ]
}
```
Ghi chú: Wave 0 = Wave A (Task 1 server velocity + Task 2 client extrapolation). Wave 1 = Wave B (Task 3 removal). Wave 2 = Wave C GATED (Task 4 domain tracker + Task 5 hợp nhất — chờ user duyệt). Wave 3 = Wave D nghiệp vụ (tương lai).

## Tasks

- [x] 1. Server: phơi vận tốc track ra `/overlay` (vx/vy) — Wave A, TDD ✅ (#416/D-128; updatedAtMs BỎ — clock server≠client, client dùng thời-điểm-nhận)
  - Bảo đảm `DisplayTrack` (hoặc snapshot track) mang vận tốc tâm (tái dùng motion model D-124/`_predict_box` đã có — KHÔNG tính lại) + mốc update. `project_overlay` thêm `vx`, `vy` (chuẩn-hoá/giây), `updatedAtMs` cho mỗi display box; track <2 update → `vx=vy=0`.
  - Giữ nguyên trường cũ (tương thích ngược) + KHÔNG đụng raw truth (Property 10).
  - Test (thuần): track có vận tốc → projection trả vx/vy đúng dấu/độ lớn; track mới → 0; clip [0,1] giữ.
  - _Requirements: 1.1, 4.2, 5.1_

- [x] 2. Client: render bù chuyển động (requestAnimationFrame ngoại suy) — Wave A ✅ (#415/D-127: poll self-reschedule ⊥ render rAF + ngoại suy pos+vel*dt; đóng pile-up ERR_INSUFFICIENT_RESOURCES)
  - Cờ `--overlay-extrapolate` (mặc định TẮT = hành vi hiện tại). Bật → tách hàm thuần `extrapolate(pos, vel, dt)` = `clamp(pos+vel*dt, [0,1])`; vòng vẽ dùng `requestAnimationFrame` vẽ tại vị trí ngoại suy theo `now-updatedAtMs`; `vel=0` → tĩnh.
  - Verify: browser MCP với **nguồn synthetic moving-square** (`vision_web_app` không `--video/--camera/--rtsp` → `moving_square_frame` + BrightBlobDetector) → so box vẽ có bám sát ô vuông di chuyển mượt hơn (không giật giữa poll) so cờ tắt.
  - _Requirements: 1.2, 1.3, 4.1_

- [x] 3. Removal evidence-based — Wave B ✅ (#417/D-129, REVISED: KHÔNG thêm maxAgeMs)
  - **PHÁT HIỆN (valid code #417):** `lease_deadline = last_match + displayLeaseMs` (refresh mỗi khớp) + xoá khi `<= now` → `displayLeaseMs` ĐÃ CHÍNH LÀ "time_since_update" timeout. `maxAgeMs` riêng = TRÙNG cơ chế → KHÔNG thêm (chống phức tạp vô ích, R3.2).
  - **S2 fix = tune `displayLeaseMs`** (expose CLI `--overlay-display-lease-ms`, +`--overlay-candidate-lease-ms` giữ ordering) + off-frame-evict (D-124 đã có). Verify webcam browser: lease 350 → box present 25/25 (KHÔNG flicker, detect gap<350 bắc cầu) · max_rem 335<350 (chứng minh lease=timeout) · 0 lỗi. Removal khi rời = last_match+350 (nhanh hơn 600).
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 4. (GATED) `domain/tracker` — nguồn track duy nhất (motion+association+lifecycle) — Wave C, TDD
  - CHỜ USER DUYỆT RÕ (R3.3). Tracker thuần: motion model (v1 vận tốc tuyến tính), association (IoU+dự-đoán; v2 center-distance/size-aware/Hungarian), lifecycle `tentative→confirmed→lost` theo thời gian. Fake-clock test.
  - _Requirements: 3.1_

- [ ] 5. (GATED) Hợp nhất: analytics + display đọc CÙNG `domain/tracker` — Wave C
  - CHỜ USER DUYỆT. Chuyển `iou_tracker` (analytics) + `DisplayStabilizer` (display) sang dùng chung tracker → ID nhất quán. Refactor lớn, từng bước; giữ `web-live-overlay-sync` + `object-tracking-count` XANH.
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 6. (TƯƠNG LAI) Nghiệp vụ trên tracker chung — Wave D
  - Đếm/zone/tốc-độ dùng track ổn định từ tracker chung. Ngoài phạm vi spec này (đặt chỗ).
  - _Requirements: (nền cho nghiệp vụ)_

- [ ] 7. Verify gate mỗi wave
  - `scripts\vp.cmd verify` XANH sau mỗi task (không tăng timeout che K-035). Browser MCP verify VISUAL (box-continuity, KHÔNG đếm ID — K-111) trên nguồn synthetic; RTSP/video thật khi có để đo per-object.
  - _Requirements: 1.1–5.1 (regression)_

## Notes
- **TDD bắt buộc:** test TRƯỚC → GREEN → vp verify giữ baseline.
- **Additive:** mọi cờ mới mặc định TẮT = hành vi hiện tại (R4.1). Không đổi raw truth (Property 10).
- **Wave A trước** (client ngoại suy) = thắng nhanh S1, rủi ro thấp (chỉ display, không đụng domain/analytics).
- **Wave C GATED:** hợp nhất tracker đụng analytics → chỉ khi user duyệt rõ; trước đó chỉ Wave A/B.
- **Verify no-GPU:** browser MCP + nguồn synthetic moving-square (không cần webcam/RTSP/model/GPU). Video/RTSP thật khi có để đo per-object churn/ghost.
- **K-111:** đo VISUAL = box-continuity (box bám người liên tục), KHÔNG đếm displayId.
- **Bug clamp #410/#411 (K-111):** mọi vị trí dự đoán clamp [0,1] trước khi dựng BBox/vẽ (P5).
