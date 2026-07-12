# 11.11 — `_lookup`: tra registry, `type` lạ → `ConfigError` liệt kê type hợp lệ

## 1. Thuộc về đâu
profiles — `pipeline_factory.py::_lookup`. Cầu nối "chuỗi type" → "hàm builder" (mẩu 08).

## 2. Cần biết trước
mẩu 08 (registry 2 tầng), mẩu 05 (loader đã đảm bảo `type` là chuỗi không rỗng — nhưng CHƯA biết có hợp lệ không).

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`)
```python
def _lookup(registry: Mapping, section: str, type_: str):
    table = registry.get(section, {})
    if type_ not in table:
        valid = ", ".join(sorted(table)) or "(rỗng)"
        raise ConfigError(f"{section}.type không hỗ trợ: {type_!r}. Hợp lệ: {valid}")
    return table[type_]
```

## 4. Giải thích từng mẩu nhỏ nhất
- `table = registry.get(section, {})` — lấy nhóm (`"sources"`...); nhóm lạ → dict rỗng (rồi báo hợp-lệ-rỗng).
- `if type_ not in table` — `type` không có trong nhóm = loại không hỗ trợ.
- `valid = ", ".join(sorted(table))` — liệt kê MỌI type hợp lệ (sắp xếp) → operator biết gõ gì đúng.
- `raise ConfigError(...{type_!r}...Hợp lệ: {valid})` — fail-fast, thông điệp có type-sai + danh sách đúng.
- `return table[type_]` — trả hàm builder để caller gọi.

## 5. Là gì
Hàm tra cứu an toàn: đúng type → builder; sai type → lỗi rõ (kèm gợi ý các type hợp lệ).

## 6. Tại sao tồn tại / vấn đề nó giải
Đây là chỗ bắt "type sai chính tả / type không tồn tại" — thứ mà loader (application) CỐ Ý không bắt (mẩu 06,
ranh giới tầng). Không có `_lookup` → `table[type_]` ném `KeyError` thô (không gợi ý). `_lookup` đổi thành
`ConfigError` thân thiện + liệt kê lựa chọn.

## 7. Dùng ở đâu
`validate_config` (mẩu 12) + `build_runner` (mẩu 13): mỗi source/stage/sink/detector → `_lookup(registry, nhóm, type)`
→ (rồi `_check_params` mẩu 10) → gọi builder.

## 8. Không có nó thì sao
`type = "rtps"` (gõ nhầm rtsp) → `KeyError: 'rtps'` thô lên tận CLI, không nói "hợp lệ: fake, noise, rtsp, video".
Operator phải mò. `_lookup` biến lỗi thành hướng-dẫn-sửa.

## 9. Ví von
Tổng đài: gọi số phòng không có → "số bạn gọi không tồn tại; các số hợp lệ: ..." thay vì cúp máy im.

## 10. Liên kết bức tranh lớn
Cặp đôi kiểm ngữ-nghĩa ở factory: `_lookup` (type hợp lệ) + `_check_params` (params hợp lệ) — bù cho phần loader
không kiểm (ranh giới tầng). Chạy `--validate` = loader + 2 kiểm này = "chắc file đúng trước khi mang đi".

## 11. Cạm bẫy
- `sorted(table)` sắp xếp KEY (tên type) → thông điệp ổn định (không phụ thuộc thứ tự dict).
- Nhóm sai (`section` gõ nhầm) → `get(section, {})` rỗng → báo "Hợp lệ: (rỗng)" (lỗi lập trình, không phải lỗi config user).

## 12. Tự kiểm (Feynman)
- `type="rtps"` (typo) đi qua loader (mẩu 05) rồi tới `_lookup` — ai bắt, báo gì?
- Vì sao `_lookup` ở factory chứ không loader? (nối mẩu 06)

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py::_lookup` (đọc thật #322/#324). Độ chắc: cao (quote trực tiếp).
