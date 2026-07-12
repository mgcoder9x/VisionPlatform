# 11.07 — `_parse_observability`: validate KIỂU tường minh (chặn `bool` lọt `int`)

## 1. Thuộc về đâu
application — `config_loader.py::_parse_observability`. Parse bảng TOP-LEVEL `[observability]` → `ObservabilityConfig` (mẩu 03).

## 2. Cần biết trước
- mẩu 03 (`ObservabilityConfig`), mẩu 05 (`_require`). Bẫy Python: `bool` là **lớp con của `int`** →
  `isinstance(True, int)` trả `True` (link `knowledge-base/00-GLOSSARY.md#bool-la-int` nếu lạ).

## 3. Code thật (quote nguyên văn — `config_loader.py`)
```python
def _parse_observability(raw: Any) -> ObservabilityConfig:
    """Parse table top-level `[observability]` → `ObservabilityConfig`. Validate KIỂU từng field (fail-fast).

    KHÔNG dùng bool vô-tình cho int (isinstance(True,int) là True trong Python) → kiểm loại tường minh."""
    _require(isinstance(raw, dict), f"observability phải là bảng, nhận {type(raw).__name__}")

    observe = raw.get("observe", False)
    _require(isinstance(observe, bool), f"observability.observe phải là bool (nhận {observe!r})")

    port = raw.get("metrics_port")
    _require(port is None or (isinstance(port, int) and not isinstance(port, bool)),
             f"observability.metrics_port phải là số nguyên hoặc vắng (nhận {port!r})")

    host = raw.get("metrics_host", "127.0.0.1")
    _require(isinstance(host, str) and host != "", f"observability.metrics_host phải là chuỗi không rỗng (nhận {host!r})")

    interval = raw.get("observe_interval_s", 0.0)
    _require(isinstance(interval, (int, float)) and not isinstance(interval, bool),
             f"observability.observe_interval_s phải là số (nhận {interval!r})")

    every = raw.get("observe_every_n", 0)
    _require(isinstance(every, int) and not isinstance(every, bool),
             f"observability.observe_every_n phải là số nguyên (nhận {every!r})")

    return ObservabilityConfig(
        observe=observe, metrics_port=port, metrics_host=host,
        observe_interval_s=float(interval), observe_every_n=every,
    )
```

## 4. Giải thích từng mẩu nhỏ nhất
- `isinstance(observe, bool)` — `observe` PHẢI đúng bool (không nhận 0/1/int).
- `isinstance(port, int) and not isinstance(port, bool)` — **mấu chốt**: nếu chỉ `isinstance(port, int)` thì
  `metrics_port = true` (TOML) sẽ LỌT (vì `True` là int) → cổng `True`?! `and not isinstance(port, bool)` loại bỏ.
- `port is None or (...)` — cho phép VẮNG (None) = không bật exporter.
- `interval`: `(int, float)` and not bool — chấp nhận số, chặn bool. `float(interval)` chuẩn hoá về float khi dựng DTO.
- `every`: int and not bool.
- Trả `ObservabilityConfig(...)` (DTO frozen mẩu 03).

## 5. Là gì
Bộ parse + kiểm-kiểu-nghiêm cho section observability, đặc biệt bịt bẫy `bool`-lọt-`int`.

## 6. Tại sao tồn tại
`[observability]` map thẳng vào tham số vận hành (`metrics_port` mở cổng HTTP, `observe_interval_s` nhịp emit).
Sai kiểu ở đây = hành vi vận hành sai (mở cổng số `True`, nhịp emit lạ). Kiểm tường minh → chặn tại parse, báo rõ.

## 7. Dùng ở đâu
`parse_app_config`: `observability = _parse_observability(obs_raw) if obs_raw is not None else None` → gắn vào
`AppConfig.observability`. Sau đó `vision_slice_app._merge_observability` hợp nhất với cờ CLI (chủ đề #13).

## 8. Không có nó thì sao
Thiếu `and not isinstance(..., bool)`: `metrics_port = true` trong TOML lọt qua → `True` truyền xuống làm cổng
→ lỗi khó hiểu lúc bind socket (hoặc bind cổng 1). Thiếu cả hàm: observability không kiểu-hoá, sai nổ muộn ở runtime.

## 9. Ví von
Máy đếm tiền phân biệt tờ THẬT với tờ "hao hao": `True` trông giống `1` nhưng KHÔNG phải số nguyên hợp lệ cho "số cổng".

## 10. Liên kết bức tranh lớn
Ví dụ điển hình "validate ở BIÊN nhập liệu" + bẫy ngôn ngữ Python. Nối chuỗi observability: parse (đây) → merge
(CLI↔TOML) → dựng observer/exporter (chủ đề #13).

## 11. Cạm bẫy
- Quên `not isinstance(x, bool)` khi kiểm int/float → bool lọt (bẫy phổ biến nhất khi validate config Python).
- `observability=None` (không khai) KHÁC `ObservabilityConfig()` — mẩu 03 đã nêu; ảnh hưởng precedence merge (#13).

## 12. Tự kiểm (Feynman)
- Vì sao `isinstance(True, int)` là `True`? Nó gây bug gì cho `metrics_port` nếu không chặn?
- `metrics_port` vắng (None) nghĩa là gì về hành vi observability?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`application/config_loader.py::_parse_observability` (đọc thật #322/#324) · D-086 (observability trong TOML). Độ chắc: cao (quote trực tiếp). "`bool` là con của `int`" = đặc tính Python [độ chắc: cao].
