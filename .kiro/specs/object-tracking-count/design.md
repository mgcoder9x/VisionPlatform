# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · đóng Lỗ 3 (K-042) · mở rộng `vision-vertical-slice` (thêm 1 analytics
> Stage stateful bên cạnh CountStage stateless).
> **Cập nhật lúc:** 2026-07-09.

## Overview

Thêm analytics **stateful đầu tiên**: theo dõi vật xuyên frame (gán track_id ổn định) + đếm KHÔNG TRÙNG. Chuỗi
pipeline mở rộng (additive):

```
source → DetectStage → [CountStage (stateless, giữ nguyên)]
                     → TrackingStage (STATEFUL, MỚI) → sink
```

`TrackingStage` đọc `artifacts["detections"]` (do `DetectStage` ghi — CÙNG nguồn với CountStage, fan-out R3.1) →
gọi `ITracker.update(detections)` → ghi `artifacts["tracks"]` + `artifacts["unique_count"]` + `artifacts["active_count"]`.

**Vì sao gốc, không ngọn:** trạng thái là bản chất của tracking — không thể "đếm không trùng" mà không nhớ vật đã
thấy. Ta không né trạng thái (như v1 slice cố tình stateless) mà **đóng gói trạng thái đúng chỗ** (trong tracker
impl) + **ràng buộc camera-affinity** (1 instance/1 camera) để state không rò giữa camera — đúng cảnh báo K-042.

**Nền đã đọc code thật (chống bịa — trích chính xác):**
- `Detection(label:str, confidence:float, box:BBox)` — `kernel/inference_protocol.py` (frozen).
- `BBox(x,y,w,h:float, space:CoordinateSpace)` có `.x2/.y2/.area`; `domain/nms.py::iou(a,b:BBox)->float`
  (fail-fast nếu khác space) ĐÃ TỒN TẠI → **tái dùng** cho association.
- `BaseStage(name)`: override `_do_process(packet)->MediaPacket` (raise→ERROR, trả sai kiểu→ERROR); `setup/teardown`
  overridable; instance CÓ THỂ giữ field trạng thái (BaseStage không cấm).
- `MediaPacket`: `.artifacts.get(k)`, `.with_artifact(k,v)` (CoW, trả packet mới), `.source_id:str`.
- `ISink` Protocol (`kernel/ports/sink.py`) — sink hiện có xử `artifacts` tuỳ ý; tracking chỉ thêm key artifacts.

## Architecture

```
   domain/tracking.py           : greedy_associate(prev_boxes, new_boxes, iou_thr) -> list[(new_i, prev_i)]
      (THUẦN hình học, INDEX-BASED — KHÔNG import Detection@kernel; cùng triết lý nms_indices)
                    ▲ dùng
   kernel/tracking_protocol.py  : Track(track_id,label,box,age,hits) [frozen DTO]
   kernel/ports/tracker.py      : ITracker Protocol — update(dets)->tuple[Track,...] · reset() · properties
                    ▲ impl
   runtime/iou_tracker.py       : IouTracker(ITracker) — GIỮ STATE (_tracks, _next_id), dùng domain.greedy_associate
                    ▲ DI (port)
   runtime/stages/tracking_stage.py : TrackingStage(BaseStage) — đọc detections → tracker.update → ghi artifacts
```

**Layer (không phá import-linter 5 contract):**
- `domain/tracking.py` — THUẦN (BBox + số), index-based, KHÔNG import kernel. (giống `domain/nms.py`.)
- `kernel/tracking_protocol.py::Track` + `kernel/ports/tracker.py::ITracker` — DTO + port (kernel được phụ thuộc domain: dùng BBox).
- `runtime/iou_tracker.py` + `runtime/stages/tracking_stage.py` — impl + stage (runtime→kernel/domain OK).
Không đụng adapters/application/profiles lõi. (profile slice CÓ THỂ thêm tuỳ chọn `--track` sau — ngoài phạm vi lõi v1.)

## Components and Interfaces

