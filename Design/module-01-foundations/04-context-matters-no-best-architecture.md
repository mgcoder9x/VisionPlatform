# 04 — Context quyết định tất cả — không có "best architecture"

## TL;DR (30 giây)

> Mọi quyết định kiến trúc đều là **trade-off**. Không có "best practice tuyệt đối", chỉ có "phù hợp với context X, không phù hợp với context Y".
>
> Trước khi áp dụng pattern (Hexagonal, Microservices, Event-Sourced...) phải hỏi: **context của tôi là gì?** Trả lời được mới chọn được pattern.

---

## Mental hook

Bạn vừa đọc 1 bài blog: "Why microservices are the future". Bạn về dự án HeadDetect, đề xuất chuyển sang microservices. Sếp hỏi:

- "Bao nhiêu camera?" — 8 camera.
- "Bao nhiêu request/giây?" — ~240 frame/s tổng cộng.
- "Đội bao nhiêu người?" — 3 dev.
- "Triển khai ở đâu?" — 1 server on-premise.

Sếp: "Microservices? Để làm gì?"

→ Bạn nhận ra: **"future" của bài blog là context Netflix/Uber với 1000+ engineers, 100M user, multi-region**. Context của bạn khác hoàn toàn. Cùng pattern, áp dụng sai context = thảm hoạ.

---

## Câu chuyện: 3 dự án, 3 kiến trúc khác nhau

### Dự án 1: Trang blog cá nhân

- 1 dev, 100 visitor/day, 50 bài viết.
- DB: SQLite trong file.
- Server: 1 VPS $5/tháng.

**Kiến trúc tốt nhất**: 1 file `app.py` 200 dòng dùng Flask. Hết.

Áp dụng Hexagonal/CQRS/Microservices vào đây = tự bắn chân:
- Tốn 2 tuần setup.
- 5 file abstraction cho 1 endpoint /post/<id>.
- Performance còn chậm hơn vì serialization overhead.
- Maintain khó hơn vì phải nhớ 5 file thay vì 1.

### Dự án 2: HeadDetect — Vision Platform

- 3 dev, 8-16 camera real-time, GPU shared, 24/7 uptime.
- Pain points thật: GPU thermal throttle, camera disconnect, OOM khi backpressure sai.
- Triển khai: 1-2 server, on-premise hoặc edge.

**Kiến trúc tốt nhất**: 4-layer Hexagonal + Bulkhead per camera + Centralized inference + ZMQ IPC.

