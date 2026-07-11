# Requirements Document

> **Spec:** config-observability-toml (khai báo observability TRONG file TOML — GitOps thuần-config, no-GPU)
> **Trạng thái:** PHA 1 (requirements) — DESIGN-FIRST, CHỜ user valid trước khi code.
> **Nối tiếp:** D-082/#299 (đã wire `/metrics` cho `--config` qua CỜ CLI) + T-029 (v1 chọn cờ CLI, TOML = follow-on).
> **Nền tảng (đã ĐỌC CODE thật #308):**
> - `kernel/config.py`: `AppConfig` frozen chỉ có `pipelines: tuple`. Mọi *Config `@dataclass(frozen=True)`; `params` bọc `MappingProxyType`.
> - `application/config_loader.py::parse_app_config(dict)->AppConfig`: validate CẤU TRÚC (field/id-duy-nhất/type-chuỗi), `ConfigError` fail-fast; `load_app_config(path)` đọc tomllib.
> - `profiles/vision_slice_app.py::_run_from_config(path,*,build,observe,observe_interval_s,observe_every_n,metrics_port,metrics_host)` (#299) + `_build_config_observability(observe,metrics_port,metrics_host)->(observer,exporter)` — TÁI DÙNG NGUYÊN.
> - `main()` đã tính `obs_interval=5.0` khi `_want_periodic` + route cờ xuống `_run_from_config`.
> **Cập nhật lúc:** 2026-07-11.

## Introduction

Mô hình deploy thương mại ~100 camera thường theo **GitOps**: mọi cấu hình 1 tiến-trình/camera nằm TRỌN trong 1
file `cam_x.toml` version-controlled — kể cả observability (cổng `/metrics`, nhịp emit). Hiện (#299) observability
trên đường `--config` CHỈ bật được qua **cờ CLI** (`--metrics-port`...); để "1 lệnh 1 file khai báo đủ", operator
phải nhớ truyền cờ ngoài file → cấu hình BỊ TÁCH (file + cờ) → khó audit/GitOps.

Tính năng này cho phép khai báo observability **TRONG TOML** qua 1 section TOP-LEVEL `[observability]` (KHÔNG
per-pipeline — observability là quyết định FLEET/tiến-trình, `source_id` đã phân biệt camera; đúng T-029). TÁI
DÙNG NGUYÊN đường thực thi #299 (`_build_config_observability`/`_run_from_config`): section TOML chỉ là 1 NGUỒN
KHÁC của cùng bộ tham số, hợp nhất với cờ CLI theo precedence rõ ràng. Additive, mặc định TẮT (không section +
không cờ = hành vi `--config` hiện tại). No-GPU verify (parse + merge + validate thuần, không dựng detector).

**Chống bịa:** mọi tham chiếu (AppConfig frozen, parse_app_config, _run_from_config params, _build_config_observability)
ĐÃ đọc code thật (#308).

### Goals
- Khai báo observability trong TOML: `[observability]` top-level → `observe`/`metrics_port`/`metrics_host`/`observe_interval_s`/`observe_every_n`.
- Deploy GitOps: `--config cam.toml` (KHÔNG cờ) mà vẫn bật `/metrics` nếu TOML khai báo.
- TÁI DÙNG đường #299 (không viết lại observer/exporter/merge-logic-mới ngoài parse + precedence).
- Additive + backward-compat (không section = hành vi hiện tại; cờ CLI vẫn hoạt động).
- Precedence RÕ RÀNG + kiểm-chứng-được giữa cờ CLI và TOML.
- Verify KHÔNG cần GPU (parse + merge + validate; không dựng detector/torch).

### Non-Goals
- KHÔNG observability PER-PIPELINE trong TOML (giữ top-level — observability là fleet-level; tránh schema-bloat, T-029).
- KHÔNG đổi ngữ nghĩa `_build_config_observability`/`_run_from_config`/exporter (#299) — chỉ THÊM nguồn tham số.
- KHÔNG auth/push-gateway/adapter Prometheus khác (giữ như metrics-http-endpoint).
- KHÔNG áp `[observability]` cho đường CLI-direct (không `--config`) — section chỉ thuộc file config.

## Glossary
- **`[observability]`** — section top-level trong file TOML app, ánh xạ tới bộ tham số observability của `_run_from_config`.
- **Precedence** — quy tắc quyết định khi CỜ CLI và TOML cùng khai báo 1 tham số (xem R3).
- **ObservabilityConfig** — DTO frozen @kernel giữ giá trị observability đọc từ TOML.

## Requirements

### Requirement 1: Section `[observability]` trong schema (kernel) + parse (loader)
**User Story:** Là operator GitOps, tôi muốn khai báo `/metrics` trong file TOML để deploy thuần-file.
#### Acceptance Criteria
- 1.1 — THE `kernel/config.py` SHALL thêm DTO `ObservabilityConfig` (frozen): `observe:bool=False`, `metrics_port:int|None=None`, `metrics_host:str="127.0.0.1"`, `observe_interval_s:float=0.0`, `observe_every_n:int=0`.
- 1.2 — THE `AppConfig` SHALL thêm field optional `observability: ObservabilityConfig | None = None` (mặc định None → không khai báo).
- 1.3 — THE `parse_app_config` SHALL parse table top-level `[observability]` (nếu có) → `ObservabilityConfig`, validate KIỂU từng field (`ConfigError` fail-fast nếu sai kiểu). Vắng section → `observability=None`.
- 1.4 — THE thay đổi SHALL frozen + MappingProxyType-style bất biến như các *Config khác (nhất quán schema).

### Requirement 2: Hợp nhất TOML + cờ CLI theo precedence rõ ràng
**User Story:** Là operator, tôi muốn cờ CLI ghi đè TOML cho tinh chỉnh ad-hoc, còn TOML là mặc định deploy.
#### Acceptance Criteria
- 2.1 — WHERE cả cờ CLI (được set tường minh) và TOML `[observability]` khai báo 1 tham số, THE hệ SHALL ưu tiên **CỜ CLI** (override ad-hoc); nếu cờ ở giá-trị-mặc-định-không-set → dùng TOML; nếu cả hai vắng → built-in default.
- 2.2 — THE `observe` (bool) SHALL dùng ngữ nghĩa OR an toàn: `--observe` cờ HOẶC TOML `observe=true` → bật (vì store_true không phân biệt "không set" với "false").
- 2.3 — THE `metrics_port`/`metrics_host`/`observe_interval_s`/`observe_every_n` SHALL: cờ CLI khác giá-trị-sentinel (None/không-set) → override TOML; ngược lại dùng TOML.
- 2.4 — THE smart-default `observe_interval_s=5.0` (khi `observe∨metrics_port` & nhịp=0) SHALL áp SAU merge (giữ hành vi #299).

### Requirement 3: Backward-compat + tái dùng đường #299
**User Story:** Là kiến trúc sư, tôi muốn thêm nguồn-TOML KHÔNG phá đường CLI-direct/`--config` hiện tại.
#### Acceptance Criteria
- 3.1 — WHERE file config KHÔNG có `[observability]` VÀ không cờ CLI, THE `_run_from_config` SHALL hành xử Y HỆT #299 (observer=None, không exporter).
- 3.2 — THE tính năng SHALL TÁI DÙNG `_build_config_observability`/exporter-lifecycle/bulkhead #299 KHÔNG đổi ngữ nghĩa (chỉ THÊM đường lấy tham số từ TOML).
- 3.3 — THE đường CLI-direct (không `--config`) SHALL KHÔNG bị ảnh hưởng (section chỉ thuộc file config).
- 3.4 — THE test observability #299 (`test_config_observability.py`) SHALL vẫn xanh (không regress).

### Requirement 4: Kiểm chứng KHÔNG cần GPU (xác định)
**User Story:** Là kỹ sư, tôi muốn test parse + merge + validate xác định trên máy dev no-GPU.
#### Acceptance Criteria
- 4.1 — Test parse `[observability]` từ TOML → `ObservabilityConfig` đúng field + validate kiểu sai → ConfigError.
- 4.2 — Test merge precedence: (a) chỉ TOML → dùng TOML; (b) cờ CLI override TOML; (c) không cả hai → default; (d) observe OR-semantics.
- 4.3 — Test backward-compat: config không `[observability]` → observability=None → hành vi #299 giữ.
- 4.4 — Test end-to-end no-GPU: `main(["--config", cfg_có_observability_metrics_port_0])` → `_run_from_config` nhận đúng tham số (spy) + rc hợp lệ.

## Tiêu chí ĐẬU (Definition of Done — PHA thiết kế)
`design.md` (0 diagnostic; đủ heading Kiro Spec Format: Overview/Architecture/Components/Data Models/Error Handling/
Testing Strategy + Correctness Properties map Requirements + doubt-driven review) có: (a) `ObservabilityConfig` DTO
+ `AppConfig.observability`; (b) parse trong `parse_app_config`; (c) hàm merge precedence TOML↔CLI (giải quyết
sentinel bool/None rõ ràng); (d) tái dùng `_build_config_observability`/#299; (e) test no-GPU parse+merge+backward-compat.
**KHÔNG code ở PHA này** — chờ user valid.