### C1 — `domain/tracking.py::greedy_associate` (thuần hình học, index-based)
```
def greedy_associate(
    prev_boxes: Sequence[BBox], new_boxes: Sequence[BBox],
    iou_threshold: float, *, prev_labels=None, new_labels=None,
) -> list[tuple[int, int]]:
    # trả list (new_idx, prev_idx) đã ghép; greedy theo IoU giảm dần, cùng label (nếu cấp labels),
    # mỗi prev/new dùng tối đa 1 lần, chỉ ghép khi iou >= threshold. Tie-break: (‑iou, new_idx, prev_idx) ổn định.
```
- KHÔNG import `Detection` (domain là tầng thấp nhất) — nhận `BBox` + `labels:list[str]` rời (giống nms_indices nhận boxes/scores/labels rời).
- Xác định tuyệt đối: tính mọi cặp (i,j) cùng label có iou≥thr → sort theo `(-iou, new_idx, prev_idx)` → duyệt gán nếu cả 2 chưa dùng. (Tie-break bằng index → không phụ thuộc thứ tự vòng lặp.)

### C2 — `kernel/tracking_protocol.py::Track` (frozen DTO)
```
@dataclass(frozen=True)
class Track:
    track_id: int
    label: str
    box: BBox        # box MỚI NHẤT (space giữ nguyên từ detection — thường ORIGINAL_FRAME qua DetectorPipeline)
    age: int         # số frame LIÊN TIẾP chưa được khớp (0 khi vừa khớp)
    hits: int        # tổng số frame track này được khớp (>=1)
```
Lý do ở kernel: DTO thuần, downstream (sink/event) đọc — đối xứng `Detection`. Được import BBox (kernel↠domain OK).

### C3 — `kernel/ports/tracker.py::ITracker` (Protocol)
```
@runtime_checkable
class ITracker(Protocol):
    def update(self, detections: Sequence[Detection]) -> tuple[Track, ...]: ...  # 1 frame → tracks (đã gán id)
    def reset(self) -> None: ...          # xoá toàn bộ state (đổi camera / khởi động lại)
    @property
    def unique_count(self) -> int: ...    # tổng track_id đã tạo (đơn điệu)
    @property
    def active_count(self) -> int: ...    # số track đang sống
```
Vì sao PORT (không YAGNI): roadmap R3.3 nêu rõ `ITracker`; cho phép thay `IouTracker` bằng ML tracker (Kalman/
DeepSORT) sau mà KHÔNG đụng `TrackingStage`. Cùng pattern DI-port như `IDetector`.

### C4 — `runtime/iou_tracker.py::IouTracker(ITracker)` (GIỮ STATE)
- `__init__(self, *, iou_threshold: float = 0.3, max_age: int = 30)`.
- State nội bộ: `self._tracks: dict[int, _TrackState]` (id → box/label/age/hits) · `self._next_id: int = 0`.
- `update(detections)`:
  1. `age += 1` cho MỌI track hiện có (giả định chưa khớp).
  2. `greedy_associate(prev_boxes, new_boxes, iou_thr, prev_labels, new_labels)` với prev = track hiện có, new = detections.
  3. Cặp khớp → cập nhật track: `box=det.box`, `age=0`, `hits+=1`, label giữ.
  4. Detection KHÔNG khớp → track mới: `id=self._next_id; self._next_id+=1`; `age=0, hits=1`.
  5. Retire: track có `age > max_age` → xoá khỏi `_tracks` (không trả, không tái dùng id).
  6. Trả `tuple(Track(...))` cho các detection frame NÀY (mỗi detection ↔ 1 track_id: khớp cũ hoặc mới). (Track đã retire/không có detection frame này KHÔNG nằm trong output frame — output = "tracks quan sát thấy frame này".)
- `unique_count == self._next_id` (đơn điệu); `active_count == len(self._tracks)`.
- `reset()`: clear `_tracks`, `_next_id=0`.
- **Thuần Python + BBox/iou** — không numpy nặng, không GPU. Deterministic.

### C5 — `runtime/stages/tracking_stage.py::TrackingStage(BaseStage)`
- `__init__(self, tracker: ITracker)` — DI port. `super().__init__("track")`. `self._source_id: str | None = None`.
- `_do_process(packet)`:
  - `dets = packet.artifacts.get("detections")`; `None` → raise ValueError (thiếu key — R3.3, giống CountStage).
  - **Camera-affinity (R3.2):** nếu `self._source_id is None` → set = `packet.source_id`; elif `packet.source_id != self._source_id` → raise ValueError("TrackingStage nhận 2 source_id — 1 instance/1 camera (K-042)"). (raise → BaseStage → ERROR.)
  - `tracks = self._tracker.update(dets)` (dets có thể là `()` → mọi track già đi, output rỗng, hợp lệ).
  - `return packet.with_artifact("tracks", tracks).with_artifact("unique_count", self._tracker.unique_count).with_artifact("active_count", self._tracker.active_count)`.
