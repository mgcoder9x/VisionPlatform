# Bài #08 — Observability: câu chuyện (vòng cung vấn đề → giải pháp)

> Đọc file này TRƯỚC. Kể *tại sao cần observability* và *tại sao thiết kế như vậy*, trước khi xem
> từng dòng ở các mẩu `01..09`. Thuật ngữ lạ có gloss/link ngay tại chỗ.
> Bám code thật: `vision-platform/src/vision_platform/runtime/observability.py` + test
> `tests/test_step_08_observability.py` (trạng thái: **12 test pass**, full 284/1, lint 5/0).

---

## Nhịp 1 — Tổng quan: observability là gì, nằm ở đâu?

**Observability** (khả năng quan sát) = khả năng *nhìn vào bên trong* một hệ đang chạy để biết nó
đang làm gì, có khoẻ không, hỏng ở đâu — chỉ qua **dữ liệu nó phát ra**. Với sản phẩm chạy 24/7,
nhiều camera, nhiều tiến trình, đây là điều kiện sống còn (không có nó = "mù" khi sự cố).

Ba trụ (3 pillars):
| Trụ | Công cụ (bài này) | Để làm gì |
|-----|-------------------|-----------|
| **Logs** (nhật ký sự kiện) | structlog | truy vết từng sự kiện, debug |
| **Metrics** (số đo tổng hợp) | InMemoryMetrics | nhìn hành vi gộp (bao nhiêu frame/giây, hàng đợi sâu bao nhiêu) |
| **Traces** (dấu vết xuyên tiến trình) | (Module 04, chưa làm) | theo 1 request đi qua nhiều process |

```
                       ┌─────────────────────────┐
  code phát sự kiện ──►│ runtime/observability.py │──► JSON logs (Loki/ELK)
   + số đo            │  structlog + Metrics     │──► metrics (Prometheus sau)
                       └─────────────────────────┘
```

> **Layer nào?** `observability.py` ở `runtime/` (được phép dùng structlog — thư viện ngoài).

---

## Nhịp 2 — Vấn đề & TẠI SAO nó là vấn đề (Forces)

**Nỗi đau: log không biết của ai.** Một tiến trình xử lý nhiều frame/nhiều camera. Log ra:
```
{"event": "frame_received"}
{"event": "detection_started"}
```
→ **Không biết frame nào của camera nào, request nào.** Khi 16 camera chạy chung, log trộn lẫn → vô dụng lúc debug.

**Cách dở (naive):** nhét `camera_id` vào MỌI lời gọi log:
```python
logger.info("frame_received", camera_id="cam_1")
logger.info("detection_started", camera_id="cam_1")   # lặp khắp nơi, dễ quên, bẩn code
```
Lực giằng: *muốn mọi log có camera_id/request_id* ↔ *không muốn nhét tay vào từng dòng*.

**Nỗi đau 2 (metrics): đếm sai khi đa luồng.** Nhiều thread cùng `+= 1` một biến đếm → mất update
(race condition). Cần đếm **đúng** dưới tải.

**Nỗi đau 3 (metrics): nổ số nhãn.** Nếu gắn nhãn (label) là thứ vô hạn (packet_id, toạ độ) → hàng
triệu chuỗi khác nhau → hệ metrics (Prometheus) **hết RAM**.

→ 🤔 **Đoán thử:** làm sao để mọi log trong một "phiên xử lý frame" tự động mang camera_id mà không
phải nhét tay từng dòng?

---

## Nhịp 3 — Khám phá nhiều hướng

**Cho nỗi đau "log không biết của ai":**
- *Hướng 1 — nhét tay mỗi dòng:* bẩn, dễ quên, dễ sai. Loại.
- *Hướng 2 — biến toàn cục:* sai khi đa luồng (thread này ghi đè thread kia). Loại.
- *Hướng 3 — `threading.local`:* lưu theo thread. Nhưng **async** (1 thread chạy nhiều task) hoặc
  thread-pool tái dùng thread → rò rỉ context sang task khác. Loại cho hệ async.
- *Hướng 4 — `contextvars` + structlog processor:* biến theo *ngữ cảnh* (đúng cả sync/async/thread);
  một *processor* tự chèn các biến này vào mọi dòng log. **Chọn.**

**Cho metrics:** dùng `Lock` để mọi thao tác đếm là nguyên tử (atomic) → không mất update. Đơn giản, đúng.

---

## Nhịp 4 — Chốt giải pháp + TẠI SAO nó thắng

1. **`contextvars` + `log_context`** — đặt `camera_id`/`packet_id`/`request_id` vào *ngữ cảnh* một lần
   (bằng `with log_context(...)`), rồi một **processor** (`_add_context_vars`) tự chèn vào mọi dòng
   log trong block. Thắng vì: không nhét tay, đúng cả async/thread, nested-safe (khôi phục đúng khi lồng nhau).

2. **structlog + JSONRenderer** — log ra **JSON có cấu trúc** → máy (Loki/ELK/Datadog) parse được, query được. Hơn hẳn log chuỗi tự do.

3. **`InMemoryMetrics` thread-safe (Lock)** — 3 loại số đo (counter chỉ tăng / gauge lên-xuống /
   histogram phân phối), + nhãn (label) tạo key kiểu Prometheus. `snapshot()` trả **bản copy độc lập**.

4. **Ngân sách cardinality (K-019)** — nhãn phải là *tập hữu hạn nhỏ* (camera_id, status). Thứ vô hạn
   (coords, packet_id) → cho vào **logs**, KHÔNG vào label metric (tránh Prometheus OOM).

> Đây là bước dựng **nền (sink)**. Các *nguồn* dữ liệu đã có (sự kiện `ShmObservabilityHook` từ #05,
> counters backpressure từ #07) — **nối nguồn vào nền này là bước sau** (không nhồi vào #08 — một-vấn-đề-một-lần).

---

## Nhịp 5 — Triển khai (vào code thật)

Đọc lần lượt (`00-muc-luc.md`): vì-sao → contextvars vs threadlocal → log_context → processor →
setup_logging → InMemoryMetrics 3 loại → labels & cardinality → snapshot & thread-safe → 12 test.

## Nhịp 6 — Nên làm / nên tránh

- ✅ **NÊN:** bọc `with log_context(camera_id=..., request_id=...)` quanh xử lý 1 frame → log tự gắn nhãn.
- ✅ **NÊN:** log JSON (parse được) + metrics có nhãn bounded.
- ✅ **NÊN:** `snapshot()` khi cần đọc metrics ra ngoài (bản copy, không đụng internal).
- ⛔ **TRÁNH:** `threading.local` cho context nếu hệ có async/thread-pool.
- ⛔ **TRÁNH:** nhãn metric vô hạn (packet_id/coords) → Prometheus OOM (K-019).
- ⛔ **TRÁNH:** tưởng #08 đã "wire hết" — mới có nền; nối nguồn (#05/#07) là bước sau.
- ⚠️ **NHỚ (K-018):** bản này bỏ production log handlers (non-blocking/rotation/flush) — sản phẩm thật cần thêm.
