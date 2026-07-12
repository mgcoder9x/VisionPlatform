# F1 — Design: Hợp nhất 2 đường lắp-ráp pipeline (CLI-direct → PipelineConfig → build_runner)

> **Trạng thái:** 🔵 DESIGN-ONLY — chờ user VALID trước khi code (design-first). Gắn LOG #322 · D-088.
> **Nguồn:** review `2026-07-11-architecture-review.md` §F1 (Medium-High). **Bám code thật đã đọc** (`vision_slice_app.main`, `pipeline_factory.build_runner`).

## 1. Vấn đề (đã verify)
`main()` (CLI-direct) tự ráp `source/stages/sinks/observer` bằng TAY (~90 dòng), trong khi `build_runner()`
(đường config) ráp CÙNG việc qua registry → **2 nguồn sự thật**. Hệ quả THẬT: `MotionGateStage` ở CLI-direct
thiếu `pixel_diff_threshold`/`min_area_ratio` (factory có) → cùng khái niệm, năng lực khác. Thêm stage ⇒ sửa 2 chỗ.

## 2. Mục tiêu / Non-goal
- **Mục tiêu:** CLI-direct sinh **1 `PipelineConfig` in-memory** rồi gọi `build_runner` → **1 đường lắp-ráp duy nhất**.
  Xoá ~90 dòng hand-assembly; diệt nguồn phân kỳ.
- **Non-goal (v1):** KHÔNG thêm cờ CLI mới cho pixel_diff_threshold/min_area_ratio (giữ CLI như cũ; config vẫn là
  nơi tinh chỉnh sâu). KHÔNG đổi schema TOML. KHÔNG đổi output summary (backward-compat từng dòng).

## 3. Thiết kế đề xuất
### 3.1 Hàm thuần `_args_to_pipeline_config(args) -> PipelineConfig` (mới, trong profile)
Map cờ CLI → `PipelineConfig` (thuần, test được không I/O):
- `source`: fake→`{max_frames: args.frames}` · noise→`{max_frames: args.frames}` · video→`{path: args.video}` ·
  rtsp→`{url: args.rtsp, max_reconnect: args.max_reconnect}`.
- `detector`: fake→`{model_size: args.model_size}` · pt→`{weights: args.weights, device: args.device}`.
- `stages` (GIỮ THỨ TỰ hiện tại): `[motion_gate?]` + `detect` + `count` + `[track?]` + `[line_crossing?]`.
  - motion_gate params: `{max_consecutive_skip, roi, illumination_robust}` (khớp cờ CLI hiện có).
  - track params: `{iou_threshold: args.track_iou, max_age: args.track_max_age}` (ĐỔI TÊN cờ→param registry).
  - line_crossing params: `{ax,ay,bx,by}` (parse từ `args.line`).
- `sinks`: `jsonl(--out)?` + `crossing_events(--crossing-out)?` + `crossing_events_sqlite(--crossing-db)?`.
- `max_frames`: `args.max_frames` (cờ `--max-frames`, cho rtsp/video).

### 3.2 `build_runner` thêm 1 param additive `extra_sinks: Sequence[ISink] = ()`
Vì sao CẦN: đường CLI in summary `unique_tracks/crossings` qua `_TrackSummarySink` (đọc artifacts) — sink NÀY là
concern PRESENTATION, KHÔNG thuộc config. `build_runner` dựng `CompositeSink` NỘI BỘ → không chèn được từ ngoài.
→ thêm `extra_sinks` (append vào composite sau các sink từ config). CLI truyền `[_TrackSummarySink()]` khi `--track`
+ giữ tham chiếu để in. Additive, default `()` → đường config KHÔNG đổi hành vi.

### 3.3 CLI-direct path (main) rút gọn
```
pcfg = _args_to_pipeline_config(args)
track_summary = _TrackSummarySink() if args.track else None
extra = [track_summary] if track_summary else []
try:
    runner = build_runner(pcfg, observer=observer, emit_every_n=obs_every,
                          emit_interval_s=obs_interval, extra_sinks=extra)
except CapabilityError as e:   # GIỮ: ép cuda thiếu GPU → exit 2 (không traceback thô)
    print(...); return 2
try:
    stats = runner.run(max_frames=args.max_frames)
finally:
    if exporter is not None: exporter.stop()
_print_summary(stats, track_summary, args)   # tách hàm (F2)
```

