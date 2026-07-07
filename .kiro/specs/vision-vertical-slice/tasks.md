# Implementation Plan

> **Trạng thái:** PHA 1 (tasks) — kế hoạch atomic theo `design.md` (đã đào sâu, 0-diagnostic). CHỜ user duyệt → PHA 2 code TDD.

## Overview

Hiện thực lát cắt dọc `source → DetectStage → CountStage → sink` chạy qua `PipelineRunner`, TDD, ADDITIVE (không
sửa lõi cũ), giữ 369 test cũ + lint 5/0 + 0 diagnostic. Thứ tự: nền (ISink/runner/composite) → stage (detect/count)
→ sink file → profile+test tích hợp → verify. Mỗi task chỉ ✅ khi có bằng chứng chạy thật (lệnh + output).

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"], "reason": "nền port ISink — mọi thứ phụ thuộc" },
    { "wave": 2, "tasks": ["2", "3", "4", "5", "6"], "reason": "song song sau T1: runner/composite/detect/count/jsonl độc lập nhau" },
    { "wave": 3, "tasks": ["7"], "reason": "profile + test tích hợp cần T2..T6" },
    { "wave": 4, "tasks": ["8"], "reason": "verify toàn cục + journal" }
  ],
  "dependencies": {
    "1": [],
    "2": ["1"],
    "3": ["1"],
    "4": [],
    "5": [],
    "6": ["1"],
    "7": ["2", "3", "4", "5", "6"],
    "8": ["7"]
  }
}
```
- T1 mở đầu (nền port). T2/T3/T6 phụ thuộc T1. T4/T5 độc lập. T7 cần T2..T6. T8 cuối.

## Tasks

- [x] 1. Port `ISink` (kernel/ports/sink.py) + test conformance ✅ (isinstance CollectingSink pass, lint 5/0)
  - Protocol @runtime_checkable: `setup()` · `handle(result: ExecutionResult)` · `teardown()`. Chỉ import kernel.
  - Test: 1 impl giả thoả ISink (isinstance) — giữ lint 5/0.
  - _Requirements: 1.1, 1.2_

- [x] 2. `PipelineRunner` + `RunStats` (runtime/pipeline_runner.py) + tests ✅ (end-to-end/bulkhead/source-error/composite pass)
  - DI source/executor/sink + media_ref_factory(mặc định InMemoryArrayRef.from_copy) + clock_ns + stop (max_frames/should_stop).
  - Vòng: read→xử ReadStatus(EOF/ERROR/no-data)→MediaPacket→execute→sink.handle(mọi status)→RunStats; teardown finally sink→executor→source.
  - Tests: end-to-end đếm khớp · source ERROR không raise · teardown-on-raise · stop conditions.
  - _Requirements: 1.1, 1.3_

- [x] 3. `CompositeSink` (runtime/composite_sink.py) + test ✅ (forward 2 sink pass)
  - Thoả ISink; setup thuận, teardown ngược + nuốt-lỗi-từng-cái; handle forward tất cả.
  - _Requirements: 4.1_

- [x] 4. `DetectStage` (runtime/stages/detect_stage.py) + test ✅ (detections ghi đúng + bulkhead pass)
  - `__init__(detector: IDetector)`; setup/teardown ủy quyền; `_do_process` → artifacts["detections"]=tuple(dets). STATELESS.
  - Test: ghi detections đúng (space tag giữ) · detector ném → StageResult.ERROR (bulkhead, không raise).
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5. `CountStage` (runtime/stages/count_stage.py) + test edge ✅ (thiếu-key→ERROR, rỗng→0, count/by_label pass)
  - artifacts["detections"]: None→ERROR (thiếu key) · ()→count=0/by_label={} · có→count=len + count_by_label theo label. STATELESS.
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. `JsonlEventSink` (adapters/jsonl_event_sink.py) + test tmp_path ✅ (N dòng JSON, event_ts Z, box.space=original)
  - setup: mkdir cha + mở "a" utf-8 fail-fast; handle SUCCESS→1 dòng JSON (event_ts UTC ISO + capture_time_ns + source_id + count + count_by_label + detections[box+space]) + flush; teardown đóng.
  - Test: N dòng JSON parse được, event_ts parse ISO, box.space=="original"; không gắn → không tạo file.
  - _Requirements: 4.2, 4.3_

- [x] 7. Profile `profiles/vision_slice_app.py` + test CI tích hợp XÁC ĐỊNH ✅ (10 test slice pass, wire + validate)
  - Wire: source→DetectStage(DetectorPipeline(detector,sz,sz))→CountStage→CompositeSink→PipelineRunner.run. Cờ (bảng C5) + validate fail-fast.
  - Test CI: FakeFrameSource(N)+FakeDetector → processed=N, count=1, by_label={"object":1}, sink đủ; + stub K/rỗng/raise; + inject_error_at→source_errors.
  - Chế độ thật (rtsp/pt/video) KHÔNG chạy trong pytest.
  - _Requirements: 5.1, 5.2, 6.1, 6.2_

- [x] 8. VERIFY thật + cập nhật journal ✅
  - `pytest -q` → **379 passed / 1 skipped** (369+10). `lint-imports` → **5 kept / 0 broken**. `get_diagnostics`=0. tmp_path tự dọn.
  - LOG #218 + activeContext + INDEX (D-041 → ✅, baseline 369→379).
  - _Requirements: 1.3, 5.3_

## Notes

- ADDITIVE tuyệt đối: KHÔNG sửa `MediaPacket`/executor/SHM/ZMQ cũ — chỉ THÊM file mới. Giữ 369 test cũ xanh.
- CI XÁC ĐỊNH: chỉ Fake/Noise + FakeDetector/stub (không camera/GPU/mạng — tránh flaky K-035). Chế độ thật ngoài pytest.
- v1 STATELESS (né Lỗ 3 K-042). Tracking/đếm-không-trùng · async low-latency live · classify tầng-2 · cross-process SHM = sub-spec SAU.
- Mỗi task: test trước/cùng, chạy THẬT mới ✅ (bằng chứng lệnh+output). Không đánh ✅ suông.
