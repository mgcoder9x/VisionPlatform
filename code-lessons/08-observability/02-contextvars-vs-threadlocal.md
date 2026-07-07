# Mẩu 02 — `contextvars`: 3 biến ngữ cảnh, vì sao không dùng threading.local

**(1) Thuộc về đâu:** `runtime/observability.py` — 3 `ContextVar` (`_camera_id_var`, `_packet_id_var`, `_request_id_var`).

**(2) Cần biết trước:** thread vs async/coroutine (glossary `#thread`, `#async`); biến toàn cục vs
theo-ngữ-cảnh; "context bleed" (rò rỉ ngữ cảnh sang task khác).

**(3) Code thật (quote `runtime/observability.py`):**
```python
_camera_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "camera_id", default=None,
)
_packet_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "packet_id", default=None,
)
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None,
)
```

**(4) Giải thích từng dòng:**
- `contextvars.ContextVar("camera_id", default=None)` → tạo một "ô nhớ theo ngữ cảnh", mặc định None
  (khi chưa set thì không có camera_id).
- 3 biến cho 3 field xuyên suốt: camera nào, gói frame nào, request inference nào.
- `str | None` → hoặc chuỗi hoặc None (cú pháp union py3.10+).

**(5) Là gì:** `ContextVar` = biến mà giá trị *gắn theo ngữ cảnh thực thi hiện tại* (context), không
phải toàn cục, không phải theo-thread.

**(6) Tại sao tồn tại / vấn đề nó giải (vì sao KHÔNG threading.local):**
- *Biến toàn cục:* nhiều thread ghi đè nhau → sai.
- *`threading.local`:* lưu theo **thread**. Nhưng **async** (1 thread chạy nhiều coroutine) → các task
  dùng chung thread → chia sẻ nhầm (context bleed). Thread-pool tái dùng thread → state task cũ dính task mới.
- *`contextvars`:* đúng cho cả sync, threading, VÀ async (mỗi context có cây riêng). Vision Platform có
  thể chạy async/threaded → contextvars nhất quán. (Self-check #1 Design.)

**(7) Dùng ở đâu trong project:** `log_context` set các biến này (mẩu 03); `_add_context_vars`
processor đọc chúng chèn vào log (mẩu 04).

**(8) Không có (dùng threading.local) thì sao:** trong hệ async, camera_id của task A rò sang task B →
log gắn sai camera → truy vết sai. Bug rất khó tìm.

**(9) Ví von:** `threading.local` = "tủ đồ theo phòng" (thread). Nếu một phòng cho nhiều người luân
phiên dùng (async trên 1 thread) → đồ người trước còn trong tủ, người sau tưởng của mình.
`contextvars` = tủ đồ theo *phiên làm việc* của từng người, không lẫn.

**(10) Liên kết bức tranh lớn:** nền cho "log tự gắn nhãn". Là ví dụ pattern immutability/scoped-state
(Module 02 file 05). Nối trực tiếp mẩu 03 (set) + 04 (đọc).

**(11) Cạm bẫy:** `default=None` quan trọng — để khi chưa set thì processor bỏ qua (không chèn field
rỗng). Đừng thay bằng biến module thường.

**(12) Tự kiểm:**
- Vì sao `threading.local` hỏng trong hệ async? Cho 1 kịch bản bleed.
- `contextvars` đúng cho những loại đồng thời nào?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (ContextVar) · Design step-08 (contextvars vs threadlocal + Self-check #1). Độ chắc: cao (quote thật).