## 4. TỰ REVIEW ĐỐI KHÁNG (hố phải xử trước khi code)
- **H1 — device log mất:** CLI hiện dùng `_resolve_device_logged` (in `[device] yêu cầu→dùng`); `_det_pt` (registry)
  resolve IM LẶNG. Unify → mất dòng log đó. **Xử:** thêm log device VÀO `_det_pt` (1 nơi, cả 2 đường cùng hưởng) —
  đúng tinh thần "1 nguồn". KHÔNG giữ `_resolve_device_logged` riêng.
- **H2 — CapabilityError exit-code:** CLI-direct phải giữ exit 2 khi ép cuda thiếu GPU. `build_runner` gọi `_det_pt`
  → `resolve_device` raise `CapabilityError` (RuntimeError). **Xử:** main bắt `CapabilityError` quanh `build_runner`
  (như hiện tại quanh `_build_detector`). Đường config KHÔNG đổi (bulkhead `_run_from_config` tự cô lập).
- **H3 — `--frames` vs `--max-frames`:** fake/noise dùng `--frames` (→ source.max_frames); rtsp/video dùng
  `--max-frames` (→ runner.run). **Xử:** map `--frames` vào `source.params.max_frames`; `--max-frames` vào
  `pcfg.max_frames` + `runner.run(max_frames=args.max_frames)`. (Hiện main gọi `runner.run(max_frames=args.max_frames)`
  — GIỮ; pcfg.max_frames=args.max_frames để đồng nhất, KHÔNG double vì run() override.) → cần kiểm `build_runner`
  KHÔNG tự truyền pcfg.max_frames vào run (nó không gọi run — chỉ main gọi). ✅ an toàn.
- **H4 — validate cờ:** `_validate(args, parser)` (rtsp cần --rtsp, pt cần --weights, --line cần --track...) phải chạy
  TRƯỚC khi map. **Xử:** giữ `_validate` nguyên, gọi trước `_args_to_pipeline_config`.
- **H5 — motion-gate param gap → ✅ ĐÃ KIỂM (#323): defaults KHỚP, AN TOÀN.** `MotionGateStage.__init__`
  default `pixel_diff_threshold=25, min_area_ratio=0.005`; `_stage_motion_gate` dùng `get(...,25)`/`get(...,0.005)`
  = ĐÚNG default đó; CLI-direct hiện KHÔNG truyền 2 param này (dùng __init__ default). → map qua config (bỏ 2
  param) cho ra hành vi Y HỆT. Đối chiếu thêm: fake model_size 640=640 · track iou 0.3=0.3/max_age 30=30 · fake
  source max_frames 20=20 — MỌI default khớp → unify KHÔNG đổi hành vi im lặng.
- **H6 — test backward-compat:** phải giữ `test_vision_slice*.py` xanh (output summary + exit codes). Thêm test
  `_args_to_pipeline_config` (thuần, map đúng) + test CLI-direct qua build_runner cho ra runner tương đương.

## 5. Kế hoạch code (SAU khi user valid) — TDD
1. Thêm `extra_sinks` vào `build_runner` (+ test đường config không đổi + extra_sinks append đúng).
2. Thêm log device vào `_det_pt` (H1).
3. Viết `_args_to_pipeline_config` + test thuần (mọi tổ hợp cờ → pcfg đúng).
4. Rút gọn `main()` CLI-direct dùng build_runner + tách `_print_summary` (H2 exit-2 giữ).
5. Xoá hand-assembly cũ. Verify: full suite ≥624 · lint 5/0 · drift PASS. Kỳ vọng KHÔNG giảm test.

## 6. Rủi ro & quyết định
- **Rủi ro chính:** đổi hành vi im lặng (H5 default motion-gate, H1 device log). Giảm thiểu: kiểm default TRƯỚC code + giữ test cũ xanh.
  → **H5 ĐÃ KIỂM (#323): defaults KHỚP hết → rủi ro-đổi-hành-vi-im-lặng ở motion-gate = KHÔNG CÓ.** Còn H1 (device-log-chuyển-chỗ) là chủ đích.
- **Nếu H5 lộ default lệch:** căn chỉnh để `_args_to_pipeline_config` truyền default GIỐNG hành vi cũ (không đổi mặc định người dùng đang thấy).
- **Đề xuất:** LÀM (giá trị: 1 nguồn lắp-ráp, đóng phân kỳ, giảm ~90 dòng). Nhưng CHỜ user valid design này (nhất là chấp nhận H1 device-log-chuyển-chỗ + Non-goal không thêm cờ motion-gate).
