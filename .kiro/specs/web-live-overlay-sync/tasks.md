# Implementation Plan — Web Live Overlay Freshness and Stability

> Dẫn xuất từ `design.md` V3 + `requirements.md`. **TDD nghiêm ngặt:** mỗi task viết test (fake clock, tiêm event — KHÔNG sleep cứng) TRƯỚC, rồi code tới GREEN, rồi `scripts\vp.cmd verify` giữ baseline (654/2) không vỡ.
> **Nguyên tắc layer (import-linter):** DTO frozen → `kernel`; matching/EMA thuần → `domain`; store/stabilizer/scheduler/health → `runtime`; `/overlay` wiring + threads + browser → `profiles`. Display DTO KHÔNG được import/thoả analytics input port (Property 10, cưỡng chế bằng contract).
> **Cổng đo (Task 0):** chỉ diagnostic behind-flag, KHÔNG đổi behavior; policy default (lease/ghostSla) chỉ chốt khi có cadence p50/p95/p99 đo thật (design §Diagnostic measurement task).

## Overview
Kế hoạch triển khai fix gốc bbox flicker: tách raw inference truth ⊥ display projection, authority serialized (`OverlayStateStore`), epoch/lease/frame-identity, endpoint `/overlay` additive (giữ `/boxes` legacy). Thi công theo waves TDD — leaf/pure trước (DTO + matching/EMA), rồi stabilizer, rồi authority store + scheduler, rồi health/reconnect, rồi endpoint + video-independence, rồi browser + legacy, cuối là verify tổng + webcam E2E. Task 0 (diagnostic) song song, chỉ đo cadence để chốt policy default, KHÔNG đổi behavior.

## Task Dependency Graph
```json
{
  "waves": [
    { "wave": 0, "tasks": ["0"], "depends_on": [] },
    { "wave": 1, "tasks": ["1", "2"], "depends_on": [] },
    { "wave": 2, "tasks": ["3"], "depends_on": ["1", "2"] },
    { "wave": 3, "tasks": ["4", "5"], "depends_on": ["1", "3"] },
    { "wave": 4, "tasks": ["6", "7"], "depends_on": ["4"] },
    { "wave": 5, "tasks": ["8", "9"], "depends_on": ["4", "6"] },
    { "wave": 6, "tasks": ["10", "11"], "depends_on": ["8"] },
    { "wave": 7, "tasks": ["12"], "depends_on": ["10", "11", "9", "5", "7"] }
  ]
}
```
Ghi chú graph: Task 5 phụ thuộc 4; Task 8 phụ thuộc 4+6; Task 9 phụ thuộc 4; Task 11 độc lập (legacy). Task 12 là gate cuối gom mọi nhánh.

## Tasks

- [ ] 0. Diagnostic instrumentation behind flag (đo cadence — KHÔNG đổi behavior)
  - Thêm cờ `--overlay-trace` (mặc định tắt) ghi trace monotonic durations/states/counts/epochs/revisions + bounded reason enums; KHÔNG ảnh/coords/labels/URL/credential. File tạm local, xóa sau tổng hợp.
  - Thu ≥5 phút HOẶC ≥1000 unique inference completions (whichever later) + kịch bản forced detector delay / source reconnect / server stop.
  - Xuất cadence p50/p95/p99 → dùng chốt `candidateLeaseMs/displayLeaseMs/ghostSlaMs/clientSilenceCapMs` (nếu không có SLA → giữ explicit experimental config, KHÔNG tuyên bố "tối ưu").
  - _Requirements: (grounding cho 2.2, 3.2) · design §Diagnostic measurement task_

- [x] 1. DTO bất biến @kernel + config invariants fail-fast
  - `InputFrameSnapshot` (processEpoch/sourceEpoch/frameVersion/inputAcquiredNs/dims/buffer), `RawDetectionSnapshot` (input identity + start/end/publish ns + outcome DETECTED|EMPTY + immutable boxes), `HealthSnapshot` (source/detector enum), `NormalizedBox` (finite-clamped wire contract), `OverlayViewSnapshot` (immutable committed view) — đều frozen dataclass.
  - `OverlayConfig` + validate fail-fast: `0<iouThreshold<=1`, `0<emaAlpha<=1`, `minHits>=1`, `maxMisses>=0`, `reconnectMinMs<=reconnectMaxMs`, `candidateLeaseMs<=displayLeaseMs<=ghostSlaMs`, `clientSilenceCapMs<=ghostSlaMs`; impossible ghost-SLA-vs-cadence → `ConfigError`.
  - Test: mọi invariant boundary (đậu/rớt); frozen (immutability); no NaN/Inf/negative wire value.
  - _Requirements: 1.1 (snapshot immutable), 2.2 (lease fields) · design §Data Models, §Configuration invariants_

