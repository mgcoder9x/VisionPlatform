# Design — config-declarative (đóng lỗ hổng C2 / K-040)

> Sub-spec design-first (HLD + LLD). Đóng **C2 (no-config)** — trục BẮT BUỘC cho scale ~100 cam (C-014, K-040).
> Nhãn: 🟢 verify với code thật · 🟡 quyết định thiết kế · 🔴 chưa verify / cần đo.
> Grounded: đọc nguyên văn `profiles/vision_slice_app.py` (wiring argparse) + `runtime/pipeline_runner.py`
> (PipelineRunner/RunStats) + `runtime/sync_linear_executor.py` interface.

## Overview

**Vấn đề (K-040 C2):** hôm nay việc dựng pipeline nằm CỨNG trong `vision_slice_app.py` qua `argparse` — mỗi
tiến trình 1 pipeline, tham số truyền tay. Với đích **~100 camera** (C-014), không thể mỗi camera một lệnh
argparse; cần **khai báo** (declarative) toàn bộ: danh sách camera + nguồn + pipeline stage + sink, trong 1
file, để 1 launcher dựng nhiều pipeline mà KHÔNG sửa code.

**Mục tiêu v1 (phạm vi hẹp, tránh over-engineer):**
- Định nghĩa **schema config** cho: danh sách `pipelines`, mỗi cái gồm `source` (type+params), chuỗi `stages`,
  danh sách `sinks`, `detector` (khi có DetectStage), `run` (max_frames...).
- **Loader** đọc file (**TOML qua `tomllib` — stdlib py3.11, KHÔNG thêm dependency**) → validate → `AppConfig` (typed, immutable).
- **Builder** map `AppConfig` → dựng đúng các object hiện có (`_build_source`/`_build_detector` tương đương) →
  trả `PipelineRunner` sẵn chạy. KHÔNG sửa `PipelineRunner`/adapter/stage hiện có (additive).

**Ngoài phạm vi v1:** chạy song song N tiến trình/GPU-scheduling (thuộc scale-architecture) · hot-reload config ·
config phân tán (etcd...) · secret management (K-031). v1 chỉ: file tĩnh → dựng pipeline(s) trong 1 tiến trình.

**Nền GROUNDED (🟢 đọc code):** `vision_slice_app` dựng `source∈{fake,noise,video,rtsp}` · `detector∈{fake,pt}`
· `executor=SyncLinearExecutor([DetectStage(detector), CountStage()])` · `sink=CompositeSink([JsonlEventSink?])`
· `PipelineRunner(source, executor, sink).run(max_frames=...)`. Config chỉ khai báo lại các lựa chọn này.

## Architecture

```
config.toml ──tomllib──> ConfigLoader.load() ──validate──> AppConfig (typed, immutable)
                                                                  │
                                     PipelineFactory.build(cfg)   │  (map type-string → object, DI registry)
                                                                  ▼
     source(IFrameSource) + SyncLinearExecutor([stages]) + CompositeSink([sinks])  ──> PipelineRunner (san co)
```

- **Layer:** `AppConfig` + schema = **dataclass thuần** ở `kernel/config.py` (chỉ stdlib — không I/O, không
  đọc file). `ConfigLoader` (đọc file + tomllib) + `PipelineFactory` (dựng adapter) = tầng **application/profiles**
  (composition — được import adapter). 🟢 khớp AGENTS §4 (kernel thuần; dựng adapter ở composition root).
- **Registry pattern (🟡):** map `type` string → hàm dựng, để thêm source/detector/sink mới = đăng ký, không sửa loader.
- **Tách parse ⊥ build:** load+validate ra `AppConfig` (không đụng adapter) → build (đụng adapter). Test parse độc lập, không cần GPU.

## Components and Interfaces

- **`kernel/config.py` (mới, thuần dataclass, frozen):**
  - `SourceConfig(type: str, params: dict)` · `StageConfig(type: str, params: dict)` ·
    `SinkConfig(type: str, params: dict)` · `DetectorConfig(type: str, params: dict)`.
  - `PipelineConfig(id: str, source: SourceConfig, stages: list[StageConfig], sinks: list[SinkConfig], detector: DetectorConfig | None, max_frames: int | None)`.
  - `AppConfig(pipelines: list[PipelineConfig])`. Tất cả frozen; `params` là `MappingProxyType` (immutable).
- **`application/config_loader.py` (mới):**
  - `load_app_config(path: str) -> AppConfig` — `tomllib.load` (nhị phân) → `parse_app_config(dict) -> AppConfig`
    (validate: field bắt buộc, id duy nhất, type hợp lệ). Fail-fast `ConfigError` với thông điệp rõ (dòng/khoá).
  - `parse_app_config(raw: dict) -> AppConfig` tách riêng (test không cần file).
- **`profiles/pipeline_factory.py` (mới):**
  - `build_runner(pcfg: PipelineConfig, *, registry=DEFAULT_REGISTRY) -> PipelineRunner` — map type→builder,
    dựng source/stages/detector/sinks, ráp `SyncLinearExecutor` + `CompositeSink` + `PipelineRunner`.
  - `DEFAULT_REGISTRY` = dict {`"sources"`: {fake,noise,video,rtsp}, `"detectors"`: {fake,pt}, `"stages"`:
    {detect,count}, `"sinks"`: {jsonl}} — mỗi entry là callable(params)->object (bọc `_build_*` hiện có).
