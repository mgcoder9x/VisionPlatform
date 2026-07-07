# Mẩu 04 — `_add_context_vars`: processor chèn contextvars vào mỗi log

**(1) Thuộc về đâu:** `runtime/observability.py`, hàm `_add_context_vars` — một *structlog processor*.

**(2) Cần biết trước:** mẩu 02 (ContextVar) + 03 (log_context set); "processor chain" (chuỗi hàm biến
đổi bản ghi log tuần tự); `event_dict` (từ điển mô tả 1 dòng log).

**(3) Code thật (quote `runtime/observability.py`):**
```python
def _add_context_vars(_, __, event_dict: dict) -> dict:
    """structlog processor: chèn giá trị contextvars vào mỗi dòng log (nếu có set)."""
    cid = _camera_id_var.get()
    pid = _packet_id_var.get()
    rid = _request_id_var.get()
    if cid:
        event_dict["camera_id"] = cid
    if pid:
        event_dict["packet_id"] = pid
    if rid:
        event_dict["request_id"] = rid
    return event_dict
```

**(4) Giải thích từng ý nhỏ:**
- `def _add_context_vars(_, __, event_dict)` → chữ ký processor structlog: 3 tham số (logger, method_name,
  event_dict). Hai cái đầu không dùng → đặt tên `_`, `__`.
- `_camera_id_var.get()` → đọc giá trị hiện tại của contextvar (None nếu chưa set trong context).
- `if cid: event_dict["camera_id"] = cid` → **chỉ chèn khi có giá trị** (không chèn field rỗng).
- `return event_dict` → trả dict đã bổ sung cho processor kế tiếp trong chuỗi.

**(5) Là gì:** một hàm nằm trong dây chuyền xử lý log của structlog, nhiệm vụ: đọc contextvars và gắn
vào bản ghi log.

**(6) Tại sao tồn tại / vấn đề nó giải:** đây là mảnh nối "context (mẩu 02–03) → log ra". Nhờ nó, chỉ
cần `with log_context(camera_id=...)` một lần, MỌI dòng log trong block tự có `camera_id` — không nhét tay.

**(7) Dùng ở đâu trong project:** đăng ký trong `setup_logging` (mẩu 05) giữa chuỗi processor. Test
kiểm trực tiếp (`test_processor_injects_context_vars_into_event_dict`) — gọi hàm trong `log_context` và
assert dict có field.

**(8) Không có nó thì sao:** contextvars có set nhưng log KHÔNG mang chúng → quay lại phải nhét nhãn tay.

**(9) Ví von:** người đóng dấu ở cuối dây chuyền: mỗi hồ sơ (log) đi qua, họ dập thêm dấu "camera_1"
(lấy từ bảng ngữ cảnh) trước khi hồ sơ ra ngoài.

**(10) Liên kết bức tranh lớn:** structlog xử lý log theo **chuỗi processor**:
`add_log_level → TimeStamper → _add_context_vars → JSONRenderer → output` (mẩu 05). Mỗi processor
biến đổi `event_dict` rồi chuyền tiếp.

**(11) Cạm bẫy:** `if cid:` bỏ qua cả chuỗi rỗng `""` (coi như chưa set) — hợp lý ở đây. Thứ tự trong
chuỗi quan trọng: `_add_context_vars` phải TRƯỚC `JSONRenderer` (renderer biến dict thành chuỗi cuối cùng).

**(12) Tự kiểm:**
- Processor nhận gì, trả gì? Vì sao phải `return event_dict`?
- Vì sao `_add_context_vars` phải đứng trước `JSONRenderer` trong chuỗi?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (_add_context_vars) · Design step-08 (Processor pattern). Độ chắc: cao (quote thật + test pass).
