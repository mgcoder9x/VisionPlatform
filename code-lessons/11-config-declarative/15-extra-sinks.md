# 11.15 — F1: `extra_sinks` — chèn sink PRESENTATION (`_TrackSummarySink`) ngoài-config

## 1. Thuộc về đâu
profiles — `build_runner` (tham số `extra_sinks`) + `vision_slice_app.main`/`_TrackSummarySink`. Mảnh cuối của F1.

## 2. Cần biết trước
mẩu 13 (`build_runner` dựng `CompositeSink` nội bộ), mẩu 14 (`_args_to_pipeline_config`). `ISink` (bài #04).

## 3. Code thật (quote nguyên văn)
`pipeline_factory.py`:
```python
def build_runner(pcfg: PipelineConfig, *, registry: Mapping = DEFAULT_REGISTRY,
                 observer=None, emit_every_n: int = 0, emit_interval_s: float = 0.0,
                 extra_sinks: Sequence = ()) -> PipelineRunner:
    ...
    sinks.extend(extra_sinks)   # F1/#324: sink presentation ngoài-config (vd _TrackSummarySink) — append cuối
```
`vision_slice_app.py` (main, nhánh CLI-direct):
```python
    track_summary = _TrackSummarySink() if args.track else None
    extra_sinks = [track_summary] if track_summary is not None else []
    ...
    runner = build_runner(pcfg, observer=observer, emit_every_n=obs_every,
                          emit_interval_s=obs_interval, extra_sinks=extra_sinks)
    ...
    _print_summary(stats, track_summary, args)
```

## 4. Giải thích từng mẩu nhỏ nhất
- `extra_sinks: Sequence = ()` — tham số MỚI, **additive**, mặc định rỗng → đường `--config` KHÔNG đổi hành vi.
- `sinks.extend(extra_sinks)` — nối các sink dựng-sẵn (ngoài config) VÀO CUỐI `CompositeSink`.
- `_TrackSummarySink` — sink nhỏ đọc `unique_count`/`crossings` từ artifacts frame SUCCESS (để in summary CLI).
  CLI giữ tham chiếu `track_summary` → sau `run()` gọi `_print_summary(stats, track_summary, args)`.
- Vì sao `_TrackSummarySink` KHÔNG vào registry/config: nó là **presentation** (phục vụ in ra màn hình CLI), KHÔNG
  phải cấu hình deploy → không thuộc file TOML. `extra_sinks` là "cửa" tiêm sink presentation từ ngoài.

## 5. Là gì
Cơ chế cho phép đường CLI chèn sink-của-riêng-nó (in summary) vào pipeline dựng qua `build_runner`, mà không
làm bẩn schema config.

## 6. Tại sao tồn tại / vấn đề nó giải
F1 muốn CLI dùng chung `build_runner` (mẩu 14). Nhưng `build_runner` dựng `CompositeSink` NỘI BỘ → CLI không
chèn được `_TrackSummarySink` từ ngoài. Nếu ép `_TrackSummarySink` vào registry → nó lọt vào file TOML (sai — nó
là presentation). `extra_sinks` giải quyết: tiêm sink ngoài-config, giữ config sạch, giữ 1 đường lắp-ráp.

## 7. Dùng ở đâu
CLI-direct (`main`): tạo `_TrackSummarySink` khi `--track` → truyền qua `extra_sinks` → in summary. Đường
`--config` KHÔNG truyền → `extra_sinks=()` → không đổi.

## 8. Không có nó thì sao
Không có `extra_sinks`: F1 không dùng được `build_runner` cho CLI (mất summary), phải giữ đường ráp-tay riêng →
F1 thất bại (vẫn 2 đường). Hoặc nhét `_TrackSummarySink` vào registry → rò presentation vào schema config (sai tầng).

## 9. Ví von
Dây chuyền chuẩn (build_runner) lắp xe theo phiếu; `extra_sinks` = "khe gắn thêm phụ kiện riêng của khách" (đồng hồ
đo hiển thị) mà không phải sửa bản thiết kế xe.

## 10. Liên kết bức tranh lớn
Hoàn tất F1: CLI (mẩu 14 sinh config) + `extra_sinks` (chèn presentation) → dùng chung `build_runner` → 1 nguồn
lắp-ráp, đóng phân kỳ. Tách bạch *cấu hình deploy* (TOML) khỏi *trình bày* (CLI summary).

## 11. Cạm bẫy
- Default PHẢI là `()` (không `[]`) — additive an toàn, đường config không đổi.
- Đừng đưa sink presentation vào registry/TOML (rò tầng); dùng `extra_sinks`.

## 12. Tự kiểm (Feynman) — cũng là cổng đóng #11
- Vì sao `_TrackSummarySink` KHÔNG vào config mà đi qua `extra_sinks`? (presentation vs deploy-config)
- **Tổng hợp #11:** kể lại chuỗi TOML → `AppConfig` → `build_runner` → `PipelineRunner`, chỉ rõ mỗi mảnh ở tầng nào
  (kernel/application/profiles) và VÌ SAO tách vậy. (Nếu giải thích trôi chảy = nắm config-declarative.)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py::build_runner` + `vision_slice_app.py` (đọc thật #324) · F1/D-088. Độ chắc: cao (quote trực tiếp).
