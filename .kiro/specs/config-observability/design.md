# Design Document — config-observability (bật observability/`/metrics` cho `--config`)

## Review đối kháng (#298) — SỬA design theo CODE THẬT (đọc-lại-valid TRƯỚC code)

> ⚠️ **PHẦN NÀY SUPERSEDE mọi mô tả cũ bên dưới khi mâu thuẫn.** Đọc code thật (`_run_from_config`,
> `build_runner`, `main`, `MetricsObserver`, `MetricsHttpExporter`) phát hiện design ban đầu LỆCH trạng thái
> hiện tại → thu hẹp phạm vi + tránh code trùng/phá backward-compat.

**Trạng thái THẬT đã có (KHÔNG làm lại):**
- `build_runner(pcfg, *, registry, observer=None, emit_every_n=0, emit_interval_s=0.0)` — **ĐÃ có đủ 3 param**
  (D-070/#278) → **Requirement 2 = NO-OP, KHÔNG đụng `build_runner`.**
- `_run_from_config(path, *, build=None, observe=False, observe_interval_s=0.0, observe_every_n=0)` — **ĐÃ có**
  observe + wire `LoggingObserver` per-pipeline (closure `build = lambda pcfg: build_runner(pcfg, observer=LoggingObserver(), ...)`).
- `main` — ĐÃ tính `obs_interval=5.0` khi `_want_periodic=(observe or metrics_port is not None)` + ĐÃ route
  `observe/observe_interval_s/observe_every_n` xuống `_run_from_config`.
- `MetricsObserver.on_snapshot` đọc `snapshot.source_id` → gán nhãn `source=src` ⇒ **1 MetricsObserver + 1
  InMemoryMetrics DÙNG CHUNG TỰ aggregate theo source_id** (cơ chế trung tâm — VERIFIED đọc code).
- `MetricsHttpExporter`: `start()->int` (cổng thực), `.port` property, `stop()` idempotent (chờ `_serving`), `is_loopback`.

**Phạm vi CÒN LẠI thực sự (nhỏ hơn design gốc):**
1. THÊM 2 param `metrics_port: int|None = None`, `metrics_host: str = "127.0.0.1"` vào `_run_from_config`
   (GIỮ tên `observe_every_n`/`observe_interval_s` — KHÔNG đổi thành `emit_*` [Lỗ-2]).
2. TÁCH `_build_config_observability(observe, metrics_port, metrics_host) -> (observer, exporter)` — extract
   NGUYÊN khối observability đang nằm inline trong `main` (khử trùng lặp — fix bản chất). Điều kiện wire =
   `observe OR metrics_port is not None` [Lỗ-4].
3. `_run_from_config`: khi `build is None` → gọi helper; nếu `observer is not None` → GIỮ pattern closure
   `build = lambda pcfg: build_runner(pcfg, observer=observer, emit_every_n=observe_every_n, emit_interval_s=observe_interval_s)`
   (KHÔNG đổi loop sang `build(pcfg, observer=...)` [Lỗ-3]) + `try/finally: exporter.stop()` [R3.2].
4. `main` config-branch: THÊM `metrics_port=args.metrics_port, metrics_host=args.metrics_host` vào lời gọi
   `_run_from_config`; đồng thời main CLI-direct DÙNG LẠI `_build_config_observability` (DRY).
5. Smart-default: `_run_from_config` tự áp `observe_interval_s=5.0` khi `(observe or metrics_port is not None)`
   và cả hai nhịp = 0 → self-consistent kể cả khi gọi trực tiếp (không qua main) [Lỗ-6].
6. **Test P1/P2 đánh vào seam `_build_config_observability` TRỰC TIẾP** (không qua `_run_from_config` vì sync +
   `finally stop()` → không scrape được sau return [Lỗ-5]): helper trả `(observer, exporter)` đã `start()` →
   `exporter.port` → feed ≥2 snapshot khác `source_id` qua `observer.on_snapshot` → urllib GET `/metrics` →
   assert `source="camA"` & `source="camB"` → `exporter.stop()`. P4 (build_runner observer) ĐÃ có test #278 → không lặp.

## Overview

Đóng nợ "🟡 wire config" của D-069: đường `--config` (`_run_from_config`) hiện ĐÃ bật `--observe` (LoggingObserver
per-pipeline, D-070/#278) nhưng CHƯA bật `/metrics` (MetricsObserver + MetricsHttpExporter — chỉ đường CLI-direct
có). Thêm đúng phần `/metrics` còn thiếu bằng cách **tái dùng NGUYÊN các mảnh đã có** (LoggingObserver,
MetricsObserver, MetricsHttpExporter, InMemoryMetrics.iter_metrics, is_loopback, _CompositeObserver) — KHÔNG viết
lại. Mô hình deploy chuẩn: **1 process/1 camera, mỗi process 1 `/metrics` port → Prometheus scrape N target**.
Opt-in, mặc định TẮT (backward-compat tuyệt đối). ADDITIVE, no-GPU, giữ baseline 601/2.

**Nguyên tắc gốc:** cùng 1 process CHIA SẺ 1 `InMemoryMetrics` + 1 exporter cho MỌI pipeline trong config →
`/metrics` aggregate theo `source_id` (mỗi camera 1 series gauge). Chạy tuần tự (T-015) là đủ cho mô hình
1-pipeline/process; nhiều-pipeline/process → aggregate tuần tự (gauge giữ giá trị cuối mỗi source; camera đang
chạy realtime). Song song = Non-Goal (scale tương lai).

## Bằng chứng code đã đọc (chống bịa)
- `profiles/vision_slice_app.py::_run_from_config(path, *, build=None)`: `load_app_config` → for pcfg in
  app.pipelines: try `runner=build(pcfg)`; `stats=runner.run(max_frames=pcfg.max_frames)` except Exception →
  bulkhead (log, failed+=1). return `0 if failed==0 else 1` (C-016). `build` default = `build_runner`.
- `profiles/pipeline_factory.py::build_runner(pcfg, *, registry=DEFAULT_REGISTRY)` → dựng source/stages/sinks →
  `PipelineRunner(source, executor, sink)`. **CHƯA truyền observer.**
- `main()` đường CLI-direct: `observers_list` (LoggingObserver nếu `--observe`; MetricsObserver+exporter nếu
  `--metrics-port`) → `_CompositeObserver` nếu ≥2 → `PipelineRunner(..., observer=, emit_every_n=obs_every,
  emit_interval_s=obs_interval)`; `exporter.stop()` trong finally; `is_loopback` cảnh báo phơi-mạng.
- `PipelineRunner.__init__(..., observer=None, emit_every_n=0, emit_interval_s=0.0)` (đã có, D-069/#276) —
  observer=None → NoopObserver; `_emit` cô lập lỗi observer.
- `_CompositeObserver` (D-079): gọi nhiều observer, đã có ở `vision_slice_app`.

## Architecture

KHÔNG layer mới, KHÔNG đảo hướng phụ thuộc. Chỉ sửa 2 hàm ở `profiles` (composition root) + tái dùng runtime/
adapters/kernel có sẵn.

```
main() [--config + --observe/--metrics-port] 
      │  (truyền cờ observability xuống)
      ▼
profiles/_run_from_config(path, *, build, observe, emit_*, metrics_port, metrics_host)
      │  dựng 1 lần: InMemoryMetrics(shared) + MetricsHttpExporter(iter_metrics) + observer (composite)
      │  for pcfg: build(pcfg, observer=, emit_every_n=, emit_interval_s=)  ← BULKHEAD giữ nguyên
      │  finally: exporter.stop()
      ▼
profiles/build_runner(pcfg, *, registry, observer=None, emit_every_n=0, emit_interval_s=0.0)
      ▼
runtime PipelineRunner(source, executor, sink, observer=, emit_every_n=, emit_interval_s=)
              ├─ observer: _CompositeObserver([LoggingObserver, MetricsObserver(shared_metrics)])  (runtime)
              └─ exporter: MetricsHttpExporter(shared_metrics.iter_metrics)  (adapters, leaf)
```

- **Chia sẻ metrics:** MỘT `InMemoryMetrics` cho cả process → MỌI runner dùng chung `MetricsObserver(metrics)`;
  gauge gắn nhãn `source=source_id` → aggregate tự nhiên (mỗi camera 1 series). 1 exporter phơi tất cả.
- **Hướng phụ thuộc:** profiles → runtime/adapters/kernel (composition root, hợp lệ). Không đụng import-linter.
- **Vì sao dùng CỜ CLI (không field TOML) ở v1:** thêm field vào schema frozen + loader + validate + strict-key =
  bề mặt lớn; cờ CLI trên đường `--config` khớp cách CLI-direct đã làm + đủ cho "1 process/camera" (mỗi process
  1 lệnh có cờ riêng). Config-declared observability = follow-on (Non-Goal).

## Components and Interfaces

### 1. profiles/pipeline_factory.py — `build_runner` (⚠️ ĐÃ CÓ — KHÔNG sửa)
```
# HIỆN TẠI (D-070/#278) — đã đủ, Requirement 2 = NO-OP:
def build_runner(pcfg, *, registry=DEFAULT_REGISTRY,
                 observer=None, emit_every_n=0, emit_interval_s=0.0) -> PipelineRunner:
    ... return PipelineRunner(source, executor, sink,
                              observer=observer, emit_every_n=emit_every_n, emit_interval_s=emit_interval_s)
```
- **KHÔNG đụng file này** (đã backward-compat, đã có test #278). Giữ nguyên registry/`_check_params`/`validate_config` (R2.3).

### 2. profiles/vision_slice_app.py — `_run_from_config` mở rộng (GIỮ tên param thật)
```
def _run_from_config(path, *, build=None,
                     observe=False, observe_interval_s=0.0, observe_every_n=0,   # ĐÃ CÓ (D-070) — giữ tên
                     metrics_port=None, metrics_host="127.0.0.1") -> int:        # THÊM MỚI
    from ... import build_runner, load_app_config
    # smart-default: (observe or metrics) & chưa set nhịp → 5s (self-consistent kể cả gọi trực tiếp) [Lỗ-6]
    if (observe or metrics_port is not None) and observe_every_n == 0 and observe_interval_s == 0.0:
        observe_interval_s = 5.0
    exporter = None
    if build is None:                       # đường chạy thật (test tiêm build → tôn trọng, bỏ qua observability)
        observer, exporter = _build_config_observability(observe, metrics_port, metrics_host)  # 1 lần, DÙNG CHUNG
        if observer is not None:            # GIỮ pattern closure (KHÔNG đổi loop sang build(pcfg, observer=)) [Lỗ-3]
            build = lambda pcfg: build_runner(pcfg, observer=observer,
                        emit_every_n=observe_every_n, emit_interval_s=observe_interval_s)
        else:
            build = build_runner
    try:
        app = load_app_config(path)
        ok = failed = 0
        for pcfg in app.pipelines:
            try:
                runner = build(pcfg); stats = runner.run(max_frames=pcfg.max_frames); ... ; ok += 1
            except Exception as e:          # BULKHEAD giữ nguyên (chừa BaseException) — R3.1
                failed += 1; ... log ...
        return 0 if failed == 0 else 1
    finally:
        if exporter is not None:
            exporter.stop()                 # R3.2: luôn đóng cổng/thread (kể cả raise/KeyboardInterrupt)
```
- **1 InMemoryMetrics + 1 exporter + 1 observer DÙNG CHUNG** cho mọi pipeline (aggregate theo source_id — VERIFIED
  `MetricsObserver` đọc `snapshot.source_id`). LoggingObserver/MetricsObserver stateless → 1 observer dùng lại
  cho mọi pipeline là ĐÚNG (không cần "mới mỗi pipeline").

### 2b. `_build_config_observability(observe, metrics_port, metrics_host) -> (observer, exporter)`
- EXTRACT NGUYÊN khối inline đang ở `main` (khử trùng lặp): `observers_list=[]`; `observe`→`LoggingObserver()`;
  `metrics_port is not None`→`InMemoryMetrics`+`MetricsObserver`+cảnh-báo-`is_loopback`+`MetricsHttpExporter(metrics.iter_metrics).start()`;
  observer = phần tử đơn / `_CompositeObserver` / None. Trả `(observer, exporter)`. **main CLI-direct dùng lại hàm này (DRY).**

### 3. main() — định tuyến cờ observability xuống đường config
- Nhánh `if args.config:` hiện gọi `_run_from_config(args.config)` → đổi thành truyền cờ:
  `return _run_from_config(args.config, observe=args.observe, emit_every_n=args.observe_every,
  emit_interval_s=args.observe_interval, metrics_port=args.metrics_port, metrics_host=args.metrics_host)`.
- KHÔNG thêm cờ CLI mới (tái dùng `--observe/--observe-every/--observe-interval/--metrics-port/--metrics-host` đã có).

### 4. `_build_config_observability` đặt ở đâu?
- Đặt trong `vision_slice_app.py` (profiles, cùng chỗ khối CLI-direct). Cân nhắc REFACTOR khối main CLI-direct
  gọi CHUNG hàm này (khử trùng lặp) — nhưng để additive tối thiểu + tránh phá test main, v1 chỉ THÊM hàm cho
  đường config; refactor main dùng chung = tuỳ chọn (ghi, không bắt buộc).

## Data Models
KHÔNG thêm DTO. Chỉ luồng tham số (bool/int/float/str) + tái dùng `MetricSample` (kernel, đã có) qua `iter_metrics`.

| Tham số | Kiểu | Ràng buộc | Nơi |
|---|---|---|---|
| `observe` | bool | default False | _run_from_config (ĐÃ CÓ) |
| `observe_every_n` | int ≥0 | 0=tắt theo-frame | _run_from_config (ĐÃ CÓ) → build_runner → PipelineRunner |
| `observe_interval_s` | float ≥0 | 0=tắt theo-giờ; (observe∨metrics)+cả-hai-0 → 5.0 | như trên |
| `metrics_port` | int\|None | None=không exporter; 0=ephemeral (test); THÊM MỚI | _run_from_config |
| `metrics_host` | str | default "127.0.0.1"; non-loopback → cảnh báo; THÊM MỚI | _run_from_config |

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| 1 pipeline lỗi build/run | BULKHEAD (try/except Exception, chừa BaseException) → log + failed++, chạy tiếp; return 1 | R3.1 |
| Có exporter + thân raise/ngắt | `finally: exporter.stop()` → đóng cổng+thread (idempotent, có timeout) | R3.2 |
| observer.on_snapshot lỗi | đã cô lập trong `PipelineRunner._emit` (đếm+log, không sập) — return-code KHÔNG tính | R3.4 |
| metrics_host non-loopback | in CẢNH BÁO "không xác thực — mạng nội bộ" (is_loopback False) | R3.3 |
| metrics_port bận | `MetricsHttpExporter.start()` → OSError fail-fast (không nuốt) | (vận hành) |

- Quan sát PHỤ TRỢ: lỗi observer/exporter KHÔNG được tính là lỗi pipeline; nhưng exporter start lỗi (cổng bận)
  = lỗi cấu hình vận hành → fail-fast trước vòng lặp (chưa chạy pipeline nào) là hợp lý.

## Correctness Properties

### Property 1: Config-path bật observer + /metrics (tái dùng)
`--config + --observe --metrics-port 0` → mỗi runner có observer (composite Logging+Metrics); `/metrics` phơi + scrape được.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Aggregate per-camera dùng chung
≥2 pipeline khác source_id, 1 InMemoryMetrics + 1 exporter dùng chung → `/metrics` có gauge nhãn `source` cho MỖI camera.
**Validates: Requirements 1.2**

### Property 3: Backward-compat tuyệt đối
`--config` KHÔNG cờ observability → observer=None (Noop), không exporter → return-code + hành vi BẰNG hiện tại.
**Validates: Requirements 1.4, 2.2**

### Property 4: build_runner additive
`build_runner(pcfg)` (không observer) == hành vi cũ; `build_runner(pcfg, observer=spy, emit_every_n=1)` → runner phát snapshot cho spy.
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 5: Bulkhead + exporter lifecycle
1 pipeline build raise → pipeline khác vẫn chạy + return 1 + exporter `stop()` (cổng đóng sau finally, không rò).
**Validates: Requirements 3.1, 3.2, 3.4**

### Property 6: Cảnh báo phơi-mạng
metrics_host không loopback → in cảnh báo "không xác thực"; mặc định 127.0.0.1 không cảnh báo.
**Validates: Requirements 3.3**

## Testing Strategy
- **Aggregate scrape (P1/P2) — QUA SEAM `_build_config_observability` [Lỗ-5]:** `_build_config_observability(observe=True,
  metrics_port=0, metrics_host="127.0.0.1")` → `(observer, exporter)` (đã `start()`) → `port=exporter.port` →
  feed 2 snapshot khác `source_id` (`observer.on_snapshot(PipelineSnapshot(source_id="camA",...))` + `"camB"`) →
  `urllib` GET `http://127.0.0.1:{port}/metrics` → assert có `source="camA"` VÀ `source="camB"` (aggregate dùng
  chung) → `exporter.stop()`. KHÔNG scrape qua `_run_from_config` (sync + finally-stop → port không lộ, đã đóng).
- **Backward-compat (P3):** `_run_from_config(cfg)` không cờ → observer=None/không exporter → return-code + hành vi
  == test cũ (#278 còn xanh); full suite giữ.
- **build_runner (P4):** ĐÃ có test #278 (`build_runner(observer=..., emit_every_n=1)`) → KHÔNG lặp lại.
- **Bulkhead+exporter (P5):** DI `build` raise ở pipeline thứ 1 (đường này exporter=None vì build tiêm) → xác nhận
  bulkhead return 1 + pipeline 2 chạy. Lifecycle exporter.stop() kiểm riêng qua seam: `_build_config_observability(
  metrics_port=0)` → `exporter.port` mở → `stop()` → GET lại → `ConnectionRefused`/OSError (đã đóng, không rò cổng).
- **Cảnh báo (P6):** `_build_config_observability(observe=False, metrics_port=0, metrics_host="0.0.0.0")` → capsys bắt
  cảnh báo "KHÔNG xác thực"; `metrics_host="127.0.0.1"` → không cảnh báo. (port=0 → không thực bind ra ngoài.)
- **main routing:** `main(["--config", cfg, "--metrics-port", "0"])` smoke → rc hợp lệ + `_run_from_config` nhận
  metrics_port (monkeypatch spy) — chứng minh main route cờ metrics xuống config.
- **Baseline:** full `pytest -q` ≥ 601 passed (+ test mới) / 2 skipped; lint 5 kept/0 broken.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** thấy-sức-khỏe-khi-deploy-config (vận hành) ⟂ tái-dùng-không-trùng-lặp (khử copy khối main) ⟂
  backward-compat (mặc định TẮT) ⟂ bulkhead-không-rò-exporter ⟂ an-toàn-phơi-mạng. Cân: tách `_build_config_observability`
  dùng chung + finally-stop + is_loopback cảnh báo.
- **What varies?** BỘ observer (log/metrics/none) + có-exporter-hay-không → trừu tượng đúng chỗ = compose observer +
  optional exporter (đã có `_CompositeObserver`/`MetricsHttpExporter`), KHÔNG đẻ lớp mới.
- **Which way deps point?** profiles(compose) → runtime/adapters/kernel. Không đảo. build_runner thêm param optional,
  không kéo dep observability vào kernel/schema.
- **Cái GIÁ:** `build_runner` +3 param optional (nhỏ); `_run_from_config` +1 hàm dựng + finally. Chia sẻ 1 metrics
  cho nhiều pipeline = aggregate tuần tự (không realtime song song) — chấp nhận (Non-Goal song song).
- **Khi nào KHÔNG dùng:** (a) nhiều-pipeline/process CẦN /metrics realtime song song → cần runtime song song
  (Non-Goal, scale tương lai). (b) observability khai báo trong TOML (GitOps thuần config) → cần field schema
  (follow-on). (c) phơi 0.0.0.0 ra internet công cộng → phải firewall/proxy/auth (ngoài phạm vi, cảnh báo đã có).
- **Recognize:** operator deploy `--config cam.toml` mà "không thấy gì đang chạy" = triệu chứng thiếu wire →
  bật `--observe`/`--metrics-port` trên chính đường config.

## Non-Goals (nhắc lại)
Runtime song song đa-pipeline · observability khai báo trong TOML (field schema) · auth/push-gateway/adapter Prometheus khác ·
đổi RunStats/bulkhead return-code · refactor bắt-buộc khối main CLI-direct (tùy chọn khử trùng lặp).
