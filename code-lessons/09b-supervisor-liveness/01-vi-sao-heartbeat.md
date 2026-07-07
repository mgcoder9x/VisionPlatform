# Mẩu 01 — Vì sao cần heartbeat: is_alive() không bắt được HANG (K-020)

**(1) Thuộc về đâu:** bức tranh tổng #09b. "Móc treo".

**(2) Cần biết trước:** `p.is_alive()` (#09 — hỏi OS process còn tồn tại không); crash vs hang/deadlock; heartbeat (nhịp sống).

**(3) Code thật (quote docstring `application/supervisor.py`):**
```python
LIVENESS (sub-spec supervisor-liveness, đóng K-020/K-021 — ADDITIVE, default TẮT):
- **Heartbeat (K-020):** ... Supervisor coi HANG nếu alive nhưng (now − nhịp-cuối) > heartbeat_timeout_s
  → terminate + xử lý như failure (restart theo cap). Bắt được hang/deadlock mà `is_alive()` KHÔNG bắt
  được (camera chết thầm).
```

**(4) Giải thích từng ý nhỏ:**
- "alive nhưng (now − nhịp-cuối) > timeout" → process còn sống NHƯNG lâu rồi không đập nhịp → coi treo.
- "`is_alive()` KHÔNG bắt được" → điểm cốt lõi: is_alive chỉ biết "tồn tại", không biết "còn làm việc".

**(5) Là gì:** heartbeat = worker phát nhịp định kỳ; supervisor coi treo nếu nhịp ngừng quá lâu (dù process còn sống).

**(6) Tại sao tồn tại / vấn đề nó giải (K-020):** worker deadlock / kẹt I/O / vòng lặp vô hạn → `is_alive()`
=True → supervisor tưởng khoẻ → KHÔNG restart → camera "chết thầm" (không ra frame nhưng hệ báo OK). Đây là
lỗi 24/7 **vô hình, tệ nhất**. Heartbeat biến "còn sống" thành "còn LÀM VIỆC".

**(7) Dùng ở đâu trong project:** `WorkerSpec.uses_heartbeat=True` → supervisor cấp kênh nhịp; `_is_hung`
kiểm trong `run` loop. Test `test_hang_detected_and_restarted` (mẩu 07).

**(8) Không có nó thì sao:** đúng lỗ hổng K-020 — worker treo không bao giờ được phát hiện/khôi phục.

**(9) Ví von:** bảo vệ điểm danh "còn thở không" (is_alive) — người NGẤT vẫn "còn thở" nên không ai cấp cứu.
Heartbeat = bắt mỗi người "vẫy tay mỗi 30 giây"; ai ngừng vẫy (dù còn thở) → biết có chuyện → can thiệp.

**(10) Liên kết bức tranh lớn:** bổ sung cho crash-detection (#09). Cùng resilience với bulkhead (#09),
backpressure (#07), shutdown cascade (#09). Production Vision Platform dùng ZMQ heartbeat reply (bản này dùng mp.Value nội bộ).

**(11) Cạm bẫy:** đừng tin `is_alive()`=True là "đang làm việc". Heartbeat chỉ hoạt động nếu worker CHỦ
ĐỘNG đập nhịp (worker phải gọi cập nhật định kỳ — mẩu 03).

**(12) Tự kiểm:**
- Phân biệt crash vs hang. `is_alive()` bắt cái nào?
- Vì sao "chết thầm" (hang không phát hiện) là loại lỗi tệ nhất cho hệ 24/7?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (docstring LIVENESS) · journal K-020 · Design step-09 (Self-check #5). Độ chắc: cao (quote thật + test hang pass).
