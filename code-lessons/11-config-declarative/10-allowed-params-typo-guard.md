# 11.10 — `allowed_params` + `_check_params`: chặn typo nuốt IM LẶNG (K-046)

## 1. Thuộc về đâu
profiles — `pipeline_factory.py`. Mỗi builder khai `allowed_params`; `_check_params` từ chối key lạ.

## 2. Cần biết trước
mẩu 08 (builder đọc `params`), mẩu 05 (loader chỉ kiểm `params` là bảng, KHÔNG kiểm key nào hợp lệ).

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`)
```python
_src_rtsp.allowed_params = frozenset({"url", "max_reconnect"})
_det_pt.allowed_params = frozenset({"weights", "device"})
_stage_motion_gate.allowed_params = frozenset(
    {"pixel_diff_threshold", "min_area_ratio", "max_consecutive_skip", "roi", "illumination_robust"}
)
```
```python
def _check_params(builder: Callable, where: str, params: Mapping) -> None:
    """Từ chối key params LẠ (typo) → chống nuốt im lặng (K-046)."""
    allowed = getattr(builder, "allowed_params", None)
    if allowed is None:
        return
    unknown = set(params) - allowed
    if unknown:
        valid = ", ".join(sorted(allowed)) or "(không có)"
        raise ConfigError(f"{where} có tham số lạ: {sorted(unknown)}. Params hợp lệ: {valid}")
```

## 4. Giải thích từng mẩu nhỏ nhất
- `_src_rtsp.allowed_params = frozenset({...})` — gắn thuộc tính "tập key hợp lệ" LÊN chính hàm builder (builder
  là nơi ĐỌC params → là "authority" biết key nào hợp lệ; khai ngay cạnh nó).
- `_check_params`: `unknown = set(params) - allowed` — key có trong config NHƯNG không thuộc allowed = typo/thừa.
- `unknown` khác rỗng → `ConfigError` liệt kê key lạ + key hợp lệ → operator sửa ngay.
- `allowed is None` → BỎ QUA (builder bên thứ 3 chưa khai → lenient, không siết cái mình không biết).

## 5. Là gì
Lưới chặn typo trong `params` (vd gõ `max_reconect` thiếu chữ) → báo lỗi thay vì âm thầm dùng default.

## 6. Tại sao tồn tại / vấn đề nó giải
`params` là dict tự do → gõ sai key thì builder `params.get("max_reconnect")` trả `None` (default) → chạy "bình
thường" nhưng SAI Ý người dùng (họ tưởng đã set), KHÔNG có báo lỗi. Đây là "nuốt im lặng" — bug khó phát hiện.
`_check_params` biến im-lặng thành fail-fast (K-046).

## 7. Dùng ở đâu
`validate_config` (mẩu 12) VÀ `build_runner` (mẩu 13) đều gọi `_check_params` TRƯỚC khi gọi builder → chặn typo
ở CẢ đường dry-run lẫn đường chạy thật. Chạy ở cả 2 vì `_run_from_config` gọi `build_runner` KHÔNG qua `validate_config`.

## 8. Không có nó thì sao
Typo key → builder dùng default im lặng → vd `max_reconnect` gõ sai → RTSP thử lại vô hạn dù operator định giới
hạn; hoặc ROI gõ sai → motion-gate đo cả khung. Sai vận hành mà log không báo. K-046 sinh ra để đóng lỗ này.

## 9. Ví von
Như form có kiểm "ô lạ": điền nhầm tên trường → hệ báo "trường X không tồn tại, các trường hợp lệ là ..." thay vì
lặng lẽ bỏ qua ô đó.

## 10. Liên kết bức tranh lớn
Tầng "validate ngữ nghĩa" (khác validate cấu trúc ở loader, mẩu 05/06). Cùng triết lý fail-fast + thông điệp rõ.

## 11. Cạm bẫy
- Quên gắn `allowed_params` cho builder mới → `_check_params` bỏ qua (lenient) → typo lọt. Builder mới NÊN khai `allowed_params`.
- `frozenset()` rỗng cho builder không nhận param (`_stage_detect.allowed_params = frozenset()`) → mọi key đều "lạ" (đúng: detect/count không có param).

## 12. Tự kiểm (Feynman)
- Không có `_check_params`, gõ `max_reconect` (thiếu n) trong config RTSP thì chuyện gì xảy ra? Vì sao nguy hiểm?
- Vì sao `_check_params` chạy ở CẢ `validate_config` lẫn `build_runner` (không chỉ 1)?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`pipeline_factory.py` (đọc thật #322/#324) · K-046 (typo-guard). Độ chắc: cao (quote trực tiếp).
