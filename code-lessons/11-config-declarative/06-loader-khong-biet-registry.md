# 11.06 — Vì sao loader (application) KHÔNG kiểm `type ∈ registry` — giữ RANH GIỚI tầng

## 1. Thuộc về đâu
application — `config_loader.py`. Đây là mẩu về QUYẾT ĐỊNH KIẾN TRÚC (phân tách trách nhiệm), không phải 1 dòng code.

## 2. Cần biết trước
- mẩu 05 (loader validate cấu trúc). "registry" = bảng `type→builder` ở `pipeline_factory.py` (tầng profiles, mẩu 08).
- Ranh giới import-linter: **application KHÔNG được import adapters/profiles** (xem `docs/ARCHITECTURE.md` §2.1 contract #4).

## 3. Code thật (quote — docstring `parse_app_config`, `config_loader.py`)
```python
def parse_app_config(raw: dict) -> AppConfig:
    """Dựng `AppConfig` từ dict đã đọc + validate CẤU TRÚC. Sai → `ConfigError`.

    KHÔNG kiểm `type` có trong registry (việc của pipeline_factory — layer profiles).
    """
```
Và ở đầu file:
```python
"""Layer: application (được import kernel + stdlib; KHÔNG import adapters/profiles — import-linter ép). Do đó
loader chỉ validate **CẤU TRÚC** (field bắt buộc, id duy nhất, type là chuỗi không rỗng). Kiểm `type` có
trong registry là việc của `profiles/pipeline_factory.py` (Task 3) — nơi biết registry.
"""
```

## 4. Giải thích (đây là "tại sao", không phải "dòng nào")
- Loader biết `source.type` là chuỗi không rỗng (cấu trúc), nhưng **cố ý KHÔNG biết** `"rtsp"` có phải type hợp
  lệ không — vì để biết điều đó phải tra registry, mà registry sống ở `profiles` (nơi được import adapter).
- Nếu loader kiểm registry → loader phải import `pipeline_factory` (profiles) → **application phụ thuộc profiles**
  → VI PHẠM contract import-linter #4 (`lint-imports` sẽ báo "broken").
- Giải pháp: **chia đôi việc validate** — cấu trúc ở loader (application), ngữ nghĩa-registry ở factory (profiles).

## 5. Là gì
Nguyên tắc phân tách: "kiểm cái gì" đặt ở tầng "biết cái đó", không kéo tri thức tầng dưới lên tầng trên.

## 6. Tại sao tồn tại / vấn đề nó giải
Giữ hướng phụ thuộc 1 chiều (Dependency Inversion cưỡng chế). Nếu trộn → tầng nghiệp vụ (application) dính chi
tiết hạ tầng (danh sách adapter) → đổi adapter phải sửa application → mất lợi ích hexagonal.

## 7. Dùng ở đâu
- Cấu trúc: `config_loader.parse_app_config` (mẩu 05).
- Registry/ngữ nghĩa: `pipeline_factory.validate_config` + `build_runner` (`_lookup` tra registry → type lạ → `ConfigError`, mẩu 11–12).
- `--validate` gọi CẢ HAI (loader rồi factory.validate_config) — kiểm đầy đủ trước khi chạy.

## 8. Không có nó thì sao (nếu loader kiểm registry)
`lint-imports` báo broken (application→profiles) → cổng verify đỏ. Kiến trúc "thủng" ranh giới: sau này khó thay
adapter, khó test application độc lập. Đây là ví dụ cụ thể "vì sao ranh giới ép-máy có giá trị".

## 9. Ví von
Lễ tân (loader) kiểm tờ khai điền đủ ô chưa; còn "mã dịch vụ này có tồn tại không" là việc của phòng chuyên môn
(factory) — lễ tân không ôm danh mục dịch vụ.

## 10. Liên kết bức tranh lớn
Đây là minh hoạ SỐNG của contract import-linter #4 (application cấm import adapters/profiles). Muốn "thấy" ranh
giới → chạy `lint-imports`.

## 11. Cạm bẫy
- Cám dỗ "gộp validate 1 chỗ cho gọn" → kéo registry vào loader → thủng ranh giới. Đừng.
- Hệ quả: 1 config có `type` sai chính tả sẽ qua loader (cấu trúc OK) nhưng bị factory bắt (`_lookup`). Đúng thiết kế.

## 12. Tự kiểm (Feynman)
- Nếu loader import `pipeline_factory` để kiểm type, `lint-imports` báo gì? Vi phạm contract số mấy?
- "Validate cấu trúc" (loader) vs "validate registry" (factory) — cái nào ở tầng nào, VÌ SAO?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`config_loader.py` (docstring + parse_app_config, đọc thật #322/#324) · `pyproject.toml` contract #4 · `docs/ARCHITECTURE.md` §2.1. Độ chắc: cao.
