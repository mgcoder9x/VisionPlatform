# Design Document — Web Live Overlay Freshness and Stability

> **Trạng thái:** PHA 1 — Design-first V2 sau adversarial review; chưa code.  
> **Nguồn:** user quan sát bbox nhấp nháy; static review `vision_web_app.py`; `vision-vertical-slice/design.md` chủ ý tách async-live thành sub-spec.  
> **Cập nhật:** 2026-07-14.

## Overview
Mục tiêu là overlay web live ổn định, có freshness đo được và hết hạn chắc chắn, trong khi video MJPEG tiếp tục drop-to-latest độc lập với inference chậm. Đây là **freshness/stability**, không phải pixel-perfect synchronization: `<img>` MJPEG không cho JavaScript biết multipart frame nào đang hiển thị.

Tính đúng được tách thành hai dòng:
- **Raw inference truth:** kết quả detector bất biến, dùng cho analytics nếu cần; không smoothing/hysteresis.
- **Display projection:** trạng thái chỉ để vẽ, có matching/EMA/hit-miss/lease; tuyệt đối không đi vào tracker, count hoặc event sink.

Success không có nghĩa box luôn hiện. Empty detection hợp lệ phải làm box hết hạn theo policy; source/detector lỗi phải có trạng thái riêng; không dữ liệu mới thì client phải tự clear theo lease hữu hạn.

### Scope and assumptions
- Flask app hiện là demo/nội bộ, chưa auth/TLS. Không được expose Internet; security hardening là spec khác.
- V1 giữ một detect thread và tối đa một inference in-flight. Thiết kế vẫn có publish gate để an toàn khi concurrency đổi sau.
- `/overlay` anti-resurrection applies fully. `/boxes` intentionally remains legacy best-effort and may expose the historical stale-race; web UI mới không dùng nó. This explicit scope is the compatibility cost, not a safety claim.
- Guarantee client chỉ áp dụng khi JS event loop chạy. Nếu tab bị browser freeze, phần mềm không thể repaint; ngay khi resume, render đầu tiên phải kiểm lease rồi clear trước draw.

### Static evidence verified from code
1. Video publish `_raw_ver`/JPEG; detect infer ngoài lock nhưng chỉ publish `_boxes`, làm mất identity của input frame.
2. `/boxes` thiếu epoch, revision, input version, timestamp và health.
3. `setInterval(async tick,80)` cho phép fetch overlap; payload không có sequence để loại kết quả cũ.
4. `HOLD_MS=500` làm mới `lastSeen` bằng cùng snapshot non-empty, nên có thể blink khi empty-run và giữ ghost khi producer đứng.
5. `_video_loop` bỏ qua `retry_after_ms` lúc `RECONNECTING`, có đường busy-spin.
6. Lock hiện tại ngăn torn assignment; lỗi là semantic freshness/order, chưa có bằng chứng thiếu mutex.

## Architecture
```text
Frame source -> VideoPublisher -----> MJPEG latest frame --------------------> <img>
                    | owned InputFrameSnapshot
                    v
              single-flight Detector -> RawDetectionSnapshot
                                             |
                                             v
                               DisplayStabilizer (server, pure/event-driven)
                                             |
                                             v
                            OverlayView endpoint ----lease----> Browser canvas
```

### Authority, epochs, and atomic state store
- `processEpoch`: UUID 128-bit mới mỗi process start. Client giữ tập epoch đã retired trong tab session; epoch đã retired không bao giờ được nhận lại.
- `sourceEpoch`: bắt đầu 1; tăng **đúng một lần tại transition LIVE→discontinuity đầu tiên**, trước khi publish `RECONNECTING/ERROR`. Các retry/reopen thuộc epoch mới đó, không tăng lần hai. Frame version reset về 0, frame đầu mới là 1.
- `eventRevision`: tăng cho mọi semantic state commit (raw result, source/detector transition, expiry/recovery).
- `inferenceGeneration`: tăng chỉ khi một inference completion unique được chấp nhận.

Mọi semantic mutation đi qua `OverlayStateStore.apply(event)` dưới **một lock authority**. Trong critical section duy nhất: validate epochs/token/version → chạy pure transition → tăng revisions → thay một immutable `OverlayViewSnapshot`. HTTP endpoint chỉ snapshot reference đã commit; không tự mutate/lazy-expire. Vì vậy không thể trả epoch mới ghép raw/display cũ hoặc để completion cũ chen giữa gate-check và clear.

