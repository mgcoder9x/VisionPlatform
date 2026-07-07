# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · reuse design `pipeline-runner` · roadmap `scale-architecture` (T-011).
> **Cập nhật lúc:** 2026-07-06. **Đào sâu (#217):** đặc tả bám code thật (Detection/BBox/FakeDetector/Fake&Noise
> source/DetectorPipeline đã đọc) — schema chính xác + edge case + CompositeSink + timestamp + giới hạn sync-vs-live.

## Overview

Lát cắt dọc nhỏ nhất chạy THẬT: **source → DetectStage → CountStage → sink**, điều khiển bởi `PipelineRunner`.
Mục tiêu kép: (1) hiện thực nền `PipelineRunner`+`ISink`+`RunStats` (đã design, chưa code) — cho người-dùng-thật;
(2) chứng minh luồng nghiệp vụ đầu tiên (detect + đếm/frame + xuất event), test CI xác định.

**Vì sao gốc, không ngọn:** giá trị thương mại từ luồng nghiệp vụ chạy được (T-011). Slice cũng là **bằng chứng
kiểm chứng** cho pipeline-runner + Stage-hoá detector (Gap-2 K-037) trước khi nhân bản lên scale. **v1 STATELESS
có chủ đích** (né Lỗ 3 K-042).

**Nền đã đọc code thật (chống bịa — trích chính xác):**
- `Detection(label:str, confidence:float, box:BBox)` (kernel/inference_protocol). `BBox(x,y,w,h:float,
  space:CoordinateSpace)` — space ∈ {ORIGINAL_FRAME, MODEL_INPUT, NORMALIZED, DISPLAY}, tag BẮT BUỘC.
- `FakeDetector.detect` → **1** Detection/frame, label="object", conf=`frame.mean()/255`, box **MODEL_INPUT**.
- `DetectorPipeline(inner, model_h, model_w, nms_iou=None)` = IDetector Decorator: letterbox → inner.detect →
  `inverse_box` về **ORIGINAL_FRAME** → NMS optional. Chính nó thoả IDetector.
- `FakeFrameSource(width,height,max_frames,inject_error_at)`: frame fill=`count%256` (XÁC ĐỊNH), `is_finite`,
  `source_id` unique, đọc EOF khi hết, phát ReadStatus.ERROR tại `inject_error_at`.
- `NoiseFrameSource(seed=42)`: random có seed.
- `BaseStage.process`: bọc try/except → StageResult.SUCCESS/SKIPPED/ERROR (bulkhead sẵn).

## Architecture

```
   composition root (profiles/vision_slice_app.py)
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │ source (Fake/Noise[CI] | RTSP/Video[flag])                                     │
   │    │ IFrameSource                                                              │
   │    ▼                                                                           │
   │ PipelineRunner ── read→MediaPacket(media_ref_factory=InMemoryArrayRef.from_copy)│
   │    │                → executor.execute → sink.handle(result) → RunStats         │
   │    ▼                                                                           │
   │ SyncLinearExecutor([ DetectStage(detector), CountStage() ])                    │
   │    ▼                                                                           │
   │ sink = CompositeSink([ CollectingSink(test) , JsonlEventSink(out.jsonl)? ])    │
   └──────────────────────────────────────────────────────────────────────────────┘

 detector (DI):  CI = DetectorPipeline(FakeDetector(), mh, mw)  →  box ORIGINAL_FRAME
                 real = DetectorPipeline(Yolov5PtDetector(...)) | wraps any IDetector
 DetectStage:  media_ref.array → detector.detect() → artifacts["detections"]=tuple[Detection]  (STATELESS)
 CountStage :  artifacts["detections"] → artifacts["count"]=int + artifacts["count_by_label"]=dict  (STATELESS)
```

