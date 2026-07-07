# 🗂️ TAXONOMY — Phân tầng (tier) các loại "pattern" (portable)

> Tham chiếu từ `_TEMPLATE-pattern.md` (ô Tier) + `00-PATTERN-METHOD.md`. Gọi đúng tier để chọn đúng cách học.

| Tier | Là gì | Ví dụ | Cách học |
|------|-------|-------|----------|
| **Principle** | Quy luật nền | Dependency direction, SOLID | upfront, thấm dần |
| **Architectural style** | Cách tổ chức tổng thể | Layered, Microservices, Event-driven | upfront, so trade-off |
| **Architectural pattern** | Cấu trúc giải vấn đề kiến trúc | Hexagonal, Clean/Onion, CQRS | upfront (4-step, POSA) |
| **Design pattern** | Cấu trúc class/object | GoF: Strategy, Adapter, Factory | refactor-to-pattern |
| **Resilience pattern** | Giữ ổn định khi lỗi/quá tải | Bulkhead, Circuit breaker, Backpressure | upfront, gắn nỗi đau vận hành |
| **Mechanism** | Kỹ thuật/công cụ cụ thể | DI, mutex, event loop | học khi chạm |

> Cùng tên có thể ở 2 tier (vd Adapter = design pattern + mảnh ghép của Hexagonal). Ghi rõ ngữ cảnh.
> Nguồn: POSA (Buschmann), GoF (1994), Fowler (PoEAA). Cách gộp 6 tier = quy ước làm việc [suy đoán hợp lý].
