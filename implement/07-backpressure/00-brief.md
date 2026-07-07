# Vấn đề #07 — Backpressure: BoundedQueue 4 policy (PHA 1 valid + PHA 2 plan)

> **Nguồn Design:** `Design/module-03-build-along/step-07-add-backpressure.md` (đọc nguyên văn).
> **Trạng thái:** PHA 1 valid xong — thiết kế SẠCH, không deviation cần duyệt. Tiến thẳng PHA 2.
> **Cập nhật lúc:** 2026-07-04.

## 1. Mục tiêu #07 (theo Design)
`kernel/backpressure.py` gồm:
- `BackpressurePolicy(Enum)` — 4 policy: `DROP_OLDEST`, `DROP_NEWEST`, `BLOCK`, `REJECT`.
  (Module 02 có 6 policy; #07 bỏ `SAMPLE`/`DEGRADE_QUALITY` vì là quyết định source-side, không phải queue-side — SRP.)
- `BoundedQueue(Generic[T])` — hàng đợi có chặn, thread-safe, metrics (`drops`/`rejects`/`block_timeouts`).
- 11 test: 4 policy basic + 2 BLOCK + 1 concurrent stress + (còn lại: get/get_or_raise/qsize/maxsize/validate).

## 2. Đối chiếu Design ↔ CODE THẬT (chống bịa)
| Design giả định | Code THẬT | Kết luận |
|---|---|---|
| package `vision_demo` | `vision_platform` | đổi tên nhất quán |
| file `kernel/backpressure.py` | CHƯA tồn tại (kernel/ có media_packet/read_result/shm_*/stage_contract/inference_protocol/ports) | additive, 0 đụng độ |
| import `threading`/`collections.deque`/`queue`/`enum`/`typing` ở kernel | contract #2 kernel forbidden KHÔNG chứa các module này (chỉ cấm cv2/torch/zmq/multiprocessing/shared_memory/PyQt6/fastapi/psutil/runtime/application) | ✅ hợp lệ layer |
| `BoundedQueue[int](maxsize=3, policy=...)` | `Generic[T]` subscripting → callable instantiate (py3.13) | ✅ chạy được (sẽ verify bằng test) |

## 3. Đánh giá diện rộng (doubt-driven — thiết kế đã đúng chưa?)
- **Condition + wait_for:** đúng — 2 điều kiện (`_not_empty`/`_not_full`) trên 1 lock; `wait_for(pred)` chống spurious wakeup. Event không làm được (chỉ 1 boolean).
- **notify() (không notify_all):** đúng + hiệu quả — mỗi `get()` giải phóng đúng 1 chỗ → wake 1 producer BLOCK; mỗi `put()` thêm đúng 1 item → wake 1 consumer. Không starvation trong mô hình 1-item-1-slot.
- **DROP_OLDEST** popleft+append: net size không đổi → chỉ notify `_not_empty` (có item mới), KHÔNG notify `_not_full` (không giải phóng chỗ) — đúng.
- **Metrics under-lock:** `drops/rejects/block_timeouts += 1` đều trong `with self._lock` → thread-safe không cần atomic. (Design ghi rõ né lỗi HI-OBS-01 kiểu class-var race.)
- **get() None-ambiguity:** Design đã lường (T có thể là None) → cung cấp `get_or_raise` raise `queue.Empty`. Defensive tốt.
→ **Kết luận: thiết kế production-minded, giữ nguyên. KHÔNG có deviation cần đổi.**

## 4. Điều NÊN BIẾT (ghi journal — ranh giới đúng cho sản phẩm thương mại)
- **K-016 (correctness):** `BoundedQueue` là **THREAD-safe** (`threading.Lock`/`Condition`) — KHÔNG **process-safe**. Chỉ dùng cho hàng đợi TRONG 1 tiến trình (vd capture-thread → submit-thread). Cross-process phải dùng SHM ring (#05). Dùng nhầm cross-process → lock vô hiệu → hỏng dữ liệu. (Nguồn: threading không đồng bộ qua process; đối lập mp.Lock của #05.)
- **Observability:** `BoundedQueue` mới expose metrics dạng counter; **wiring `ObservabilityHook`/structlog hoãn tới #08** (không nhồi vào #07 — LAW #1 một-vấn-đề). Không phải thiếu sót, là ranh giới chủ ý.
- **BLOCK cấm cho RTSP:** ràng buộc "source RTSP không được dùng BLOCK (gây TCP Zero Window)" enforce ở **tầng cấu hình/per-source** (production doc `06-resilience-and-shutdown/01-...`), KHÔNG ở `BoundedQueue` — queue giữ policy-agnostic (SRP đúng).

## 5. Kế hoạch PHA 2 (TDD) — tiến thẳng (không deviation nên không chờ duyệt)
1. `kernel/backpressure.py`: enum + BoundedQueue theo Design (giữ nguyên vì đã sạch) + docstring ghi rõ K-016 (thread-safe not process-safe).
2. `tests/test_step_07_backpressure.py`: 11 test (4 policy + 2 BLOCK + 1 concurrent + 4 phụ: get None/timeout, get_or_raise raise, qsize/maxsize/policy props, maxsize<1 → ValueError).
3. Chạy THẬT `pytest tests/test_step_07_backpressure.py` + full suite + `lint-imports` (kỳ vọng 5 kept/0 broken).