`OverlayExpiryScheduler` phát `TimerTick(nowNs)` tại next deadline qua cùng `apply`; tick lặp không đổi state thì không tăng revision. Clock/wait tiêm được. Source/detector threads không sở hữu state, chỉ gửi event; lock không bao quanh I/O/inference.

### Publication and ownership
`_video_loop` atomically publishes `(ownedFrame, sourceEpoch, frameVersion, inputAcquiredNs, jpeg)`. `inputAcquiredNs` là thời điểm `read()` thành công trả về theo server monotonic clock, **không** phải camera-capture time và không phát hiện RTSP buffer cũ.

V1 copy frame trước publish (hoặc adapter phải có ownership contract tương đương); sau publish không bên nào mutate buffer. Detect thread snapshot toàn tuple dưới video lock, inference ngoài lock.

Completion chỉ được state store nhận nếu: epochs còn khớp; inference token là single-flight token hiện hành; và `sourceFrameVersion` **lớn hơn** last accepted version. Duplicate equality bị reject nên một frame không thể tự tích hit/miss hoặc refresh lease. Completion reject không tăng inference generation; counter reason bounded.

### Low-latency invariant
Detector không giữ video lock hoặc overlay-state lock trong preprocess/inference/postprocess. Video publisher phải tiếp tục tăng accepted-frame/JPEG count khi fake detector bị block. Locks chỉ bao snapshot/swap hoặc pure state transition; test dùng event/barrier, không sleep timing làm oracle.

## Components and Interfaces
### 1. InputFrameSnapshot
Owned immutable input: `processEpoch`, `sourceEpoch`, `frameVersion`, `inputAcquiredNs`, dimensions, frame buffer. `frameVersion` đơn điệu trong source epoch; không so sánh qua source epoch.

### 2. RawDetectionSnapshot
Một inference truth bất biến (tuple/frozen DTO + immutable boxes): input identity, inference start/end/publish monotonic timestamps, outcome `DETECTED | EMPTY`, raw boxes. Detector exception không tạo `EMPTY`.

### 3. HealthSnapshot
Hai state độc lập:
- source: `INITIALIZING | LIVE | RECONNECTING | STALE | STOPPED | ERROR`;
- detector: `INITIALIZING | LIVE | STALE | ERROR | STOPPED`.

Detector hung được TimerTick phát hiện từ in-flight start/last completion deadline. Source STALE dựa read-success cadence (không phải content freshness). Mọi state transition commit qua OverlayStateStore; endpoint không suy diễn/mutate.

### 4. DisplayStabilizer
Server-side pure transition owned by OverlayStateStore, một instance/source. Nó nhận unique accepted result, source discontinuity và TimerTick. Không import/call analytics. Mỗi confirmed track có `displayId`, `trackRevision`, lease deadline và miss count riêng.

### 5. BrowserLeaseGuard
Client render full authoritative `display.boxes`. Mỗi box có per-track revision/remaining lease; deadline chỉ cập nhật khi **trackRevision của chính box** tăng. Same track revision không gia hạn. Box vắng trong full list bị xóa.

Client chống rollback:
- cùng `processEpoch`: reject `sourceEpoch < current`; source epoch lớn hơn thì clear+accept;
- process epoch khác: reject nếu đã nằm trong `retiredProcessEpochs`; epoch chưa thấy thì retire current, clear, accept. Tập retired giữ **toàn bộ tab session** (số phần tử chỉ tăng khi server restart), không eviction;
- cùng epochs: reject `eventRevision < current`;
- request token + fetch timeout vẫn bắt callback cũ. UUID collision được coi là xác suất mật mã ngoài threat model.

### 6. OverlayStateStore and scheduler
Một authority cho check-and-commit; lưu immutable current view. `TimerTick` exactly-once về hiệu ứng (tick lặp chỉ no-op). Endpoint read-only. Config validation fail-fast trước start.

### 7. Legacy endpoint
`GET /boxes` tiếp tục đọc `_legacy_boxes` riêng: detector success publish list mới (kể cả empty); detector exception/source reconnect giữ list trước — đúng behavior hiện tại. Không đổi status, content type hoặc cache headers trong spec này. Overlay epochs/gates không được điều khiển legacy state.

