# Hexagonal — POSA 5-box (đã điền)

> Bản chốt lý thuyết, rút từ `session.md`. Khung: `../02-pattern-template.md`.
> Đọc lại file này thay vì lội lại cả session.

## 1. Name
- **Tên chuẩn:** Hexagonal Architecture
- **Tên kỹ thuật đúng hơn:** Ports & Adapters
- **Tier:** Architectural pattern (xem `../architecture-taxonomy-map.md`)
- **Một câu:** Đặt business logic ở giữa; mọi I/O (DB, email, UI, file) đẩy ra
  rìa qua *interface (Port)*; thứ cụ thể (*Adapter*) cắm vào port. Đổi adapter
  không đụng logic.

## 2. Context + Forces
- **Context:** App có business logic đáng bảo vệ + phải nói chuyện với thế giới
  ngoài (DB, network, file...) — thứ hay đổi và khó test.
- **Forces (giằng nhau):**
  - Muốn test logic nhanh, không cần hạ tầng thật ↔ logic lại gọi thẳng hạ tầng.
  - Muốn đổi hạ tầng (SQL→Postgres) dễ ↔ logic đang dính cứng vào hạ tầng cụ thể.
  - Muốn ít file/đơn giản ↔ muốn tách tầng để bảo vệ logic.
- **What varies:** thứ ở "rìa" — DB, kênh gửi, UI. Cô lập nó sau một interface.

## 3. Problem
- **Triệu chứng:** business logic `new SqlConnection(...)` ngay trong method →
  không test được nếu thiếu SQL; đổi DB phải sửa vào tận logic.
- **Gốc:** mũi tên phụ thuộc sai chiều — cái *ổn định* (logic) phụ thuộc cái
  *hay đổi* (hạ tầng cụ thể).

## 4. Solution
- **Diagram (tầng code):**

  ```
  TRƯỚC:  OrderService ───────────► SqlConnection (cụ thể, hay đổi)

  SAU:    OrderService ──► IOrderRepository ◄── SqlOrderRepository  (adapter thật)
          (ổn định)         (Port)          ◄── FakeOrderRepository (adapter test)
                              ▲ cả hai phía trỏ VÀO interface
  ```

- **Port** = interface do phía Core định nghĩa (`IOrderRepository`).
- **Adapter** = class implement Port (SQL thật, Fake test, Postgres...). EF cũng
  chỉ là *một* adapter.
- **Driving vs Driven (hai phía của lục giác — KHÔNG chỉ một phía):**

  ```
  DRIVING side (gọi VÀO)        CORE             DRIVEN side (Core gọi RA)
  RestController ─┐                                   ┌─► SqlOrderRepository
  CliCommand    ─┼─► ICheckoutUseCase ► OrderService ►IOrderRepository┤
  TestRunner    ─┘   (driving port)     (logic)       (driven port)   └─► FakeOrderRepository
  ```

  | | Driving port (`ICheckoutUseCase`) | Driven port (`IOrderRepository`) |
  |---|---|---|
  | Định nghĩa ở | **Core** | **Core** |
  | Core làm gì | **implement** (chính OrderService) | **gọi** (.Save()) |
  | Bên ngoài làm gì | **gọi** (controller gọi vào) | **implement** (SQL/Fake) |
  | Adapter loại | driving adapter (web, CLI, test) | driven adapter (SQL, email, file) |

  Mẹo nhớ theo chữ **DRIVE (lái)**: *Driving* = lái app từ ngoài → Core bị gọi →
  Core **implement** để có thân bị gọi. *Driven* = app lái ra ngoài → Core gọi
  đi → thứ ngoài **implement**.
  → Cái RIÊNG của Hexagonal so với "Layered có interface": **cả hai phía đều là
  port + adapter, app ngồi giữa, không trỏ ra phía nào.** Đổi web↔CLI (trái) hay
  SQL↔file (phải) đều không đụng Core.

- **Dependency Injection:** Core KHÔNG tự `new` adapter; nhận qua constructor.
  Nơi ráp nối = *Composition Root* (học sau).
- **Ép bằng compiler (quan trọng nhất):** tách 2 project.
  `Shop.Sql.csproj ──reference──► Shop.Core.csproj`. Core KHÔNG reference Sql.
  Interface **phải nằm ở Core**. Lỡ `new SqlOrderRepository()` trong Core →
  compiler báo đỏ. Hướng phụ thuộc được *vật lý hóa* bằng project reference.

- **Bản C# tối giản (intent over ceremony):**

  ```csharp
  // Shop.Core
  public interface IOrderRepository { void Save(Order o); }

  public class OrderService
  {
      private readonly IOrderRepository _repo;
      public OrderService(IOrderRepository repo) => _repo = repo;
      public void Checkout(Order order)
      {
          decimal total = order.Items.Sum(i => i.Price * i.Qty); // logic thuần
          _repo.Save(order with { Total = total });               // I/O qua port
      }
  }

  // Shop.Sql  (reference Shop.Core)
  public class SqlOrderRepository : IOrderRepository { /* ADO/EF thật */ }
  ```

## 5. Consequences
- **Lợi:** test logic không cần hạ tầng (dùng Fake adapter); đổi hạ tầng không
  sửa logic; ranh giới rõ; ép được bằng compiler.
