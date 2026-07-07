# Bài #09 — Supervisor + shutdown: câu chuyện (vòng cung vấn đề → giải pháp)

> Đọc file này TRƯỚC. Kể *tại sao cần supervisor + graceful shutdown* và *tại sao cascade như vậy*,
> trước khi xem từng dòng ở các mẩu `01..09`. Thuật ngữ lạ có gloss/link ngay tại chỗ.
> Bám code thật: `vision-platform/src/vision_platform/application/supervisor.py` +
> `tests/worker_funcs_for_step_09.py` + `tests/test_step_09_shutdown.py` (trạng thái: **6 test pass**,
> full 290/1, lint 5/0).

---

## Nhịp 1 — Tổng quan: supervisor nằm ở đâu, làm gì?

Hệ Vision chạy **nhiều camera**, mỗi camera nặng (đọc RTSP, giải mã, xử lý). Kiến trúc: **mỗi camera
= 1 tiến trình (process) riêng** — gọi là **bulkhead** (vách ngăn — như khoang tàu: 1 khoang thủng
không chìm cả tàu). Cần một "người quản đốc" (**Supervisor**) để: sinh (spawn) các worker process,
theo dõi chúng sống/chết, khởi động lại (restart) khi crash, và **dừng cả hệ một cách sạch sẽ**
(graceful shutdown) khi tắt.

```
              ┌────────────── Supervisor (process cha) ──────────────┐
              │  spawn · monitor(is_alive) · restart(cap) · shutdown  │
              └───┬───────────────┬───────────────┬──────────────────┘
        spawn     │               │               │
                  ▼               ▼               ▼
             worker cam_1    worker cam_2    worker cam_3   (mỗi cái 1 process — bulkhead)
```

> **Layer nào?** `Supervisor` ở `application/` (điều phối vòng đời — được dùng multiprocessing/signal).

---

## Nhịp 2 — Vấn đề & TẠI SAO nó là vấn đề (Forces)

**Nỗi đau 1 — worker chết thì sao?** Camera 1 crash (RTSP rớt, lỗi giải mã). Nếu không ai restart →
mất camera đó vĩnh viễn. Nếu restart **vô tận** (worker hỏng cấu hình, crash ngay mỗi lần) → spawn/exit
dồn dập → CPU 100%. Lực giằng: *tự phục hồi* ↔ *không lặp vô tận*.

**Nỗi đau 2 — tắt hệ mà không mất dữ liệu.** Khi shutdown, worker đang ghi file/giữ kết nối/buffer.
Nếu **giết cứng** ngay → mất dữ liệu, hỏng trạng thái. Cần cho worker **cơ hội dọn dẹp** (cleanup) trước.

**Nỗi đau 3 (nền tảng — cực quan trọng) — Windows không có SIGTERM cooperative.** Trên Linux,
`terminate()` gửi tín hiệu `SIGTERM` mà worker có thể bắt để dọn dẹp. Trên **Windows**, `terminate()`
= `TerminateProcess` — **giết cứng, KHÔNG chạy khối `finally`/handler**. → "graceful" kiểu dựa SIGTERM
KHÔNG chạy trên Windows.

→ 🤔 **Đoán thử:** làm sao dừng worker "sạch" (chạy được cleanup) trên CẢ Windows lẫn Linux?

---

## Nhịp 3 — Khám phá nhiều hướng

**Cho "dừng sạch":**
- *Hướng 1 — `terminate()` ngay:* Linux (worker có handler) thì cleanup chạy; Windows thì KHÔNG (kill
  cứng). Không đồng nhất. Và **bug E-10**: nếu set event rồi terminate() NGAY → cleanup bị race, gần
  như luôn mất trên Windows (đo thật: 1/20 lần cleanup chạy). Loại.
- *Hướng 2 — cooperative (worker tự poll tín hiệu dừng):* supervisor set một `shutdown_event`; worker
  chủ động kiểm event trong vòng lặp, thấy set thì **tự thoát vòng lặp** → chạy `finally` cleanup. Đúng
  trên CẢ Windows lẫn Linux (không dựa SIGTERM). **Chọn.**

**Cho "restart":** đếm số lần restart, vượt ngưỡng (`max_restarts`) thì **bỏ** (give up) → tránh loop vô tận.

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO nó thắng

1. **Cooperative shutdown + cascade "cooperative-first"** (fix ERRATA E-10) — thứ tự ĐÚNG:
   - (0) set `shutdown_event`;
   - (1) **JOIN** worker cooperative với thời gian ân hạn (grace) TRƯỚC → cho `finally` cleanup chạy xong;
   - (2) `terminate()` worker còn sống (non-cooperative / bị treo);
   - (3) `kill()` kẻ ngoan cố cuối cùng.
   Thắng vì: worker cooperative được dọn dẹp sạch TRƯỚC khi ai đó ra tay cứng. Bug cũ (terminate ngay)
   làm cleanup race → mất (đo thật 1/20 → sau fix 20/20).

2. **restart cap `>`** — "max 3 restarts" = restart đúng 3 lần rồi bỏ → không loop vô tận.

3. **`daemon=True`** — worker tự chết theo supervisor (an toàn nếu supervisor crash không kịp cascade).

4. **Worker ở module riêng** — Windows spawn re-import module chứa worker; để trong test file dễ gây
   lỗi re-import → tách ra `tests/worker_funcs_for_step_09.py`.

> #09 giao **cơ chế supervisor** + test. Nối worker Vision thật (camera/inference) vào = composition bước sau.

---

## Nhịp 5 — Triển khai (vào code thật)

Đọc lần lượt (`00-muc-luc.md`): vì-sao supervisor/bulkhead → WorkerSpec → spawn/monitor/restart →
restart cap → cascade cooperative-first (E-10) → graceful_worker → worker module (spawn) → giới hạn
hang (K-020) → 6 test.

## Nhịp 6 — Nên làm / nên tránh

- ✅ **NÊN:** dùng cooperative `shutdown_event` cho worker cần cleanup (đúng Windows + Linux).
- ✅ **NÊN:** đặt restart cap để tránh loop vô tận.
- ✅ **NÊN:** worker ở module riêng (spawn-safe).
- ⛔ **TRÁNH:** dựa `terminate()`/SIGTERM để "graceful" trên Windows (kill cứng, không cleanup).
- ⛔ **TRÁNH:** terminate() NGAY sau set event (bug E-10 — cleanup race).
- ⚠️ **NHỚ (K-020):** `is_alive()` chỉ bắt crash, KHÔNG bắt hang → sản phẩm cần heartbeat liveness.
- ⚠️ **NHỚ (K-021):** production cần exponential backoff giữa các lần restart.
