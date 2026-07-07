# Module 04 — Deep Dives (đọc khi đã build xong vision_demo_workspace)

## Mục tiêu

Module 03 đã làm cho bạn build được `vision_demo_workspace/`. Module 04 trả lời các câu hỏi **"tại sao"** sâu hơn — các quyết định technical mà bạn có thể đã làm "theo chỉ dẫn" mà chưa hiểu rõ.

**Đặc biệt**: các file có benchmark đều in code experiment để bạn tự tạo/chạy trong `vision_demo_workspace/experiments/` sau khi hoàn thành Module 03. Bạn không phải tin theory — chạy để thấy số liệu trên máy bạn.

## Yêu cầu trước

Đã hoàn thành Module 03 step 01-09. (Step 10 packaging có thể sau.)

## File list

| # | File | Câu hỏi trả lời | Có benchmark? | Trạng thái |
|---|------|-----------------|---------------|------------|
| 1 | [`01-gil-truth.md`](01-gil-truth.md) | Tại sao Python multi-thread vô dụng cho CPU-bound? Numbers cụ thể. | ✓ `bench_gil.py` | ✓ COMPLETE |
| 2 | [`02-shm-atomicity-explained.md`](02-shm-atomicity-explained.md) | Header torn read là gì? x86-64 atomic guarantees. R5-CRITICAL-01 fix sâu. | – | ✓ COMPLETE |
| 3 | [`03-zmq-patterns-comparison.md`](03-zmq-patterns-comparison.md) | PUB/SUB vs REQ/REP vs ROUTER/DEALER. Khi nào chọn cái nào. | – | ✓ COMPLETE |
| 4 | [`04-asyncio-event-loop-mental-model.md`](04-asyncio-event-loop-mental-model.md) | Cách event loop work. Coroutine vs thread vs process. R5-HIGH-02 watchdog. | – | ✓ COMPLETE |
| 5 | [`05-circuit-breaker-math.md`](05-circuit-breaker-math.md) | Threshold tính sao? Recovery jitter staggered? Half-open probe. | – | ✓ COMPLETE |
| 6 | [`06-traceback-memory-retention.md`](06-traceback-memory-retention.md) | R5-CRITICAL-02 deep dive. Tại sao Python exception giữ MediaPacket sống. | ✓ `bench_traceback_retention.py` | ✓ COMPLETE |

## Output

Sau Module 04: bạn đọc `Vision_platform_architecture_design/05-inference-and-ipc/` và `04-pipeline-and-concurrency/` → **hiểu MỌI quyết định**, không chỉ "đọc cho biết".

## Cách đọc

KHÁC Module 01-02 (đọc tuần tự). Module 04 = **deep reference**. Bạn có thể:
- Đọc tuần tự nếu muốn understand toàn bộ.
- Hoặc đọc khi gặp vấn đề cụ thể (e.g. debug latency spike → đọc `04-asyncio-event-loop`).

## Format

Mỗi file:
- **Câu hỏi cốt lõi** — 1 dòng.
- **Theory** — concept + analogy.
- **Code experiment** — chạy thật để verify.
- **Real numbers** — output của experiment.
- **Áp dụng vào Vision Platform** — link tới production design + R-fix nếu có.
- **Self-check** — 5 câu hỏi.

---

➡️ Bắt đầu: [`01-gil-truth.md`](01-gil-truth.md)
