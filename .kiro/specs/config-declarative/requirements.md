# Requirements Document

> **config-declarative** — đóng lỗ hổng K-040 **C2 (no-config)**. Workflow: Design-First → suy ra từ `design.md`.
> Mỗi requirement trỏ ngược mục design/code nguồn (chống bịa). CHƯA code — hợp đồng để valid trước triển khai.
> **Nhãn:** 🟢 [GROUNDED] · 🟡 [THIẾT KẾ MỚI] · 🔴 [CẦN KIỂM CHỨNG].
> **EARS:** WHEN/WHILE/IF…THEN/WHERE + "THE SYSTEM SHALL". "Hệ thống" = lớp config (`kernel/config.py` +
> `application/config_loader.py` + `profiles/pipeline_factory.py`).

## Introduction

Việc dựng pipeline hiện CỨNG trong `vision_slice_app.py` (argparse, 1 pipeline/tiến trình). Đích ~100 camera
(C-014) đòi **khai báo** toàn bộ (camera + nguồn + stages + sink) trong 1 file → 1 launcher dựng nhiều pipeline
KHÔNG sửa code. v1: file TOML tĩnh (`tomllib` stdlib, không thêm dep) → `AppConfig` (typed, immutable) →
`PipelineFactory` dựng đúng object hiện có → `PipelineRunner`. Additive: KHÔNG sửa runner/adapter/stage (giữ 379/1).

Phạm vi (design §Overview): parse+validate config, build 1 pipeline/PipelineRunner từ config, registry type mở rộng.
Ngoài phạm vi: chạy N tiến trình song song/GPU-scheduling (scale-architecture), hot-reload, secret management (K-031).

## Requirements

### Requirement 1: Schema khai báo + parse thành model bất biến

**User Story:** Là kỹ sư vận hành, tôi muốn khai báo pipeline trong file config, để thêm/sửa camera mà không sửa code.

#### Acceptance Criteria
*(Nguồn design: §Data Models · §Components (`kernel/config.py`) · Property 1, 4.)*

1. WHEN `parse_app_config(raw)` nhận dict config hợp lệ, THE SYSTEM SHALL trả `AppConfig` phản ánh đúng số `pipelines`, thứ tự `stages`, và `params` của mỗi phần.
2. THE SYSTEM SHALL biểu diễn `AppConfig` và mọi `*Config` là dataclass **frozen**, với `params` bất biến (không sửa được sau parse).
3. WHERE một pipeline không khai báo `sinks`, THE SYSTEM SHALL coi là danh sách rỗng (không lưu trữ — hợp C-013 "lưu trữ optional").
4. WHERE một pipeline không có stage `detect`, THE SYSTEM SHALL cho phép `detector` vắng mặt (None).

### Requirement 2: Validate fail-fast, thông điệp rõ

**User Story:** Là người vận hành, tôi muốn config sai bị từ chối ngay với lý do rõ, để sửa nhanh, không chạy nửa vời.

#### Acceptance Criteria
*(Nguồn design: §Error Handling · Property 2.)*

1. IF config thiếu field bắt buộc, hoặc `type` không có trong registry, hoặc `id` pipeline trùng, THEN THE SYSTEM SHALL raise `ConfigError` và KHÔNG dựng object nào.
2. WHEN `ConfigError` được phát, THE SYSTEM SHALL nêu rõ pipeline (`id`) và khoá/`type` gây lỗi (liệt kê type hợp lệ khi type lạ).
3. WHEN file config không tồn tại hoặc sai cú pháp TOML, THE SYSTEM SHALL raise `ConfigError` bọc nguyên nhân gốc (path / vị trí TOML).

### Requirement 3: Dựng pipeline từ config, tương đương wiring tay, không phá base

**User Story:** Là kỹ sư, tôi muốn config dựng ra pipeline giống hệt cách `vision_slice_app` dựng tay, để tin cậy và không hồi quy.

#### Acceptance Criteria
*(Nguồn design: §Architecture · §Components (`pipeline_factory.py`) · Property 3, 5. Code nền: `vision_slice_app._build_*`, `PipelineRunner`.)*

1. WHEN `build_runner(pcfg)` nhận `PipelineConfig` hợp lệ, THE SYSTEM SHALL trả `PipelineRunner` với cùng cấu trúc (source + `SyncLinearExecutor([stages])` + `CompositeSink([sinks])`) như wiring tay hiện tại.
2. THE SYSTEM SHALL NOT sửa đổi `PipelineRunner`/`SyncLinearExecutor`/adapter/stage hiện có; baseline **379 passed/1 skipped** phải giữ nguyên.
3. WHERE cần thêm loại source/detector/stage/sink mới, THE SYSTEM SHALL cho đăng ký qua registry (thêm entry) mà KHÔNG sửa `ConfigLoader`/`PipelineFactory` lõi.

### Requirement 4: Ranh giới layer + không thêm dependency

**User Story:** Là người bảo trì kiến trúc, tôi muốn lớp config tôn trọng hexagonal + không kéo dep mới, để giữ base gọn và đúng ranh giới.

#### Acceptance Criteria
*(Nguồn design: §Architecture (layer) · §Overview (tomllib stdlib). Ràng buộc: import-linter 5 contract.)*

1. THE SYSTEM SHALL đặt `AppConfig`/schema ở `kernel` dưới dạng dataclass THUẦN (chỉ stdlib; không I/O, không đọc file, không import adapter).
2. THE SYSTEM SHALL đặt việc đọc file + dựng adapter ở tầng `application`/`profiles` (composition root).
3. THE SYSTEM SHALL dùng `tomllib` (Python 3.11 stdlib) để đọc config; KHÔNG thêm dependency runtime mới.

## Glossary

- **AppConfig:** model bất biến (frozen dataclass) phản ánh toàn bộ file config; gồm danh sách `PipelineConfig`.
- **PipelineConfig:** khai báo 1 pipeline: `id`, `source`, `stages`, `sinks`, `detector?`, `max_frames?`.
- **Registry:** bảng map `type` (chuỗi) → hàm dựng object (source/detector/stage/sink); điểm mở rộng không-sửa-lõi.
- **ConfigLoader:** đọc file TOML (`tomllib`) + validate → `AppConfig`. `parse_app_config` (dict→AppConfig) tách để test không cần file.
- **PipelineFactory:** map `PipelineConfig` → dựng object hiện có → `PipelineRunner` (additive).
- **ConfigError:** ngoại lệ fail-fast khi config sai (thiếu field / type lạ / id trùng / TOML hỏng).
- **tomllib:** thư viện đọc TOML trong Python 3.11 stdlib (chỉ đọc) — không cần cài thêm.
