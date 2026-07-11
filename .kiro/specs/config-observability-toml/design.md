# Design Document — config-observability-toml (khai báo observability trong TOML)

## Overview

Cho phép khai báo observability TRONG file TOML qua 1 section TOP-LEVEL `[observability]`, để deploy GitOps thuần-file
(`--config cam.toml` KHÔNG cần cờ ngoài). TÁI DÙNG NGUYÊN đường thực thi #299 (`_build_config_observability` +
`_run_from_config` + exporter/bulkhead) — section TOML chỉ là 1 NGUỒN KHÁC của cùng bộ tham số observability, HỢP
NHẤT với cờ CLI theo precedence rõ ràng. Additive, mặc định TẮT (không section + không cờ = hành vi #299). No-GPU
(parse + merge + validate thuần; không dựng detector/torch). Giữ baseline 612/2.

**Nguyên tắc gốc:** observability là quyết định FLEET/tiến-trình (1 process = 1 scrape target; `source_id` đã phân
biệt camera) → section TOP-LEVEL, KHÔNG per-pipeline (tránh schema-bloat — T-029). Đổi mới DUY NHẤT so với #299 =
thêm 1 nguồn tham số (TOML) + hàm merge precedence; đường observer/exporter/bulkhead giữ nguyên.

## Bằng chứng code đã đọc (chống bịa, #308)
- `kernel/config.py`: `AppConfig` frozen `pipelines: tuple`; mọi *Config `@dataclass(frozen=True)` + `_freeze_params` MappingProxyType.
- `application/config_loader.py::parse_app_config(dict)->AppConfig`: validate cấu trúc + `_require`/`_require_str` fail-fast `ConfigError`; `load_app_config` đọc tomllib.
- `profiles/vision_slice_app.py::_run_from_config(path,*,build=None,observe=False,observe_interval_s=0.0,observe_every_n=0,metrics_port=None,metrics_host="127.0.0.1")` (#299): smart-default 5s → `_build_config_observability` (khi build None) → bulkhead loop → finally exporter.stop().
- `main()`: tính `obs_interval=5.0` khi `_want_periodic=(observe or metrics_port is not None)`; route `observe/observe_interval_s/observe_every_n/metrics_port/metrics_host` xuống `_run_from_config`.

## Architecture

KHÔNG layer mới, KHÔNG đảo phụ thuộc. Thêm 1 DTO @kernel + parse @application + 1 hàm merge + reorder nhỏ trong
`_run_from_config` (@profiles). Đường observer/exporter (#299) giữ NGUYÊN.

```
file.toml [observability]           CLI flags (--observe/--metrics-port/...)
      │ parse (config_loader)              │
      ▼                                    ▼
AppConfig.observability: ObservabilityConfig|None      (giá trị CLI, có sentinel)
      └──────────────┬─────────────────────┘
                     ▼  _merge_observability(cli, toml)  ← PRECEDENCE: CLI-explicit > TOML > default
                     ▼  (observe, metrics_port, metrics_host, observe_interval_s, observe_every_n)
      _run_from_config: load app → MERGE → smart-default 5s → _build_config_observability (#299, KHÔNG đổi)
                     ▼
      1 InMemoryMetrics + 1 exporter DÙNG CHUNG (aggregate source_id) — y #299
```

- **Hướng phụ thuộc:** kernel (DTO thuần) ← application (parse) ← profiles (merge + wire). Không đụng import-linter.
- **Vì sao TOP-LEVEL:** observability = fleet-level; per-pipeline sẽ đẻ N exporter/1 process = sai mô hình "1 process=1 target" + schema-bloat.

## Components and Interfaces

### 1. kernel/config.py — `ObservabilityConfig` (DTO frozen, THÊM) + `AppConfig.observability`
```
@dataclass(frozen=True)
class ObservabilityConfig:
    observe: bool = False
    metrics_port: int | None = None
    metrics_host: str = "127.0.0.1"
    observe_interval_s: float = 0.0
    observe_every_n: int = 0

@dataclass(frozen=True)
class AppConfig:
    pipelines: Sequence[PipelineConfig] = ()
    observability: "ObservabilityConfig | None" = None   # THÊM (None = không khai báo)
```
- Thuần stdlib, frozen — nhất quán schema hiện có. Không MappingProxyType (không có `params` dict ở đây).

### 2. application/config_loader.py — parse `[observability]`
```
obs_raw = raw.get("observability")           # top-level table (optional)
observability = None
if obs_raw is not None:
    _require(isinstance(obs_raw, dict), "observability phải là bảng")
    observability = ObservabilityConfig(
        observe=_req_bool(obs_raw.get("observe", False), "observability.observe"),
        metrics_port=_req_int_or_none(obs_raw.get("metrics_port"), "observability.metrics_port"),
        metrics_host=_req_str_default(obs_raw.get("metrics_host", "127.0.0.1"), "observability.metrics_host"),
        observe_interval_s=_req_float(obs_raw.get("observe_interval_s", 0.0), "observability.observe_interval_s"),
        observe_every_n=_req_int(obs_raw.get("observe_every_n", 0), "observability.observe_every_n"),
    )
return AppConfig(pipelines=pipelines, observability=observability)
```
- Thêm helper kiểu nhỏ (`_req_bool`/`_req_int`/`_req_int_or_none`/`_req_float`/`_req_str_default`) — fail-fast `ConfigError` (nhất quán `_require_str`).

### 3. profiles/vision_slice_app.py — `_merge_observability` + reorder `_run_from_config`
```
def _merge_observability(cli, toml):
    """CLI-explicit > TOML > built-in default. cli = dict giá trị CLI (có sentinel None/0.0/False)."""
    t = toml or ObservabilityConfig()
    return dict(
        observe            = bool(cli["observe"]) or t.observe,                 # OR (store_true không phân biệt not-set/false)
        metrics_port       = cli["metrics_port"] if cli["metrics_port"] is not None else t.metrics_port,
        metrics_host       = cli["metrics_host"] if cli["metrics_host"] is not None else t.metrics_host,
        observe_interval_s = cli["observe_interval_s"] if cli["observe_interval_s"] else t.observe_interval_s,
        observe_every_n    = cli["observe_every_n"] if cli["observe_every_n"] else t.observe_every_n,
    )
```
- `_run_from_config` REORDER: load app TRƯỚC → `merged = _merge_observability(cli, app.observability)` → áp smart-default 5s TRÊN merged → `_build_config_observability(**...)` (khi build None). Chi tiết §Data Models + §Error Handling.
- **`metrics_host` default sentinel:** đổi argparse `--metrics-host default=None` (resolve "127.0.0.1" SAU merge) → phân biệt "user set host" vs "không set" (nếu giữ default "127.0.0.1", CLI luôn override TOML host = sai precedence). Đây là thay đổi nhỏ nhưng CẦN cho precedence đúng.

### 4. main() — truyền RAW CLI (bỏ tiền-tính smart-default) + host-sentinel
- main KHÔNG còn tự tính `obs_interval=5.0` để truyền (dời smart-default vào SAU merge trong `_run_from_config` — vì cần biết "CLI có set interval không" để merge). main truyền RAW: `observe_interval_s=args.observe_interval` (0.0 nếu không set), `observe_every_n=args.observe_every`, `metrics_host=args.metrics_host` (None nếu không set).
- Đường CLI-direct (không `--config`) VẪN tự tính smart-default như #299 (không dùng TOML).

## Data Models

| Tham số | Kiểu | Sentinel "không set" | Nguồn ưu tiên |
|---|---|---|---|
| `observe` | bool | False (store_true) | OR(CLI, TOML) |
| `metrics_port` | int\|None | None | CLI nếu ≠None, else TOML |
| `metrics_host` | str\|None(cli) | None (đổi default) | CLI nếu ≠None, else TOML, else "127.0.0.1" |
| `observe_interval_s` | float | 0.0 | CLI nếu ≠0.0, else TOML |
| `observe_every_n` | int | 0 | CLI nếu ≠0, else TOML |

- `ObservabilityConfig` frozen; `AppConfig.observability: ObservabilityConfig|None`. KHÔNG đổi DTO #299 nào khác.

## Error Handling

| Tình huống | Xử lý | Map |
|---|---|---|
| `[observability]` sai kiểu (vd metrics_port là chuỗi) | `ConfigError` fail-fast (parse) | R1.3 |
| `[observability]` không phải bảng | `ConfigError` "observability phải là bảng" | R1.3 |
| Không có `[observability]` | `observability=None` → merge dùng CLI/default (hành vi #299) | R3.1 |
| metrics_port bận (sau merge) | `MetricsHttpExporter.start()` OSError fail-fast (như #299) | (vận hành) |
| bulkhead 1 pipeline lỗi | giữ nguyên #299 (try/except Exception, exporter.stop finally) | R3.2 |

## Correctness Properties

### Property 1: Khai báo TOML bật /metrics (không cờ CLI)
`[observability] metrics_port=0` + `--config` (không cờ) → `_run_from_config` nhận metrics_port=0 → exporter phơi /metrics.
**Validates: Requirements 1.1, 1.2, 1.3, 2.1**

### Property 2: Precedence CLI override TOML
TOML `metrics_port=9000` + CLI `--metrics-port 9100` → dùng 9100 (CLI thắng). TOML host + không CLI host → dùng TOML host.
**Validates: Requirements 2.1, 2.3**

### Property 3: observe OR-semantics
TOML `observe=true` + không `--observe` → observe bật. `--observe` + TOML vắng → observe bật.
**Validates: Requirements 2.2**

### Property 4: Backward-compat tuyệt đối
Config KHÔNG `[observability]` + không cờ → observability=None → merge = default → observer=None/không exporter (== #299).
**Validates: Requirements 3.1, 3.3, 3.4**

### Property 5: Tái dùng #299 (không đổi ngữ nghĩa)
Sau merge, `_build_config_observability`/exporter-lifecycle/bulkhead chạy Y HỆT #299.
**Validates: Requirements 3.2**

### Property 6: Smart-default sau merge
`[observability] observe=true` (không nhịp) → sau merge, `observe_interval_s=5.0` (áp SAU merge). CLI interval set → giữ CLI.
**Validates: Requirements 2.4**

## Testing Strategy
- **Parse (P1, R4.1):** `parse_app_config({... "observability": {...}})` → `ObservabilityConfig` đúng field; sai kiểu → `ConfigError`; vắng → None.
- **Merge precedence (P2/P3, R4.2):** unit-test `_merge_observability(cli, toml)`: (a) chỉ TOML → TOML; (b) CLI-explicit override; (c) cả hai vắng → default; (d) observe OR.
- **Backward-compat (P4, R4.3):** config không `[observability]` không cờ → `_run_from_config` (spy `_build_config_observability`/build) nhận default → == #299; `test_config_observability.py` #299 vẫn xanh.
- **End-to-end no-GPU (P1/P6, R4.4):** `main(["--config", cfg_có_observability_metrics_port_0])` → monkeypatch `_run_from_config`/`_build_config_observability` spy → nhận metrics_port=0 + interval=5.0 (smart-default sau merge) + rc hợp lệ. (Không scrape thật qua main — Lỗ-5 #298: sync + finally-stop; scrape qua seam như #299 nếu cần.)
- **Baseline:** full `pytest -q` ≥ 612 passed (+ test mới) / 2 skipped; lint 5 kept/0 broken; drift PASS.

## Doubt-driven review (tự phản biện — KHẮT KHE)
- **Forces:** GitOps-thuần-file (khai báo trong TOML) ⟂ backward-compat (#299 cờ CLI vẫn chạy) ⟂ precedence-rõ (không nhập nhằng CLI/TOML) ⟂ không-schema-bloat (top-level, không per-pipeline) ⟂ tái-dùng-#299 (không đường-observer-thứ-2).
- **What varies?** NGUỒN của bộ tham số observability (CLI vs TOML) → trừu tượng đúng = `_merge_observability` (1 hàm thuần), KHÔNG đẻ đường thực thi mới. Bộ tham số + observer/exporter đã cố định (#299).
- **Which way deps point?** kernel(DTO)←application(parse)←profiles(merge+wire). Không đảo; DTO thuần không kéo dep.
- **Cái GIÁ:** (a) đổi argparse `--metrics-host default None` (cần cho precedence đúng — nếu quên, CLI-default luôn đè TOML host); (b) DỜI smart-default từ main → sau-merge trong `_run_from_config` (cần biết "CLI set interval?"); rủi ro: nếu dời sai, đường CLI-direct mất smart-default → phải GIỮ smart-default cho CLI-direct riêng (đã ghi §Components 4).
- **Hạn chế THẬT (trung thực):** (1) `observe` OR-semantics → KHÔNG thể TẮT observe qua CLI khi TOML bật (không có `--no-observe`); muốn tắt → sửa TOML. Chấp nhận v1 (thêm `--no-observe` = follow-on nếu cần). (2) `observe_interval_s=0.0`/`observe_every_n=0` là sentinel "không set" → KHÔNG thể set tường minh 0 qua CLI để đè TOML>0 (0 = "dùng TOML"). Chấp nhận (0 = tắt-nhịp vốn = default; hiếm khi cần đè 0). Ghi rõ.
- **Khi nào KHÔNG dùng:** nếu observability cần PER-CAMERA khác nhau trong 1 process → cần per-pipeline (nhưng mô hình 1-process/camera khiến điều này hiếm; Non-Goal). Nếu chỉ deploy ad-hoc (không GitOps) → cờ CLI #299 đã đủ, section TOML thừa.
- **Recognize:** operator muốn `git`-quản-lý toàn bộ deploy 1 camera trong 1 file (kể cả /metrics port) mà không rải cờ ngoài → dấu hiệu cần section này.

## Non-Goals (nhắc lại)
Observability per-pipeline trong TOML · `--no-observe` (tắt-qua-CLI khi TOML bật) · đè-tường-minh-0 qua CLI · auth/push-gateway · đổi ngữ nghĩa #299 · áp `[observability]` cho đường CLI-direct.
