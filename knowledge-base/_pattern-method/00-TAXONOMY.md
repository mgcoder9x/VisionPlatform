# 🗂️ TAXONOMY — Phân tầng (tier) các loại "pattern"

> Tham chiếu từ `_TEMPLATE-pattern.md` (ô **Tier**) và `00-PATTERN-METHOD.md` (cùng folder).
> Mục đích: gọi đúng TÊN tầng của một thứ, để không lẫn "nguyên lý" với "cơ chế" và
> chọn đúng cách học (xem ghi chú "cách học" cuối mỗi tier).
>
> Lý do tạo file: `pattern-study/` tham chiếu `architecture-taxonomy-map.md` nhưng file đó
> chưa tồn tại — đây là bản chính thức lấp chỗ trống. Độ chắc chắn: **vừa** (đây là cách phân
> loại làm việc của repo, không phải chuẩn ISO; tên gọi bám POSA/GoF/Fowler).

---

## Bảng tier (từ trừu tượng → cụ thể)

| Tier | Là gì | Phạm vi | Ví dụ | Cách học |
|------|-------|---------|-------|----------|
| **Principle** (Nguyên lý) | Quy luật nền, không phải cấu trúc cụ thể | Toàn hệ | Dependency direction, Coupling/Cohesion, SOLID | upfront, học 1 lần, thấm dần |
| **Architectural style** (Phong cách) | Họ cách tổ chức tổng thể hệ thống | Toàn hệ | Layered, Microservices, Event-driven, Pipes & Filters | upfront, so sánh trade-off |
| **Architectural pattern** (Mẫu kiến trúc) | Cấu trúc giải 1 vấn đề kiến trúc lặp lại | Module/hệ con | **Hexagonal**, Clean/Onion, CQRS | upfront (4-step, POSA) |
| **Design pattern** (Mẫu thiết kế) | Cấu trúc class/object giải vấn đề thiết kế | Vài class | GoF: Strategy, Adapter, Factory, Observer | refactor-to-pattern (4-step, POSA) |
| **Resilience pattern** (Mẫu chịu lỗi) | Giữ hệ ổn định khi lỗi/quá tải | Ranh giới I/O | Bulkhead, Circuit breaker, Backpressure, Retry | upfront, gắn nỗi đau vận hành |
| **Mechanism** (Cơ chế) | Kỹ thuật/công cụ cụ thể, không phải "pattern" | Điểm | DI, SHM atomicity, GIL, mutex, event loop | học khi chạm, gắn vào pattern dùng nó |

---

## Vì sao phân tier quan trọng (kẻo học sai cách)
- **Principle/Style/Architectural pattern** → thường **upfront** (thiết kế trước). Khó "refactor
  vô tình mà ra". Học bằng vẽ sơ đồ + so trade-off.
- **Design pattern (GoF)** → hợp **refactor-to-pattern**: lộ ra từ code xấu (bước Hook the pain).
- **Resilience pattern** → neo vào **nỗi đau vận hành thật** (pipeline stall, OOM, latency spike —
  xem `Design/module-07-troubleshooting/`).
- **Mechanism** → KHÔNG cố nhét vào "2 câu hỏi gốc"; học khi pattern nào đó cần tới nó.

> Cùng tên có thể ở 2 tier: **Adapter** vừa là *design pattern* (GoF) vừa là *mảnh ghép* trong
> *architectural pattern* Hexagonal. Ghi rõ ngữ cảnh đang nói tier nào.

## Ánh xạ vào repo (6 layer §4)
- **Principle** "dependency direction" được **vật lý hóa** bằng import-linter (domain ⇏ adapters).
- **Architectural pattern** Hexagonal = chính cấu trúc kernel(ports) ↔ adapters của repo.
- **Resilience pattern** (bulkhead/backpressure/circuit-breaker) = Module 02 + 04.

## Nguồn + độ chắc chắn
- POSA — *Pattern-Oriented Software Architecture* (Buschmann et al.) — tier + 5-box. Độ chắc: cao (tồn tại).
- GoF — *Design Patterns* (1994) — design pattern tier. Độ chắc: cao.
- M. Fowler, *Patterns of Enterprise Application Architecture* — style/architectural. Độ chắc: cao.
- Cách gộp thành 6 tier ở trên = **quy ước làm việc của repo** [suy đoán hợp lý], không phải chuẩn chính thức. Độ chắc: vừa.