**Layer (không phá contract import-linter):** `ISink`@kernel/ports · `PipelineRunner`+`CompositeSink`+`CollectingSink`
@runtime · `DetectStage`/`CountStage`@runtime/stages · `JsonlEventSink`@adapters (chạm I/O file = leaf) ·
profile@profiles. (runtime→kernel OK; adapters=leaf OK.)

## Components and Interfaces

### C1 — nền (hiện thực theo design pipeline-runner, KHÔNG lặp lại chi tiết)
`kernel/ports/sink.py::ISink` (setup/handle(ExecutionResult)/teardown) · `runtime/pipeline_runner.py::
PipelineRunner`+`RunStats`. Slice là consumer đầu tiên.

### C2 — `runtime/stages/detect_stage.py::DetectStage(BaseStage)`
- `__init__(self, detector: IDetector)` — DI kiểu PORT (không import adapter cụ thể). Tên stage="detect".
- `setup()` → `detector.setup()`; `teardown()` → `detector.teardown()` (ủy quyền lifecycle model — nạp/giải phóng).
- `_do_process(packet)`: `dets = self._detector.detect(packet.media_ref.array)` →
  `packet.with_artifact("detections", tuple(dets))`. **STATELESS** (không field trạng thái).
- Lỗi detect (model/GPU) → BaseStage bọc thành `StageResult.ERROR` (không raise ra runner). Bulkhead sẵn.
- **KHÔNG lọc confidence ở đây** (SRP): lọc là việc của detector/postprocess hoặc 1 FilterStage sau. DetectStage
  chỉ Stage-hoá + truyền thẳng detections detector trả.

### C3 — `runtime/stages/count_stage.py::CountStage(BaseStage)`
- Tên stage="count". `_do_process(packet)`:
  - `dets = packet.artifacts.get("detections")`. **Phân biệt (edge case quan trọng):**
    - `None` (KHÔNG có key) → raise `KeyError`/ValueError → StageResult.ERROR (R3.3: pipeline sai thứ tự stage,
      KHÔNG đếm bừa 0).
    - `()` (có key, tuple RỖNG) → HỢP LỆ: `count=0`, `count_by_label={}` (khung hình không có object — không lỗi).
  - `count = len(dets)`; `count_by_label = {}` cộng dồn theo `d.label` (đọc thuộc tính label — không cần import
    Detection). → `packet.with_artifact("count", count).with_artifact("count_by_label", count_by_label)`.
- **STATELESS tuyệt đối:** chỉ đọc frame hiện tại. `count_by_label` cardinality bounded (nhãn từ tập lớp model — K-019 OK).

### C4 — Sinks
- `runtime/composite_sink.py::CompositeSink(sinks: list[ISink])` — thoả ISink: `setup()`/`teardown()`/`handle()`
  forward tới từng sink con (setup theo thứ tự, teardown NGƯỢC thứ tự; teardown nuốt-lỗi-từng-cái để không kẹt).
  Lý do TỒN TẠI: runner nhận 1 sink, nhưng slice cần VỪA gom (test) VỪA ghi file → cần 1 sink hợp thành.
- `CollectingSink` (runtime hoặc tests-support): `handle(result)` append vào list; expose `results`/`counts`. Test-helper.
- `adapters/jsonl_event_sink.py::JsonlEventSink(path)`:
  - `setup()`: `mkdir` thư mục cha nếu thiếu; mở file mode **"a"** (append), encoding utf-8. Fail-fast nếu không mở được.
  - `handle(result)`: chỉ khi `result.status == SUCCESS` → ghi **1 dòng JSON** (schema §Data Models) + `flush()`
    (durability cho event log — chấp nhận chậm hơn để không mất event khi crash). non-SUCCESS → bỏ qua ở v1 (đếm
    trong RunStats; profile in ra).
  - `teardown()`: đóng file (idempotent).

### C5 — Profile `profiles/vision_slice_app.py` (composition root)
Bảng cờ (chốt cụ thể + validate fail-fast):