- **Hại / cái giá:**
  - **Indirection cost** — nhiều file/tầng hơn; người đọc phải nhảy qua nhiều
    file để lần một luồng.
  - **KHÔNG phải hiệu năng** — virtual call qua interface gần như 0 chi phí ở
    tầng nghiệp vụ. Đừng dùng hiệu năng làm lý do chê (hiểu lầm phổ biến).
  - **Over-engineering** nếu "what varies" = không có gì.
- **Khi nào KHÔNG dùng:**
  - Script/tool nhỏ dùng một lần, không có logic đáng bảo vệ.
  - CRUD mỏng gần như không nghiệp vụ — port chỉ là tầng rỗng.
  - Cái ở rìa chắc chắn 1 implement, không đổi, không cần mock.
  - Prototype cần ra nhanh → viết thẳng rồi *refactor to pattern* sau.
  - **Quy tắc:** đáng giá khi *có logic đáng bảo vệ* + *rìa sẽ đổi hoặc cần test*.
    Thiếu cả hai → over-engineering.

## Câu hỏi chẩn đoán (DIAGNOSTIC QUESTIONS — dùng mỗi khi gặp tình huống)

> Bộ câu hỏi thực chiến cho Hexagonal. Gặp một class/đoạn code, hỏi tuần tự.
> Hai câu gốc cho MỌI pattern ở `../00-READ-FIRST.md`: *What varies?* và
> *Which way do dependencies point?*

**Nhóm A — CÓ NÊN dùng không? (sàng lọc trước)**
1. Class này có **business logic đáng bảo vệ** không? (không chỉ CRUD đẩy dữ liệu)
2. Cái ở "rìa" (DB, email, file, API) có **varies** không — sẽ đổi, hoặc cần
   nhiều implement (thật + giả để test)?
3. Có cần **test logic mà không cần hạ tầng thật** không?
   → Cả 3 đều "không" → KHÔNG dùng (over-engineering). Có ≥1 "có" → cân nhắc dùng.

**Nhóm B — ÁP THẾ NÀO? (sau khi quyết dùng)**
4. **What varies** ở đây là gì? → đó là thứ cần giấu sau Port.
5. Port đặt tên theo **ý định nghiệp vụ** hay theo công nghệ? (phải theo nghiệp
   vụ: `IInvoiceDelivery`, không phải `IPrinter`).
6. **Mũi tên** sau khi tách: Core còn trỏ ra hạ tầng cụ thể không? (phải KHÔNG).
7. Interface đặt ở **project nào**? (phải ở Core; hạ tầng reference Core, không
   ngược lại).
8. Core có tự `new` adapter không? (phải KHÔNG — nhận qua constructor / DI).

**Câu khóa quyết định:**
> "Có nên dùng pattern không?" = "Có **lực (force)** nào đang giằng nhau mà
> pattern này gỡ được không?" — Không lực → không pattern.

## Dấu hiệu NHẬN BIẾT vi phạm (Recognize — đọc code lạ)

> Năng lực khó nhất: nhìn code lạ mà *ngửi* ra chỗ sai, dù nó núp dưới vỏ nào
> (SQL, mail, file, HTTP...). Cùng một bệnh, khác lớp sơn.

**Smell chính:** trong một class business logic (Core) xuất hiện `new <hạ tầng
cụ thể>` hoặc gọi thẳng API hạ tầng:
- `new SqlConnection(...)`, `new SmtpClient(...)`, `new HttpClient(...)`
- `File.*`, `Directory.*`, `DateTime.Now`, `Console.*`, `Environment.*`
- → Core đang trỏ mũi tên ra hạ tầng → vi phạm.

**Phép thử quyết định (đắt nhất — Turn 15):**
> "Test logic được không?" KHÔNG hỏi *"logic có đúng không"* mà hỏi
> **"chạy logic có kéo theo I/O thật không?"**
> Nếu chạy 1 hàm logic mà nó mở mạng / ghi file / gửi mail thật → side-effect
> đang trộn trong logic → CHƯA test cô lập được → vi phạm Hexagonal.

**Bẫy hay trượt:** thấy "code vẫn chạy được / vẫn test được bình thường" rồi cho
là ổn. Sai — nó *chạy* được nhưng *không test cô lập* được, và mỗi lần test lại
gửi mail thật / ghi rác file. "Chạy được" ≠ "test được".

## Self-location
- **Level đạt:** 4 — Master (driven side vững; driving side đã nắm; Recognize
  đạt mức Use→Master qua 1 bài săn lỗi).
- **Còn lại:** Level 5 (đọc hệ thống lạ, chọn giữa nhiều phương án) — để dành
  tới khi có thêm pattern khác để so sánh.
- **Mốc ôn:** 1 ngày → vẽ lại diagram (cả 2 phía) + nói vì sao interface ở Core |
  1 tuần → tự áp vào 1 domain mới | 1 tháng → đọc 1 codebase lạ, chỉ chỗ
  thiếu/thừa port + áp phép thử "chạy logic có kéo theo I/O thật không".

## Sources
- Alistair Cockburn, "Hexagonal Architecture / Ports and Adapters" (2005).
- Gốc khái niệm "what varies": GoF (1994) + *Head First Design Patterns* (2004).
- Bản thân session học: `./session.md`.