→ Đây là context **Vision_platform_architecture_design/** giải quyết.

Áp dụng monolith 1 file vào đây? CHẾT vì 1 camera disconnect kéo theo 15 cái.
Áp dụng microservices full đây? OVER-ENGINEER vì 3 dev không đủ vận hành 10 service.

### Dự án 3: Hệ thống Uber

- 5000+ dev, 100M request/giây, multi-region, 24/7.
- Pain points: scale linearly, deploy nhiều team đồng thời, fail isolation cấp service.

**Kiến trúc tốt nhất**: Microservices + Event-driven + Saga + CQRS.

→ Đây là chỗ "Why microservices are the future" nói đến.

---

## Quy tắc: 3 chiều quyết định kiến trúc

Trước khi chọn kiến trúc, đo 3 chiều:

### Chiều 1: Quy mô (Scale)

- **Số user/request đồng thời**? 10? 1000? 1M?
- **Throughput**? 1 req/s, 1000, 1M?
- **Data volume**? GB? TB? PB?

→ Nhỏ: monolith đủ. Vừa: vertical scaling + good architecture. Lớn: distributed.

Vision Platform: **vừa** — 16 camera × 30 FPS = 480 fps. Vertical scaling + good arch là đủ.

### Chiều 2: Tính phức tạp business (Domain Complexity)

- **Logic nghiệp vụ phức tạp**? (e.g. ngân hàng — calculate interest over 50 product types)
- Hay **technical complexity** chiếm chính? (e.g. video streaming — bytes flow, ít business rule)

→ Domain phức tạp: DDD, CQRS, Event Sourcing có giá trị.
→ Technical heavy: Hexagonal đủ, không cần CQRS.

Vision Platform: **technical heavy**. Logic nghiệp vụ "phát hiện vật thể" tương đối simple. Phức tạp nằm ở GIL/SHM/IPC. Hexagonal đủ, không cần CQRS.

### Chiều 3: Tổ chức (Team)

- **Bao nhiêu dev**?
- **Distributed team** hay co-located?
- **Skill level đồng đều** hay phân tán?

→ 1-3 dev: monolith / well-structured single repo.
→ 5-15: modular monolith.
→ 15+: microservices (Conway's Law: code organization mirrors team organization).

Vision Platform: **3 dev**. Không cần microservices. Modular monolith với clear boundaries là đỉnh cao của lựa chọn cho team size này.

---

## Quy tắc: KHÔNG có pattern xấu, chỉ có sai context

### Singleton: pattern bị ghét nhất

Sách nào cũng nói "Singleton là anti-pattern":

```python
# pattern xấu?
class DatabaseConnection:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**Khi nào tệ**:
- Test khó vì state global.
- Hidden dependency — code dùng `DatabaseConnection()` không khai báo.

**Khi nào TỐT**:
- **Cross-cutting infrastructure** không nên duplicate. Ví dụ: `LoggingHandle` trong Vision Platform — 1 process có 1 log queue listener. Tạo 2 = drop log mỗi lần. Singleton ở đây ĐÚNG.
- **Performance critical**: object pool, connection pool — tạo nhiều instance = tốn.

→ Singleton xấu khi dùng thay cho dependency injection. Tốt khi quản lý infrastructure resource.

### Microservices: pattern hot nhất

Khi nào ĐÚNG:
- Team 50+ dev, deploy độc lập là vấn đề.
- Different scaling profile per service (auth scale 100x, search scale 10x).
- Khác stack tech (Python ML + Go API + Rust kernel).

Khi nào SAI:
- Team < 10 dev.
- Single domain.
- Latency critical (network call thay function call = +1ms mỗi hop).

→ Vision Platform có **3 process** (camera, inference, supervisor) — ĐỦ. Đây là **multi-process bulkhead**, KHÔNG phải microservices.

### Event Sourcing: pattern xịn nhất

Khi nào ĐÚNG:
- Audit trail là legal requirement (banking, healthcare).
- Cần "replay history" để debug bug production.
- Nhiều derived view (read model) từ cùng source of truth.

Khi nào SAI:
- Đơn giản CRUD app.
- Storage cost không kham nổi (lưu mọi event = TB).
- Đội không hiểu CQRS.

→ Vision Platform: **không** dùng event sourcing. Detection events thì lưu vào sink (Kafka/MQTT/file) — KHÔNG cần rebuild state từ events. Audit không phải critical.

---

## Mental model: bộ tool đa dụng

Bạn thợ mộc. Có nhiều tool:

| Tool | Khi dùng |
|------|----------|
| Búa | Đóng đinh |
| Tua-vít | Vặn ốc |
| Cưa | Cắt gỗ |
| Khoan | Khoan lỗ |

"Búa là best tool" — sai. "Khi đóng đinh, búa là best tool" — đúng.

Pattern kiến trúc cũng vậy:

| Pattern | Khi dùng |
|---------|----------|
| Hexagonal | Khi cần testability + swap implementation. |
| Bulkhead | Khi 1 component fail không được kéo cả hệ thống. |
| Backpressure | Khi consumer chậm hơn producer. |
| CQRS | Khi read/write có pattern rất khác nhau. |
| Event Sourcing | Khi history là source of truth. |
| Microservices | Khi team scale + service scale độc lập. |

→ Đọc bài blog "X is the future" = ai đó đang giới thiệu cái búa của họ. Bạn cần biết mình **đang đóng đinh hay vặn ốc** trước.

---

## Áp dụng: Vision Platform là context gì?

Sau 5 vòng review, đây là context Vision Platform giải quyết:

| Chiều | Giá trị | Implication |
|-------|---------|-------------|
| **Scale** | 8-16 camera × 30 FPS = 240-480 fps | Vertical scaling, không distributed. |
| **Domain complexity** | Technical heavy (GIL, SHM, IPC), business logic moderate. | Hexagonal, không CQRS. |
| **Team** | 3-5 dev | Modular monolith, không microservices. |
| **Latency** | <33ms per frame budget | Avoid network hops. ZMQ IPC OK (~1ms), HTTP không OK (~10ms). |
| **Reliability** | 24/7, 1 camera fail không kéo cả hệ thống | Bulkhead per camera. |
| **Hardware** | 1 GPU shared | Centralized inference service. |

→ 4-layer Hexagonal + Bulkhead + Centralized inference + ZMQ + Backpressure.

**Mỗi quyết định kiến trúc có thể truy về 1 context constraint.** Đó là dấu hiệu kiến trúc tốt.

---

## Pattern KHÔNG phù hợp Vision Platform (và lý do)

### 1. Microservices full-blown

Lý do: 3-5 dev không đủ vận hành 10 service. Network hop overhead phá latency budget.

→ Dùng **multi-process trong cùng host** thay thế. Same isolation benefit, không network overhead.

### 2. Event Sourcing

Lý do: detection events ghi xuống sink để consume downstream — không cần rebuild state. Storage cost lưu mọi raw frame quá lớn.

→ Lưu **events** vào sink (Kafka/MQTT) cho consumer downstream. **Không** event-source state.

### 3. Synchronous request-response qua HTTP

Lý do: HTTP có 1-10ms overhead per call. Tại 480 fps, 1ms × 480 = 480ms/s = không thể đạt.

→ Dùng **ZMQ async** (~1ms total). Hoặc **SHM** (~5µs).

### 4. Single-threaded event loop (kiểu Node.js)

Lý do: Python GIL không cho true parallelism trong 1 process. CV detector cần GPU = blocking.

→ Dùng **multi-process** (bypass GIL) + **asyncio trong process** cho IO concurrency.

### 5. Database-centric architecture

Lý do: data flow chính là **frame stream** (nghìn frames/s), không phải SQL transaction.

→ Database là **sink**, không phải center. Data flow đi qua memory/SHM.

---

## Code-along: kiểm tra context của dự án bạn (15 phút)

Mở `_my_context.md`. Trả lời 10 câu hỏi cho dự án bạn đang làm:

1. Bao nhiêu user/request đồng thời (peak)?
2. Throughput target (req/s, fps)?
3. Latency budget per request (ms)?
4. Bao nhiêu dev trong team?
5. Domain logic phức tạp (1-10)? Cho ví dụ.
6. Technical complexity phức tạp (1-10)? Cho ví dụ.
7. Triển khai: 1 host, multiple host, cloud, edge?
8. Hardware constraint: GPU shared? Memory limit?
9. Reliability target: 99%, 99.9%, 99.99%?
10. Audit/compliance requirement?

**Sau đó**, dựa trên đó, đánh dấu các pattern PHÙ HỢP và KHÔNG phù hợp:

| Pattern | Phù hợp? | Lý do |
|---------|----------|-------|
| Hexagonal | | |
| Bulkhead | | |
| Microservices | | |
| Event Sourcing | | |
| CQRS | | |
| Backpressure | | |
| Multi-process | | |
| Async IO | | |

Đây là bài tập cốt lõi. Làm xong = bạn có **rationale** đầu tiên cho dự án mình.

---

## Checkpoint

Trả lời ra `_my_answers.md`:

1. Bài blog "Microservices are the future" áp dụng cho công ty bao nhiêu người? Nếu áp vào team 3 người sẽ ra sao?

2. Vision Platform có phải "microservices" không? Nếu không, gọi nó là gì?

3. Cho 1 ví dụ pattern X "tốt trong context A nhưng tệ trong context B" — không lấy ví dụ trong file này.

4. Bạn nghe đồng nghiệp đề xuất "dùng Event Sourcing cho Vision Platform". Bạn phản biện thế nào, dựa trên context?

5. Trong dự án HeadDetect bạn đang làm, pattern nào ĐANG dùng SAI context? (Nhìn vào `main_app/`).

<details>
<summary>Đáp án gợi ý</summary>

1. Áp cho 50+ engineers, hàng triệu request, multi-region. Áp vào team 3 người = chưa kịp viết business logic, đã ngập trong infra (10+ service, 10+ CI pipeline, distributed tracing, service mesh...). Sau 6 tháng = giao được 1 feature đáng kể.

2. KHÔNG. Gọi là **multi-process bulkhead**. Khác microservices ở chỗ:
   - Cùng codebase, deploy 1 lần.
   - Cùng host (không network).
   - Cùng team owner.
   - IPC qua SHM/ZMQ (cùng host) thay vì HTTP cross-network.
   
   Lợi ích isolation tương tự, không có chi phí distributed system.

3. *(Câu cá nhân)*. Ví dụ: **GraphQL** — tốt khi nhiều client mobile/web cần shape khác nhau từ cùng backend. Tệ khi 1 client duy nhất, vì over-engineer query plan + 2× latency vs REST.

4. "Detection event là **fact**, không phải state cần rebuild. Chúng ta không cần 'replay từ event 0 để xây current state'. Chúng ta chỉ cần stream events ra sink. Event Sourcing thêm storage cost khổng lồ (raw frame ndarray = TB/ngày), thêm complexity rebuild logic, KHÔNG giải quyết pain point gì hiện tại. YAGNI."

5. *(Câu cá nhân)*. Common pattern thấy trong main_app/: 
   - Coupling cao giữa UI thread và camera read.
   - Không có ranh giới rõ giữa adapter (cv2) và logic.
   - Single process = 1 camera die kéo cả app.
   - Không bulkhead.

</details>

---

## Trade-offs

### "Vậy tôi không cần học microservices?"

KHÔNG nói vậy. Bạn cần học để **biết khi nào dùng**. Khi dự án scale lên 10+ team, 100M request, bạn sẽ cần.

→ Nguyên tắc: **học nhiều pattern, áp dụng đúng context**. Đừng vội áp dụng pattern "hot" vào context không phù hợp.

### "Tôi mới bắt đầu, làm sao biết context?"

Câu hỏi cụ thể giúp bạn:

1. **Quy mô hiện tại** (không phải tương lai)? Gấp ×2 trong 6 tháng tới — chấp nhận được. ×100 — KHÔNG.
2. **Pain point thật**? Không phải "có thể có". Pain hôm nay.
3. **Nếu chọn pattern X thì TRADE OFF gì**? List ra. Có chấp nhận được không?

### "Nhưng kiến trúc tốt phải scale được chứ?"

Có và không. **Modular monolith với good boundaries** scale tốt — có thể split ra microservices SAU khi pain xuất hiện. Vision Platform là ví dụ: thiết kế modular từ đầu, sau này tách process tương đối dễ.

→ Nguyên tắc: **build for today, design for tomorrow**. Build pattern đơn giản nhất giải quyết pain hôm nay, NHƯNG **đặt boundary đúng** để tomorrow refactor được.

---

## Liên kết

- Production: `Vision_platform_architecture_design/01-overview/03-deployment-modes.md` — 5 deployment mode khác nhau cho 5 context.
- Production: `Vision_platform_architecture_design/13-adr/` — mỗi ADR là 1 quyết định context-specific.
- Module 02 file 03 — `bulkhead-pattern.md` — concrete pattern phù hợp Vision Platform context.
- Sách: "Software Architecture: The Hard Parts" — Mark Richards. Nói về trade-off thực tế.

---

## Tóm tắt 1 câu

> **Không có "best architecture". Có "phù hợp với context X". Trước khi áp dụng pattern, đo context: scale, domain complexity, team size. Pattern hot có thể là sai cho dự án bạn.**

➡️ Tiếp theo: [`99-self-check.md`](99-self-check.md)