| Cờ | Giá trị | Mặc định | Ghi chú |
|---|---|---|---|
| `--source` | fake / noise / video / rtsp | fake | video/rtsp = chế độ THẬT (ngoài CI) |
| `--detector` | fake / pt | fake | pt cần extra `.[pt]` + `--weights` |
| `--weights` | path | (none) | bắt buộc khi `--detector pt` (validate) |
| `--model-size` | int (vd 640) | 640 | model_h=model_w cho DetectorPipeline |
| `--frames` / `--max-frames` | int | 20 | fake/noise: max_frames; runner: giới hạn |
| `--video` / `--rtsp` | path/url | (none) | bắt buộc tương ứng khi chọn source đó |
| `--out` | path .jsonl | (none) | có → gắn JsonlEventSink; không → chỉ CollectingSink |

Wire: chọn source + detector → `DetectStage(DetectorPipeline(detector, size, size))` → `CountStage()` → executor
→ `CompositeSink([CollectingSink(), JsonlEventSink(out)?])` → `PipelineRunner(...).run(max_frames=...)` → in RunStats.
**Validate fail-fast:** combo sai (vd `--detector pt` thiếu `--weights`; `--source video` thiếu `--video`) → báo lỗi + thoát.

## Data Models

**Artifacts trên MediaPacket (in-process, không pickle ở v1):**
- `detections`: `tuple[Detection, ...]` — Detection frozen; **box GIỮ NGUYÊN space tag** (không strip — invariant Step 02).
- `count`: `int` (tổng số detection trong frame).
- `count_by_label`: `dict[str, int]` (đếm theo nhãn; bounded).

**JSONL event (1 dòng/frame SUCCESS) — schema chốt:**
```json
{
  "event_ts": "2026-07-06T08:15:30.123456Z",   // WALL-CLOCK UTC (datetime.now(timezone.utc)) — cho LOG lưu trữ
  "capture_time_ns": 123456789,                  // monotonic nội bộ (chỉ để đo trễ trong-process, KHÔNG phải giờ thật)
  "source_id": "fake_0",
  "count": 1,
  "count_by_label": {"object": 1},
  "detections": [
    {"label": "object", "confidence": 0.5, "box": {"x": 160.0, "y": 120.0, "w": 320.0, "h": 240.0, "space": "original"}}
  ]
}
```
**QUYẾT ĐỊNH quan trọng (đào sâu):** event log dùng **wall-clock `event_ts` (UTC ISO-8601)** làm mốc thời gian
CHÍNH — vì `capture_time_ns` là **monotonic** (mốc gốc không xác định, KHÔNG phải giờ thật → vô nghĩa khi lưu/đọc
lại sau). Giữ `capture_time_ns` như field phụ để đo trễ nội bộ. Box ghi kèm **space tag** (không giả định original).

## Correctness Properties

### Property 1: End-to-end đếm đúng (stateless)
Source hữu hạn N frame + detector trả K detection/frame → mỗi ExecutionResult SUCCESS có `artifacts["count"]==K`
và `count_by_label` tổng = K; `RunStats.processed==N`.
**Validates: Requirements 3.1, 5.2**

### Property 2: DetectStage Stage-hoá đúng + bulkhead
`DetectStage` ghi `artifacts["detections"]` = tuple detector trả (space tag giữ nguyên); detector ném →
StageResult.ERROR (không raise ra runner, `RunStats.stage_errors` tăng), vòng chạy KHÔNG chết.
**Validates: Requirements 2.1, 2.3**

### Property 3: Edge — thiếu-key vs rỗng
`artifacts` KHÔNG có "detections" (CountStage chạy sai thứ tự) → ERROR (không đếm 0 âm thầm). Có key nhưng tuple
RỖNG (detector không thấy gì) → count=0, count_by_label={} (HỢP LỆ, không lỗi).
**Validates: Requirements 3.1, 3.3**

