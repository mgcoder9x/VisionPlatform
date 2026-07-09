# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · xây TRÊN `line-crossing-count` (#262) · tái dùng mẫu `JsonlEventSink`.
> **Cập nhật lúc:** 2026-07-09.

## Overview

Biến ĐẾM-qua-vạch (aggregate) → SỰ KIỆN có-thời-gian bền vững. `LineCrossingStage` (đã có) khi phát hiện băng-vạch
sẽ THÊM tạo `CrossingEvent` + phơi qua `artifacts["crossing_events"]`; `CrossingEventJsonlSink` ghi mỗi event thành
1 dòng JSONL. Đếm cũ (`crossings_in/out/total`) GIỮ NGUYÊN.

**Vì sao gốc, không ngọn:** "đếm qua cửa" cho con số; nhưng tích hợp/audit thương mại cần TỪNG sự kiện (ai/khi/hướng).
Nơi DUY NHẤT biết chi tiết 1 lượt qua = `LineCrossingStage` (lúc phát hiện cắt) → nó phải phát event. Sink chỉ thấy
số tổng thì không tái tạo được sự kiện → phải phơi qua artifacts. Đây là ranh giới đúng (stage phát, sink ghi).

**Nền đã đọc code thật (chống bịa):**
- `JsonlEventSink` (adapters): `setup` mkdir+open("a"); `handle` chỉ khi SUCCESS → `json.dumps(...)+"\n"` + `flush`;
  `event_ts = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")`; `teardown` close. → CrossingEventJsonlSink theo Y mẫu.
