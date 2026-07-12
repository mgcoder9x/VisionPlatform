# 11.01 — `@dataclass(frozen=True)`: vì sao config phải BẤT BIẾN

## 1. Thuộc về đâu
Layer **kernel** — file `vision-platform/src/vision_platform/kernel/config.py`. Đây là *hình dạng* (schema)
của 1 file cấu hình, KHÔNG đọc file, KHÔNG import adapter (bám ranh giới import-linter, xem `00-cau-chuyen.md`).

## 2. Cần biết trước
- `dataclass` = cách khai báo "lớp chứa dữ liệu" gọn (link `knowledge-base/00-GLOSSARY.md#dataclass` nếu lạ).
- Bài #02 (`code-lessons/02-data-objects`) đã dạy `frozen` cho `BBox`/`MediaPacket` — ở đây dùng lại cho config.

## 3. Code thật (quote nguyên văn — `kernel/config.py`)
```python
@dataclass(frozen=True)
class SourceConfig:
    """Khai báo nguồn frame: `type` (fake/noise/video/rtsp...) + `params` khớp chữ ký adapter."""
    type: str
    params: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _freeze_params(self.params))
```

## 4. Giải thích từng mẩu nhỏ nhất
- `@dataclass(frozen=True)` — biến class thành "hộp dữ liệu" + **khoá lại**: sau khi tạo, gán `obj.type = "x"`
  sẽ **raise `FrozenInstanceError`**. (mẩu 02 giải thích vì sao vẫn `__post_init__` sửa được `params`.)
- `type: str` — trường bắt buộc, kiểu chuỗi (vd `"rtsp"`).
- `params: Mapping = field(default_factory=dict)` — trường tuỳ chọn; mặc định = dict RỖNG MỚI mỗi lần
  (`default_factory` — KHÔNG dùng `= {}` vì dict mặc-định-chung sẽ bị chia sẻ giữa các instance = bẫy kinh điển).

## 5. Là gì (1–2 câu)
`SourceConfig` là bản ghi bất biến mô tả "nguồn frame loại gì + tham số gì". Các *Config khác
(`StageConfig`/`SinkConfig`/`DetectorConfig`/...) cùng khuôn.

## 6. Tại sao tồn tại / vấn đề nó giải
Config được truyền qua nhiều tầng (loader → factory → nhiều pipeline). Nếu **mutable**, một chỗ lỡ sửa
`pcfg.source.type` giữa chừng → các chỗ khác thấy giá trị KHÁC → bug "cấu hình đổi giữa đường" cực khó truy.
`frozen=True` khoá điều đó ngay từ gốc: cấu hình đọc-xong-là-đông-cứng.

## 7. Dùng ở đâu trong project
- `application/config_loader.py::parse_app_config` DỰNG các object này từ dict TOML.
- `profiles/pipeline_factory.py::build_runner` ĐỌC chúng (`pcfg.source.type`, `pcfg.source.params`) để dựng adapter.
- `profiles/vision_slice_app.py::_args_to_pipeline_config` (F1/#324) cũng dựng chúng từ cờ CLI.

## 8. Không có nó (nếu bỏ `frozen`) thì sao
Config thành mutable → mất bảo đảm bất biến; một bug ở tầng factory/entry có thể ghi đè cấu hình dùng chung →
pipeline sau chạy sai cấu hình mà không ai biết. `frozen` = "fail-fast": sửa nhầm → raise NGAY tại dòng sửa.

## 9. Ví von
Như **hợp đồng đã ký + đóng dấu**: đọc bao nhiêu cũng được, nhưng không ai tẩy xoá điều khoản giữa chừng.

## 10. Liên kết bức tranh lớn
DTO bất biến ở **kernel** = "danh từ" của hệ; "động từ" (dựng object) ở **profiles**. Tách danh-từ/động-từ theo tầng.

## 11. Cạm bẫy
- `= {}` hay `= []` làm default → **chia sẻ 1 object giữa mọi instance** (bug). Luôn `field(default_factory=...)`.
- `frozen=True` chỉ chặn gán trường; KHÔNG tự đóng băng `dict`/`list` BÊN TRONG → phải `_freeze_params` (mẩu 02).

## 12. Tự kiểm (Feynman)
- Giải thích bằng lời mình: vì sao config mutable nguy hiểm trong hệ nhiều-pipeline?
- `field(default_factory=dict)` khác `= {}` ở điểm nào? Bug gì nếu dùng `= {}`?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`kernel/config.py` (đọc thật #322/#324) · bài #02 (frozen dataclass) · D-042 (config schema). Độ chắc: cao (quote trực tiếp).
