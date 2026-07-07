# Mẩu 05 — `InferenceError`: chỉ giữ CHUỖI, không giữ Exception + trường `retryable`

**(1) Thuộc về đâu:** `kernel/inference_protocol.py`, class `InferenceError`.

**(2) Cần biết trước:** Exception (glossary `#exception` — đối tượng lỗi khi chạy); pickle/serialize
(đóng gói dữ liệu để gửi qua wire); pattern "R5" ở bài #04 (lỗi chỉ giữ chuỗi, không giữ đối tượng lỗi).

**(3) Code thật (quote `kernel/inference_protocol.py`):**
```python
@dataclass(frozen=True)
class InferenceError:
    """Lỗi inference — CHỈ giữ chuỗi (không giữ Exception gốc; pattern R5 #04).

    Giữ Exception trực tiếp = rủi ro pickle/leak state qua wire. error_type/error_message là str.
    """
    error_type: str
    error_message: str
    retryable: bool = False   # production: timeout/transient=True; OOM/bad-input=False.
```

**(4) Giải thích từng dòng:**
- `error_type: str` → tên loại lỗi (chuỗi, ví dụ "ShmReadFailed", "RuntimeError").
- `error_message: str` → mô tả (chuỗi).
- `retryable: bool = False` → **có nên thử lại không**. Mặc định `False`.

**(5) Là gì:** DTO mô tả lỗi inference bằng **chuỗi thuần**, kèm cờ có-thể-thử-lại.

**(6) Tại sao tồn tại / vấn đề nó giải:**
- *Chỉ chuỗi:* Exception gốc mang theo traceback + tham chiếu object → gửi qua wire (ZMQ) dễ **vỡ
  pickle** hoặc **rò rỉ state** nội bộ. Rút thành `error_type`/`error_message` (str) là an toàn +
  serialize được. (Cùng bài học R5 ở #04.)
- *`retryable`:* production cần phân biệt lỗi **tạm** (timeout, hàng đợi đầy → thử lại có ích) vs lỗi
  **cố định** (GPU hết bộ nhớ, input sai → thử lại vô ích, thậm chí hại). Camera-side circuit breaker
  dùng cờ này để quyết định.

**(7) Dùng ở đâu trong project:** `InlineInferenceClient.infer` bọc mọi lỗi thành `InferenceError`
(mẩu 10): đọc SHM thất bại → `error_type="ShmReadFailed"`; detect ném lỗi → `error_type=type(e).
__qualname__`, `error_message=str(e)`. Test `test_response_error_case_is_not_success` (mẩu 11).

**(8) Không có nó (giữ Exception thẳng) thì sao:** response ôm cả Exception → không serialize sạch qua
ZMQ (production) + lộ nội bộ; và không có `retryable` → camera không biết nên thử lại hay bỏ.

**(9) Ví von:** biên bản sự cố ghi bằng chữ ("Lỗi: hết mực, không cần gọi lại thợ") thay vì gói cả cái
máy hỏng gửi đi. Chữ thì fax được; cả máy thì không.

**(10) Liên kết bức tranh lớn:** giữ biên giới DTO "sạch" (chỉ dữ liệu serialize được) — điều kiện để
sau này gửi qua ZMQ mà không đổi thiết kế.

**(11) Cạm bẫy:** đừng nhét `exception` object hay traceback dài vào DTO. `retryable` phải đặt ĐÚNG:
gán bừa `True` cho lỗi cố định (OOM) → thử lại vô hạn.

**(12) Tự kiểm:**
- Vì sao không giữ Exception gốc trong `InferenceError`?
- Cho 2 ví dụ `retryable=True` và 2 ví dụ `retryable=False`.

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/inference_protocol.py` (InferenceError) · Design step-06 ("Error handling —
không retain Exception" + "retryable field"). Độ chắc: cao (quote thật).
