# Mẩu 02 — `WorkerSpec`: bản mô tả 1 worker

**(1) Thuộc về đâu:** `application/supervisor.py`, `WorkerSpec` (dataclass).

**(2) Cần biết trước:** `@dataclass` (glossary `#dataclass`); `Callable` (kiểu "hàm gọi được"); mp.Event (bài này, mẩu 05/06).

**(3) Code thật (quote `application/supervisor.py`):**
```python
@dataclass
class WorkerSpec:
    """Spec để spawn 1 worker process."""
    worker_id: str
    target: Callable[..., None]
    args: tuple = ()
    max_restarts: int = 3
    uses_shutdown_event: bool = False
```

**(4) Giải thích từng field:**
- `worker_id: str` → tên định danh worker (log, tra restart_count).
- `target: Callable[..., None]` → **hàm** worker sẽ chạy trong process con.
- `args: tuple = ()` → tham số truyền cho target.
- `max_restarts: int = 3` → số lần restart tối đa trước khi bỏ.
- `uses_shutdown_event: bool = False` → **True** nếu target nhận `shutdown_event` làm arg ĐẦU TIÊN
  (worker cooperative — tự poll để thoát sạch, mẩu 05/06).

**(5) Là gì:** một "tờ khai" mô tả worker: chạy hàm nào, tham số gì, restart tối đa mấy lần, có
cooperative không.

**(6) Tại sao tồn tại / vấn đề nó giải:** tách **cấu hình worker** (dữ liệu) khỏi **cơ chế quản lý**
(Supervisor). Supervisor nhận list `WorkerSpec` → không cần biết chi tiết từng worker, chỉ theo spec.

**(7) Dùng ở đâu trong project:** `Supervisor(workers=[WorkerSpec(worker_id="w1", target=ok_worker,
args=(path,)), ...])`. `uses_shutdown_event=True` cho `graceful_worker` (mẩu 06).

**(8) Không có nó thì sao:** phải truyền rời rạc nhiều tham số cho Supervisor → rối, khó mở rộng
(thêm max_restarts/cooperative phải sửa chữ ký).

**(9) Ví von:** phiếu công việc cho từng máy: máy nào (worker_id), chạy chương trình gì (target), tham
số (args), hỏng thì thử lại mấy lần (max_restarts), có nút "tự tắt" không (uses_shutdown_event).

**(10) Liên kết bức tranh lớn:** `uses_shutdown_event` là mấu chốt cho cascade cooperative-first (mẩu
05): Supervisor chỉ chờ grace cho worker cooperative, non-coop bị terminate thẳng.

**(11) Cạm bẫy:** nếu `uses_shutdown_event=True` thì target PHẢI nhận `shutdown_event` làm arg đầu
(Supervisor tự chèn) — sai chữ ký → worker lỗi. `max_restarts` mặc định 3 (không vô hạn).

**(12) Tự kiểm:**
- `uses_shutdown_event` ảnh hưởng gì tới cách Supervisor spawn + shutdown?
- Vì sao tách WorkerSpec (dữ liệu) khỏi Supervisor (cơ chế)?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (WorkerSpec) · Design step-09 (Phần 1). Độ chắc: cao (quote thật).
