# Mẩu 04 — `put()`: còn chỗ → nhận; đầy → rẽ 4 nhánh policy

**(1) Thuộc về đâu:** `kernel/backpressure.py`, `BoundedQueue.put`. Đây là "trái tim" backpressure.

**(2) Cần biết trước:** mẩu 02 (4 policy) + mẩu 03 (cấu trúc); `with self._lock:` (vào là acquire, ra
là release — kể cả khi lỗi).

**(3) Code thật (quote `kernel/backpressure.py`):**
```python
def put(self, item: T, timeout: Optional[float] = None) -> bool:
    """Thử đưa item vào. True = item của caller đã vào; False = drop/reject/timeout."""
    with self._lock:
        if len(self._buf) < self._maxsize:
            self._buf.append(item)
            self._not_empty.notify()
            return True

        if self._policy == BackpressurePolicy.DROP_OLDEST:
            self._buf.popleft()
            self._buf.append(item)
            self.drops += 1
            self._not_empty.notify()
            return True

        if self._policy == BackpressurePolicy.DROP_NEWEST:
            self.drops += 1
            return False

        if self._policy == BackpressurePolicy.REJECT:
            self.rejects += 1
            return False

        if self._policy == BackpressurePolicy.BLOCK:
            if not self._not_full.wait_for(
                lambda: len(self._buf) < self._maxsize, timeout=timeout,
            ):
                self.block_timeouts += 1
                return False
            self._buf.append(item)
            self._not_empty.notify()
            return True

        raise ValueError(f"Unknown policy: {self._policy}")
```

**(4) Giải thích từng nhánh:**
- `with self._lock:` → toàn bộ thao tác dưới khoá → thread-safe.
- **Còn chỗ** (`len < maxsize`): `append` + `notify()` báo consumer "có item" → return True.
- **DROP_OLDEST**: `popleft()` (bỏ cũ nhất) + `append` (nhận mới) + `drops += 1` + notify not_empty.
  Net size KHÔNG đổi → KHÔNG notify not_full. Return True (item caller ĐÃ vào).
- **DROP_NEWEST**: `drops += 1`, return False (item caller KHÔNG vào).
- **REJECT**: `rejects += 1`, return False.
- **BLOCK**: `wait_for(còn chỗ, timeout)` → nếu hết giờ → `block_timeouts += 1`, return False; nếu có
  chỗ → append + notify → True.
- Cuối: policy lạ → `raise ValueError` (fail-fast).

**(5) Là gì:** hàm bỏ 1 item vào; nếu đầy thì hành xử theo policy; trả bool "item của bạn có vào không".

**(6) Tại sao return-semantics như vậy:** `True` = item của caller **cuối cùng nằm trong queue** (kể
cả DROP_OLDEST — nó bỏ cái khác, không phải cái bạn). `False` = item của bạn **không vào**
(DROP_NEWEST/REJECT/BLOCK-timeout). Nhờ vậy caller chỉ cần `if not q.put(x): handle_fail()`.

**(7) Dùng ở đâu:** producer gọi `q.put(frame)` hoặc `q.put(frame, timeout=...)` (BLOCK). Test 4 policy
+ 2 BLOCK kiểm từng nhánh (mẩu 08).

**(8) Không có nó (hoặc thiếu khoá) thì sao:** 2 producer cùng `append` khi gần đầy → vượt maxsize /
hỏng deque. Thiếu `notify` → consumer ngủ mãi dù có item.

**(9) Ví von:** bảo vệ bãi xe: còn ô thì cho vào + bấm chuông "có xe"; hết ô thì xử theo nội quy (đuổi
xe cũ / từ chối xe mới / bắt chờ / báo hết chỗ).

**(10) Liên kết bức tranh lớn:** `notify()` (wake 1) đủ vì mỗi thao tác đổi trạng thái đúng 1 đơn vị
(mẩu 05). Metrics tăng dưới khoá → đếm chính xác (không đua).

**(11) Cạm bẫy:** DROP_OLDEST return **True** (dễ nhầm là False vì "có drop"). `drops` đếm số item bị
bỏ, không phải số lần put thất bại. Đừng notify not_full ở DROP_OLDEST (size không đổi).

**(12) Tự kiểm:**
- `put` trả True/False khi nào với mỗi policy?
- Vì sao DROP_OLDEST return True còn DROP_NEWEST return False?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (put) · test `test_drop_oldest_basic`/`test_drop_newest_basic`/
`test_reject_basic`/`test_block_*`. Độ chắc: cao (quote thật + test pass).