- [x] 2. Matching một-một + EMA THUẦN @domain
  - `match_one_to_one(prev_tracks, new_boxes, iou_threshold)`: cùng label, candidates `IoU>=threshold`, sort `(-IoU, oldDisplayId, newIndex)`, greedy claim; nhãn khác KHÔNG khớp. Trả kept pairs (index-based, KHÔNG import Detection — K-028).
  - `ema_step(prev, new, alpha)`: mỗi toạ độ smoothed ∈ [prev,new]; input hằng → không drift.
  - Test (pure, xác định): cùng input có thứ tự → output y hệt; khác-label không khớp; EMA bound + constant-no-drift.
  - _Requirements: 2.4 (Property 8), 2.5 (Property 9)_

- [x] 3. `DisplayStabilizer` — pure transition (hit-streak/miss/lease/trackRevision)
  - Nhận unique accepted result + TimerTick; mỗi confirmed track có `displayId="<sourceEpoch>:<counter>"`, `trackRevision`, lease deadline, missCount riêng.
  - Matched: missCount=0, EMA update, lease refresh, `trackRevision+=1` (kể cả coords bằng). Unmatched: missCount+=1, KHÔNG refresh lease; xóa khi `missCount>maxMisses` HOẶC TimerTick chạm lease. Candidate hitStreak: đủ `minHits` → promote; bất kỳ result unmatched → xóa candidate.
  - `EMPTY` = mọi track/candidate unmatched. Detector/source error KHÔNG gọi hit/miss, KHÔNG refresh lease. Discontinuity clear tất cả ngay.
  - Test (fake clock): exact miss (giữ ở miss thứ nhất, xóa ở maxMisses+1, match reset); per-track lease độc lập; promote sau minHits; deterministic displayId.
  - _Requirements: 2.2 (Property 5 server-side), 2.3 (Property 7) · design §Stabilizer exact semantics_

- [x] 4. `OverlayStateStore` — authority serialized check-and-commit
  - Một lock authority: `apply(event)` validate epochs/token/version → pure transition → tăng revisions → thay MỘT immutable `OverlayViewSnapshot`. Endpoint chỉ đọc snapshot đã commit (không mutate/lazy-expire).
  - Acceptance gate: completion nhận CHỈ khi epochs khớp + single-flight token hiện hành + `sourceFrameVersion` > last accepted; duplicate/old = no-op + bounded reason counter (KHÔNG tăng inference generation).
  - Epoch anti-rollback (server side) + revision đơn điệu.
  - Test (barrier race discontinuity↔completion): check-and-commit atomic; concurrent read chỉ thấy committed snapshot; poll idempotence (revision lặp → state không đổi).
  - _Requirements: 1.1 (Property 1), 1.2 (Property 2 server), 1.3 (Property 3), 2.1 (Property 4)_

- [x] 5. `OverlayExpiryScheduler` — TimerTick exactly-once
  - Phát `TimerTick(nowNs)` tại next deadline qua cùng `apply`; tick lặp qua cùng deadline → no-op (không tăng revision). Clock/wait tiêm được.
  - Test (fake clock): nhiều tick qua cùng deadline → hiệu ứng state exactly-once; KHÔNG đọc HTTP nào mutate state.
  - _Requirements: 2.6 (Property 13)_

- [x] 6. Health hai chiều + trung thực lỗi
  - source `INITIALIZING|LIVE|RECONNECTING|STALE|STOPPED|ERROR`; detector `INITIALIZING|LIVE|STALE|ERROR|STOPPED`. Detector hung phát hiện qua TimerTick (in-flight start/last completion deadline). Source STALE theo read-success cadence.
  - Raw `EMPTY` = valid (tăng generation + 1 miss event); detector ERROR/STALE KHÔNG bịa empty + KHÔNG refresh; init/null trước first result.
  - Test: 4 trạng thái (init/empty/source-degrade/detector-degrade) phân biệt được; lỗi không refresh display.
  - _Requirements: 3.1 (Property 6)_

- [x] 7. Reconnect pacing + source discontinuity (epoch tăng đúng một lần)
  - Tại `LIVE→discontinuity` lần đầu: state store tăng `sourceEpoch` + clear ĐÚNG MỘT LẦN trước retry; retry/reopen/success thuộc epoch mới, KHÔNG tăng thêm. Consumer sleep `clamp(retry_after_ms, reconnectMinMs, reconnectMaxMs)` (wait/clock tiêm được); missing/invalid → configured minimum; success reset backoff; KHÔNG busy-loop/zero.
  - Test (fake clock): discontinuity tăng epoch/clear đúng-một-lần; mỗi attempt obey clamp; success không tăng epoch lần hai.
  - _Requirements: 3.2 (Property 11) · design §Reconnect pacing_

