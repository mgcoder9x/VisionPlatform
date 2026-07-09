# Design Document

> **Trạng thái:** PHA 1 (design SÂU) — CHỜ user đọc-lại-valid trước khi code (PHA 2).
> **Gắn với:** `requirements.md` cùng thư mục · scale-architecture R2.4 · dùng `SkipFrameSignal` (đã có).
> **Cập nhật lúc:** 2026-07-09.

## Overview

`MotionGateStage` (CPU, rẻ) đứng TRƯỚC `DetectStage`: đo tỉ lệ pixel đổi giữa frame này ↔ frame trước; nếu <
ngưỡng (cảnh tĩnh) → `raise SkipFrameSignal` → frame bị SKIP (detector không chạy). Giảm tải GPU cho ~100 camera.

```
source → MotionGateStage(--motion-gate) → DetectStage → TrackingStage → ... → sink
              │ đủ chuyển động → đi tiếp (+ artifacts["motion_ratio"])
              └ tĩnh → SkipFrameSignal → SKIPPED (detector KHÔNG chạy, RunStats.skipped++)
```

**Vì sao gốc, không ngọn:** không tối ưu detector (khó, GPU) mà GIẢM SỐ LẦN gọi detector (gate rẻ) — đúng bản chất
bài toán GPU-bound đa-camera (R2.4). Dùng `SkipFrameSignal` có sẵn (không thêm cơ chế skip mới = không đập lõi executor).

**Nền đã đọc code thật (chống bịa):**
- `base_stage.py`: `_do_process` raise `SkipFrameSignal` → `except SkipFrameSignal → StageResult.skipped(reason, stage)`.
- `sync_linear_executor.py`: stage non-SUCCESS → `ExecutionResult.from_stage_result` → **dừng chuỗi** (stage sau không chạy).
- `pipeline_runner.py`: `StageStatus.SKIPPED → skipped += 1`; sink.handle vẫn được gọi (mọi status).
- `media_packet.py`: `packet.media_ref.array` (np.ndarray uint8, read-only by contract) → đọc để diff (không ghi).
- `stage_contract.py`: `SkipFrameSignal(Exception)` sẵn.

## Architecture

```
   domain/motion.py            : changed_ratio(prev, curr, pixel_diff_threshold) -> float  (THUẦN numpy)
                    ▲ dùng
   runtime/stages/motion_gate_stage.py : MotionGateStage(BaseStage)
       - params pixel_diff_threshold/min_area_ratio · state _prev (np.ndarray) · _source_id guard
       - _do_process: prev None|shape khác → pass+lưu; else ratio=changed_ratio; ratio<min → SkipFrameSignal; else pass + artifact
```
**Layer:** `domain/motion.py` THUẦN (numpy — luật cho phép domain dùng numpy; KHÔNG cv2/torch). `MotionGateStage`@runtime.
Không phá 5 contract (runtime→domain/kernel OK).

## Components and Interfaces

### C1 — `domain/motion.py::changed_ratio` (thuần numpy)
```
import numpy as np
def changed_ratio(prev: np.ndarray, curr: np.ndarray, pixel_diff_threshold: int) -> float:
    # |curr - prev| theo int (tránh underflow uint8) > threshold → phần tử "đổi"; trả tỉ lệ [0,1].
    diff = np.abs(curr.astype(np.int16) - prev.astype(np.int16))
    changed = np.count_nonzero(diff > pixel_diff_threshold)
    return changed / diff.size if diff.size else 0.0
```
- **QUAN TRỌNG (bug tiềm ẩn):** uint8 - uint8 UNDERFLOW (250-10 OK nhưng 10-250 wrap 255) → PHẢI cast `int16` trước khi trừ (đã đọc: array là uint8). Không cast = motion sai.
- Yêu cầu `prev.shape == curr.shape` (caller đảm bảo — shape khác xử ở Stage).

### C2 — `runtime/stages/motion_gate_stage.py::MotionGateStage(BaseStage)`
- `__init__(self, *, pixel_diff_threshold: int = 25, min_area_ratio: float = 0.005)`. `super().__init__("motion_gate")`.
- State: `self._prev: np.ndarray | None = None` · `self._source_id: str | None = None`.
- `_do_process(packet)`:
  - Camera-affinity (R3.2): set/kiểm `packet.source_id` (mixed → raise ValueError).
  - `curr = packet.media_ref.array`.
  - Nếu `self._prev is None` OR `self._prev.shape != curr.shape` (R1.3/R2.3): `self._prev = curr`; return `packet.with_artifact("motion_ratio", 1.0)` (coi như có chuyển động — cho đi tiếp; frame đầu/đổi-shape KHÔNG bỏ).
  - `ratio = changed_ratio(self._prev, curr, self._pixel_diff_threshold)`; `self._prev = curr`.
  - `if ratio < self._min_area_ratio`: `raise SkipFrameSignal(f"no motion (ratio={ratio:.4f} < {min})")` → SKIPPED.
  - else: return `packet.with_artifact("motion_ratio", ratio)`.
- `teardown()`: `self._prev = None`.
- **KHÔNG sửa DetectStage** — chỉ đứng trước. Frame skip → detector không chạy (executor dừng chuỗi).

### C3 — Đăng ký config + CLI
- `pipeline_factory`: `_stage_motion_gate(params, detector)` → `MotionGateStage(pixel_diff_threshold=params.get(...,25), min_area_ratio=params.get(...,0.005))`; `allowed_params={"pixel_diff_threshold","min_area_ratio"}`; registry `stages["motion_gate"]`.
- `vision_slice_app`: cờ `--motion-gate` → chèn `MotionGateStage()` ĐẦU chuỗi (trước detect).