- STATEFUL: trạng thái nằm trong `tracker` (+ `_source_id` guard). Lifecycle: `teardown()` gọi `tracker.reset()` (giải phóng state).
- KHÔNG sửa CountStage — TrackingStage chạy SONG SONG/nối tiếp, đọc chung `detections` (fan-out).

## Data Models

**Artifacts thêm trên MediaPacket (in-process):**
- `tracks`: `tuple[Track, ...]` — mỗi Track cho 1 detection frame này (track_id gán). Box giữ space tag.
- `unique_count`: `int` — tổng track distinct đã tạo (đơn điệu tăng theo stream).
- `active_count`: `int` — số track đang sống.

**Nếu ghi event (tái dùng JsonlEventSink — KHÔNG bắt buộc v1):** thêm khoá `tracks`/`unique_count` vào dòng JSON;
schema hiện có (`event_ts`/`count`/`detections`) KHÔNG đổi → backward-compat. (Wire vào profile = tuỳ chọn sau.)

## Correctness Properties

### Property 1: Giữ track_id khi vật liên tục (IoU cao)
Chuỗi frame với 1 detection cùng label, box dịch nhẹ (IoU ≥ thr) → MỌI frame trả CÙNG track_id; `unique_count==1`.
**Validates: Requirements 1.1, 1.2, 2.1**

### Property 2: Track_id mới khi vật mới / nhảy xa (IoU < thr)
Detection ở vị trí khác hẳn (IoU < thr) hoặc label khác → track_id MỚI; `unique_count` tăng đúng số vật distinct.
**Validates: Requirements 1.3, 2.1**

### Property 3: Retire theo max_age + không tái dùng id
Vật biến mất > `max_age` frame → `active_count` giảm; nếu xuất hiện lại → track_id MỚI (không tái dùng id cũ);
`unique_count` tăng.
**Validates: Requirements 2.2, 2.3**

### Property 4: Xác định (deterministic) + tie-break ổn định
Cùng chuỗi detections (kể cả 2 detection cùng IoU với 1 track) → cùng chuỗi track_id qua nhiều lần chạy (tie-break
theo index). Đảo thứ tự detection trong 1 frame KHÔNG đổi tập (id, box) kết quả.
**Validates: Requirements 1.4, 5.2**

### Property 5: Edge — thiếu key / rỗng / mixed-source
Thiếu `detections` → ERROR (R3.3). Tuple RỖNG → hợp lệ: mọi track `age+1`, output `()`, `active_count` có thể giảm.
Frame `source_id` khác source đã thấy → ERROR (R3.2, không trộn state).
**Validates: Requirements 3.2, 3.3**

### Property 6: Stateless CountStage KHÔNG bị ảnh hưởng + không hồi quy
Pipeline có CẢ CountStage + TrackingStage → `count` (per-frame) vẫn đúng độc lập `unique_count` (cumulative). Baseline
465/1 giữ; lint 5/0; 0 diagnostic; chỉ THÊM file.
**Validates: Requirements 4.1, 4.2, 4.3**

## Error Handling
- Thiếu `artifacts["detections"]` → `ValueError` → BaseStage → `StageResult.ERROR` (không đếm bừa).
- `source_id` lạ (mixed camera) → `ValueError` → ERROR (fail-fast, chống trộn state = đếm loạn).
- `iou` khác space → domain đã fail-fast (ValueError). Detection từ DetectorPipeline là ORIGINAL_FRAME đồng nhất →
  bình thường không xảy ra; nếu trộn space → nổ rõ (đúng invariant Step 02).
- Tuple detections rỗng → KHÔNG lỗi (track già đi). `_do_process` trả sai kiểu → BaseStage bắt (E-16).