- [x] 8. Endpoint `/overlay` (pure projection) + cưỡng chế cô lập analytics
  - `GET /overlay`: HTTP 200 `application/json` `Cache-Control: no-store,no-cache,must-revalidate`; body = pure projection của một committed snapshot + một `serializedAtNs` (tính ages/remaining lease từ 2 input đó, KHÔNG mutate). Trước first result: `rawResult=null`, health INITIALIZING, display rỗng lease 0. Transport failure (timeout/500/malformed) KHÔNG hứa application shape.
  - Import-linter contract MỚI: display DTO/module KHÔNG import analytics input port; toggle stabilizer để raw byte-equivalent (test).
  - Test: shape ổn định (nullable, không fake generation 0); no-store headers; finite box validation (clip/reject non-finite/zero-area + bounded reason counter + sort displayId); analytics isolation.
  - _Requirements: 1.1 (Property 1 wire), 4.1 (Property 10)_

- [ ] 9. Video independence + publication ownership
  - `_video_loop` atomically publish `(ownedFrame, sourceEpoch, frameVersion, inputAcquiredNs, jpeg)`; copy frame trước publish (hoặc ownership contract tương đương); detector KHÔNG giữ video-lock/overlay-state-lock trong preprocess/inference/postprocess.
  - Test (barrier): fake detector bị chặn → video/JPEG count VẪN tăng (video progresses).
  - _Requirements: 4.2 (Property 12) · design §Low-latency invariant_

- [ ] 10. Browser lease guard + canvas mapping (hàm THUẦN test được)
  - Tách logic JS thành hàm thuần: per-box lease (chỉ cập nhật deadline khi `trackRevision` của chính box tăng; same revision không gia hạn; absence → xóa; RTT-safe `max(0, remainingLeaseMs-RTT)` clamp `clientSilenceCapMs`); rollback (reject sourceEpoch<current; retiredProcessEpochs giữ toàn tab-session; unseen epoch → clear+accept); on-resume kiểm mọi lease trước first draw.
  - Canvas: backing size = CSS×DPR, `object-fit: contain`; ResizeObserver + image load/reconnect/resolution/aspect change cập nhật mapping TRƯỚC draw.
  - Test (fixture JS thuần): per-track lease độc lập; rollback; DPR transform.
  - _Requirements: 1.2 (Property 2 client), 2.2 (Property 5 client)_

- [ ] 11. Bảo toàn legacy `/boxes` (snapshot hành vi)
  - `GET /boxes` giữ `_legacy_boxes` riêng: detector success publish list mới (kể cả empty); detector exception/source reconnect giữ list trước — KHÔNG đổi status/content-type/cache headers. Overlay epochs/gates KHÔNG điều khiển legacy state.
  - Test: chuỗi success→empty→exception→reconnect, so body/status/content-type/header khớp hành vi trước-spec (snapshot).
  - _Requirements: 5.1 (Property 14)_

- [ ] 12. Verify tổng + webcam E2E (gate cuối)
  - Property tests interleaved (source/detector/tick, duplicate frame, retired epoch rollback, out-of-order completion, repeated poll, per-track lease, matching, EMA, finite expiry) + config boundary + concurrency (barrier atomic; concurrent GET committed-only; detector blocked video progresses).
  - `scripts\vp.cmd verify` PASS (không tăng timeout che K-035). Manual webcam E2E là gate cuối (không thay unit/property tests) — user xác nhận bbox ổn định trực quan.
  - _Requirements: 1.1–5.1 (toàn bộ) · design §Testing Strategy_

## Notes
- **TDD bắt buộc:** mỗi task viết test (fake clock, tiêm event/`git_facts`-style — KHÔNG sleep cứng) TRƯỚC → code tới GREEN → `scripts\vp.cmd verify` giữ baseline 654/2 không vỡ.
- **Không sửa behavior trước khi user valid design/requirements/tasks.** Task 0 diagnostic chỉ được chạy sau khi design duyệt; nó KHÔNG phải điều kiện hoàn tất design.
- **Policy default (lease/ghostSla) chờ số đo Task 0** (cadence p50/p95/p99). Không có SLA → giữ explicit experimental config, KHÔNG tuyên bố "tối ưu".
- **Giới hạn trung thực:** `<img>` MJPEG không cho JS biết frame đang hiển thị → V1 chỉ freshness/stability, KHÔNG pixel-perfect. WebRTC/WebSocket là follow-on CHỈ khi measured skew vượt SLA.
- **`HOLD_MS=500` hiện tại (worktree #377)** là mitigation sai tầng (K-100) — gỡ khi overlay mới thay thế, không giữ song song.
- **Layer/import-linter:** Task 8 thêm contract MỚI cấm display DTO import analytics input port (cưỡng chế Property 10, không nhắc miệng).
