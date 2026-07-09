# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · xây TRÊN `object-tracking-count` (Track/TrackingStage đã có, #259).
> **Cập nhật lúc:** 2026-07-09.

## Overview

Analytics tầng-2 chạy TRÊN tracking: đếm vật **băng qua 1 vạch** theo hướng. Pipeline mở rộng (additive):

```
source → DetectStage → TrackingStage → LineCrossingStage → sink
                        (track_id)      (đếm qua vạch)
```

`LineCrossingStage` đọc `artifacts["tracks"]` (do TrackingStage ghi) → với mỗi track, so tâm frame trước ↔ tâm
frame này với đoạn vạch `[A,B]` → nếu cắt: +1 lượt (theo hướng). Ghi `artifacts["crossings_in/out/total"]`.

**Vì sao gốc, không ngọn:** "đếm qua cửa" = sự kiện THỜI-GIAN (vật DI CHUYỂN qua vạch), không phải trạng-thái-1-frame.
Phải có track_id (biết cùng vật) + vị-trí-2-frame (biết đã băng qua). Ta xây trên tracking (đã có track_id ổn
định) + geometry đoạn-thẳng thuần (test được) — không đoán, không ML.

**Nền đã đọc code thật (chống bịa):**
- `Track(track_id:int, label:str, box:BBox, age:int, hits:int)` — `kernel/tracking_protocol.py` (#259). `box.space`
  thường `ORIGINAL_FRAME` (qua DetectorPipeline). `BBox` có `.x/.y/.w/.h` + `.space`.
- `BaseStage(name)` override `_do_process(packet)->MediaPacket` (raise→ERROR); giữ field state OK; `teardown` overridable.
- `MediaPacket.artifacts.get(k)`, `.with_artifact(k,v)`, `.source_id`.

## Architecture

```
   domain/geometry.py        : _orient(a,b,c) [cross-product sign] · segments_intersect(p1,p2,p3,p4) -> bool
                                (THUẦN toán trên (x,y) float — KHÔNG import BBox/kernel; tối giản, tái dùng)
                    ▲ dùng
   runtime/stages/line_crossing_stage.py : LineCrossingStage(BaseStage)
       - line (A,B) float · state: _last_center: dict[track_id -> (cx,cy)] · _source_id guard
       - _do_process: đọc tracks → tâm box → so với _last_center → segments_intersect([prev,curr],[A,B])
         → đếm in/out (dấu orient) → prune id vắng → ghi artifacts
```

**Layer (không phá 5 contract):** `domain/geometry.py` THUẦN (chỉ float/tuple — thậm chí KHÔNG cần BBox) ·
`LineCrossingStage`@runtime/stages (đọc `Track`@kernel, dùng geometry@domain). runtime→kernel/domain OK.

**QĐ layer:** geometry nhận `(x,y)` float rời (KHÔNG BBox) → thuần nhất, test dễ, tái dùng cho zone sau. Stage
rút tâm từ `Track.box` rồi gọi geometry. (Giống nms nhận số rời.)

## Components and Interfaces

### C1 — `domain/geometry.py` (thuần, test riêng)
```
def _orient(ax, ay, bx, by, cx, cy) -> float:
    # cross-product (B-A)×(C-A): >0 C bên trái AB, <0 bên phải, =0 thẳng hàng.
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

def segments_intersect(p1, p2, p3, p4) -> bool:
    # 2 đoạn [p1,p2] & [p3,p4] (mỗi điểm (x,y)) có cắt nhau không (proper + không xét collinear-chồng ở v1).
    d1 = _orient(p3[0],p3[1], p4[0],p4[1], p1[0],p1[1])
    d2 = _orient(p3[0],p3[1], p4[0],p4[1], p2[0],p2[1])
    d3 = _orient(p1[0],p1[1], p2[0],p2[1], p3[0],p3[1])
    d4 = _orient(p1[0],p1[1], p2[0],p2[1], p4[0],p4[1])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))   # dấu khác nhau ở CẢ 2 phép → cắt thật
```
- Dùng so-sánh `(d>0)` (strict) → điểm NẰM ĐÚNG trên vạch (d==0) coi như "chưa qua" (tránh đếm khi chạm mép; qua hẳn mới tính — khớp R1.4). Collinear-chồng-lấn hiếm → v1 coi không cắt (tài liệu).

### C2 — `runtime/stages/line_crossing_stage.py::LineCrossingStage(BaseStage)`
- `__init__(self, ax, ay, bx, by, *, space=CoordinateSpace.ORIGINAL_FRAME)` — vạch cố định + space kỳ vọng. `super().__init__("line_crossing")`.
- State: `self._last_center: dict[int, tuple[float,float]] = {}` · `self._in = 0` · `self._out = 0` · `self._source_id: str|None = None`.
- `_do_process(packet)`:
  - `tracks = packet.artifacts.get("tracks")`; `None` → raise ValueError (R3.3, thiếu TrackingStage trước).
  - Camera-affinity (R3.2): set/kiểm `packet.source_id` như TrackingStage (mixed → raise).
  - `seen: set[int] = set()`.
  - for `tr` in tracks:
    - fail-fast nếu `tr.box.space != self._space` → ValueError (so vạch khác space = vô nghĩa, đồng bộ invariant Step 02).
    - `curr = (tr.box.x + tr.box.w/2, tr.box.y + tr.box.h/2)`; `seen.add(tr.track_id)`.
    - nếu `tr.track_id in _last_center`: `prev = _last_center[id]`; nếu `segments_intersect(prev, curr, A, B)`:
      - hướng: `d_curr = _orient(A,B, curr)`; `if d_curr > 0: _in += 1 else: _out += 1` (curr nằm phía + → "in"; quy ước theo thứ tự A,B — R2.1/2.3).
    - `_last_center[id] = curr`.
  - **prune (R3.4 bounded):** `for id in list(_last_center): if id not in seen: del _last_center[id]`.
  - `return packet.with_artifact("crossings_in", _in).with_artifact("crossings_out", _out).with_artifact("crossings_total", _in + _out)`.
- `teardown()`: clear state (`_last_center.clear()`, đếm giữ hay reset? → reset về 0: giống tracker, giải phóng + phiên mới sạch).

### C3 — Wire profile (tuỳ chọn, PHA2 hoặc sau)
Cờ `--line ax,ay,bx,by` cho `vision_slice_app`: khi có → chèn `LineCrossingStage` SAU `TrackingStage` (yêu cầu
`--track`). Summary in `crossings_in/out/total` (đọc artifacts qua sink nhỏ, giống `_TrackSummarySink`). *(Có thể
gộp PHA2 hoặc tách — quyết ở PHA2.)*

## Data Models
**Artifacts thêm:** `crossings_in:int`, `crossings_out:int`, `crossings_total:int` (cộng dồn, đơn điệu).
Không DTO mới (số thuần). Nếu cần event "vật X qua vạch lúc t" → CrossingEvent DTO là mở rộng sau (Non-Goal v1).

## Correctness Properties

### Property 1: Băng qua tính đúng 1 lượt
Track di chuyển từ phía này sang phía kia của vạch (đoạn tâm cắt [A,B]) → total +1 ĐÚNG 1 lần tại frame băng qua.
**Validates: Requirements 1.2, 1.4**

### Property 2: Không băng qua → không đếm
Track di chuyển NHƯNG không cắt vạch (cùng phía, hoặc song song, hoặc đi tới gần rồi lui) → total không đổi.
Đứng yên cạnh vạch nhiều frame → không đếm (đoạn prev→curr không cắt).
**Validates: Requirements 1.4, 2.2**

### Property 3: Hướng in/out đúng + phụ thuộc thứ tự (A,B)
prev phía âm → curr phía dương ⇒ in+1; ngược lại out+1. Đảo (A,B) → đảo in/out.
**Validates: Requirements 2.1, 2.3**

### Property 4: Edge — thiếu key / rỗng / mixed-source / khác space
Thiếu `tracks` → ERROR. `tracks=()` → hợp lệ (không đổi đếm, prune sạch _last_center). source lạ → ERROR.
`box.space` khác space vạch → ERROR (fail-fast).
**Validates: Requirements 3.2, 3.3**

### Property 5: Bounded memory (prune)
Sau mỗi frame, `_last_center` chỉ chứa track_id CÓ MẶT frame đó → track biến mất bị prune (RAM ~ active, không tích luỹ).
**Validates: Requirements 3.4**

### Property 6: Không hồi quy
480 test cũ xanh + test mới; lint 5/0; 0 diagnostic; additive (không sửa TrackingStage/lõi).
**Validates: Requirements 4.1, 4.2, 4.3**

## Error Handling
- Thiếu `tracks` / mixed source_id / box khác space → `ValueError` → BaseStage → `StageResult.ERROR` (fail-fast, không đếm bừa).
- `tracks=()` → hợp lệ (đếm giữ nguyên, prune toàn bộ _last_center).

## Testing Strategy
`tests/test_line_crossing.py` (CI, XÁC ĐỊNH) — dựng `Track` tay (box tại vị trí muốn) chạy qua `LineCrossingStage`:
1. **P1:** vạch dọc x=50; track box tâm đi 40→60 (qua phải) giữa 2 frame → total=1, in=1 (hoặc out tuỳ A,B).
2. **P2:** track đi 40→45 (cùng phía) → total=0; đứng yên 45 nhiều frame → total=0.
3. **P3 hướng:** trái→phải = in; phải→trái = out; đảo (A,B) → đảo.
4. **P4 edge:** thiếu `tracks`→ERROR; `()`→hợp lệ; source lạ→ERROR; box space MODEL_INPUT vs vạch ORIGINAL_FRAME→ERROR.
5. **P5 prune:** track vắng frame sau → `_last_center` không còn id đó (kiểm nội bộ hoặc gián tiếp: quay lại không nối đoạn cũ).
6. **domain unit:** `segments_intersect` (cắt/không/song song/chạm-mép d==0→không cắt) + `_orient` dấu.
7. **P6 regression:** `scripts\vp.cmd verify` (≥480 + mới · lint 5/0 · drift PASS).

## Quyết định thiết kế (lý do — cho journal)
- **QĐ-1: geometry nhận (x,y) rời, KHÔNG BBox** — domain thuần nhất, tái dùng cho zone sau; stage rút tâm.
- **QĐ-2: strict `(d>0)` (điểm trên vạch = chưa qua)** — chỉ đếm khi QUA HẲN, tránh đếm rung khi chạm mép (R1.4).
- **QĐ-3: prune id vắng mỗi frame** — bounded memory 24/7 (R3.4); đổi lấy: track nhấp-nháy reset mốc (có thể sót 1 lượt) — chấp nhận + tài liệu.
- **QĐ-4: đếm cộng dồn in/out/total trong state** (không phải per-frame) — "đếm qua cửa" là tích luỹ; artifact đơn điệu.
- **QĐ-5: camera-affinity fail-fast** (giống TrackingStage) — 1 instance/1 camera/1 vạch; nhiều vạch = nhiều instance.
- **QĐ-6: build TRÊN tracks (không tự track)** — SRP: tracking lo id, line lo đếm-qua-vạch; tách analytic (fan-out).

## Self-Review (doubt-driven)
- **Lỗ 1 (đã xử):** đếm lặp khi đứng cạnh vạch → dùng đoạn prev→curr (chỉ đếm khi thực sự cắt) + strict d>0 (QĐ-2).
- **Lỗ 2 (đã xử):** RAM phình theo tổng vật → prune id vắng (QĐ-3, R3.4).
- **Lỗ 3 (đã xử):** so tâm khác space vạch = sai → fail-fast space (P4).
- **Lỗ 4 (giới hạn, tài liệu):** track nhấp-nháy (mất 1 frame) reset mốc → có thể sót 1 lượt; collinear-chồng-vạch coi không cắt. Chấp nhận v1.
- **Còn mở (sub-spec sau):** đa-vạch/zone-đa-giác · đếm theo label · CrossingEvent (log lúc-nào-ai-qua) · tốc-độ/hướng-vector.
**Phán quyết:** đủ sâu để THI CÔNG v1 (thuật toán chuẩn + edge + test cụ thể, bám Track thật). Món "còn mở" là sub-spec riêng.

## Glossary
- **_orient / segments_intersect** — cross-product dấu / cắt-đoạn-thẳng. Xem C1.
- **LineCrossingStage** — Stage stateful đếm qua vạch trên nền tracks. Xem C2.
- **in/out/total** — đếm theo hướng (dấu phía) + tổng, cộng dồn.
- **prune** — xoá center_prev của track vắng → bounded memory (R3.4).