## Data Models
Artifact thêm: `motion_ratio: float` (chỉ trên frame ĐI TIẾP; frame skip không có packet). Quan sát/tuning ngưỡng.

## Correctness Properties

### Property 1: Frame tĩnh bị skip (detector không chạy)
2 frame giống hệt liên tiếp → frame thứ 2 SKIPPED (ratio=0 < min). Qua PipelineRunner: `skipped` tăng, `processed` không tăng cho frame đó; nếu có DetectStage sau → detector KHÔNG được gọi.
**Validates: Requirements 1.1, 2.1**

### Property 2: Frame chuyển động đi tiếp + artifact
Frame đổi nhiều (ratio ≥ min) → trả packet + `artifacts["motion_ratio"]≈ratio`; đi tiếp DetectStage.
**Validates: Requirements 1.2, 2.2**

### Property 3: Frame đầu + đổi shape → đi tiếp
Frame đầu (prev None) → đi tiếp (motion_ratio=1.0), lưu mốc. Frame sau khác shape → đi tiếp + cập nhật mốc.
**Validates: Requirements 1.3, 2.3**

### Property 4: uint8 underflow xử đúng
prev sáng (250), curr tối (10): |10-250|=240 (cast int16) > threshold → ĐỔI. Nếu KHÔNG cast → wrap = 16 (sai). Test khẳng định ratio cao (không bị underflow nuốt).
**Validates: Requirements 2.1**

### Property 5: camera-affinity + không hồi quy
source lạ → ERROR. 511 test cũ xanh + mới; lint 5/0; 0 diagnostic; additive (không sửa executor/detect).
**Validates: Requirements 3.2, 4.3**

## Error Handling
- Mixed source_id → ValueError → ERROR (không trộn mốc).
- `media_ref.array` read-only → chỉ đọc (diff), không ghi → an toàn.
- SkipFrameSignal KHÔNG phải lỗi (là tín hiệu skip có chủ đích) → SKIPPED, không phải ERROR.

## Testing Strategy
`tests/test_motion_gate.py` (CI, XÁC ĐỊNH):
1. **domain unit:** `changed_ratio` — giống hệt→0.0; đổi hết→1.0; underflow (250↔10)→cao (P4).
2. **P1 skip tĩnh:** stage: frame1 (pass, đầu) → frame2 giống frame1 → StageResult.SKIPPED (reason chứa "motion").
3. **P2 đi tiếp:** frame2 đổi nhiều → SUCCESS + artifacts["motion_ratio"]>0.
4. **P3 first/shape:** frame đầu → SUCCESS (ratio 1.0); frame khác shape → SUCCESS.
5. **P5 mixed source:** đổi source_id → ERROR.
6. **integration:** PipelineRunner [MotionGate, DetectStage(stub đếm gọi), Count] + source phát frame trùng → detector gọi < số frame (skip thật) + RunStats.skipped>0.
7. **config/CLI:** build_runner stage `motion_gate` + `main(--motion-gate ...)` rc0. `scripts\vp.cmd verify` ≥511+mới.

## Quyết định thiết kế (lý do)
- **QĐ-1: dùng SkipFrameSignal có sẵn** (không cơ chế skip mới) — executor/runner đã xử SKIPPED đúng; fix bản chất, zero đập lõi.
- **QĐ-2: cast int16 trước trừ** — tránh underflow uint8 (bug tinh vi) → motion đúng. (Điểm "code chuẩn".)
- **QĐ-3: frame đầu/đổi-shape → ĐI TIẾP (không skip)** — thiếu mốc để quyết → an toàn KHÔNG bỏ nhầm (thà chạy thừa hơn bỏ sót sự kiện).
- **QĐ-4: gate đứng TRƯỚC detect** (không tối ưu detect) — giảm SỐ LẦN inference = lever GPU đúng bài (R2.4).
- **QĐ-5: motion=tỉ-lệ-pixel-đổi full-frame** (không MOG2/optical-flow) — rẻ, đủ, xác định; nâng cao là sub-spec sau.

## Self-Review (doubt-driven)
- **Lỗ 1 (đã xử):** uint8 underflow → cast int16 (QĐ-2, P4).
- **Lỗ 2 (đã xử):** frame đầu không có mốc → đi tiếp (QĐ-3), không crash/không bỏ nhầm.
- **Lỗ 3 (đã xử):** đổi độ phân giải giữa chừng → shape khác → đi tiếp + reset mốc (R2.3).
- **Lỗ 4 (đã xử):** trộn camera → fail-fast source_id.
- **Còn mở (sub-spec sau):** background-subtraction (MOG2) chịu thay-đổi-ánh-sáng · ROI-mask (chỉ gate vùng quan tâm) · downscale tối ưu tốc độ · min-frame-interval (luôn chạy 1 frame/N kể cả tĩnh, chống miss).
**Phán quyết:** đủ sâu để THI CÔNG (metric + skip-mechanism + edge + test cụ thể, bám code thật). Món "còn mở" là sub-spec riêng.

## Glossary
- **changed_ratio** — hàm domain: tỉ lệ pixel đổi (cast int16 chống underflow).
- **MotionGateStage** — Stage CPU chặn frame tĩnh (SkipFrameSignal) trước detector.
- **min_area_ratio / pixel_diff_threshold** — ngưỡng tỉ-lệ-đổi / ngưỡng-chênh-pixel.
