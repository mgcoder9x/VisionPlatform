# 14.08 — Wiring: `_det_pt` resolve device + `main` bắt `CapabilityError` → exit 2

## 1. Thuộc về đâu
Hai điểm NỐI cuối cùng của chủ đề capability:
- `profiles/pipeline_factory.py::_det_pt` — nơi năng-lực-máy được ÁP vào lúc dựng detector `pt`.
- `profiles/vision_slice_app.py::main` — nơi lỗi năng-lực được BIẾN thành exit code sạch cho operator.

## 2. Cần biết trước
Cả chủ đề: mẩu 01 (`MachineCapabilities`), 02–03 (`resolve_device` thuần + fail-fast `CapabilityError`), 04 (`probe_capabilities` không-raise), 05 (tách DÒ khỏi QUYẾT-ĐỊNH). Mẩu này GHÉP tất cả lại.

## 3. Code thật (quote nguyên văn — `pipeline_factory.py::_det_pt`)
```python
def _det_pt(params: Mapping):
    from vision_platform.adapters.yolov5_pt_detector import Yolov5PtDetector
    _need(params, "weights", "detector pt")
    # Capability-aware: resolve device theo năng lực máy (auto→best / cuda-thiếu→CapabilityError fail-fast).
    # probe TRƯỚC construct (construct không import torch → resolve raise được mà không kéo dep nặng).
    # CapabilityError (RuntimeError) ở đường config → _run_from_config bulkhead cô lập (log + chạy tiếp cam kế).
    caps = probe_capabilities()
    dev = resolve_device(params.get("device", "cpu"), caps)
    # F1/H1 (#324): LOG device THỰC TẾ đã chọn ở ĐÂY (1 nơi, cả đường CLI-direct lẫn config cùng hưởng —
    # chống "tưởng GPU mà chạy CPU", R3.2). Trước: chỉ đường CLI-direct log qua `_resolve_device_logged`.
    print(f"[device] yêu cầu={params.get('device', 'cpu')!r} → dùng={dev!r} "
          f"(has_cuda={caps.has_cuda}, gpu={caps.gpu_name})", file=sys.stderr)
    return Yolov5PtDetector(params["weights"], device=dev)
```

