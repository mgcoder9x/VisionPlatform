# Mẩu 08 — Giới hạn: is_alive() chỉ bắt CRASH, không bắt HANG (K-020) + thiếu backoff (K-021)

**(1) Thuộc về đâu:** `application/supervisor.py`, cách giám sát `p.is_alive()`. Đây là ranh giới trung thực cho sản phẩm.

**(2) Cần biết trước:** crash (process exit) vs hang/deadlock (process sống nhưng kẹt, không làm gì);
heartbeat (nhịp sống định kỳ); exponential backoff (chờ 2^n giữa lần thử).

**(3) Code thật (quote — điểm giám sát trong `run()`):**
```python
if not p.is_alive():
    ...   # phát hiện chết → restart
```

**(4) Giải thích từng ý nhỏ:**
- `p.is_alive()` → hỏi OS "process này còn tồn tại không". Trả True cả khi process đang **ngủ/kẹt**.
- Vì vậy: worker **crash** (exit) → `is_alive()`=False → phát hiện + restart. Nhưng worker **hang**
  (vòng lặp vô hạn, deadlock, chờ I/O mãi) → `is_alive()`=**True** → supervisor tưởng khoẻ → KHÔNG restart.

**(5) Là gì:** hai lỗ hổng đã biết + ghi rõ: (K-020) không phát hiện hang; (K-021) restart không backoff.

**(6) Tại sao là vấn đề cho sản phẩm 24/7:**
- **K-020 (hang):** camera "chết thầm" — process sống nhưng không xử lý frame nào; dashboard thấy
  "alive" nên không ai biết. → sản phẩm thật cần **heartbeat liveness**: worker ghi timestamp/gửi
  nhịp định kỳ; supervisor so mtime, quá hạn → kill+restart. (Vision Platform production dùng ZMQ heartbeat reply.)
- **K-021 (backoff):** worker crash liên tục → restart NGAY mỗi lần → spawn/exit dồn dập (CPU spike).
  Production cần `sleep(2^restart_count)` (có trần) để giãn nhịp + cho tài nguyên hồi.

**(7) Dùng ở đâu trong project:** ghi journal K-020/K-021 (04-things-to-know) — bước bổ sung tương lai.
Bản #09 CỐ Ý giản lược (chỉ crash-detection + restart cap).

**(8) Không ghi nhận (tưởng đã đủ) thì sao:** deploy bản này cho 24/7 → camera hang không tự phục hồi
→ mất dữ liệu âm thầm mà giám sát báo "khoẻ" — loại sự cố tệ nhất (mù).

**(9) Ví von:** bảo vệ chỉ điểm danh "còn thở không" (is_alive) — người ngất (hang) vẫn "còn thở" nên
không ai cấp cứu. Cần đo thêm "còn cử động/phản hồi không" (heartbeat).

**(10) Liên kết bức tranh lớn:** trung thực về giới hạn = văn hoá dự án (journal 🔴/🟡). Heartbeat sẽ
nối với observability (#08 metrics/logs) khi làm production.

**(11) Cạm bẫy:** ĐỪNG tin `is_alive()=True` nghĩa là "worker đang làm việc". Đó chỉ là "process tồn
tại". Sản phẩm phải thêm heartbeat trước khi tin.

**(12) Tự kiểm:**
- Phân biệt crash vs hang. `is_alive()` bắt được cái nào?
- Heartbeat liveness giải quyết K-020 thế nào?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `application/supervisor.py` (is_alive) · journal K-020/K-021 · Design step-09 (Self-check
#5 + Restart cap). Độ chắc: cao (giới hạn is_alive là bản chất API multiprocessing).
