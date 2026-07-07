# Mẩu 05 — `Condition` + `wait_for`: chờ đúng điều kiện, chống spurious wakeup

**(1) Thuộc về đâu:** `kernel/backpressure.py` — `_not_empty`/`_not_full` (Condition) dùng trong
`put`/`get`.

**(2) Cần biết trước:** thread ngủ/thức (chờ tín hiệu); race condition (2 thread tranh nhau); mẩu 03
(2 Condition cùng 1 Lock).

**(3) Code thật (quote — nhánh BLOCK trong `put`):**
```python
if not self._not_full.wait_for(
    lambda: len(self._buf) < self._maxsize,
    timeout=timeout,
):
    self.block_timeouts += 1
    return False
```
Và trong `get`:
```python
if not self._not_empty.wait_for(
    lambda: len(self._buf) > 0,
    timeout=timeout,
):
    return None
```

**(4) Giải thích từng ý nhỏ:**
- `Condition` = khoá + khả năng "ngủ chờ tới khi được đánh thức". Ở đây 2 Condition (`_not_empty`,
  `_not_full`) chia sẻ **cùng** `_lock`.
- `wait_for(predicate, timeout)` = "ngủ tới khi `predicate()` True **hoặc** hết `timeout`". Trả True
  nếu điều kiện thoả, False nếu timeout.
- `lambda: len(self._buf) < self._maxsize` → điều kiện "còn chỗ" cho producer BLOCK.
- `lambda: len(self._buf) > 0` → điều kiện "có item" cho consumer.

**(5) Là gì:** `Condition` là công cụ để thread ngủ chờ **một điều kiện cụ thể** rồi được đánh thức;
`wait_for` gói sẵn vòng lặp "chờ tới khi điều kiện đúng".

**(6) Tại sao tồn tại / vấn đề nó giải:**
- **Condition thay vì Event:** `Event` chỉ 1 boolean, đánh thức tất cả, không phân biệt "ai chờ gì".
  Ta cần *hai* điều kiện (có chỗ / có item) → cần Condition (nhiều điều kiện trên cùng lock).
- **`wait_for` thay vì `wait` trần:** hệ điều hành có thể đánh thức thread **vô cớ** (spurious
  wakeup — glossary; hiếm nhưng có thật, nhất là POSIX). `wait()` trần thức dậy → phải tự kiểm lại
  điều kiện. `wait_for(pred)` = `while not pred(): wait()` dựng sẵn → an toàn, gọn.

**(7) Dùng ở đâu:** `put` (BLOCK) chờ `_not_full`; `get`/`get_or_raise` chờ `_not_empty`. Bên kia
`notify()` sau khi đổi trạng thái: `put` append → `_not_empty.notify()`; `get` popleft → `_not_full.notify()`.

**(8) Không có `wait_for` (dùng `wait` trần) thì sao:** spurious wakeup → thread tưởng có chỗ/có item
trong khi chưa → append vượt maxsize / popleft deque rỗng → lỗi. Không có Condition (dùng Event) →
không tách được "chờ chỗ" vs "chờ item".

**(9) Ví von:** phòng chờ có 2 chuông: "bàn trống" (cho khách chờ bàn) và "món ra" (cho bồi bàn).
`wait_for` = "chỉ đứng dậy khi đúng chuông của mình VÀ đúng là có bàn thật" — nghe nhầm chuông
(spurious) thì ngồi lại.

**(10) Liên kết bức tranh lớn:** đây là nền thread-safety của toàn `BoundedQueue`. `notify()` (wake 1)
đủ vì mỗi `get` giải phóng đúng 1 chỗ → đánh thức 1 producer; mỗi `put` thêm đúng 1 item → 1 consumer.

**(11) Cạm bẫy:** phải `notify` ĐÚNG điều kiện đối ứng sau khi đổi trạng thái (quên → thread ngủ mãi).
`wait_for` phải chạy **trong** `with self._lock` (Condition yêu cầu giữ lock khi wait). Predicate phải
đọc trạng thái thật (`len(self._buf)`), không dùng biến cache.

**(12) Tự kiểm:**
- `Condition` khác `Event` ở đâu? Vì sao bài này cần Condition?
- Spurious wakeup là gì? `wait_for` chống nó thế nào?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (put/get) · Design step-07 (Decisions: Condition over Event,
wait_for) · Self-check #1/#2. Độ chắc: cao (quote thật + concurrent test pass).
