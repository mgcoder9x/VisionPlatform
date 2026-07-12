# 11.14 — F1: `_args_to_pipeline_config` — CLI cũng sinh `PipelineConfig` → cùng `build_runner`

## 1. Thuộc về đâu
profiles — `profiles/vision_slice_app.py::_args_to_pipeline_config`. Đây là mảnh của F1 (#324) — hợp nhất đường CLI-direct vào cùng đường lắp-ráp với `--config`.

## 2. Cần biết trước
mẩu 03 (cây DTO), mẩu 08+13 (registry + `build_runner`). Bối cảnh F1: xem `docs/ARCHITECTURE.md` §12 + `review/2026-07-11-architecture-review.md` §F1.

## 3. Code thật (quote nguyên văn — `vision_slice_app.py`)
```python
def _args_to_pipeline_config(args):
    from vision_platform.kernel.config import (
        PipelineConfig, SourceConfig, StageConfig, SinkConfig, DetectorConfig,
    )
    # --- source ---
    if args.source in ("fake", "noise"):
        source = SourceConfig(args.source, {"max_frames": args.frames})
    elif args.source == "video":
        source = SourceConfig("video", {"path": args.video})
    else:  # rtsp (đã validate có --rtsp)
        source = SourceConfig("rtsp", {"url": args.rtsp, "max_reconnect": args.max_reconnect})
    # --- detector ... ---
    # --- stages (GIỮ THỨ TỰ hiện tại) ---
    stages = []
    if args.motion_gate:
        mg = {"max_consecutive_skip": args.motion_gate_max_skip, "illumination_robust": args.motion_gate_illum_robust}
        if args.motion_gate_roi:
            mg["roi"] = tuple(float(p) for p in args.motion_gate_roi.split(","))
        stages.append(StageConfig("motion_gate", mg))
    stages.append(StageConfig("detect", {}))
    stages.append(StageConfig("count", {}))
    if args.track:
        stages.append(StageConfig("track", {"iou_threshold": args.track_iou, "max_age": args.track_max_age}))
    if args.line:
        ax, ay, bx, by = (float(p) for p in args.line.split(","))
        stages.append(StageConfig("line_crossing", {"ax": ax, "ay": ay, "bx": bx, "by": by}))
    # --- sinks ... ---
    return PipelineConfig(id="cli", source=source, stages=stages, sinks=sinks, detector=detector, max_frames=args.max_frames)
```
(quote LƯỢC phần detector/sinks — xem file thật; dấu `...` = đã lược excerpt.)

## 4. Giải thích từng mẩu nhỏ nhất
- Nhận `args` (kết quả `argparse`) → dựng các `*Config` (mẩu 03) y như config TOML dựng ra.
- Map cờ → params đúng tên registry: `--track-iou`→`iou_threshold`, `--track-max-age`→`max_age` (mẩu 08 builder đọc tên này).
- Thứ tự stage suy từ cờ: `[motion_gate?]`→`detect`→`count`→`[track?]`→`[line?]` (GIỮ đúng hành vi cũ).
- `id="cli"` — CLI-direct chỉ 1 pipeline nên id cố định.
- Trả `PipelineConfig` → `main` gọi `build_runner(pcfg, ...)` (mẩu 13) — **cùng đường với `--config`**.

## 5. Là gì
Hàm THUẦN biến cờ dòng lệnh → 1 `PipelineConfig` in-memory (không đọc file, test được).

## 6. Tại sao tồn tại / vấn đề nó giải
TRƯỚC F1: `main()` tự ráp source/stages/sinks bằng TAY (~90 dòng), song song với `build_runner` (đường config)
→ **2 nguồn lắp-ráp** → phân kỳ (vd motion-gate CLI thiếu tham số mà config có). `_args_to_pipeline_config` biến
CLI thành "bộ sinh config" → dùng chung `build_runner` → **1 nguồn lắp-ráp duy nhất** (fix GỐC review F1).

## 7. Dùng ở đâu
`vision_slice_app.main` (nhánh KHÔNG `--config`): `pcfg = _args_to_pipeline_config(args)` → `build_runner(pcfg, observer=..., extra_sinks=...)` (mẩu 15) → `runner.run(...)`.

## 8. Không có nó thì sao
Quay lại 2 đường lắp-ráp song song → thêm stage phải sửa 2 chỗ → dễ quên → phân kỳ hành vi (drift khó thấy).
Chính là vấn đề F1 review chỉ ra.

## 9. Ví von
Thay vì "thợ CLI" và "thợ TOML" mỗi người lắp xe theo cách riêng → giờ cả hai đều viết CÙNG một "phiếu đặt xe"
(`PipelineConfig`) rồi đưa CÙNG một dây chuyền (`build_runner`).

## 10. Liên kết bức tranh lớn
Đóng phát hiện F1 (`docs/ARCHITECTURE.md` §12: F1 ✅). Nối `build_runner` (mẩu 13). Verify: default cờ KHỚP
default builder (kiểm #323) → hợp nhất KHÔNG đổi hành vi im lặng.

## 11. Cạm bẫy
- `_validate(args, parser)` PHẢI chạy TRƯỚC hàm này (H4 design F1) — hàm giả định cờ đã hợp lệ (vd `--line` cần `--track`).
- Tên params phải khớp `allowed_params` builder (mẩu 10) — sai tên → `_check_params` báo lỗi lúc build.

## 12. Tự kiểm (Feynman)
- Trước F1, vì sao 2 đường lắp-ráp gây "phân kỳ"? Cho 1 ví dụ thật (gợi ý: motion-gate params).
- `_args_to_pipeline_config` là hàm thuần — lợi cho test thế nào (so với test cả `main`)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`vision_slice_app.py::_args_to_pipeline_config` (đọc thật #324) · F1/D-088 · review §F1 · #323 (default khớp). Độ chắc: cao (quote trực tiếp; excerpt có đánh dấu `...`).
