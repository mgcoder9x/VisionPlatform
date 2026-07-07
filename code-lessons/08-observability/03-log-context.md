# Mẩu 03 — `log_context`: set token, reset LIFO (nested-safe)

**(1) Thuộc về đâu:** `runtime/observability.py`, class `log_context` (context manager).

**(2) Cần biết trước:** context manager (`with ...:` — `__enter__`/`__exit__`, glossary
`#context-manager`); `ContextVar.set()` trả về **Token**; LIFO (vào sau ra trước); nested (lồng nhau).

**(3) Code thật (quote `runtime/observability.py`):**
```python
def __enter__(self):
    if self._kwargs["camera_id"] is not None:
        self._tokens.append(_camera_id_var.set(self._kwargs["camera_id"]))
    if self._kwargs["packet_id"] is not None:
        self._tokens.append(_packet_id_var.set(self._kwargs["packet_id"]))
    if self._kwargs["request_id"] is not None:
        self._tokens.append(_request_id_var.set(self._kwargs["request_id"]))
    return self

def __exit__(self, *args):
    # Reset LIFO (ngược thứ tự set) ... reversed() đảm bảo điều này.
    for token in reversed(self._tokens):
        token.var.reset(token)
```

**(4) Giải thích từng ý nhỏ:**
- `_camera_id_var.set(value)` → đặt giá trị + trả về **Token** (nhớ giá trị TRƯỚC đó). Lưu vào `self._tokens`.
- Chỉ set field nào `is not None` → không đụng field không truyền.
- `__exit__`: `for token in reversed(self._tokens)` → reset theo thứ tự **ngược** (LIFO).
- `token.var.reset(token)` → khôi phục biến về giá trị trước khi set.

**(5) Là gì:** context manager để bind các field log trong suốt 1 block `with`, tự khôi phục khi ra.

**(6) Tại sao reset LIFO (không xuôi):** khi lồng nhau `with A: with B:`, thoát B phải reset B TRƯỚC
để camera_id quay về "A"; nếu reset A trước thì Token của A cầm giá trị trước-A đã cũ (bị B ghi đè) →
khôi phục sai. `reversed()` đảm bảo token set sau cùng reset trước. (Self-check #2.)

**(7) Dùng ở đâu trong project:** `with log_context(camera_id="cam_1", request_id="r1"): logger.info(...)`
→ mọi log trong block tự có nhãn. Test nested/partial (mẩu 09).

**(8) Không có nó (hoặc reset sai order) thì sao:** phải nhét nhãn tay mỗi dòng (bẩn); reset sai order →
sau block, biến mang giá trị sai → log tiếp theo gắn nhãn nhầm.

**(9) Ví von:** chồng đĩa (stack): đặt đĩa A rồi đĩa B lên trên; muốn lấy A phải nhấc B trước. Token
cũng vậy — gỡ theo thứ tự ngược mới không đổ.

**(10) Liên kết bức tranh lớn:** dùng `ContextVar` (mẩu 02) + là "nguồn" dữ liệu cho `_add_context_vars`
processor (mẩu 04). Cùng họ context-manager với teardown ở #04 (BaseStage `__enter__/__exit__`).

**(11) Cạm bẫy:** phải reset (đừng chỉ `set` rồi quên) — không thì context "dính" mãi. `reversed`
bắt buộc cho nested. Chỉ append token khi thực sự set (field None thì bỏ qua) — nếu append cả None sẽ reset nhầm.

**(12) Tự kiểm:**
- Vì sao reset phải theo LIFO? Cho ví dụ nested A→B→A.
- `ContextVar.set()` trả về gì, dùng để làm gì?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `runtime/observability.py` (log_context) · test `test_log_context_nested_restores_outer` ·
Design step-08 (Tokens for reset + Self-check #2). Độ chắc: cao (quote thật + test pass).
