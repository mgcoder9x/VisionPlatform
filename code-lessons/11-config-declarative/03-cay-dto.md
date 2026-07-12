# 11.03 — Cây DTO: `AppConfig` → `PipelineConfig` → Source/Stage/Sink/Detector/Observability

## 1. Thuộc về đâu
kernel — `kernel/config.py`. Đây là "bản đồ" cả file config: 1 `AppConfig` ứng với 1 file `.toml`.

## 2. Cần biết trước
mẩu 01–02 (frozen + đóng băng sâu). `Optional[X]` = "X hoặc None". `Sequence[X]` = "dãy các X".

## 3. Code thật (quote nguyên văn — `kernel/config.py`)
```python
@dataclass(frozen=True)
class ObservabilityConfig:
    observe: bool = False
    metrics_port: Optional[int] = None
    metrics_host: str = "127.0.0.1"
    observe_interval_s: float = 0.0
    observe_every_n: int = 0


@dataclass(frozen=True)
class AppConfig:
    """Toàn bộ file config: danh sách pipeline (mỗi cái 1 camera/luồng) + observability (optional, top-level)."""
    pipelines: Sequence[PipelineConfig] = ()
    observability: Optional[ObservabilityConfig] = None   # None = không khai báo (backward-compat)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pipelines", tuple(self.pipelines))
```
(`PipelineConfig` xem mẩu 02; `SourceConfig/StageConfig/SinkConfig/DetectorConfig` cùng khuôn `type`+`params`.)

## 4. Giải thích từng mẩu nhỏ nhất
- **`AppConfig`** = gốc cây = 1 file config. Chứa `pipelines` (nhiều `PipelineConfig`) + `observability` optional.
- **`PipelineConfig`** = 1 camera/luồng: `id` (định danh, phải DUY NHẤT) + `source` + `stages[]` + `sinks[]` +
  `detector?` + `max_frames?`.
- **`SourceConfig/StageConfig/SinkConfig/DetectorConfig`** = mảnh `{type, params}` — `type` là chuỗi tra registry
  (mẩu 08), `params` khớp chữ ký builder.
- **`ObservabilityConfig`** = TOP-LEVEL (thuộc `AppConfig`, KHÔNG per-pipeline) — quyết định tiến-trình
  ("1 process = 1 scrape target"). Mặc định TẮT (`observe=False`, `metrics_port=None`).
- `observability: Optional[...] = None` — không khai `[observability]` trong TOML → `None` → hành vi cũ giữ
  nguyên (backward-compat).

## 5. Là gì
Cấu trúc phân cấp phản ánh 1:1 file TOML: `[[pipelines]]` → `PipelineConfig`; `[observability]` → `ObservabilityConfig`.

## 6. Tại sao tồn tại
Cần 1 mô hình bộ-nhớ rõ ràng, kiểu-hoá, bất biến cho "toàn bộ ý muốn deploy" — để tầng sau (factory) chỉ việc
duyệt cây mà dựng, không phải đoán hình dạng dict thô. Kiểu tường minh (`Optional[int]`...) giúp đọc + bắt lỗi sớm.

## 7. Dùng ở đâu
- `config_loader.parse_app_config` → trả về `AppConfig` (dựng cả cây).
- `vision_slice_app._run_from_config`: `app = load_app_config(path)`; lặp `for pcfg in app.pipelines: build_runner(pcfg)`.
- `observability` được `_merge_observability` (CLI↔TOML) tiêu thụ (chủ đề #13 observability sẽ đào sâu).

## 8. Không có nó thì sao
Không có cây DTO → factory phải làm việc với dict thô (`raw["pipelines"][i]["source"]["type"]`) → dễ KeyError
runtime, không kiểu, không bất biến, khó test. Cây DTO = "bản dịch có kiểm" từ dict-thô sang object an toàn.

## 9. Ví von
`AppConfig` như **tờ khai đăng ký cả đội xe**: mỗi dòng (`PipelineConfig`) là 1 xe (camera) + thông số; phần
chung (`observability`) ghi 1 lần ở đầu tờ.

## 10. Liên kết bức tranh lớn
Đây là "danh từ trung tâm" nối 3 tầng: loader (application) SINH ra nó · factory (profiles) TIÊU THỤ nó · entry
điều phối. Hình dạng ổn định = hợp đồng giữa các tầng.

## 11. Cạm bẫy
- `pipelines: Sequence[...] = ()` default tuple rỗng (không `= []`); `__post_init__` ép tuple (mẩu 02).
- `observability=None` KHÁC `ObservabilityConfig()` (mọi field default): `None` = "không khai" (dùng cho merge precedence, chủ đề #13).

## 12. Tự kiểm (Feynman)
- Vẽ cây DTO từ trí nhớ: `AppConfig` chứa gì? `PipelineConfig` chứa gì?
- Vì sao `observability` ở TOP-LEVEL (AppConfig) chứ không trong từng `PipelineConfig`?
- `observability=None` vs `ObservabilityConfig()` khác nhau chỗ nào, dùng để làm gì?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/config.py` (đọc thật #322/#324) · D-086 (observability trong TOML) · D-042 (config schema). Độ chắc: cao (quote trực tiếp).