- **KHÔNG sửa:** `PipelineRunner`, `SyncLinearExecutor`, adapter/stage — chỉ thêm lớp khai báo phía trên.

## Data Models

Config TOML (v1) — ví dụ:

```toml
[[pipelines]]
id = "cam-01"
max_frames = 100

[pipelines.source]
type = "video"
params = { path = "clips/cam01.mp4" }

[pipelines.detector]
type = "fake"
params = { model_size = 640 }

[[pipelines.stages]]
type = "detect"

[[pipelines.stages]]
type = "count"

[[pipelines.sinks]]
type = "jsonl"
params = { path = "events/cam01.jsonl" }
```

- `pipelines` = mảng bảng (array-of-tables) → N camera. Mỗi `id` DUY NHẤT (validate).
- `source.type` ∈ registry sources; `params` khớp chữ ký adapter (vd video→path, rtsp→url+max_reconnect).
- `stages` theo THỨ TỰ khai báo (detect trước count). `detector` chỉ cần khi có stage `detect`.
- `sinks` rỗng → CompositeSink([]) (không lưu — hợp "lưu trữ optional", C-013).

## Correctness Properties

🟡 **[THIẾT KẾ MỚI — CẦN DUYỆT]** (sẽ thành test ở tasks). Số Requirement điền khi tạo `requirements.md`.

### Property 1: Round-trip parse
`parse_app_config(raw)` với `raw` hợp lệ → `AppConfig` phản ánh ĐÚNG số pipeline, thứ tự stages, params.
**Validates: Requirements 1.1**

### Property 2: Fail-fast config sai
Config thiếu field bắt buộc / `type` không có trong registry / `id` trùng → raise `ConfigError` (KHÔNG dựng object nửa vời).
**Validates: Requirements 2.1**

### Property 3: Build khớp wiring tay
`build_runner(pcfg)` từ config tương đương argparse dựng ra pipeline CÙNG cấu trúc (source/stages/sink) như `vision_slice_app` hiện tại.
**Validates: Requirements 3.1**

### Property 4: Immutability
`AppConfig` và mọi `*Config` là frozen; `params` không sửa được sau khi parse (chống mutate toàn cục).
**Validates: Requirements 1.2**

### Property 5: Không phá base
Thêm lớp config KHÔNG đổi hành vi `PipelineRunner`/adapter/stage; baseline 379/1 vẫn xanh.
**Validates: Requirements 3.2**

## Error Handling

- **File không tồn tại / không đọc được:** `ConfigError` bọc `FileNotFoundError` (thông điệp path rõ).
- **TOML sai cú pháp:** bắt `tomllib.TOMLDecodeError` → `ConfigError` kèm vị trí.
- **Thiếu field bắt buộc** (id/source.type...): `ConfigError` nêu rõ pipeline nào + khoá nào.
- **`type` lạ** (không trong registry): `ConfigError` liệt kê type hợp lệ (giúp sửa nhanh).
- **`id` trùng:** `ConfigError` (mỗi pipeline phải định danh duy nhất — cần cho vận hành/metric per-camera).
- **params sai chữ ký adapter** (vd video thiếu path): builder để adapter tự `raise` (fail-fast) — KHÔNG nuốt.

## Testing Strategy

- **T-parse (unit, no GPU/no file):** `parse_app_config(dict)` — valid → AppConfig đúng; các nhánh sai → `ConfigError` (Property 1,2,4).
- **T-load (unit, file tạm .toml):** `load_app_config(tmp_path)` round-trip; file thiếu/sai TOML → `ConfigError`.
- **T-build (unit, fake source+detector — KHÔNG GPU):** `build_runner` từ config fake → `PipelineRunner`; chạy `.run(max_frames=n)` → RunStats.processed>0 (Property 3). Dùng fake/noise + FakeDetector (xác định, không cần GPU/onnx).
- **T-regression:** full suite vẫn 379/1 + test mới (Property 5). lint-imports khi AV cho phép (🔴 hiện AV chặn .exe — sẽ chạy lại sau).
- **PBT (hypothesis):** Property 1/4 (round-trip + immutability) trên config sinh ngẫu nhiên hợp lệ.

## Giới hạn / rủi ro (🔴 nói thật)
- v1 **1 tiến trình, nhiều pipeline tuần tự** (PipelineRunner đồng bộ) — chạy N camera SONG SONG (đa tiến trình/GPU
  scheduling) thuộc `scale-architecture`, KHÔNG trong spec này.
- `tomllib` chỉ ĐỌC (py3.11 stdlib); nếu cần GHI config → thêm `tomli-w` sau (v1 không cần).
- Chưa xử secret trong config (K-031) — v1 giả định path/URL không nhạy cảm; secret management là sub-spec bảo mật.
- lint-imports chưa verify được (AV chặn) → ranh giới import của module mới sẽ kiểm khi AV cho phép.

## Nguồn
- Code: `profiles/vision_slice_app.py` (`_build_source`/`_build_detector`/wiring), `runtime/pipeline_runner.py`
  (PipelineRunner/RunStats), `runtime/sync_linear_executor.py`. Đã đọc nguyên văn.
- K-040 (C2 no-config), C-014 (~100 cam), C-013 (lưu trữ optional). `tomllib` = Python 3.11 stdlib.