### Property 4: Sink — composite + storage optional bật/tắt + wall-clock
`CompositeSink` forward tới mọi sink con. `JsonlEventSink` gắn → file có đúng (số SUCCESS) dòng JSON hợp lệ, mỗi
dòng có `event_ts` wall-clock + box kèm space tag; KHÔNG gắn → không tạo file, pipeline chạy y hệt.
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 5: STATELESS — count chỉ phụ thuộc frame hiện tại
Cùng 1 frame chạy 2 lần rời rạc → count giống nhau; không tích luỹ xuyên-frame (khẳng định v1 KHÔNG tracking).
**Validates: Requirements 3.2**

### Property 6: Không hồi quy
369 test cũ xanh + test mới; lint 5/0; 0 diagnostic. Additive (thêm stage/sink/runner, không sửa lõi cũ).
**Validates: Requirements 1.3, 5.3**

## Error Handling
- **Detector lỗi:** BaseStage → StageResult.ERROR → runner đếm `stage_errors` + sink.handle (sink tự quyết). Không raise ra vòng chạy.
- **Thiếu detections ở CountStage:** raise → ERROR rõ (R3.3). Tuple rỗng → count=0 (không lỗi). (Property 3.)
- **Source ERROR/EOF:** PipelineRunner xử (theo design pipeline-runner): ERROR→`source_errors`++ + bỏ, EOF→dừng nếu is_finite.
- **JsonlEventSink:** setup fail-fast (không mở được file → raise, không chạy mù). handle ghi lỗi giữa chừng →
  propagate theo runner + teardown finally đóng file. flush mỗi dòng → mất tối đa 1 event khi crash cứng.
- **Combo cờ sai:** profile validate fail-fast trước khi chạy.
- **Chế độ thật:** lỗi camera/model KHÔNG ảnh hưởng CI (mode thật ngoài pytest).

## Giới hạn SYNC vs LIVE (đào sâu — trung thực, tránh dùng sai)
`PipelineRunner` v1 **đồng bộ, 1 vòng lặp**: `detect` CHẶN `read`. → phù hợp **video-file/synthetic (đường
throughput/batch)**. Với **RTSP real-time**, detect-trong-loop sẽ **chậm hơn camera → frame dồn/rớt** (đúng lý do
`vision_web_app` trước đây tách 2 thread video⊥detect). Vậy: **`--rtsp` trên slice sync = kiểm chức năng, KHÔNG
phải hiệu năng real-time.** Đường low-latency (async split / drop-to-latest) là biến thể SAU (hoặc tái dùng pattern
web_app), sẽ nêu ở sub-spec riêng. Ghi rõ để không ai kỳ vọng sai.

## Testing Strategy
File `tests/test_vision_slice.py` (CI, XÁC ĐỊNH, không cần camera/GPU):
1. **P1 count=1 (FakeDetector):** `FakeFrameSource(max_frames=N)` → `DetectStage(DetectorPipeline(FakeDetector(),
   sz,sz))` → `CountStage` → `CollectingSink` qua `PipelineRunner` → assert processed=N, mỗi count=1, count_by_label={"object":1}.
2. **P1' count=K:** stub test-local `_KDetector(k)` (trả k Detection MODEL_INPUT) → assert count=k, tổng by_label=k.
3. **P2 bulkhead:** stub `_RaisingDetector` (ném trong detect) → `stage_errors`>0, KHÔNG raise; processed=0.
4. **P3 edge:** (a) chạy CountStage KHÔNG có DetectStage → ERROR (thiếu key). (b) stub trả `[]` → count=0, by_label={}.
5. **P4 sink:** CompositeSink([Collecting, Jsonl(tmp_path)]) → Collecting đủ N; file jsonl N dòng JSON parse được,
   có `event_ts` (ISO parse ok) + box.space=="original" (vì qua DetectorPipeline). Test KHÔNG gắn Jsonl → file không tạo.
