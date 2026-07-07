# Mẩu 06 — `get` (None khi timeout) vs `get_or_raise` (raise queue.Empty)

**(1) Thuộc về đâu:** `kernel/backpressure.py`, `BoundedQueue.get` và `get_or_raise`.

**(2) Cần biết trước:** `Optional[T]` (glossary `#optional` — T hoặc None); `raise`/exception;
`queue.Empty` (exception chuẩn của thư viện `queue`).

**(3) Code thật (quote `kernel/backpressure.py`):**
```python
def get(self, timeout: Optional[float] = None) -> Optional[T]:
    """Chờ lấy item. Trả None khi timeout. ... nếu queue có thể chứa None hợp lệ ... dùng get_or_raise."""
    with self._lock:
        if not self._not_empty.wait_for(lambda: len(self._buf) > 0, timeout=timeout):
            return None
        item = self._buf.popleft()
        self._not_full.notify()
        return item

def get_or_raise(self, timeout: Optional[float] = None) -> T:
    """Chờ lấy item; raise queue.Empty khi timeout (không nhập nhằng None)."""
    with self._lock:
        if not self._not_empty.wait_for(lambda: len(self._buf) > 0, timeout=timeout):
            raise _queue.Empty
        item = self._buf.popleft()
        self._not_full.notify()
        return item
```

**(4) Giải thích từng ý nhỏ:**
- Cả hai: chờ `_not_empty` tới khi có item / timeout; lấy `popleft()`; `notify()` `_not_full` (đã
  giải phóng 1 chỗ → đánh thức producer BLOCK).
- Khác nhau ở **lúc timeout**: `get` trả `None`; `get_or_raise` **raise `queue.Empty`**.

**(5) Là gì:** hai cách lấy item ra khỏi hàng đợi, khác nhau ở cách báo "hết giờ mà không có gì".

**(6) Tại sao tồn tại / vấn đề nó giải:** **None-ambiguity**. Nếu hàng đợi có thể chứa `None` như một
item hợp lệ, thì `get` trả `None` không phân biệt được "timeout" hay "item thật là None". `get_or_raise`
dùng exception nên **không nhập nhằng** — timeout là exception, item None là giá trị trả về.

**(7) Dùng ở đâu:** consumer gọi `get(timeout=...)` khi None không phải item hợp lệ (đa số trường hợp
frame). Dùng `get_or_raise` khi item có thể là None. Test `test_get_returns_none_on_timeout` +
`test_get_or_raise_raises_on_timeout`.

**(8) Không có `get_or_raise` thì sao:** buộc dùng `get` → khi queue chứa None hợp lệ, consumer không
phân biệt được timeout vs item-None → logic sai âm thầm.

**(9) Ví von:** hỏi kho "có hàng không?": `get` trả lời "không" (None) — nhưng nếu "không" cũng là một
loại hàng hợp lệ thì rối. `get_or_raise` thay vì trả "không" thì **gõ chuông báo động timeout** — không lẫn.

**(10) Liên kết bức tranh lớn:** đây là *defensive design* — lường trước ca dùng khó (item None).
Cùng nhóm với việc đặt tên/return-semantics rõ ràng ở `put` (mẩu 04).

**(11) Cạm bẫy:** đừng dùng `get` cho queue chứa None. `queue.Empty` import từ thư viện chuẩn `queue`
(trong code là `import queue as _queue` → `raise _queue.Empty`). Cả hai vẫn `notify _not_full` sau
popleft — quên thì producer BLOCK ngủ mãi.

**(12) Tự kiểm:**
- Khi nào phải dùng `get_or_raise` thay vì `get`?
- Sau khi `popleft`, vì sao phải `notify _not_full`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (get/get_or_raise) · test #07 (None-timeout, raise Empty).
Độ chắc: cao (quote thật + test pass).
