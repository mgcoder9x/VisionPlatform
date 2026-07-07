# Mẩu 08 — 11 test: policy + BLOCK timing + concurrent stress

**(1) Thuộc về đâu:** `tests/test_step_07_backpressure.py`. Bằng chứng cho mọi khẳng định mẩu 01–07.

**(2) Cần biết trước:** `threading.Thread` (chạy hàm song song); `time.monotonic()` (đồng hồ đo
khoảng, không giật lùi); `pytest.raises`.

**(3) Code thật — hai test cốt lõi (quote `tests/test_step_07_backpressure.py`):**

BLOCK trả True khi consumer lấy chỗ:
```python
def test_block_returns_when_consumer_takes():
    q = BoundedQueue[int](maxsize=1, policy=BackpressurePolicy.BLOCK)
    q.put(1)   # đầy
    def consumer():
        time.sleep(0.1)
        q.get()
    t = threading.Thread(target=consumer); t.start()
    start = time.monotonic()
    result = q.put(2, timeout=1.0)
    elapsed = time.monotonic() - start
    t.join()
    assert result is True
    assert 0.05 < elapsed < 0.5   # có chặn, nhưng không hết timeout
```

Concurrent stress:
```python
def test_concurrent_producer_consumer():
    q = BoundedQueue[int](maxsize=10, policy=BackpressurePolicy.BLOCK)
    n = 100
    received = []
    def producer():
        for i in range(n): q.put(i, timeout=2.0)
    def consumer():
        for _ in range(n):
            item = q.get(timeout=2.0)
            if item is not None: received.append(item)
    ...
    assert len(received) == n
    assert received == list(range(n))   # FIFO giữ nguyên
```

**(4) Giải thích từng ý nhỏ:**
- `test_block_returns...`: queue đầy (maxsize=1); consumer ngủ 0.1s rồi `get()` (giải phóng chỗ);
  producer `put(2, timeout=1.0)` bị chặn → khi consumer lấy → producer thức → put thành công. `0.05 <
  elapsed < 0.5` chứng minh **có chặn thật** (>0.05) nhưng **không hết timeout** (<0.5).
  - `time.sleep(0.1)` trong consumer để producer **kịp vào trạng thái chờ** trước → test tất định
    (không đua). (Self-check #4 Design.)
- `test_concurrent...`: 100 item, queue max 10 → producer bị BLOCK liên tục; nếu khoá có bug →
  **deadlock hoặc mất item**. Pass + `received == list(range(100))` = **FIFO đúng, không mất, không kẹt**.

**(5) Là gì:** bộ 11 test: 4 policy basic + 2 BLOCK (timing) + 1 concurrent stress + 4 phụ (get None,
get_or_raise raise, props, maxsize<1).

**(6) Tại sao tồn tại / vấn đề nó giải:** biến "khoá đúng, không race, FIFO giữ" thành **bằng chứng
chạy được** (luật §5: code = chạy test thật). Concurrent test là chốt chặn bug đồng bộ.

**(7) Dùng ở đâu / kết quả thật:** `pytest tests/test_step_07_backpressure.py -q` → **11 passed**
(0.94s); full **272 passed, 1 skipped** (10.44s); `lint-imports` **5 kept, 0 broken**.

**(8) Không có test concurrent thì sao:** bug khoá (deadlock/lost item) chỉ lộ ngẫu nhiên lúc tải cao
trong sản phẩm — đúng lúc tệ nhất. Test này ép nó lộ ngay lúc dev.

**(9) Ví von:** chạy thử 100 xe qua trạm 10 ô cùng lúc để xem có kẹt/mất xe không — thay vì tin
"chắc trạm ổn".

**(10) Liên kết bức tranh lớn:** test BLOCK timing + concurrent là nơi tính đúng-đắn-đồng-bộ (mẩu 05)
được kiểm chứng thật. Nối §5 (verify bằng chạy thật).

**(11) Cạm bẫy:** test dựa thời gian (`0.05 < elapsed < 0.5`) có thể nhạy nếu máy quá tải; ngưỡng đặt
rộng để giảm flaky. `if item is not None` trong consumer vì `get` có thể trả None khi timeout.

**(12) Tự kiểm:**
- Vì sao consumer cần `time.sleep(0.1)` trong test BLOCK?
- Test concurrent phát hiện được loại bug nào mà test đơn luồng bỏ sót?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `tests/test_step_07_backpressure.py` (11 test, đã chạy pass) · Design step-07 (Phần 3
Tests + Self-check #4). Độ chắc: cao (output pytest thật: 11 passed / full 272 passed, 1 skipped).
