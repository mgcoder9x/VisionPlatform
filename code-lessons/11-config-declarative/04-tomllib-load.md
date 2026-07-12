# 11.04 — Đọc file TOML bằng `tomllib` (stdlib 3.11) + `ConfigError` fail-fast

## 1. Thuộc về đâu
Layer **application** — `vision-platform/src/vision_platform/application/config_loader.py`. Tầng NÀY chạm I/O
(đọc file); DTO (kernel, mẩu 01–03) thì KHÔNG. Đúng ranh giới: kernel thuần, application được đọc file.

## 2. Cần biết trước
- cây DTO (mẩu 03). `tomllib` = trình đọc TOML có SẴN trong Python 3.11+ (không cần cài thêm).
- `open(..., "rb")` = mở nhị phân (`tomllib` yêu cầu bytes, không phải text).

## 3. Code thật (quote nguyên văn — `application/config_loader.py`)
```python
class ConfigError(Exception):
    """Config sai (thiếu field / type không phải chuỗi / id trùng / TOML hỏng / file thiếu). Fail-fast."""
```
```python
def load_app_config(path: str) -> AppConfig:
    """Đọc file TOML (`tomllib`, mở 'rb') → `parse_app_config`. File thiếu/sai TOML → `ConfigError`."""
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"không tìm thấy file config: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML sai cú pháp trong {path}: {e}") from e
    return parse_app_config(raw)
```

## 4. Giải thích từng mẩu nhỏ nhất
- `import tomllib` (đầu file) — thư viện chuẩn 3.11; **KHÔNG thêm dependency** (lý do chọn TOML, xem cau-chuyen nhịp 3).
- `open(path, "rb")` — `"rb"` = read-binary; `tomllib.load` chỉ nhận file nhị phân (raise nếu mở text `"r"`).
- `tomllib.load(f)` → trả `dict` Python thô (chưa phải DTO).
- `except FileNotFoundError` / `except tomllib.TOMLDecodeError` → gói thành `ConfigError` với thông điệp RÕ
  (kèm path). `raise ... from e` giữ nguyên nhân gốc (chuỗi exception, dễ debug).
- `return parse_app_config(raw)` — chuyển dict thô → cây DTO (mẩu 05 dựng + validate).

## 5. Là gì
Cổng vào từ "file trên đĩa" → "dict Python", biến mọi lỗi đọc/cú pháp thành 1 loại lỗi thống nhất `ConfigError`.

## 6. Tại sao tồn tại
Tách I/O (đọc file) khỏi parse (`parse_app_config` thuần, nhận dict → test KHÔNG cần file thật). Gói lỗi thành
`ConfigError` để nơi gọi (`vision_slice_app`) chỉ cần bắt 1 loại + in gọn, không lộ traceback thô cho operator.

## 7. Dùng ở đâu
- `vision_slice_app._validate_config_only(path)`: `app = load_app_config(path)` (đường `--validate`).
- `vision_slice_app._run_from_config(path)`: `app = load_app_config(path)` (đường chạy `--config`).

## 8. Không có nó thì sao
Không tách: parse dính chặt việc mở file → test phải tạo file tạm; lỗi file/cú pháp ném `FileNotFoundError`/
`TOMLDecodeError` thô lên tận CLI → operator thấy traceback khó hiểu thay vì "không tìm thấy file config: X".

## 9. Ví von
Như quầy lễ tân: nhận "giấy tờ" (file), kiểm đọc-được không, rồi chuyển vào trong xử lý; giấy rách/thiếu → báo lỗi lịch sự ngay quầy.

## 10. Liên kết bức tranh lớn
Đây là bước 1 của chuỗi 3 tầng (cau-chuyen): **load_app_config (I/O) → parse_app_config (validate cấu trúc) →
build_runner (dựng object)**.

## 11. Cạm bẫy
- Mở `"r"` (text) thay `"rb"` → `tomllib` raise TypeError. Luôn `"rb"`.
- Python < 3.11 KHÔNG có `tomllib` (khi đó phải `tomli`) — dự án yêu cầu `>=3.11` (pyproject) nên an toàn.

## 12. Tự kiểm (Feynman)
- Vì sao tách `load_app_config` (I/O) khỏi `parse_app_config` (thuần)? Lợi cho test thế nào?
- `ConfigError` gom những loại lỗi nào? Vì sao gom về 1 loại?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`application/config_loader.py` (đọc thật phiên #322/#324). Độ chắc: cao (quote trực tiếp). `tomllib` là stdlib 3.11 [độ chắc: cao — pyproject `requires-python>=3.11`].