- `LineCrossingStage._do_process` (#262): đã tính `orient>0 → in else out` khi `segments_intersect` — CHÍNH chỗ chèn tạo event.
- `Track(track_id,label,box,...)`; `ISink` Protocol; `MediaPacket.with_artifact`.

## Architecture

```
   DetectStage → TrackingStage → LineCrossingStage(+clock, +artifacts["crossing_events"]) → sink
                                                                                              │
                                            CompositeSink([..., CrossingEventJsonlSink(path)?])
   kernel/crossing_event.py::CrossingEvent  (frozen DTO)
   adapters/crossing_event_sink.py::CrossingEventJsonlSink  (leaf, I/O file)
```
**Layer:** DTO→`kernel` · sink→`adapters` (leaf) · stage sửa additive→`runtime`. Không phá 5 contract.

## Components and Interfaces

### C1 — `kernel/crossing_event.py::CrossingEvent` (frozen DTO)
```
@dataclass(frozen=True)
class CrossingEvent:
    track_id: int
    label: str
    direction: str      # "in" | "out"
    source_id: str
    cx: float
    cy: float
    event_ts: str        # ISO-8601 UTC, hậu tố "Z" (wall-clock)
```
Kernel: DTO thuần (chỉ str/int/float — msgpack/json-friendly). KHÔNG giữ BBox (chỉ tâm cx,cy — đủ cho event; box đầy đủ ở detections nếu cần).

### C2 — `LineCrossingStage` (sửa ADDITIVE)
- `__init__(..., *, space=..., clock: Callable[[], datetime] = None)` → `self._clock = clock or (lambda: datetime.now(timezone.utc))`.
- Trong vòng track, khi `segments_intersect(...)` TRUE (đã có):
  - tính `direction = "in" if orient(...)>0 else "out"` (đã có nhánh đếm — dùng CHUNG biến, không tính 2 lần).
  - `ts = self._clock().isoformat().replace("+00:00","Z")`.
  - append `CrossingEvent(tr.track_id, tr.label, direction, self._source_id, cx, cy, ts)` vào list `events` (khởi tạo `[]` đầu `_do_process`).
- Cuối: `packet.with_artifact("crossings_in",...).with_artifact("crossings_out",...).with_artifact("crossings_total",...).with_artifact("crossing_events", tuple(events))`.
- **counts KHÔNG đổi** (chỉ THÊM 1 artifact + clock). Test cũ (không kiểm crossing_events) vẫn pass.

### C3 — `adapters/crossing_event_sink.py::CrossingEventJsonlSink(path)` (ISink, theo mẫu JsonlEventSink)
- `setup`: mkdir cha (nếu có) + `open(path,"a",encoding="utf-8")` (fail-fast).
- `handle(result)`: nếu `status != SUCCESS or packet is None` → return. Với mỗi `ev` trong `packet.artifacts.get("crossing_events", ())`:
  `self._f.write(json.dumps({track_id,label,direction,source_id,cx,cy,event_ts}, ensure_ascii=False)+"\n")`; `flush()` (durability).
- `teardown`: close (idempotent).
- Leaf (I/O file) — không import runtime.

### C4 — Wire profile `vision_slice_app`
- Cờ `--crossing-out <path.jsonl>` (cần `--line`; validate fail-fast). Có → append `CrossingEventJsonlSink(path)` vào `sinks`.
- Summary: in `f"  crossing events → {path}"` (giống `--out`).

## Data Models
**Artifact thêm:** `crossing_events: tuple[CrossingEvent,...]` (per-frame; rỗng nếu không có lượt qua frame đó).
**JSONL 1 dòng/sự kiện:** `{event_ts, source_id, track_id, label, direction, cx, cy}`.

## Correctness Properties

### Property 1: Mỗi lượt qua → đúng 1 event, field đúng
Track băng vạch → `crossing_events` frame đó có 1 CrossingEvent: track_id/label khớp track, direction khớp `crossings_in/out`, cx/cy = tâm, event_ts = clock tiêm.
**Validates: Requirements 1.1, 1.3, 2.1**

### Property 2: Không qua → không event; đếm không đổi
Không băng vạch → `crossing_events == ()`. `crossings_*` vẫn đúng như spec line-crossing (không đổi hành vi).
**Validates: Requirements 2.1, 2.2**

### Property 3: Sink ghi đúng số dòng + parse được + optional
N lượt qua (nhiều frame) → file JSONL có N dòng JSON hợp lệ (parse ok), mỗi dòng đủ field + event_ts. KHÔNG gắn sink → không tạo file, pipeline y hệt.
**Validates: Requirements 3.1, 3.2, 3.3**

### Property 4: Clock tiêm → xác định + wall-clock
Clock tiêm giờ cố định → event_ts = giá trị cố định (ISO "Z"). Mặc định = `now(UTC)` (wall-clock, không monotonic).
**Validates: Requirements 1.2, 2.3, 5.1, 5.2**

### Property 5: Không hồi quy
494 test cũ xanh + mới; lint 5/0; 0 diagnostic; additive (LineCrossingStage cũ vẫn pass, không sửa lõi khác).
**Validates: Requirements 4.1, 4.2, 4.3**

## Error Handling
- CrossingEventJsonlSink `setup` không mở được file → raise (fail-fast, không chạy mù). `handle` giữa chừng lỗi → propagate + teardown finally đóng file.
- `crossing_events` thiếu key (stage không phát) → sink `.get(...,())` → không ghi (an toàn, backward-compat với pipeline không có LineCrossingStage).
- LineCrossingStage edge (thiếu tracks/mixed-source/space) GIỮ NGUYÊN (#262) — event chỉ tạo khi có crossing hợp lệ.

## Testing Strategy
`tests/test_crossing_event.py` (CI, XÁC ĐỊNH):
1. **P1:** track 40→60 qua vạch + clock tiêm `T0` → `crossing_events` có 1 event: direction khớp, track_id/label đúng, event_ts==T0-ISO-Z.
2. **P2:** không qua → `crossing_events==()`; counts vẫn đúng (regression line-crossing).
3. **P3 sink:** chạy vài lượt qua `CrossingEventJsonlSink(tmp_path)` → file có đúng số dòng, mỗi dòng `json.loads` ok + đủ field. Không gắn → file không tồn tại.
4. **P4 clock mặc định:** không tiêm → event_ts parse được là ISO UTC (endswith "Z").
5. **P5 additive:** LineCrossingStage KHÔNG tiêm clock + test #262 cũ vẫn pass; `scripts\vp.cmd verify` ≥494+mới, lint 5/0, drift PASS.
6. **wiring:** `main(--source fake --frames 5 --track --line 50,0,50,100 --crossing-out tmp)` → rc0; file tạo (0 dòng vì box cố định không qua) hoặc không lỗi.

## Quyết định thiết kế (lý do — cho journal)
- **QĐ-1: event phát TRONG LineCrossingStage** (không sink tự suy) — chỉ stage biết lượt-qua cụ thể; sink chỉ ghi. Ranh giới đúng.
- **QĐ-2: clock TIÊM (default wall-clock)** — xác định-test + đúng mẫu QĐ-4 slice (wall-clock cho log, monotonic vô nghĩa khi đọc lại).
- **QĐ-3: CrossingEvent ở kernel, chỉ tâm cx,cy (không BBox)** — DTO tối giản json-friendly; đủ cho event qua-vạch (box đầy đủ ở detections nếu cần).
- **QĐ-4: sink RIÊNG `CrossingEventJsonlSink`** (không nhồi vào JsonlEventSink) — SRP: 1 sink 1 loại record; CompositeSink gắn nhiều.
- **QĐ-5: sửa LineCrossingStage ADDITIVE** (clock kwarg default + artifact) — không phá spec/test #262; đường không-dùng-event y hệt.

## Self-Review (doubt-driven)
- **Lỗ 1 (đã xử):** direction event lệch đếm → dùng CHUNG biến direction với nhánh đếm (1 nguồn).
- **Lỗ 2 (đã xử):** ts monotonic vô nghĩa khi lưu → wall-clock UTC (QĐ-2).
- **Lỗ 3 (đã xử):** phá test #262 → additive (clock default, artifact thêm) → test cũ pass.
- **Còn mở (sub-spec sau):** DB/queue sink · dedupe qua restart · event cho count/classify · schema-version.
**Phán quyết:** đủ sâu để THI CÔNG (schema + additive + mẫu sink có sẵn + test cụ thể). Món "còn mở" là sub-spec riêng.

## Glossary
- **CrossingEvent / CrossingEventJsonlSink** — DTO 1 lượt qua / sink ghi JSONL. Xem C1/C3.
- **crossing_events (artifact)** — tuple event per-frame do LineCrossingStage phát.
- **clock tiêm** — hàm `()->datetime` (default now UTC); test tiêm cố định.
