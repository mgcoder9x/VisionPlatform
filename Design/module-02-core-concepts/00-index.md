# Module 02 — Core Concepts (5 pattern lặp đi lặp lại)

## Mục đích

Module 01 cho bạn nền (coupling, dependency direction). Module 02 cho bạn **5 pattern cụ thể** mà bạn sẽ gặp đi gặp lại trong Vision Platform — và trong **mọi dự án real-time** tương tự.

Mỗi file dạy bạn:
1. **Pattern là gì** (1 câu)
2. **Vấn đề thực tế** nào sinh ra pattern này (không có vấn đề = không cần pattern)
3. **Build từ con số 0** — tự code 1 bản "đồ chơi" trước khi xem bản production
4. **Trade-offs** — khi nào KHÔNG dùng
5. **Pitfalls** — những bug điển hình khi áp dụng sai

## Yêu cầu trước

Đã pass Module 01 self-check. Đặc biệt cần hiểu vững:
- Coupling vs Cohesion
- Stable Dependencies Principle
- Dependency Inversion Principle

Nếu chưa rõ — quay lại Module 01.

## Thời gian

8-12 giờ. **Mỗi file ~1.5-2.5h**, gồm cả code-along và checkpoint.

## Thứ tự đọc (KHÔNG nhảy)

| # | File | Pattern | Vấn đề thực giải quyết | Thời gian |
|---|------|---------|------------------------|-----------|
| 1 | [`01-hexagonal-architecture-from-scratch.md`](01-hexagonal-architecture-from-scratch.md) | Hexagonal (Ports & Adapters) | "Đổi DB từ Postgres sang SQLite mất 2 tuần" | 2.5h |
| 2 | [`02-ports-and-adapters-build-one.md`](02-ports-and-adapters-build-one.md) | Ports & Adapters concrete | "Test camera code phải khởi RTSP server thật" | 2h |
| 3 | [`03-bulkhead-pattern.md`](03-bulkhead-pattern.md) | Bulkhead | "1 camera disconnect kéo cả 15 camera xuống" | 2h |
| 4 | [`04-backpressure-why-it-matters.md`](04-backpressure-why-it-matters.md) | Backpressure | "Producer đẩy nhanh hơn consumer xử lý → OOM" | 2h |
| 5 | [`05-immutability-and-cow.md`](05-immutability-and-cow.md) | Immutability + Copy-on-Write | "MediaPacket bị mutate giữa stage → bug ngẫu nhiên" | 1.5h |
| 6 | [`99-self-check.md`](99-self-check.md) | Tổng hợp | Tự kiểm tra. | 1h |

## Output sau Module 02

Bạn sẽ:

1. **Vẽ được Hexagonal architecture** cho 1 use case bất kỳ trong dự án (không tra cứu).
2. **Code 1 port + 2 adapter** từ rỗng, có test, chạy cả 2 adapter pass cùng test suite.
3. **Phân biệt** "multi-process vì bulkhead" vs "multi-process vì performance" — chọn đúng strategy.
4. **Chọn backpressure policy** đúng cho RTSP/file/webcam/HTTP upload — biện luận được.
5. **Implement frozen DTO trong Python** với CoW correctly — biết được 4 pitfalls.

## Format mỗi file

Theo template constructivist của Module 01:
- **TL;DR (30s)**
- **Mental hook** — câu hỏi/tình huống
- **Câu chuyện** — analogy
- **Định nghĩa chính xác**
- **Build from scratch** — code thực
- **Áp dụng vào Vision Platform**
- **Mental model** — diagram
- **Code-along** — gõ thật 20-30 phút
- **Checkpoint** — câu hỏi
- **Trade-offs**
- **Pitfalls** — bugs điển hình
- **Liên kết**

## Liên kết

- **Trước**: [`../module-01-foundations/`](../module-01-foundations/00-index.md) — nền.
- **Sau**: [`../module-03-build-along/`](../module-03-build-along/00-overview.md) — code thật `vision_demo_workspace/`.
- **Production**: 
  - Hexagonal → `Vision_platform_architecture_design/02-architecture/`
  - Bulkhead → `Vision_platform_architecture_design/13-adr/06-multi-process-bulkhead-*.md`
  - Backpressure → `Vision_platform_architecture_design/06-resilience-and-shutdown/`
  - Immutability → `Vision_platform_architecture_design/03-data-contracts/06-mediapacket-*.md`

---

➡️ Bắt đầu: [`01-hexagonal-architecture-from-scratch.md`](01-hexagonal-architecture-from-scratch.md)
