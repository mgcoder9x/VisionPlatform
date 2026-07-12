# 11.05 — Validate CẤU TRÚC: `_require` / `_require_str` / `_typed` + fail-fast kèm VỊ TRÍ

## 1. Thuộc về đâu
application — `config_loader.py::parse_app_config` + 3 helper. Biến dict-thô → cây DTO, chặn dict sai NGAY.

## 2. Cần biết trước
mẩu 03 (cây DTO), mẩu 04 (`ConfigError`). "Validate cấu trúc" = kiểm *hình dạng* (có field bắt buộc, đúng
kiểu-thô, id không trùng), CHƯA kiểm "type có tồn tại trong registry" (đó là mẩu 06 + tầng factory).

## 3. Code thật (quote nguyên văn — `config_loader.py`)
```python
def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def _require_str(value: Any, what: str) -> str:
    _require(isinstance(value, str) and value != "", f"{what} phải là chuỗi không rỗng (nhận: {value!r})")
    return value


def _typed(raw: Any, what: str) -> tuple[str, dict]:
    """Ép 1 mục {type, params?} → (type:str, params:dict). Validate cấu trúc."""
    _require(isinstance(raw, dict), f"{what} phải là bảng (table), nhận {type(raw).__name__}")
    t = _require_str(raw.get("type"), f"{what}.type")
    params = raw.get("params", {})
    _require(isinstance(params, dict), f"{what}.params phải là bảng, nhận {type(params).__name__}")
    return t, params
```
```python
    for i, p in enumerate(pipelines_raw):
        where = f"pipelines[{i}]"
        _require(isinstance(p, dict), f"{where} phải là bảng")
        pid = _require_str(p.get("id"), f"{where}.id")
        _require(pid not in seen_ids, f"id pipeline trùng: {pid!r} (mỗi pipeline phải duy nhất)")
        seen_ids.add(pid)
        s_type, s_params = _typed(p.get("source"), f"{where}.source")
        source = SourceConfig(s_type, s_params)
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_require(cond, msg)` — "assert có kiểm soát": sai → `ConfigError(msg)`. Dùng khắp nơi để mọi lỗi cấu trúc
  cùng 1 loại + thông điệp tuỳ biến.
- `_require_str(value, what)` — bắt buộc chuỗi KHÔNG rỗng; `what` = *tên trường* để thông điệp chỉ đúng chỗ sai.
- `_typed(raw, what)` — ép 1 khối `{type, params?}`: phải là bảng, có `type` chuỗi, `params` (nếu có) là bảng.
  Trả `(type, params)` cho caller dựng `SourceConfig(type, params)` v.v.
- `where = f"pipelines[{i}]"` — **VỊ TRÍ**: mọi thông điệp lỗi kèm `pipelines[2].source.type` → operator biết
  sửa dòng nào trong TOML.
- `seen_ids` — chặn `id` trùng giữa các pipeline (id phải duy nhất để log/metrics phân biệt camera).

## 5. Là gì
Bộ kiểm *hình dạng* dict TOML, fail-fast, thông điệp kèm đường-dẫn-trường.

## 6. Tại sao tồn tại
Dict từ TOML là "dữ liệu lạ" (người gõ tay, dễ sai). Nếu dựng DTO thẳng mà không kiểm → lỗi nổ MUỘN (KeyError
lúc factory dựng, hoặc tệ hơn lúc runtime). Kiểm sớm + chỉ rõ vị trí = sửa rẻ, không "mò".

## 7. Dùng ở đâu
`parse_app_config` gọi `_typed`/`_require` cho từng `source`/`stages[j]`/`sinks[j]`/`detector` của mỗi pipeline
→ dựng `SourceConfig`/`StageConfig`/... (mẩu 03). Chạy qua `load_app_config` (mẩu 04) hoặc test tiêm dict.

## 8. Không có nó thì sao
Bỏ validate cấu trúc: TOML thiếu `type` → `KeyError` thô ở factory; `params` là chuỗi thay vì bảng → lỗi mơ hồ
sâu trong builder; id trùng → 2 camera cùng nhãn, metrics/log lẫn lộn mà không báo.

## 9. Ví von
Như hải quan kiểm tờ khai: đủ mục chưa, đúng ô chưa, mã số có trùng ai không — thiếu/sai thì trả lại NGAY tại cửa, ghi rõ ô nào.

## 10. Liên kết bức tranh lớn
Bước 2 của chuỗi 3 tầng. Cố ý chỉ kiểm *cấu trúc* (không kiểm registry) để tầng application KHÔNG phụ thuộc
adapter — xem mẩu 06.

## 11. Cạm bẫy
- `{value!r}` (repr) trong thông điệp → thấy rõ `''` vs `None` vs `0` (khác nhau khi debug).
- `raw.get("params", {})` mặc định bảng rỗng → cho phép khối không có `params` (hợp lệ), nhưng nếu người dùng
  ghi `params = "abc"` (chuỗi) thì `_require(isinstance(params, dict))` bắt.

## 12. Tự kiểm (Feynman)
- Vì sao mọi thông điệp lỗi kèm `where` (vị trí)? Lợi cho operator thế nào?
- `_typed` kiểm những gì? Nó KHÔNG kiểm gì (dành cho tầng nào)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`application/config_loader.py` (đọc thật #322/#324). Độ chắc: cao (quote trực tiếp).
