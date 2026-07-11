# Requirements Document

> **Spec:** config-observability (bật observability/`/metrics` cho đường `--config` — no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Đóng:** nợ "🟡 wire config" của D-069 (observability mới wire đường CLI-direct, chưa wire `--config`).
> **Nền tảng (đã ĐỌC CODE thật):**
> - `profiles/vision_slice_app.py::_run_from_config(path, *, build=None)`: đường declarative — load AppConfig →
>   for pcfg: `build(pcfg)` (default `build_runner`) → `runner.run(max_frames=pcfg.max_frames)`; **BULKHEAD**
>   per-pipeline (try/except Exception, return 0/1 — D-044/C-016). Hiện KHÔNG dựng observer/exporter.
> - `profiles/pipeline_factory.py::build_runner(pcfg, *, registry)` → `PipelineRunner(source, executor, sink)`
>   — **CHƯA nhận observer/emit params.**
> - Đường CLI-direct (`main`) ĐÃ wire: `LoggingObserver` (`--observe`) + `MetricsObserver`+`MetricsHttpExporter`
>   (`--metrics-port`/`--metrics-host`, `is_loopback` cảnh báo) + `_CompositeObserver` + exporter.stop() trong finally.
> - `InMemoryMetrics.iter_metrics()->list[MetricSample]` (D-074) = provider cho exporter; `MetricsObserver` gắn nhãn `source`.
> **Cập nhật lúc:** 2026-07-11.

## Introduction

Deploy ~100 camera thương mại theo mô hình chuẩn Prometheus: **1 process/1 camera (1 pipeline), mỗi process
phơi 1 cổng `/metrics` riêng → Prometheus scrape N target**. Đường vận hành thực tế là `--config cam_x.toml`
(deploy-by-config, D-042). NHƯNG hiện `_run_from_config` KHÔNG bật được observer/`/metrics` — chỉ đường CLI-direct
(fake/rtsp thủ công) có. → operator deploy bằng config KHÔNG thấy sức khỏe runtime (bay mù), đúng lỗ đã ghi D-069.

Tính năng này cho đường `--config` bật observability **tái dùng NGUYÊN các mảnh đã có** (LoggingObserver,
MetricsObserver, MetricsHttpExporter, InMemoryMetrics.iter_metrics, is_loopback) — KHÔNG viết lại. Cùng process
chạy ≥1 pipeline (config có ≥1) → **CHIA SẺ 1 InMemoryMetrics + 1 exporter `/metrics`** (aggregate theo `source_id`),
đúng "1 process = 1 scrape target".

**Ranh giới bản chất (đã kiểm code):** `_run_from_config` chạy pipeline TUẦN TỰ (T-015). Với mô hình 1-pipeline/
process → tuần-tự là ĐỦ (pipeline đó = cả process). Với config nhiều-pipeline/process → /metrics aggregate tuần tự
(gauge per-source_id giữ giá trị cuối mỗi camera; camera đang chạy cập nhật realtime). Không cần runtime song song
cho v1 (song song = việc scale tương lai, cần benchmark GPU — Non-Goal). Opt-in, mặc định TẮT (backward-compat).

**Chống bịa:** mọi tham chiếu (_run_from_config bulkhead, build_runner, iter_metrics, MetricsHttpExporter,
is_loopback, _CompositeObserver, PipelineRunner observer/emit params) ĐÃ đọc code thật.

### Goals
- Đường `--config` bật được `--observe` (log snapshot) + `/metrics` HTTP (`--metrics-port`) như đường CLI-direct.
- 1 process = 1 InMemoryMetrics + 1 exporter dùng chung cho mọi pipeline trong config (aggregate theo source_id).
- Tái dùng mảnh sẵn có, KHÔNG viết lại; additive (mặc định TẮT → hành vi `--config` hiện tại giữ nguyên).
- Giữ BULKHEAD per-pipeline (1 pipeline lỗi không kéo sập + không rò rỉ exporter).
- Kiểm chứng KHÔNG cần GPU (fake source + scrape `/metrics` qua urllib + clock/observer spy).

### Non-Goals
- KHÔNG runtime SONG SONG đa-pipeline (T-015 giữ tuần tự; song song = scale tương lai).
- KHÔNG observability khai báo TRONG file TOML (thêm field schema frozen + loader + validate + strict-key) —
  v1 dùng CỜ CLI trên đường `--config` (bề mặt tối thiểu, khớp cách CLI-direct đã làm). Config-declared = follow-on.
- KHÔNG adapter Prometheus khác / push-gateway / auth (giữ như metrics-http-endpoint: localhost-default, no-auth nội bộ).
- KHÔNG đổi ngữ nghĩa RunStats / bulkhead return-code (C-016).

## Glossary
- **Đường `--config`** — nhánh `_run_from_config`: đọc TOML → dựng+chạy từng pipeline (bulkhead, tuần tự).
- **Shared metrics/exporter** — 1 `InMemoryMetrics` + 1 `MetricsHttpExporter` dùng CHUNG cho mọi pipeline 1 process.
- **1 process = 1 scrape target** — mô hình deploy: mỗi camera 1 process `--config cam.toml --metrics-port P`; Prometheus scrape mọi P.

## Requirements

### Requirement 1: Đường `--config` bật observer + `/metrics` (tái dùng mảnh CLI-direct)
**User Story:** Là operator deploy bằng config, tôi muốn `--config cam.toml --observe --metrics-port 9100` phơi `/metrics` cho pipeline trong config, để giám sát như đường CLI-direct.
#### Acceptance Criteria
- 1.1 — WHERE `--config` được dùng CÙNG `--observe`, THE `_run_from_config` SHALL gắn `LoggingObserver` cho mỗi runner (log snapshot fps/skip_rate/errors định kỳ).
- 1.2 — WHERE `--config` được dùng CÙNG `--metrics-port`, THE hệ SHALL tạo **1** `InMemoryMetrics` + **1** `MetricsHttpExporter` DÙNG CHUNG + gắn `MetricsObserver(metrics)` cho mọi runner → `/metrics` aggregate theo `source_id`.
- 1.3 — WHERE cả `--observe` và `--metrics-port`, THE observer SHALL là `_CompositeObserver([LoggingObserver, MetricsObserver])` (tái dùng, không viết lại).
- 1.4 — WHERE KHÔNG cờ observability nào, THE `_run_from_config` SHALL hành xử Y HỆT hiện tại (observer=None → NoopObserver; không exporter) — backward-compat.

### Requirement 2: `build_runner` nhận observer/emit params (additive)
**User Story:** Là kiến trúc sư, tôi muốn `build_runner` gắn observer vào runner mà không phá chữ ký/registry.
#### Acceptance Criteria
- 2.1 — THE `build_runner` SHALL nhận thêm tham số keyword optional `observer` (default None) + `emit_every_n` (default 0) + `emit_interval_s` (default 0.0), truyền thẳng vào `PipelineRunner`.
- 2.2 — WHERE không truyền, THE `build_runner` SHALL cho kết quả Y HỆT hiện tại (PipelineRunner observer mặc định Noop) — backward-compat; test `build_runner` cũ không đổi.
- 2.3 — THE thay đổi SHALL KHÔNG đụng registry/`_check_params`/`validate_config` (observability KHÔNG phải params của builder trong config v1).

### Requirement 3: An toàn vận hành (bulkhead + exporter lifecycle + phơi-mạng)
**User Story:** Là operator, tôi muốn observability KHÔNG làm hỏng chạy nhiều-camera + không rò tài nguyên.
#### Acceptance Criteria
- 3.1 — THE BULKHEAD per-pipeline (D-044) SHALL giữ nguyên: 1 pipeline lỗi (build/run) KHÔNG kéo sập loop; return 0 (mọi ok) / 1 (có lỗi) — C-016.
- 3.2 — THE exporter SHALL được `stop()` trong `finally` (đảm bảo đóng cổng/thread kể cả khi 1 pipeline raise ra ngoài bulkhead / KeyboardInterrupt) — không rò socket/thread.
- 3.3 — IF `--metrics-host` KHÔNG phải loopback (`is_loopback` False), THEN THE hệ SHALL in CẢNH BÁO "không xác thực — chỉ mạng nội bộ tin cậy" (như CLI-direct). Mặc định `127.0.0.1`.
- 3.4 — THE lỗi observer/exporter SHALL KHÔNG được đếm là lỗi pipeline (bulkhead return-code chỉ phản ánh pipeline) — quan sát là phụ trợ.

### Requirement 4: Kiểm chứng KHÔNG cần GPU (xác định)
**User Story:** Là kỹ sư, tôi muốn test đường config-observability xác định trên máy dev.
#### Acceptance Criteria
- 4.1 — Test dựng AppConfig (fake source ≥2 pipeline khác `source_id`) + gọi `_run_from_config` với metrics bật (port=0 ephemeral) → scrape `/metrics` (urllib) → thấy gauge có nhãn `source` cho MỖI pipeline (aggregate dùng chung).
- 4.2 — Test backward-compat: `_run_from_config` KHÔNG cờ observability → return-code + hành vi Y HỆT hiện tại (so test cũ).
- 4.3 — Test bulkhead + exporter: 1 pipeline lỗi (build raise) → các pipeline khác vẫn chạy + return 1 + exporter vẫn `stop()` (không rò cổng — port đóng sau).
- 4.4 — Test `build_runner(observer=...)`: runner nhận observer + emit params đúng (snapshot phát ra observer spy).

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic, đủ section Kiro Spec Format: Overview/Architecture/Components/Data Models/Error Handling/
Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) chữ ký `build_runner`
mở rộng (observer/emit optional); (b) `_run_from_config` dựng shared InMemoryMetrics+exporter+observer 1 lần,
truyền vào build, `stop()` trong finally; (c) tái dùng `_CompositeObserver`/`is_loopback`; (d) giữ bulkhead +
return-code; (e) test no-GPU (urllib scrape + spy). **KHÔNG code ở PHA này.**
