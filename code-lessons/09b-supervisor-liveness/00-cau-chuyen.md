# Bài #09b — Supervisor liveness (heartbeat + backoff): câu chuyện

> Đọc file này TRƯỚC. Kể *tại sao cần heartbeat + backoff* và *tại sao thiết kế additive như vậy*,
> trước khi xem từng dòng ở mẩu `01..07`. "b" = tiến hoá của #09 (crash-detection → + hang-detection).
> Bám code thật: `application/supervisor.py` (đã sửa additive) + `tests/liveness_workers.py` +
> `tests/test_supervisor_liveness.py` (trạng thái: **4 test pass**, #09 giữ 6 pass, full 304/1, lint 5/0).

---

## Nhịp 1 — Tổng quan: từ "biết chết" đến "biết treo"

Bài #09 dựng `Supervisor` giám sát worker bằng `p.is_alive()` — biết khi worker **chết** (process exit).
Bài #09b thêm khả năng biết khi worker **treo** (hang): process còn sống nhưng kẹt, không làm gì. Cộng
thêm **backoff**: giãn nhịp restart khi worker crash liên tục.

```
 Supervisor (#09b)
   ├── is_alive()  → bắt CRASH (đã có #09)
   ├── heartbeat   → bắt HANG (mới — worker phải "đập nhịp" định kỳ)   ← đóng K-020
   └── backoff     → crash liên tục thì giãn dần lần restart            ← đóng K-021
```

> **Layer:** vẫn `application/supervisor.py` — sửa **ADDITIVE** (thêm, không phá #09).

---

## Nhịp 2 — Vấn đề & TẠI SAO (Forces)

**Nỗi đau chính (K-020) — "chết thầm".** `is_alive()` chỉ hỏi OS "process còn tồn tại không". Worker
**deadlock / kẹt I/O / vòng lặp vô hạn** → process VẪN sống (`is_alive()`=True) → supervisor tưởng khoẻ →
KHÔNG restart → camera không ra frame nhưng dashboard báo "OK". Đây là loại lỗi 24/7 **tệ nhất: vô hình**.

**Nỗi đau phụ (K-021) — restart bão hoà.** Worker hỏng cấu hình crash NGAY mỗi lần → supervisor respawn
NGAY → spawn/exit dồn dập → CPU spike + log ngập. Cần giãn nhịp (backoff).

**Ràng buộc:** phải **không phá #09** (6 test đang xanh) → thêm phải ADDITIVE (mặc định tắt).

→ 🤔 **Đoán thử:** làm sao supervisor (process cha) biết worker (process con) "còn đang làm việc" chứ không chỉ "còn sống"?

---

## Nhịp 3 — Khám phá nhiều hướng

**Phát hiện hang:**
- *Hướng 1 — chỉ `is_alive()`:* không bắt được hang (đúng lỗ hổng K-020). Loại.
- *Hướng 2 — heartbeat qua FILE:* worker ghi timestamp ra file, supervisor đọc mtime. Được, nhưng I/O đĩa + rác file.
- *Hướng 3 — heartbeat qua `mp.Value` chia sẻ:* worker ghi `time.time()` vào ô nhớ chia sẻ; supervisor
  đọc. Không I/O đĩa, atomic dưới lock sẵn. **Chọn.**

**Backoff:**
- *Hướng 1 — `sleep(backoff)` trong vòng giám sát:* đơn giản NHƯNG **chặn giám sát worker KHÁC** (đang sleep
  cho worker A thì B treo không ai biết). Loại.
- *Hướng 2 — deadline non-blocking (`_next_spawn_ok`):* ghi "thời điểm được respawn", vòng vẫn chạy kiểm
  worker khác, chỉ respawn khi tới hạn. **Chọn.**

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO thắng

1. **Heartbeat qua `mp.Value('d')` (wall-clock `time.time()`)** — worker đập nhịp, supervisor coi HANG nếu
   alive nhưng (now − nhịp-cuối) > timeout. Dùng **wall-clock** (không monotonic) vì phải **so được giữa 2
   process** (monotonic mỗi process một gốc, không so được). Đóng **K-020**.
2. **Startup grace** — worker mới spawn chưa kịp đập nhịp lần đầu (hb=0) → dùng mốc spawn → không báo hang oan.
3. **Backoff non-blocking** (`_next_spawn_ok` deadline) — giãn `base·2^(n-1)` (trần cap) mà không chặn giám
   sát worker khác. Đóng **K-021**.
4. **ADDITIVE (mặc định TẮT)** — `uses_heartbeat=False`, `restart_backoff_base_s=0.0` → hành vi Y HỆT #09
   (chỉ crash-detection, respawn ngay). 6 test #09 giữ xanh. Thắng vì: thêm năng lực mà zero regression.
5. **Failure thống nhất** — crash và hang đi qua CÙNG đường xử lý (count + cap `>` + backoff) → logic một chỗ.

---

## Nhịp 5 — Triển khai (vào code)

Đọc các mẩu (`00-muc-luc.md`): vì-sao heartbeat → WorkerSpec additive → mp.Value + prepend → _is_hung +
startup grace → failure thống nhất → backoff non-blocking → test.

## Nhịp 6 — Nên làm / nên tránh

- ✅ **NÊN:** worker chạy vòng dài phải "đập nhịp" định kỳ để supervisor biết còn sống-và-làm-việc.
- ✅ **NÊN:** heartbeat wall-clock (so cross-process được); backoff monotonic (đo khoảng trong 1 process).
- ✅ **NÊN:** giữ additive (default tắt) để không phá hành vi cũ.
- ⛔ **TRÁNH:** tin `is_alive()`=True nghĩa là "đang làm việc" (chỉ là "process tồn tại").
- ⛔ **TRÁNH:** `sleep(backoff)` trong vòng giám sát (chặn worker khác).
- ⛔ **TRÁNH:** dùng monotonic cho heartbeat cross-process (mỗi process gốc khác nhau → so sai).
- ⚠️ **NHỚ:** startup grace — đừng báo hang worker vừa spawn chưa kịp đập nhịp.
