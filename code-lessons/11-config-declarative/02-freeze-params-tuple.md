# 11.02 — Đóng băng SÂU: `_freeze_params` (MappingProxyType) + list→`tuple`

## 1. Thuộc về đâu
kernel — `kernel/config.py`. Nối tiếp mẩu 01 (frozen chỉ khoá GÁN TRƯỜNG, chưa khoá nội dung dict/list bên trong).

## 2. Cần biết trước
- mẩu 01 (`frozen=True`). `dict`/`list` là *mutable* (sửa nội dung được dù biến "đông cứng").
- `MappingProxyType` = "khung nhìn CHỈ-ĐỌC" bọc quanh 1 dict (link `knowledge-base/00-GLOSSARY.md#mappingproxytype` nếu lạ).

## 3. Code thật (quote nguyên văn — `kernel/config.py`)
```python
def _freeze_params(params: Optional[Mapping]) -> Mapping:
    """Trả bản đọc-chỉ (MappingProxyType) của params; None → rỗng."""
    return MappingProxyType(dict(params)) if params is not None else MappingProxyType({})
```
```python
    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))
```
```python
@dataclass(frozen=True)
class PipelineConfig:
    id: str
    source: SourceConfig
    stages: Sequence[StageConfig] = ()
    sinks: Sequence[SinkConfig] = ()
    detector: Optional[DetectorConfig] = None
    max_frames: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "sinks", tuple(self.sinks))
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_freeze_params(params)` — nhận dict thường → trả `MappingProxyType(dict(params))`: `dict(params)` **copy**
  (để proxy không dính tới dict gốc caller còn giữ), rồi bọc proxy chỉ-đọc. `params is None` → proxy rỗng.
- `__post_init__` — hàm dataclass tự gọi NGAY SAU khi tạo. Vì class `frozen`, gán thường `self.params = ...`
  bị chặn → dùng `object.__setattr__(self, "params", ...)` (đường vòng hợp lệ DUY NHẤT để set 1 lần lúc khởi tạo).
- `PipelineConfig.__post_init__` — ép `stages`/`sinks` (người dùng truyền list) thành `tuple` (tuple bất biến).
  `Sequence[...] = ()` default = tuple rỗng.

## 5. Là gì
Cơ chế **đóng băng SÂU**: không chỉ khoá gán trường (frozen) mà còn khoá NỘI DUNG (`params` chỉ-đọc, danh
sách stage/sink thành tuple).

## 6. Tại sao tồn tại
`frozen=True` (mẩu 01) KHÔNG ngăn `pcfg.source.params["type"] = "x"` hay `pcfg.stages.append(...)` — vì dict/list
vẫn mutable. Đó là lỗ hổng: cấu hình "tưởng bất biến" vẫn sửa được nội dung. `_freeze_params` + `tuple` bịt lỗ đó
→ bất biến THẬT SỰ, đúng Requirement "không sửa cấu hình toàn cục sau parse".

## 7. Dùng ở đâu
Mọi *Config có `params` (`SourceConfig`/`StageConfig`/`SinkConfig`/`DetectorConfig`) gọi `_freeze_params` trong
`__post_init__`. `PipelineConfig`/`AppConfig` ép list→tuple. → sau `parse_app_config`, toàn cây config đông cứng.

## 8. Không có nó thì sao
Thiếu `_freeze_params`: một adapter/stage lỡ `params["x"]=...` sẽ sửa cấu hình mà các pipeline khác dùng chung →
bug ẩn. Thiếu `tuple(...)`: ai đó `stages.append(...)` giữa chừng → pipeline chạy khác khai báo.

## 9. Ví von
`frozen` = khoá cửa phòng; `_freeze_params`/`tuple` = niêm phong luôn từng ngăn kéo bên trong. Khoá cửa mà ngăn
kéo mở được thì vẫn mất đồ.

## 10. Liên kết bức tranh lớn
Bất biến sâu là nền cho "1 nguồn cấu hình chia sẻ an toàn qua nhiều pipeline/tiến trình" — hợp với pattern
Immutability + CoW (bài #02, `docs/ARCHITECTURE.md` §5).

## 11. Cạm bẫy
- Quên `dict(params)` (copy) → proxy bọc thẳng dict caller: caller sửa dict gốc thì "bản chỉ-đọc" cũng đổi theo (rò).
- `MappingProxyType` chỉ chặn ghi ở lớp ngoài; nếu value là dict lồng thì lớp trong vẫn mutable (ở đây params phẳng nên đủ).

## 12. Tự kiểm (Feynman)
- Vì sao `frozen=True` CHƯA đủ để config bất biến? Cho 1 ví dụ sửa được dù đã frozen.
- `object.__setattr__` dùng để làm gì trong `__post_init__` của class frozen?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/config.py` (đọc thật #322/#324). Độ chắc: cao (quote trực tiếp). Hành vi FrozenInstanceError = đặc tính dataclass chuẩn [độ chắc: cao].
