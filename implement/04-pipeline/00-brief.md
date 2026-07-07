# Vấn đề #04 — StageContract + BaseStage + SyncLinearExecutor + 2 stage + composition root

> Nguồn Design (đọc trực tiếp): `Design/module-03-build-along/step-04-first-pipeline.md`.

## Mục tiêu (xong = gì)
Pipeline chạy end-to-end: `source → BrightnessStage → DarkFilterStage → output`, sync executor,
+ composition root (profiles). **11–12 test pass** + demo CLI chạy.

## File sẽ tạo (7) — đổi `vision_demo`→`vision_platform`
1. `kernel/stage_contract.py` — `StageStatus`, `StageResult`, `ExecutionResult`, `SkipFrameSignal`, `IStage`.
2. `runtime/base_stage.py` — `BaseStage` (Template Method: process() bắt lỗi, _do_process() abstract).
3. `runtime/sync_linear_executor.py` — `SyncLinearExecutor` (chạy tuyến tính, dừng ở non-SUCCESS đầu tiên).
4. `runtime/stages/brightness_stage.py` — tính mean → artifact `brightness` (CoW).
5. `runtime/stages/dark_filter_stage.py` — `SkipFrameSignal` nếu brightness < threshold.
6. `profiles/demo_pipeline.py` — composition root (lazy import adapter; `from_copy`; try/finally; summary stderr).
7. `tests/test_step_04_pipeline.py` — 12 test.

## Concept cốt lõi (để học/viết lại)
- **Result-object (`ExecutionResult`) thay `Optional[MediaPacket]`**: phân biệt SKIPPED (filter cố ý)
  vs ERROR (stage lỗi) — `None` gộp cả 2 là bug (R5-CRITICAL-02).
- **`StageResult` KHÔNG giữ `Exception` object** — chỉ string snapshot (chống traceback retention).
- **CoW**: stage không mutate input, trả packet mới (`with_artifact`).
- **Composition root** = chỗ DUY NHẤT biết adapter cụ thể (lazy import).

## Trạng thái
- ✅ **XONG + validate thật**: `pytest` → **64 passed, 1 skipped** (13 step-04, +1 E-14 context manager) · `lint-imports` → **5 kept/0 broken**.
- Demo end-to-end (fake, 5 frames, threshold 100): Processed 0 / Skipped 5 / EOF 1 — khớp kỳ vọng Design.
- Review #04: Risk1a (teardown xuôi) là BỊA (code đã `reversed`); Risk4 thêm context manager (E-14); Risk1b/2/3 ghi nhận.