## Data Models
### NormalizedBox wire contract
```text
{ displayId: string, trackRevision: int, remainingLeaseMs: int,
  label: string, confidence: finite float [0,1],
  x: finite float [0,1], y: finite float [0,1],
  width: finite float (0,1], height: finite float (0,1] }
```
Projection clips finite coordinates to image bounds, rejects non-finite/zero-area boxes, increments bounded reason counter, and sorts by `displayId`. `remainingLeaseMs` is integer floor-clamped to `[0, ghostSlaMs]`. Label is JSON/DOM text, never HTML.
### OverlayView API (additive)
`GET /overlay` successful application response: HTTP 200, `application/json`, `Cache-Control: no-store, no-cache, must-revalidate`.

```json
{
  "schemaVersion": 1,
  "processEpoch": "uuid",
  "sourceEpoch": 3,
  "eventRevision": 84,
  "health": {"source": "LIVE", "detector": "LIVE"},
  "rawResult": {
    "inferenceGeneration": 42,
    "sourceFrameVersion": 381,
    "outcome": "EMPTY",
    "sourceAgeMs": 117,
    "resultAgeMs": 12,
    "boxes": []
  },
  "display": {
    "revision": 51,
    "reason": "MISS_HELD",
    "boxes": [{
      "displayId": "3:7",
      "trackRevision": 9,
      "remainingLeaseMs": 180,
      "label": "person", "confidence": 0.88,
      "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.4
    }]
  }
}
```

Before first result, `rawResult` is `null`, health is `INITIALIZING`, display boxes empty and lease 0. Response shape remains stable via nullable field, not fake generation 0.

Age fields are a **pure response projection**: endpoint captures one immutable semantic snapshot reference and one `serializedAtNs`, then computes all ages/remaining leases from those two inputs without mutating state. The committed snapshot stores original timestamps/deadlines, not changing age values.
- `sourceAgeMs = now - rawResult.inputAcquiredNs`;
- `resultAgeMs = now - rawResult.publishedNs`;
- display lease is derived from **last matched accepted inference**, not poll time.

`latestVideoFrameVersion-sourceFrameVersion` may be returned only as diagnostic count, never as time/SLA. HTTP timeout/500/malformed JSON are transport failures and cannot promise the application shape; client lease still expires locally.

### Browser lease calculation
For each box whose `trackRevision` is newer than the local one:
1. measure request RTT with `performance.now()`;
2. `safeRemaining = max(0, box.remainingLeaseMs - RTT)`;
3. box deadline = now + `min(safeRemaining, clientSilenceCapMs)`.

Same `trackRevision` never changes that box deadline, even if global display revision changes because another object matched. Full-list absence removes the box. Fetch/server failure cannot refresh any deadline. On tab resume, all per-box leases are checked before first draw.

## Error Handling
### Distinct truth semantics
- Raw `EMPTY`: valid inference; advances inference generation and one miss event.
- Detector `ERROR/STALE`: does not fabricate empty and does not increase miss count. Last display may live only until existing lease; never refreshes.
- Source `RECONNECTING/STALE/ERROR`: tại transition `LIVE→discontinuity`, state store tăng `sourceEpoch` và clear display **đúng một lần trước retry**. Các retry, reopen attempts và successful reopen thuộc epoch mới, không tăng thêm; lease không được refresh.
- Process restart: new `processEpoch`; client resets revisions/deadlines/display immediately.

### Reconnect pacing
For `RECONNECTING`, consumer sleeps `clamp(retry_after_ms, reconnectMinMs, reconnectMaxMs)` using injectable wait/clock. Missing/invalid delay uses configured minimum; success resets backoff. V1 uses no jitter for local webcam; distributed RTSP jitter is follow-on. Policy values require config and tests; no unbounded or zero busy-loop.

### Stabilizer exact semantics
- Deterministic one-to-one matching per label: candidates with `IoU >= threshold`, sorted `(-IoU, oldDisplayId, newIndex)`, greedily claim unmatched pairs.
- Every accepted unique result processes every track exactly once. Matched confirmed track: `missCount=0`, EMA update, lease refresh, `trackRevision += 1` even if coordinates equal. Unmatched confirmed track: `missCount += 1`, no lease refresh; remove when `missCount > maxMisses` or TimerTick reaches lease.
- New box creates candidate with `hitStreak=1`; matched in next consecutive accepted result increments streak. Any result where candidate is unmatched removes it. At `hitStreak >= minHits`, allocate deterministic `displayId="<sourceEpoch>:<counter>"`, counter monotonic within epoch, and publish confirmed track.
- `EMPTY` means all existing tracks/candidates unmatched. A `DETECTED` result can match A while B independently misses.
- Detector/source errors do not invoke hit/miss and never refresh lease. Discontinuity clears all immediately before reconnect work.
- Candidate lease and confirmed lease are per-track. EMA alpha `(0,1]`; equal frame identity and equal-generation polls are ignored.

