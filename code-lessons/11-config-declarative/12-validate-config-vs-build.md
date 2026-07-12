# 11.12 — `validate_config` (dry-run no-GPU) vs `build_runner` (dựng thật): vì sao TÁCH 2

## 1. Thuộc về đâu
profiles — `pipeline_factory.py`. Hai hàm công khai: `validate_config` (kiểm KHÔNG dựng) và `build_runner` (dựng thật, mẩu 13).

## 2. Cần biết trước
mẩu 09 (lazy-import: tra ≠ gọi builder), mẩu 10 (`_check_params`), mẩu 11 (`_lookup`).

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`)
```python
def validate_config(app, *, registry: Mapping = DEFAULT_REGISTRY) -> None:
    """Kiểm config HỢP LỆ mà KHÔNG dựng object (no-GPU/no-torch): mọi `type` ∈ registry + detect-có-detector.
    ...
    """
    for p in app.pipelines:
        try:
            _check_params(_lookup(registry, "sources", p.source.type), f"source '{p.source.type}'", p.source.params)
            for st in p.stages:
                _check_params(_lookup(registry, "stages", st.type), f"stage '{st.type}'", st.params)
            for sk in p.sinks:
                _check_params(_lookup(registry, "sinks", sk.type), f"sink '{sk.type}'", sk.params)
            if p.detector is not None:
                _check_params(_lookup(registry, "detectors", p.detector.type),
                              f"detector '{p.detector.type}'", p.detector.params)
            if any(st.type == "detect" for st in p.stages) and p.detector is None:
                raise ConfigError("stage 'detect' cần khai báo 'detector'")
        except ConfigError as e:
            raise ConfigError(f"pipeline {p.id!r}: {e}") from e
```

## 4. Giải thích từng mẩu nhỏ nhất
- `validate_config` chỉ **`_lookup` + `_check_params`** cho từng phần → tra registry + kiểm params, **KHÔNG gọi
  builder** → KHÔNG import torch/cv2 (mẩu 09) → chạy được máy no-GPU.
- Kiểm ngữ nghĩa liên-phần: `if any(st.type=="detect") and p.detector is None` → stage `detect` mà thiếu
  `detector` = cấu hình vô nghĩa → `ConfigError`.
- `except ConfigError → raise ConfigError(f"pipeline {p.id!r}: {e}")` — bọc thêm ID pipeline vào thông điệp
  (biết camera nào sai).

## 5. Là gì
Bản "kiểm khan" (dry-run): xác nhận file config hợp lệ đầy đủ (type + params + liên-phần) mà không dựng gì, không cần phần cứng.

## 6. Tại sao tồn tại / vấn đề nó giải
Operator muốn kiểm file cấu hình GPU (`pt`) NGAY trên máy dev (không torch) TRƯỚC khi mang lên máy GPU. Nếu chỉ
có `build_runner` (dựng thật → import torch → crash trên máy dev) thì không kiểm trước được. `validate_config`
tách phần "kiểm" khỏi phần "dựng" → kiểm mọi lúc mọi máy. Đây là hậu thuẫn cho cờ `--validate`.

## 7. Dùng ở đâu
`vision_slice_app._validate_config_only(path)` (đường `--validate`) gọi `load_app_config` + `validate_config`.
Có test chạy `validate_config` trên MỌI `configs/*.toml` (artifact ship) → config ship sai typo bị bắt ở CI (#308).

## 8. Không có nó thì sao
Chỉ `build_runner` → muốn kiểm config `pt` phải có torch + GPU; sai config chỉ lộ lúc deploy thật (muộn, đắt).
`validate_config` đẩy phát hiện lỗi về sớm nhất (máy dev, CI).

## 9. Ví von
Như đọc-soát bản vẽ nhà TRƯỚC khi xây: phát hiện thiếu cột/sai kích thước trên giấy (rẻ), không đợi đổ móng (đắt).

## 10. Liên kết bức tranh lớn
`validate_config` (tra) vs `build_runner` (dựng) = ứng dụng trực tiếp của lazy-import (mẩu 09) + capability-aware.
Cùng `_lookup`/`_check_params` → 2 hàm chia sẻ logic kiểm, khác ở "có gọi builder hay không".

## 11. Cạm bẫy
- Đừng nhầm: `validate_config` KHÔNG bắt lỗi RUNTIME (vd weights file không tồn tại) — chỉ kiểm type/params/liên-phần
  (tĩnh). Lỗi mở-file xảy ra lúc `build_runner`/`setup` (đường chạy thật).
- `_run_from_config` gọi `build_runner` TRỰC TIẾP (không qua validate_config) → nên `build_runner` cũng phải
  `_check_params`/`_lookup` (mẩu 13) để không thủng khi bỏ qua validate.

## 12. Tự kiểm (Feynman)
- Vì sao `validate_config` chạy được config `pt` trên máy KHÔNG torch, còn `build_runner` thì không?
- `--validate` gọi những gì? Nó bắt được loại lỗi nào, KHÔNG bắt loại nào?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py::validate_config` (đọc thật #322/#324) · #308 (test mọi config ship). Độ chắc: cao (quote trực tiếp).