## Testing Strategy
File `tests/test_object_tracking.py` (CI, XÁC ĐỊNH, không camera/GPU) — dựng `Detection` tay + gọi trực tiếp
`IouTracker` và/hoặc chạy qua `TrackingStage` với packet dựng tay:
1. **P1 giữ id:** 5 frame, 1 det box dịch 1px/frame (IoU cao) → track_id giống nhau, unique_count==1.
2. **P2 id mới:** frame A det ở góc trái, frame B det góc phải (IoU=0) → 2 track_id, unique_count==2. + label khác → id khác.
3. **P3 retire:** det biến mất `max_age+1` frame → active_count→0; xuất hiện lại → id mới, unique_count tăng.
4. **P4 deterministic/tie-break:** 2 det cùng IoU với 1 track → gán ổn định theo index; đảo thứ tự det trong frame → cùng tập (id,box).
5. **P5 edge:** (a) TrackingStage không có detections key → StageResult.ERROR. (b) dets=() → hợp lệ, tracks=(), age tăng. (c) đổi source_id giữa chừng → ERROR.
6. **domain unit:** `greedy_associate` — ghép đúng cặp IoU cao nhất, tôn trọng threshold + label + mỗi bên dùng 1 lần.
7. **P6 regression:** `pytest -q` (≥465 + mới) · lint qua importlinter.api 5/0 · `get_diagnostics`=0.
Dùng `scripts\vp.cmd verify` để chạy cả cổng.

## Quyết định thiết kế (lý do — cho journal)
- **QĐ-1: Tách 3 lớp (domain.associate / ITracker+Track kernel / IouTracker+TrackingStage runtime)** — geometry thuần xuống domain (test riêng, tái dùng), state ở runtime, DTO/port ở kernel. Đúng ranh giới 6-layer, không phá linter.
- **QĐ-2: `ITracker` là PORT** (không nhét thẳng logic vào Stage) — swap-ready ML tracker (roadmap R3.3); TrackingStage mỏng.
- **QĐ-3: State trong IouTracker, KHÔNG trong Stage** — Stage chỉ điều phối + guard camera-affinity; state đóng gói 1 chỗ → dễ reset/test.
- **QĐ-4: Camera-affinity bằng fail-fast source_id guard** (K-042) — thay vì key state theo source_id (phức tạp + che dùng sai). 1 instance/1 camera là hợp đồng rõ; trộn = nổ ngay.
- **QĐ-5: unique_count = _next_id đơn điệu** — "đếm không trùng" = số vật distinct đã thấy; KHÔNG giảm khi retire (đã thấy là đã đếm). active_count phản ánh hiện tại.
- **QĐ-6: greedy IoU (không Hungarian/Kalman)** — v1 đủ + xác định + zero-dep + không GPU; tối ưu/ML là port-swap sau (Non-Goal).
- **QĐ-7: TrackingStage đọc chung `detections` với CountStage (fan-out)** — KHÔNG sửa CountStage; 2 analytics độc lập trên cùng detection (R3.1).

## Self-Review (doubt-driven — lỗ đã soi)
- **Lỗ 1 (đã xử):** state rò giữa camera nếu 1 instance nhận nhiều source → QĐ-4 fail-fast source_id guard (R3.2).
- **Lỗ 2 (đã xử):** id tái dùng gây đếm sai → id đơn điệu `_next_id`, retire KHÔNG trả id về (R2.3).
- **Lỗ 3 (đã xử):** không xác định khi 2 cặp cùng IoU → tie-break `(-iou, new_idx, prev_idx)` (P4).
- **Lỗ 4 (đã xử):** iou khác space → domain fail-fast; DetectorPipeline cho ORIGINAL_FRAME đồng nhất.
- **Lỗ 5 (đã nêu, giới hạn):** greedy ≠ tối ưu toàn cục (2 vật gần nhau đổi id khi giao nhau) — chấp nhận v1; ML tracker qua port sau. Ghi rõ để không kỳ vọng sai.
- **Còn mở có chủ đích (sub-spec sau):** line/zone-crossing count · cross-process tracking state · re-ID · Kalman/DeepSORT impl của ITracker.
**Phán quyết:** đủ sâu để THI CÔNG v1 (API bám thật + edge + test cụ thể). Món "còn mở" là sub-spec riêng, không phải thiếu sót v1.

## Glossary
- **greedy_associate** — hàm domain ghép detection↔track theo IoU giảm dần (index-based, thuần).
- **Track / ITracker / IouTracker / TrackingStage** — DTO / port / impl IoU / Stage stateful. Xem C2–C5.
- **unique_count vs active_count** — distinct đã tạo (đơn điệu) vs đang sống. Xem QĐ-5.
- **camera-affinity** — 1 tracker/1 camera; trộn source → fail-fast (K-042). Xem QĐ-4.
- **retire / max_age** — loại track sau `max_age` frame không khớp; id không tái dùng.