### Configuration invariants
All duration values are finite positive integers; `0 < iouThreshold <= 1`, `0 < emaAlpha <= 1`, `minHits >= 1`, `maxMisses >= 0`, `reconnectMinMs <= reconnectMaxMs`, `candidateLeaseMs <= displayLeaseMs <= ghostSlaMs`, and `clientSilenceCapMs <= ghostSlaMs`. If measured cadence requirement cannot fit under `ghostSlaMs`, stable mode fails initialization with `ConfigError` instead of silently violating one constraint. Millisecond wire values use floor+clamp; no NaN/Inf/negative accepted.
## Correctness Properties
### Property 1: Atomic view
Every successful `/overlay` response is a pure projection of exactly one immutable committed `OverlayViewSnapshot` plus one captured serialization timestamp; no mixed epochs/raw/display/health, and the projection never mutates committed state.
**Validates: Requirements 1.1**

### Property 2: Epoch anti-rollback
Within a process, lower source epoch is rejected; retired process epoch is rejected; unseen process epoch resets before draw.
**Validates: Requirements 1.2**

### Property 3: Unique monotonic acceptance
Within epochs, only strictly increasing source frame versions affect inference generation/stabilizer; duplicate/old completion is a no-op plus bounded reason counter.
**Validates: Requirements 1.3**

### Property 4: Poll idempotence
Repeated event/display/track revisions do not change server state or per-track client deadlines.
**Validates: Requirements 2.1**

### Property 5: Per-track bounded ghost
When event loop runs, each box expires by its own deadline unless that same track receives a newer matched track revision; matching another track cannot extend it.
**Validates: Requirements 2.2**

### Property 6: Failure truthfulness
Initialization, raw empty, source degradation and detector degradation/hang are distinguishable; failures never fabricate empty or refresh display.
**Validates: Requirements 3.1**

### Property 7: Exact miss semantics
With `maxMisses>=1`, one miss holds; miss `maxMisses+1` removes unless lease expires first; match resets miss count.
**Validates: Requirements 2.3**

### Property 8: Deterministic matching
One-to-one same-label matching and display-ID allocation produce identical output for identical ordered inputs; different labels never match.
**Validates: Requirements 2.4**

### Property 9: EMA bound
Every smoothed coordinate lies between previous/new values; constant input cannot drift.
**Validates: Requirements 2.5**

### Property 10: Analytics isolation
Raw snapshot is immutable; display DTO cannot satisfy/import the analytics input port; toggling stabilizer leaves raw sequence byte-equivalent.
**Validates: Requirements 4.1**

### Property 11: Reconnect pacing and invalidation
Discontinuity increments epoch/clears exactly once before retry; each attempt obeys clamp; success does not increment epoch again.
**Validates: Requirements 3.2**

### Property 12: Video independence
Barrier-blocked detector cannot prevent video/JPEG publication progress.
**Validates: Requirements 4.2**

### Property 13: Expiry scheduling
TimerTicks across the same deadline have exactly-once state effect; no HTTP read mutates state.
**Validates: Requirements 2.6**

### Property 14: Legacy compatibility
For success→empty→exception→reconnect sequences, `/boxes` body/status/content-type/header behavior matches pre-spec implementation.
**Validates: Requirements 5.1**

## Testing Strategy
- Pure tests với fake clock cho store/stabilizer/health/scheduler/lease guard/reconnect pacing; không sleep cứng.
- Property tests: interleaved source/detector/tick events, duplicate frame, retired epoch rollback, out-of-order completion, repeated poll, per-track lease independence, matching, EMA, finite expiry.
- API contract: initialization/null, raw empty, simultaneous degraded states, no-store `/overlay`, finite box validation. Legacy sequence tests snapshot behavior trước thay đổi (success→empty→exception→reconnect), không chỉ body shape.
- Concurrency: barrier-controlled race giữa discontinuity và completion chứng minh check-and-commit atomic; concurrent GET chỉ thấy committed snapshots; detector blocked nhưng video progresses.
- Config boundary tests: mọi invariant duration/policy, impossible ghost-SLA-vs-cadence phải fail-fast.
- Browser logic tách thành hàm thuần test được; ResizeObserver + DPR transform có test fixture. Canvas backing size = CSS size × DPR, drawing coordinates dùng CSS transform; image load/reconnect/resolution/aspect change cập nhật mapping trước draw. V1 dùng `object-fit: contain`, không crop.
- Manual webcam E2E là gate cuối, không thay unit/property tests.
- Full `vp verify`; không tăng timeout che K-035.

