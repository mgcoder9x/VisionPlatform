# 11 — Config khai báo — MỤC LỤC (các mẩu nhỏ nhất)

> Đọc `00-cau-chuyen.md` trước (vòng cung vấn-đề→giải-pháp). Mỗi mẩu = 1 ý nhỏ nhất, quote code thật + cite path.
> Trạng thái: ⬜ chưa viết · 🔵 đang · ✅ đã viết đủ (+ code verify). Bài tạo DẦN theo yêu cầu (luật không-hàng-loạt).

| # | Mẩu (ý nhỏ nhất) | File code thật bám vào | Trạng thái |
|---|---|---|---|
| 01 | `@dataclass(frozen=True)` cho config — vì sao BẤT BIẾN (chống sửa lén cấu hình toàn cục) | `kernel/config.py` (SourceConfig) | ✅ `01-dataclass-frozen.md` |
| 02 | `MappingProxyType` + `tuple` — đóng băng `params`/list sau parse (`_freeze_params`, `__post_init__`) | `kernel/config.py` | ✅ `02-freeze-params-tuple.md` |
| 03 | Cây DTO: `AppConfig` → `PipelineConfig` → Source/Stage/Sink/Detector/Observability | `kernel/config.py` | ✅ `03-cay-dto.md` |
| 04 | `tomllib.load` (stdlib 3.11) + mở `'rb'` — đọc TOML KHÔNG thêm dependency | `application/config_loader.py::load_app_config` | ⬜ |
| 05 | `_require`/`_require_str`/`_typed` — validate CẤU TRÚC + `ConfigError` fail-fast kèm vị trí | `application/config_loader.py` | ⬜ |
| 06 | Vì sao loader (application) KHÔNG kiểm `type ∈ registry` — giữ ranh giới không phụ thuộc adapter | `config_loader.py` vs `pipeline_factory.py` | ⬜ |
| 07 | `_parse_observability` — validate KIỂU tường minh (chặn `bool` lọt `int`: `isinstance(True,int)`) | `config_loader.py::_parse_observability` | ⬜ |
| 08 | REGISTRY `DEFAULT_REGISTRY` — bảng `type`(chuỗi)→builder; thêm loại = 1 entry (Open/Closed) | `pipeline_factory.py` | ⬜ |
| 09 | Builder + lazy-import (vì sao import trong hàm, không đầu file — né kéo torch/cv2) | `pipeline_factory.py::_det_pt/_src_rtsp/...` | ⬜ |
| 10 | `allowed_params` + `_check_params` — typo-guard (K-046), chặn key lạ nuốt im lặng | `pipeline_factory.py` | ⬜ |
| 11 | `_lookup` — tra registry, type lạ → `ConfigError` liệt kê type hợp lệ | `pipeline_factory.py::_lookup` | ⬜ |
| 12 | `validate_config` (dry-run, no-GPU) vs `build_runner` (dựng thật) — vì sao tách 2 | `pipeline_factory.py` | ⬜ |
| 13 | `build_runner` — ráp source+stages+sinks → `SyncLinearExecutor`+`CompositeSink`→`PipelineRunner` | `pipeline_factory.py::build_runner` | ⬜ |
| 14 | F1 (#324): `_args_to_pipeline_config` — CLI cũng sinh `PipelineConfig` → cùng `build_runner` (1 nguồn lắp-ráp) | `vision_slice_app.py::_args_to_pipeline_config` | ⬜ |
| 15 | `extra_sinks` — chèn sink presentation (`_TrackSummarySink`) ngoài-config vào composite | `pipeline_factory.py::build_runner` + `vision_slice_app.py` | ⬜ |

**Ghi chú phạm vi:** đây là chủ đề #11 (config-declarative) — spec-based, KHÔNG có folder `implement/11` (các
tính năng sau #10 làm theo spec). Số 11 là số nối tiếp trong code-lessons cho phần "sản phẩm sau Module 03".
