# Mẩu 02 — `BackpressurePolicy`: 4 lựa chọn khi đầy

**(1) Thuộc về đâu:** `kernel/backpressure.py`, enum `BackpressurePolicy`.

**(2) Cần biết trước:** `Enum` (glossary `#enum` — tập hằng có tên); FIFO (vào trước ra trước).

**(3) Code thật (quote `kernel/backpressure.py`):**
```python
class BackpressurePolicy(Enum):
    """Chính sách khi hàng đợi đầy (maxsize)."""
    DROP_OLDEST = "drop_oldest"   # bỏ item cũ nhất, nhận item mới (giữ dữ liệu mới)
    DROP_NEWEST = "drop_newest"   # bỏ item mới (giữ item đang có)
    BLOCK = "block"               # chặn producer tới khi có chỗ / timeout
    REJECT = "reject"             # từ chối ngay, không chặn
```

**(4) Giải thích từng giá trị:**
- `DROP_OLDEST` → đầy thì **bỏ cái cũ nhất**, nhét cái mới. Ưu tiên "mới nhất".
- `DROP_NEWEST` → đầy thì **bỏ cái vừa đến**. Ưu tiên giữ cái đang có (cũ).
- `BLOCK` → **chặn** nơi bỏ vào tới khi có chỗ (hoặc hết giờ). Không mất dữ liệu nhưng kéo tụt.
- `REJECT` → **từ chối ngay**, trả về "không vào được" để caller tự xử.

**(5) Là gì:** enum liệt kê 4 cách xử lý khi hàng đợi đầy.

**(6) Tại sao tồn tại / vấn đề nó giải:** không có cách "đúng cho mọi nguồn" (nhịp 3 cau-chuyen). Enum
biến "chọn hành vi" thành **tham số cấu hình** thay vì viết 4 lớp queue khác nhau.

**(7) Dùng ở đâu trong project:** truyền vào `BoundedQueue(maxsize, policy)`; `put()` rẽ nhánh theo
policy (mẩu 04). Test mỗi policy có test riêng (mẩu 08).

**(8) Không có nó thì sao:** phải hard-code 1 hành vi cho mọi nguồn → camera live (cần mới nhất) và
file batch (không được mất) buộc dùng chung → sai một trong hai.

**(9) Ví von:** quán ăn hết chỗ: DROP_OLDEST = mời khách ngồi lâu nhất đi; DROP_NEWEST = từ chối khách
mới; BLOCK = bảo khách mới đứng chờ tới khi có bàn; REJECT = treo biển "hết chỗ, mời quán khác".

**(10) Liên kết bức tranh lớn:** enum ở `kernel` (hằng thuần). Việc *nguồn nào dùng policy nào* (vd
RTSP cấm BLOCK) là cấu hình tầng trên — SRP: enum chỉ *liệt kê lựa chọn*, không ép ai dùng gì.

**(11) Cạm bẫy:** Module 02 có 6 policy; #07 CỐ Ý bỏ `SAMPLE`/`DEGRADE_QUALITY` khỏi queue — đó là
quyết định *phía nguồn* ("tôi chỉ phát 1/N khung"), không phải "queue đầy thì làm gì". Nhồi vào queue
= phá SRP (mẩu này nối self-check #5 Design).

**(12) Tự kiểm:**
- 4 policy khác nhau ở điểm nào? Mỗi cái hi sinh gì?
- Vì sao SAMPLE KHÔNG nằm trong enum này?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `kernel/backpressure.py` (BackpressurePolicy) · Design step-07 (Phần 1 + Self-check #5).
Độ chắc: cao (quote thật).