### Diagnostic measurement task (sau design/requirements, trước behavior fix)
Task 0 là **diagnostic-only instrumentation behind flag**, được phép sau khi design được duyệt; nó không phải điều kiện để hoàn tất design và không thay behavior. Thu tối thiểu 5 phút hoặc 1,000 unique inference completions (whichever later), cộng kịch bản forced detector delay, source reconnect và server stop.

Trace chỉ gồm monotonic durations, states, counts, epochs/revisions và bounded reason enums; không ảnh/box coordinates/labels/raw URL/credential. File local tạm, xóa sau tổng hợp. Frame/revision/request IDs là log fields, **không metric labels**. Metrics labels chỉ dùng enum bounded (`outcome`, `reason`, `sourceState`, `detectorState`).

Task 0 xác nhận trigger bằng correlation, không dùng frame delta như thời gian. Policy defaults chỉ chốt khi có cả:
- cadence p50/p95/p99 đo thật;
- product `ghostSlaMs` hữu hạn;
- công thức được ghi: lease không vượt ghost SLA và đủ phủ detector cadence mục tiêu.
Nếu không có SLA, không được tuyên bố default “tối ưu”; giữ explicit experimental config.

## Rollout, Boundaries, and Trade-offs
- Browser dùng additive `/overlay`; `/boxes` giữ nguyên vô thời hạn trong spec này. Consumer inventory/deprecation thuộc spec riêng.
- Feature flag cho display stabilizer; disable chỉ phục vụ chẩn đoán, sẽ quay lại raw flicker và không phải safety-equivalent rollback.
- V1 chọn client-overlay + server stabilizer: giữ video low-latency nhưng không pixel-perfect. Server-render JPEG bị bác vì coupling/encode; WebRTC/WebSocket là follow-on nếu measured visual skew vượt SLA.
- Source “progress” nghĩa là read-success cadence, không phát hiện frozen duplicate content hoặc RTSP camera capture age. Content-freeze detection là non-goal được ghi rõ.
- Không thay confidence threshold/detector/tracker để che flicker; không batch-mux; không auth/TLS/multi-user scaling.

### Privacy and operations
- Không log exception prose chưa sanitize vì có thể chứa URL credential; chỉ stable error type/reason enum, message redacted.
- Overlay metadata có occupancy implications; endpoint chỉ bind localhost/internal trusted network hiện tại. Không lưu trace dài hạn.
- On-call phải trả lời được: source/detector state, raw result age/outcome, display reason/remaining lease, rejected completion reason, reconnect cadence.

## Adversarial Review Reconciliation
- **Actionable đã sửa:** client-silence lease; ba age semantics; process/source epochs; event revision tách inference generation; health hai chiều; raw/display tách; initialization/null; cache/HTTP semantics; server-side stabilizer; immutable ownership; publish gate; exact matching/policy; reconnect clamp; diagnostic task không còn vòng tròn.
- **Valid trade-off chấp nhận:** MJPEG `<img>` không chứng minh frame đang hiển thị; V1 chỉ freshness/stability. Pixel-perfect cần transport khác.
- **Giới hạn vật lý:** tab frozen không repaint; guarantee áp dụng khi event loop chạy và clear-before-draw khi resume.
- **Không chấp nhận làm “noise”:** không finding sống-còn nào bị bỏ qua; các mục security/content-freeze/pixel-sync được hạ thành non-goal rõ, không overclaim.

## Definition of Done — Design Phase
Chỉ chuyển Requirements khi: exact required headings có diagnostics 0; fresh-context review V2 không còn Critical; raw/display/failure/epoch/lease contracts không mơ hồ; mọi guarantee có property testable; user đọc-lại-valid. Chưa tạo tasks và chưa sửa behavior sản phẩm ở pha này.
