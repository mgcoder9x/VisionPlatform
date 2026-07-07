# Mẩu 03 — `BoundedQueue.__init__`: deque + khoá + 2 điều kiện + metrics

**(1) Thuộc về đâu:** `kernel/backpressure.py`, `BoundedQueue.__init__`.

**(2) Cần biết trước:** `deque` (glossary `#deque` — hàng đợi 2 đầu, append/popleft O(1)); `Lock`
(khoá — 1 thời điểm 1 thread giữ); `Condition` (mẩu 05); `Generic[T]` (glossary `#generic` — lớp
tổng quát theo kiểu T).

**(3) Code thật (quote `kernel/backpressure.py`):**
```python
class BoundedQueue(Generic[T]):
    def __init__(self, maxsize: int, policy: BackpressurePolicy):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._buf: deque[T] = deque()
        self._maxsize = maxsize
        self._policy = policy
        self._lock = Lock()
        self._not_empty = Condition(self._lock)
        self._not_full = Condition(self._lock)
        self.drops = 0
        self.rejects = 0
        self.block_timeouts = 0
```

**(4) Giải thích từng dòng:**
- `if maxsize < 1: raise ValueError` → fail-fast: hàng đợi 0 chỗ vô nghĩa.
- `self._buf: deque[T] = deque()` → bộ đệm chứa item. `deque` để `append`/`popleft` nhanh (2 đầu).
- `self._maxsize` → sức chứa tối đa (enforce bằng tay trong `put`, deque tự nó không giới hạn).
- `self._lock = Lock()` → khoá bảo vệ mọi thao tác lên `_buf` (thread-safe).
- `self._not_empty = Condition(self._lock)` → điều kiện "có item" (consumer chờ) — **dùng chung 1 lock**.
- `self._not_full = Condition(self._lock)` → điều kiện "còn chỗ" (producer BLOCK chờ) — cùng lock đó.
- `self.drops / rejects / block_timeouts = 0` → 3 bộ đếm quan sát.

**(5) Là gì:** hàm dựng hàng đợi: bộ đệm + giới hạn + policy + khoá + 2 điều kiện + metrics.

**(6) Tại sao tồn tại / vấn đề nó giải:** gom mọi trạng thái cần cho thread-safe + backpressure vào 1
chỗ. Hai `Condition` **cùng một `Lock`** là điểm mấu chốt (mẩu 05): cho phép chờ 2 việc khác nhau (có
item / có chỗ) mà không đua nhau.

**(7) Dùng ở đâu trong project:** mọi `BoundedQueue[int](maxsize=..., policy=...)` trong test (mẩu 08)
và tầng trên. `Generic[T]` cho phép `BoundedQueue[Frame]`, `BoundedQueue[int]`...

**(8) Không có (vd bỏ maxsize check / bỏ Lock) thì sao:** `maxsize=0` → không bao giờ nhận được item;
bỏ `Lock` → 2 thread cùng sửa `_buf` → hỏng cấu trúc/đếm sai.

**(9) Ví von:** dựng một bãi giữ xe: số ô tối đa (`maxsize`), sổ ghi (`_buf`), một chìa khoá cổng
(`_lock`), hai chuông báo "có xe ra" và "còn chỗ trống" (2 Condition), và 3 bảng đếm sự cố (metrics).

**(10) Liên kết bức tranh lớn:** `Generic[T]` + kernel-thuần → tái dùng cho mọi loại item, không dính
công nghệ. Metrics là bề mặt quan sát cho #08.

**(11) Cạm bẫy:** hai `Condition` PHẢI chia sẻ **cùng** `self._lock` (truyền `Lock` vào constructor
`Condition`). Nếu tạo 2 lock riêng → mất đồng bộ. `_buf` là deque không giới hạn — giới hạn do `put`
kiểm `len < maxsize`, đừng quên.

**(12) Tự kiểm:**
- Vì sao 2 Condition dùng chung 1 Lock?
- `maxsize < 1` bị chặn ở đâu, vì sao?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (__init__) · test `test_maxsize_must_be_positive` /
`test_props_...`. Độ chắc: cao (quote thật + test pass).
