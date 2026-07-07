# Mẩu 06 — `InferenceResponse`: echo `request_id` + property `is_success`

**(1) Thuộc về đâu:** `kernel/inference_protocol.py`, class `InferenceResponse`.

**(2) Cần biết trước:** `tuple` (dãy bất biến — glossary `#tuple`); `Optional[X]` (glossary
`#optional` — hoặc X hoặc None); `@property` (glossary `#property` — truy cập như thuộc tính nhưng tính toán).

**(3) Code thật (quote `kernel/inference_protocol.py`):**
```python
@dataclass(frozen=True)
class InferenceResponse:
    """Response echo `request_id` để client correlate đúng của mình."""
    request_id: str
    detections: tuple[Detection, ...] = field(default_factory=tuple)
    error: Optional[InferenceError] = None

    @property
    def is_success(self) -> bool:
        return self.error is None
```

**(4) Giải thích từng dòng:**
- `request_id: str` → **echo** lại mã của request (mẩu 02) để người gọi khớp.
- `detections: tuple[Detection, ...] = field(default_factory=tuple)` → danh sách vật phát hiện, mặc
  định **tuple rỗng** `()`. Dùng `field(default_factory=tuple)` vì default là giá trị "tạo mới mỗi
  lần" (không thể để mutable mặc định trong dataclass).
- `error: Optional[InferenceError] = None` → nếu lỗi thì đây khác None; nếu thành công thì None.
- `is_success` → **True khi `error is None`**. Tiện kiểm nhanh "thành công không".

**(5) Là gì:** DTO kết quả trả về: mã yêu cầu + danh sách detection (khi ok) hoặc lỗi (khi fail).

**(6) Tại sao tồn tại / vấn đề nó giải:** cần một "gói trả lời" chuẩn cho MỌI kết quả — thành công
(có detections) hoặc thất bại (có error) — mà người gọi xử lý đồng nhất. `is_success` gói logic
"thành công = không lỗi" vào một chỗ (khỏi lặp `resp.error is None` khắp nơi).

**(7) Dùng ở đâu trong project:** `InlineInferenceClient.infer` trả `InferenceResponse` ở cả nhánh ok
lẫn lỗi (mẩu 10). Test `test_response_is_success_when_no_error` + `test_response_error_case_is_not_success`.

**(8) Không có nó thì sao:** thiếu chuẩn trả lời → mỗi nơi tự chế cách báo ok/lỗi → khó ghép
correlation + xử lý lỗi rời rạc. Thiếu `is_success` → lặp kiểm `error is None` dễ sai.

**(9) Ví von:** phiếu trả kết quả xét nghiệm: luôn có **mã bệnh nhân** (request_id), phần "kết quả"
(detections) HOẶC "ghi chú lỗi mẫu" (error). `is_success` = ô tick "mẫu hợp lệ".

**(10) Liên kết bức tranh lớn:** cùng `InferenceRequest` tạo cặp request/response — hợp đồng bất biến
độc lập transport. `detections` là `tuple` (bất biến) vì DTO nên "đóng băng" ở biên (mẩu 10 freeze list→tuple).

**(11) Cạm bẫy:** đừng để default `detections=[]` (list) trực tiếp — mutable default gây chia sẻ state
giữa các instance; dùng `field(default_factory=tuple)`. Đừng tự kiểm `error is None` rải rác — dùng `is_success`.

**(12) Tự kiểm:**
- `is_success` tính từ gì? Vì sao gói thành property thay vì kiểm tay?
- Vì sao `detections` là `tuple` chứ không `list`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/inference_protocol.py` (InferenceResponse) · test #06 (is_success, error case).
Độ chắc: cao (quote thật + test pass).
