# Mẩu 01 — Vì sao cần Supervisor + bulkhead (mỗi camera 1 process)

**(1) Thuộc về đâu:** bức tranh tổng bài #09. "Móc treo" cho các mẩu sau.

**(2) Cần biết trước:** process (glossary `#process` — không gian nhớ riêng); bulkhead (vách ngăn —
`knowledge-base/` bulkhead / Module 02 file 03); spawn (sinh process con).

**(3) Code thật (quote docstring `application/supervisor.py`):**
```python
"""Supervisor: spawn worker processes, monitor, graceful shutdown cascade.
...
Bulkhead (Module 02 file 03): mỗi worker = 1 process → cách ly crash (1 worker chết không kéo cả hệ).
"""
```

**(4) Giải thích từng ý nhỏ:**
- "spawn worker processes" → supervisor sinh N tiến trình con (mỗi cái 1 worker/camera).
- "monitor" → theo dõi worker còn sống không.
- "graceful shutdown cascade" → dừng cả hệ sạch sẽ, theo trình tự.
- "mỗi worker = 1 process → cách ly crash" → bulkhead: crash 1 process không kéo process khác.

**(5) Là gì:** Supervisor = tiến trình "quản đốc" quản lý vòng đời các worker process.

**(6) Tại sao tồn tại / vấn đề nó giải:** hệ nhiều camera nặng; nếu chạy chung 1 process → 1 camera
crash kéo sập tất cả. Tách mỗi camera 1 process (bulkhead) → cách ly; nhưng cần ai đó **sinh/giám
sát/khởi động lại/tắt sạch** chúng → đó là Supervisor.

**(7) Dùng ở đâu trong project:** `Supervisor(workers=[WorkerSpec(...)]).run(duration_s=...)`. Test #09
spawn worker thật (ok/crash/graceful). Nối worker Vision thật = composition bước sau.

**(8) Không có nó thì sao:** worker crash không được khôi phục; hoặc chạy chung → mất bulkhead → 1 lỗi sập cả hệ.

**(9) Ví von:** quản đốc phân xưởng: mỗi máy (worker) ở 1 phòng riêng (bulkhead); quản đốc bật máy,
canh máy hỏng thì bật lại, và cuối ca tắt máy đúng quy trình (không rút phích đột ngột).

**(10) Liên kết bức tranh lớn:** `application/` (điều phối). Bulkhead nối #05 (SHM cross-process), #07
(backpressure in-process). Là hạ tầng resilience cho sản phẩm 24/7.

**(11) Cạm bẫy:** đừng nhầm "process" (bulkhead thật, cách ly bộ nhớ) với "thread" (chung bộ nhớ, 1
thread crash có thể kéo cả process). Bulkhead cần **process**.

**(12) Tự kiểm:**
- Vì sao mỗi camera nên là 1 process riêng, không phải 1 thread?
- Supervisor làm 4 việc gì?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (docstring) · Design step-09 (Recap bulkhead). Độ chắc: cao (quote thật + 6 test pass).
