# 11.13 — `build_runner`: ráp source + stages + sinks → `PipelineRunner` sẵn chạy

## 1. Thuộc về đâu
profiles — `pipeline_factory.py::build_runner`. ĐÍCH cuối của chuỗi config: `PipelineConfig` → object chạy được.

## 2. Cần biết trước
mẩu 08 (registry), 10 (`_check_params`), 11 (`_lookup`). `SyncLinearExecutor`/`CompositeSink`/`PipelineRunner` (bài #04).

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`, phần thân)
```python
    detector = None
    if pcfg.detector is not None:
        db = _lookup(registry, "detectors", pcfg.detector.type)
        _check_params(db, f"detector '{pcfg.detector.type}'", pcfg.detector.params)
        detector = db(pcfg.detector.params)

    sb = _lookup(registry, "sources", pcfg.source.type)
    _check_params(sb, f"source '{pcfg.source.type}'", pcfg.source.params)
    source = sb(pcfg.source.params)

    stages = []
    for st in pcfg.stages:
        stb = _lookup(registry, "stages", st.type)
        _check_params(stb, f"stage '{st.type}'", st.params)
        stages.append(stb(st.params, detector))

    sinks = []
    for sk in pcfg.sinks:
        skb = _lookup(registry, "sinks", sk.type)
        _check_params(skb, f"sink '{sk.type}'", sk.params)
        sinks.append(skb(sk.params))
    sinks.extend(extra_sinks)   # F1/#324: sink presentation ngoài-config (vd _TrackSummarySink) — append cuối

    executor = SyncLinearExecutor(stages)
    sink = CompositeSink(sinks)
    return PipelineRunner(source, executor, sink, observer=observer,
                          emit_every_n=emit_every_n, emit_interval_s=emit_interval_s)
```

## 4. Giải thích từng mẩu nhỏ nhất
- Dựng `detector` TRƯỚC (nếu có) — vì stage builder nhận `detector` làm tham số (`stb(st.params, detector)`;
  `_stage_detect` cần nó, các stage khác bỏ qua).
- Mỗi phần: `_lookup` (type hợp lệ) → `_check_params` (params hợp lệ) → gọi builder (`sb(params)`) → object thật.
  Thứ tự kiểm-TRƯỚC-gọi quan trọng: `_check_params` chạy TRƯỚC lazy-import trong builder → typo bị chặn trước cả
  khi kéo torch/cv2 (an toàn máy no-GPU).
- `stages` theo ĐÚNG thứ tự khai trong config (list) → chuỗi xử lý đúng ý.
- `sinks.extend(extra_sinks)` — F1 (#324): append sink presentation ngoài-config (vd `_TrackSummarySink` để CLI
  in summary) — default `()` → đường config không đổi (mẩu 15 đào sâu).
- Ráp: `SyncLinearExecutor(stages)` + `CompositeSink(sinks)` → `PipelineRunner(source, executor, sink, observer, ...)` sẵn `.run()`.

## 5. Là gì
Hàm biến 1 `PipelineConfig` (dữ liệu bất biến) thành 1 `PipelineRunner` (object chạy được), qua registry.

## 6. Tại sao tồn tại / vấn đề nó giải
Đây là "động từ" của config: nơi DUY NHẤT ráp adapter thật vào ports. Tập trung tại 1 hàm → mọi đường (config
TOML lẫn CLI sau F1) dùng chung → không phân kỳ (mẩu 14–15). Kiểm (`_lookup`/`_check_params`) nhúng ngay trong
đường dựng → an toàn kể cả khi bỏ qua `validate_config` (như `_run_from_config` gọi thẳng build_runner).

## 7. Dùng ở đâu
- `vision_slice_app._run_from_config`: `for pcfg in app.pipelines: runner = build(pcfg); runner.run(...)` (`build`=build_runner mặc định).
- `vision_slice_app.main` (CLI-direct, F1/#324): `build_runner(_args_to_pipeline_config(args), extra_sinks=...)`.

## 8. Không có nó thì sao
Không có `build_runner` tập trung → mỗi đường (config, CLI) tự ráp tay → phân kỳ (đúng vấn đề F1). Đây chính là
"1 nguồn lắp-ráp" mà F1 hợp nhất về.

## 9. Ví von
Dây chuyền lắp ráp: nhận "phiếu đặt xe" (`PipelineConfig`) → lắp động cơ (source) + các bộ phận (stages) + đầu ra
(sinks) theo đúng phiếu → xe chạy được (`PipelineRunner`).

## 10. Liên kết bức tranh lớn
Bước 3 (cuối) của chuỗi 3 tầng (cau-chuyen): load → parse/validate → **build**. Nối engine `PipelineRunner.run()`
(bài #04 / `docs/ARCHITECTURE.md` §4).

## 11. Cạm bẫy
- Thứ tự `_check_params` TRƯỚC gọi builder — nếu đảo, typo chỉ lộ sau khi đã kéo torch (chậm + có thể crash máy no-GPU).
- `stb(st.params, detector)` — mọi stage builder nhận 2 tham số `(params, detector)` cho đồng nhất chữ ký (dù count/motion bỏ qua detector).

## 12. Tự kiểm (Feynman)
- Vì sao dựng `detector` trước `stages`? Stage nào cần nó?
- Vì sao `_check_params` phải chạy TRƯỚC khi gọi builder (liên quan lazy-import)?
- `extra_sinks` để làm gì, ai truyền vào (nối F1)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py::build_runner` (đọc thật #322/#324) · F1/D-088 (#324, extra_sinks + hợp nhất) · bài #04 (executor/runner). Độ chắc: cao (quote trực tiếp).
