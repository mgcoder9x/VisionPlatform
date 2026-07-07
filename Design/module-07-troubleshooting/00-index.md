# Module 07 — Troubleshooting (khi production có bug)

## Mục đích

3h sáng. Pager kêu. Production pipeline stall. Bạn mở module này.

Mỗi file = **1 symptom phổ biến** với decision tree debug.

## Cách đọc

KHÔNG đọc tuần tự. Đọc khi gặp symptom cụ thể.

→ Mỗi file độc lập, có decision tree dán lên tường.

## File list

| # | File | Symptom | Trạng thái |
|---|------|---------|------------|
| 1 | [`01-pipeline-stalls.md`](01-pipeline-stalls.md) | Frame không chảy. Không error. Stuck. | ✓ |
| 2 | [`02-memory-grows.md`](02-memory-grows.md) | Memory tăng dần theo giờ. OOM crash sau 24h. | ✓ |
| 3 | [`03-latency-spikes.md`](03-latency-spikes.md) | p99 latency tăng đột ngột nhưng p50 OK. | ✓ |
| 4 | [`04-shutdown-hangs.md`](04-shutdown-hangs.md) | Ctrl+C không tắt. Container kill timeout. | ✓ |
| 5 | [`05-cant-find-the-bug-systematic.md`](05-cant-find-the-bug-systematic.md) | "Tôi đã tìm 3 ngày, không ra." Systematic approach. | ✓ |

---

➡️ Đọc theo symptom hiện tại bạn gặp.
