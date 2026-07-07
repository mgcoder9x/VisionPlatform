# Bài #07 — Backpressure: câu chuyện (vòng cung vấn đề → giải pháp)

> Đọc file này TRƯỚC. Nó kể *tại sao cần backpressure* và *tại sao thiết kế BoundedQueue như vậy*,
> trước khi xem từng dòng ở các mẩu `01..08`. Thuật ngữ lạ có gloss/link ngay tại chỗ.
> Bám code thật: `vision-platform/src/vision_platform/kernel/backpressure.py` + test
> `tests/test_step_07_backpressure.py` (trạng thái: **11 test pass**, full 272 passed/1 skipped, lint 5/0).

---

## Nhịp 1 — Tổng quan: thứ này nằm ở đâu?

Trong hệ thị giác, **nơi sản xuất** (camera đọc frame ~30–60 khung/giây) thường **nhanh hơn nơi tiêu
thụ** (detector chạy AI, có thể chỉ kịp 10–20 khung/giây). Giữa hai bên cần một **hàng đợi** (queue).

```
Producer (nhanh)        Hàng đợi có giới hạn        Consumer (chậm hơn)
 camera/thread   ──put──►  [ ][ ][ ][ ]  ──get──►   detector/thread
                          maxsize = N (đầy → ?)
```

Câu hỏi sống-còn: **khi hàng đợi ĐẦY mà producer vẫn muốn bỏ thêm vào thì làm gì?** Đó chính là
**backpressure** (áp lực ngược): cơ chế để hệ "đẩy lùi" khi bị quá tải, thay vì vỡ.

> **Layer nào?** `BoundedQueue` sống ở `kernel/backpressure.py` — cơ chế thuần Python (hàng đợi +
> khoá), không dính công nghệ cụ thể (glossary `#kernel`). Nó là *công cụ nền*, các tầng trên dùng lại.

---

## Nhịp 2 — Vấn đề & TẠI SAO nó là vấn đề (Forces)

Nếu làm **ngây thơ** (naive): dùng hàng đợi *không giới hạn* (cứ đầy thì phình ra). Hỏng ở đâu?
- Producer nhanh hơn consumer kéo dài → hàng đợi phình vô hạn → **hết RAM → crash cả tiến trình**.
- Với luồng mạng (RTSP), nếu chặn producer sai cách → dồn ứ tầng TCP (**TCP Zero Window**) → nghẽn cả kết nối.

Lực giằng nhau (Forces) khi đầy:
- *Giữ frame MỚI* (thực tế mới nhất quan trọng) ↔ *giữ frame CŨ* (đang xử lý dở, thứ tự).
- *Chặn producer chờ* (không mất frame) ↔ *không chặn* (không kéo tụt cả hệ / không nghẽn mạng).
- *Đơn giản* ↔ *đúng khi nhiều thread tranh nhau put/get cùng lúc* (an toàn luồng — thread safety).

→ 🤔 **Đoán thử:** khi hàng đợi đầy, có mấy cách xử lý khác nhau, và mỗi cách hi sinh cái gì?

---

## Nhịp 3 — Khám phá nhiều hướng (chính là 4 policy)

Không có một cách "đúng cho mọi trường hợp" — nên ta cho **chọn chính sách (policy)**:
- **DROP_OLDEST** — đầy thì bỏ frame *cũ nhất*, nhận frame mới. Hi sinh: mất frame cũ. Hợp: real-time
  cần "mới nhất" (live view).
- **DROP_NEWEST** — đầy thì bỏ frame *mới đến*. Hi sinh: mất frame mới. Hợp: khi frame cũ đang xử lý dở quan trọng hơn.
- **BLOCK** — đầy thì *chặn* producer tới khi có chỗ (hoặc hết giờ chờ). Hi sinh: kéo tụt producer.
  ⛔ **KHÔNG dùng cho RTSP** (gây TCP Zero Window). Hợp: nguồn file/batch, không được mất dữ liệu.
- **REJECT** — đầy thì *từ chối ngay*, báo caller tự xử. Hi sinh: caller phải xử lý thất bại. Hợp: khi
  muốn phản hồi tức thì, không chặn.

(Module 02 có 6 policy; #07 bỏ `SAMPLE`/`DEGRADE_QUALITY` — đó là quyết định *phía nguồn* "tôi chỉ
phát 1/N khung", không phải việc của hàng đợi. Xem nhịp 4.)

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO nó thắng

1. **`BoundedQueue` có `maxsize` + `policy` cấu hình** — một lớp hàng đợi, chọn hành vi lúc tạo. Thắng
   vì: mỗi nguồn (camera live / file / RTSP) chọn policy phù hợp mà không cần viết lớp queue riêng.

2. **Thread-safe bằng `Lock` + 2 `Condition`** (`_not_empty`, `_not_full`) — nhiều thread put/get đồng
   thời vẫn đúng. Dùng `Condition` (không `Event`) vì cần *hai* điều kiện chờ khác nhau trên cùng khoá
   (mẩu 05). Dùng `wait_for(predicate)` để chống *spurious wakeup* (thức giấc vô cớ — glossary).

3. **Chia trách nhiệm (SRP):** hàng đợi lo *"đầy thì xử theo policy"*; còn *"nguồn phát quá nhanh nên
   tự tiết chế"* (SAMPLE) là việc của nguồn. Không nhồi SAMPLE vào queue → queue đơn giản, đúng một việc.

4. **Ranh giới thread ≠ process** (K-016 — điểm sống còn cho sản phẩm): `BoundedQueue` dùng
   `threading.Lock` → chỉ đồng bộ **trong một tiến trình** (nhiều thread). Truyền frame **giữa các
   tiến trình** vẫn phải dùng **SHM ring** (#05) + `mp.Lock`. Dùng `BoundedQueue` cross-process = khoá
   vô hiệu → hỏng dữ liệu âm thầm. (Chi tiết mẩu 07.)

---

## Nhịp 5 — Triển khai (vào code thật)

Đọc lần lượt các mẩu (`00-muc-luc.md`): 4 policy (enum) → cấu trúc `BoundedQueue` → luồng `put` 4 nhánh
→ `Condition`/`wait_for` → `get` vs `get_or_raise` → thread-vs-process → 11 test.

## Nhịp 6 — Nên làm / nên tránh

- ✅ **NÊN:** chọn policy theo nguồn (live→DROP_OLDEST; file→BLOCK; cần phản hồi ngay→REJECT).
- ✅ **NÊN:** đọc metrics (`drops`/`rejects`/`block_timeouts`) để biết hệ đang quá tải (obs wire ở #08).
- ✅ **NÊN:** dùng `get_or_raise` nếu queue có thể chứa `None` hợp lệ (tránh nhập nhằng None-timeout).
- ⛔ **TRÁNH:** dùng `BLOCK` cho nguồn RTSP (gây TCP Zero Window).
- ⛔ **TRÁNH:** dùng `BoundedQueue` để chia sẻ **giữa các tiến trình** (threading.Lock không cross-process).
- ⛔ **TRÁNH:** hàng đợi không giới hạn (phình RAM → crash).
