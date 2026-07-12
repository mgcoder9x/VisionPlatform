# 11.08 — REGISTRY: bảng `type`(chuỗi) → hàm dựng object (điểm mở-rộng-không-sửa)

## 1. Thuộc về đâu
Layer **profiles** (composition root) — `profiles/pipeline_factory.py`. Tầng NÀY được phép import adapter
(khác application, mẩu 06) → là nơi đúng để "biết type nào dựng adapter nào".

## 2. Cần biết trước
cây DTO (mẩu 03: mỗi mảnh có `type`+`params`). "Registry" = từ điển tra cứu (link `knowledge-base/00-GLOSSARY.md#registry` nếu lạ).

## 3. Code thật (quote nguyên văn — `pipeline_factory.py`)
```python
DEFAULT_REGISTRY: dict[str, dict[str, Callable]] = {
    "sources": {"fake": _src_fake, "noise": _src_noise, "video": _src_video, "rtsp": _src_rtsp},
    "detectors": {"fake": _det_fake, "pt": _det_pt},
    "stages": {"detect": _stage_detect, "count": _stage_count, "motion_gate": _stage_motion_gate,
               "track": _stage_track, "line_crossing": _stage_line_crossing},
    "sinks": {"jsonl": _sink_jsonl, "crossing_events": _sink_crossing_events,
              "crossing_events_sqlite": _sink_crossing_events_sqlite},
}
```

## 4. Giải thích từng mẩu nhỏ nhất
- `DEFAULT_REGISTRY` — dict 2 tầng: nhóm (`"sources"`/`"detectors"`/`"stages"`/`"sinks"`) → { `type`(chuỗi) → hàm builder }.
- Mỗi giá trị là 1 **hàm** (`_src_rtsp`...) nhận `params` → trả object thật (adapter/stage). "Callable" = gọi được.
- Chuỗi `"rtsp"` trong TOML → tra `DEFAULT_REGISTRY["sources"]["rtsp"]` → `_src_rtsp` → `RtspFrameSource(...)`.

## 5. Là gì
Bảng ánh xạ "tên khai báo → cách dựng". Trái tim biến *dữ liệu* (config) thành *object* (pipeline).

## 6. Tại sao tồn tại / vấn đề nó giải
Không có registry → phải viết chuỗi `if type=="rtsp": ... elif type=="fake": ...` rải khắp nơi (khó mở rộng,
dễ sót). Registry = 1 bảng tập trung: **thêm loại mới = thêm 1 entry**, KHÔNG sửa `build_runner`/lõi
(nguyên lý Open/Closed — mở-để-mở-rộng, đóng-để-sửa-đổi).

## 7. Dùng ở đâu
`_lookup(registry, "sources", type)` (mẩu 11) tra bảng này trong `validate_config` (mẩu 12) + `build_runner`
(mẩu 13). `registry` là THAM SỐ (`registry: Mapping = DEFAULT_REGISTRY`) → test tiêm registry giả được.

## 8. Không có nó thì sao
Chuỗi if/elif phình theo số loại; thêm sink mới phải sửa nhiều hàm → dễ quên chỗ (đúng loại phân kỳ F1 từng
gặp ở đường CLI trước khi hợp nhất). Registry gom về 1 nguồn.

## 9. Ví von
Như **danh bạ tổng đài**: gọi tên phòng ("rtsp") → tổng đài nối đúng máy. Thêm phòng = thêm 1 dòng danh bạ.

## 10. Liên kết bức tranh lớn
Registry đặt ở `profiles` (được import adapter) — cùng lý do mẩu 06 (loader không được). Đây là "composition root":
nơi DUY NHẤT biết adapter cụ thể.

## 11. Cạm bẫy
- Entry trỏ tới hàm builder (`_src_rtsp`) — KHÔNG phải gọi sẵn (`_src_rtsp()`); gọi lúc dựng, không lúc khai báo bảng.
- `registry` là tham số có default → cho phép mở rộng bằng registry riêng mà không sửa file (test/plugin).

## 12. Tự kiểm (Feynman)
- Thêm sink loại `"kafka"` thì đụng vào đâu, KHÔNG đụng vào đâu? (Open/Closed)
- Vì sao registry ở `profiles` chứ không `application`/`kernel`?

## 13. Mốc ôn: 1 ngày / 1 tuần / 1 tháng.

## 14. Nguồn
`profiles/pipeline_factory.py` (đọc thật #322/#324). Độ chắc: cao (quote trực tiếp).