## 4. Giải thích từng mẩu nhỏ nhất (`_det_pt`)
- `caps = probe_capabilities()` — DÒ máy (mẩu 04, không bao giờ raise). Lấy sự-thật-máy trước.
- `dev = resolve_device(params.get("device", "cpu"), caps)` — QUYẾT-ĐỊNH thuần (mẩu 02): trộn "ý muốn user" (`device` trong config, mặc định `"cpu"`) với "sự-thật-máy" (`caps`). Nếu user ép `cuda` mà `caps.has_cuda=False` → **raise `CapabilityError` NGAY tại đây** (fail-fast, chưa kịp import torch).
- Thứ tự **probe TRƯỚC construct**: `Yolov5PtDetector(...)` chỉ được gọi ở dòng cuối, SAU khi device đã hợp lệ → nếu năng lực sai thì thoát sớm, không kéo dep nặng (torch) một cách vô ích.
- `print(f"[device] ... → dùng={dev!r} ...", file=sys.stderr)` — log device THỰC TẾ ở ĐÚNG MỘT NƠI (H1/#324). Cả đường CLI-direct lẫn đường `--config` đều đi qua `_det_pt` → cả hai cùng thấy log này → chống "tưởng chạy GPU mà thực ra CPU".
- `return Yolov5PtDetector(params["weights"], device=dev)` — trao device ĐÃ resolve cho adapter; adapter không tự đoán device nữa.

## 5. Code thật (quote nguyên văn — `vision_slice_app.py::main`, khối CLI-direct)
```python
    from vision_platform.kernel.capabilities import CapabilityError
    from vision_platform.profiles.pipeline_factory import build_runner

    # F1 (#324): CLI-direct DÙNG CHUNG build_runner (1 đường lắp-ráp, xoá hand-assembly) — map cờ → PipelineConfig.
    pcfg = _args_to_pipeline_config(args)
    track_summary = _TrackSummarySink() if args.track else None
    extra_sinks = [track_summary] if track_summary is not None else []

    observer, exporter = _build_config_observability(args.observe, args.metrics_port, args.metrics_host)
    try:
        runner = build_runner(pcfg, observer=observer, emit_every_n=obs_every,
                              emit_interval_s=obs_interval, extra_sinks=extra_sinks)
    except CapabilityError as e:   # H2: ép cuda thiếu GPU → thông báo gọn + exit 2 (không traceback thô)
        print(f"LỖI NĂNG LỰC (device): {e}", file=sys.stderr)
        if exporter is not None:
            exporter.stop()   # exporter đã start trong _build_config_observability → đóng cổng, không rò
        return 2
```

## 6. Giải thích từng mẩu nhỏ nhất (`main`)
- `build_runner(pcfg, ...)` gọi vào factory → cuối cùng chạm `_det_pt` (nếu detector `pt`) → có thể ném `CapabilityError`.
- `except CapabilityError as e:` — bắt ĐÚNG lỗi năng-lực (không nuốt lỗi khác). `CapabilityError` là `RuntimeError` con → nếu KHÔNG bắt sẽ in traceback thô, xấu cho operator.
- `print(f"LỖI NĂNG LỰC (device): {e}", file=sys.stderr)` — thông báo NGƯỜI-ĐỌC-ĐƯỢC ra stderr (một dòng, không traceback).
- `exporter.stop()` trước khi return — nếu `/metrics` đã mở cổng ở `_build_config_observability`, phải ĐÓNG lại, tránh rò cổng/thread khi thoát lỗi.
- `return 2` — exit code RIÊNG cho lỗi năng-lực (khác 0 = OK, khác 1 = lỗi chung). Script/CI phân biệt được "sai device" với lỗi khác.

## 7. Là gì
Hai chỗ "cắm dây": nơi năng-lực máy được ÁP (`_det_pt`) và nơi lỗi năng-lực được BIẾN thành exit code + thông báo sạch (`main`).

## 8. Tại sao tồn tại / vấn đề nó giải
Nếu resolve/probe chỉ nằm rời trong kernel/adapters mà không ai GỌI đúng chỗ thì vô dụng. `_det_pt` là điểm áp năng-lực đúng lúc (trước construct detector). `main` là điểm biến exception kỹ-thuật thành trải-nghiệm-vận-hành tốt (exit 2 + 1 dòng lỗi thay vì traceback).

## 9. Dùng ở đâu
Mọi lần chạy pipeline detector `pt` (cả `--config` lẫn CLI-direct). Máy toann (K-079): config ép `device="cuda"` → `_det_pt` raise → operator thấy `LỖI NĂNG LỰC (device): ...`, exit 2 (không crash traceback).

## 10. Không có nó thì sao
- Không có log ở `_det_pt` → chạy nhầm CPU mà tưởng GPU, không ai biết (R3.2).
- Không bắt `CapabilityError` ở `main` → operator thấy traceback Python thô, khó đọc, exit code lẫn với lỗi khác.
- Không `exporter.stop()` → rò cổng `/metrics` khi thoát lỗi.

## 11. Ví von
`resolve_device` = còi báo "xe không đủ nhiên liệu chạy đường này". `_det_pt` = chỗ bấm còi đúng lúc trước khi lăn bánh. `main` bắt lỗi = bảng điện tử dịch còi thành câu người-đọc-được + tắt máy gọn, thay vì để động cơ gào thét.

## 12. Liên kết bức tranh lớn (KHÉP #14)
Chuỗi capability TRỌN: **DÒ** (`probe_capabilities` @adapters, mẩu 04 — chạm torch, không raise) → **QUYẾT-ĐỊNH** (`resolve_device` @kernel, mẩu 02–03 — thuần, fail-fast) → **DTO** chở kết quả (`MachineCapabilities`, mẩu 01) → **ÁP** (`_det_pt`, mẩu này) → **DỊCH LỖI** (exit 2 @main, mẩu này) → **VẬN HÀNH** (`--capabilities`, mẩu 07) + **TEST MỌI MÁY** (gate GPU, mẩu 06). Tách DÒ/QUYẾT-ĐỊNH (mẩu 05) là điều làm test được năng-lực mà không cần GPU thật.

## 13. Cạm bẫy
- Đặt log device SAI CHỖ (chỉ ở đường CLI-direct) → đường config im lặng (bug cũ trước H1/#324). Đặt ở `_det_pt` = 1 nơi phủ cả 2.
- Quên `exporter.stop()` ở nhánh lỗi → rò cổng.
- Bắt `Exception` chung thay vì `CapabilityError` → nuốt luôn lỗi thật khác. Bắt ĐÚNG loại.
- Ở đường `--config`, `CapabilityError` cô lập trong `_run_from_config` (bulkhead: log + chạy tiếp camera kế) — KHÁC đường CLI-direct (exit 2). Cùng exception, xử theo ngữ cảnh.

## 14. Tự kiểm (Feynman) — CỔNG TỔNG HỢP #14
Trả lời được hết = nắm chủ đề capability:
1. Vẽ dòng chảy 1 lần chạy `pt` trên máy không GPU với `device="cuda"`: `_det_pt` gọi gì → chỗ nào raise → `main` làm gì → exit code bao nhiêu?
2. Vì sao probe (chạm torch, không-raise) phải TÁCH khỏi resolve (thuần, raise)? Nếu gộp làm một thì test-không-GPU vỡ chỗ nào? (nối mẩu 05)
3. Vì sao log device đặt ở `_det_pt` mà KHÔNG ở `main`? (nối H1/#324 — 1 nơi phủ 2 đường)
4. Đường `--config` và đường CLI-direct xử `CapabilityError` KHÁC nhau thế nào, vì sao? (bulkhead vs exit 2)
5. Exit 2 khác exit 1 để làm gì cho CI/script?

## 15. Nguồn
`profiles/pipeline_factory.py::_det_pt` + `profiles/vision_slice_app.py::main` (đọc thật #324/#338) · D-072/D-073 (capability-aware) · H1/H2 (#324). Độ chắc: cao (quote trực tiếp).