6. **P4' source ERROR:** `FakeFrameSource(inject_error_at=i)` → `RunStats.source_errors>=1`, không raise, vẫn tới EOF.
7. **P6 regression:** `pytest -q` (≥369 + mới) · `lint-imports` 5/0 · `get_diagnostics`=0. Dọn tmp sau test (tmp_path tự dọn).

## Quyết định thiết kế (lý do — cho journal)
- **QĐ-1: v1 STATELESS (count/frame), KHÔNG tracking** — né Lỗ 3 (K-042). Tracking = sub-spec sau.
- **QĐ-2: DetectStage tách CountStage** — SRP + `detections` tái dùng cho analytics khác (classify sau đọc chung).
- **QĐ-3: DetectStage bọc `DetectorPipeline`** (không FakeDetector trần) — để box ra **ORIGINAL_FRAME** (đúng khi
  lưu/vẽ); FakeDetector trần trả MODEL_INPUT (sai để lưu). CI vẫn xác định.
- **QĐ-4: event dùng WALL-CLOCK `event_ts` (UTC)** làm mốc chính, capture_time_ns chỉ phụ — vì monotonic vô nghĩa
  khi đọc lại log sau (mốc gốc không xác định). (Đào sâu — sửa lỗi tiềm ẩn ở bản design nông trước.)
- **QĐ-5: CompositeSink** — runner nhận 1 sink nhưng slice cần gom+ghi đồng thời; hợp thành sạch, tái dùng được.
- **QĐ-6: KHÔNG lọc confidence trong CountStage** — SRP; lọc là việc detector/FilterStage. CountStage đếm cái được đưa.
- **QĐ-7: CI dùng FakeFrameSource** (fill=count%256, XÁC ĐỊNH) + inject_error_at cho nhánh lỗi — không phụ thuộc camera/GPU (tránh flaky K-035).

## Self-Review (doubt-driven — lỗ tìm thêm khi đào sâu, đã đưa vào design)
- **Lỗ A (đã sửa):** bản nông ghi `capture_time_ns` (monotonic) làm mốc event → SAI cho log lưu trữ → thêm
  `event_ts` wall-clock UTC (QĐ-4).
- **Lỗ B (đã sửa):** runner nhận 1 sink nhưng cần vừa test vừa lưu → thêm `CompositeSink` (QĐ-5).
- **Lỗ C (đã sửa):** chưa phân biệt thiếu-key (lỗi) vs tuple-rỗng (0 object hợp lệ) → Property 3 + C3.
- **Lỗ D (đã sửa):** FakeDetector trả MODEL_INPUT → nếu bọc trần thì box sai không gian khi lưu → QĐ-3 bọc DetectorPipeline.
- **Lỗ E (đã nêu, giới hạn):** slice sync chặn read → không phải đường RTSP real-time → mục "Giới hạn SYNC vs LIVE".
- **Còn mở có chủ đích (sub-spec sau):** tracking/đếm-không-trùng (Lỗ 3) · async low-latency live · confidence
  FilterStage · classify tầng 2 · cross-process qua SHM.
**Phán quyết:** giờ đủ sâu để THI CÔNG v1 (schema/edge/lifecycle/test cụ thể + bám API thật). Các món "còn mở" là
sub-spec riêng, KHÔNG phải thiếu sót của v1.

## Glossary
- **DetectStage / CountStage** — Stage bọc detector / analytics đếm stateless. Xem C2/C3.
- **CompositeSink** — sink hợp thành forward tới nhiều sink con. Xem C4.
- **JsonlEventSink** — sink ghi 1 JSON/dòng (event_ts wall-clock + count + detections). Lưu trữ optional.
- **event_ts vs capture_time_ns** — mốc thời gian THẬT (wall-clock UTC, cho log) vs monotonic nội bộ (đo trễ).
- **stateless per-frame** — kết quả chỉ phụ thuộc frame hiện tại (đối lập tracking — Lỗ 3, để sau).
- **sync-vs-live** — v1 đồng bộ (throughput/video); real-time RTSP cần async split (sau).
