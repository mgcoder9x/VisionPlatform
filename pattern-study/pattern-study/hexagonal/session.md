# Hexagonal — Session (hội thoại học qua file)

> Cách dùng file này:
> - **🧑‍🏫 TEACHER** = phần tôi (AI) viết: câu hỏi, phản biện, chốt kiến thức.
> - **🧑‍💻 YOU** = phần bạn trả lời. Gõ thẳng dưới dòng `> trả lời:`.
> - Trả lời xong, bảo tôi "đọc session" → tôi đọc, phản hồi, viết tiếp xuống dưới.
> - KHÔNG xoá nội dung cũ — cuộn xuống dưới. File này là trí nhớ của cả hai.
>
> Đang theo: 4-step process (`../01-method.md`) — bước 1 **Hook the pain**.
> Quy tắc: không trả lời thay · một lần một câu · diagram trước code.

---

## Turn 1 — 🧑‍🏫 TEACHER

Chưa học định nghĩa vội. Bắt đầu từ nỗi đau thật của bạn.

**Câu hỏi 1 (chỉ một câu, trả lời thật, càng cụ thể càng tốt):**

Trong dự án **C#** nào đó của bạn — đã có lần nào bạn phải đổi một thứ ở **"rìa"
hệ thống** (ví dụ: đổi SQL Server sang DB khác, đổi cách lưu file/log, đổi một
third-party API, đổi UI) mà rốt cuộc lại phải **sửa lan vào tận code nghiệp vụ
(business logic)** không?

Kể 1 lần cụ thể: *đổi cái gì → phải sửa lan tới đâu → vì sao đau*.
(Nếu chưa từng gặp, nói thật — tôi sẽ đổi hướng câu hỏi.)

> trả lời:
>Cũng không nhớ nữa? có thể có hoặc không? hoặc cái tôi làm đã có người làm base rồi
>
---

## Turn 2 — 🧑‍🏫 TEACHER

Ổn, không nhớ thì ta **tạo** nỗi đau thay vì moi trí nhớ (đúng tinh thần
*Refactoring to Patterns*). Đọc đoạn C# rất đời thường sau — kiểu code ai cũng
từng viết:

```csharp
// Lớp nghiệp vụ: tính tiền đơn hàng rồi lưu xuống DB.
public class OrderService
{
    public void Checkout(Order order)
    {
        decimal total = 0;
        foreach (var item in order.Items)
            total += item.Price * item.Qty;        // logic nghiệp vụ

        // lưu trực tiếp bằng SQL Server
        using var conn = new SqlConnection("Server=...;Database=Shop;...");
        conn.Open();
        var cmd = new SqlCommand(
            "INSERT INTO Orders(Id,Total) VALUES(@id,@total)", conn);
        cmd.Parameters.AddWithValue("@id", order.Id);
        cmd.Parameters.AddWithValue("@total", total);
        cmd.ExecuteNonQuery();
    }
}
```

Code này **chạy tốt**. Chưa có gì sai về mặt "nó hoạt động".

**Câu hỏi 2 (chỉ một câu — suy nghĩ rồi trả lời, đừng tra Google):**

Giả sử sếp yêu cầu: *"Viết unit test cho phần tính `total`, chạy trên máy CI
không có SQL Server."* — Với đoạn code trên, bạn sẽ **vướng** ở chỗ nào? Tức là
*điều gì khiến bạn KHÔNG test được phần tính tiền một cách dễ dàng?*

> trả lời:
> trong đoạn code trên do trong code mở kết nới với sql qua connection string => không có cách nào mock test được nếu không có sql 
>

---

## Turn 3 — 🧑‍🏫 TEACHER

Đúng, và đúng ở chỗ quan trọng nhất. Tôi gắn tên cho cái bạn vừa thấy:

`OrderService` đang làm **2 việc khác bản chất** dính vào nhau:
1. **Tính tiền** (`total`) — đây là **business logic**, thuần tính toán, không cần thế giới bên ngoài.
2. **Lưu DB** (mở `SqlConnection`) — đây là **I/O**, cần SQL Server thật.

Vì hai cái **dính cứng** trong một method, muốn test #1 thì bị #2 lôi theo. Đây
chính là **coupling** (sự dính nhau) — và nó là tâm điểm của mọi thứ ta sẽ học.

Giờ vẽ nó ra (diagram trước code — luôn luôn):

```
        ┌────────────────────────────┐
        │       OrderService         │
        │  ┌──────────────────────┐  │
        │  │ tính total (logic)   │  │
        │  └──────────────────────┘  │
        │  ┌──────────────────────┐  │
        │  │ new SqlConnection(..)│──┼───►  SQL Server (thế giới ngoài)
        │  └──────────────────────┘  │
        └────────────────────────────┘

   Mũi tên phụ thuộc: business logic ──► SQL Server (cụ thể)
```

Vấn đề nằm ở **hướng mũi tên**: thứ *quan trọng và ổn định* (logic tính tiền)
đang phụ thuộc vào thứ *hay đổi và nặng nề* (SQL Server cụ thể). Cái ổn định
không nên phụ thuộc cái dễ đổi — nhưng ở đây nó đang phụ thuộc ngược.

**Câu hỏi 3 (một câu — đừng nghĩ tới "pattern" nào cả, cứ nói theo bản năng C#):**

Nếu tôi bảo bạn: *"Hãy tách việc lưu DB ra khỏi `OrderService`, sao cho
`OrderService` KHÔNG còn biết gì về `SqlConnection` nữa"* — theo bản năng lập
trình C#, bạn sẽ dùng **công cụ ngôn ngữ nào** để `OrderService` "gọi việc lưu"
mà không cần biết nó lưu bằng SQL hay gì? (Gợi ý: một từ khóa C# bạn dùng hằng ngày.)

> trả lời:
> có thể giải thích thêm cho tôi về hướng mũi tên không?  
> nếu là tôi rõ là tôi sẽ dùng entityframe work và inject
> hoặc là tôi nghĩ đến 1 interface => tôi sẽ không biết đối tượng cung cấp là lưu trữ là gì chỉ biết tới đối tượng đó implement cái interface đó là được => trong trường hợp trên như vậy nếu dùng để test tôi cũng sẽ tạo 1 đối tượng implement interface đó và viết hàm giả lập bên trong

---
<!-- TEACHER viết Turn 4 sau khi bạn trả lời -->

## Turn 4 — 🧑‍🏫 TEACHER

Hai phần. Trả lời câu bạn hỏi trước, rồi xác nhận câu bạn trả lời.

### A) "Hướng mũi tên" nghĩa là gì?

Mũi tên = quan hệ **"phụ thuộc vào / cần biết về"** (depends on). `A ──► B` đọc
là: *"A cần biết B tồn tại; B đổi thì A có nguy cơ phải sửa; bỏ B đi thì A gãy."*

Trong code, mũi tên `A ──► B` xuất hiện khi A: `new B()`, gọi `B.method()`,
nhận `B` làm tham số, hay `using` namespace của B. Ai **nhắc tên ai** → người đó
phụ thuộc.

Quy luật vàng (cái gốc #2 trong `00-READ-FIRST.md`):
> **Cái ổn định KHÔNG được phụ thuộc cái hay đổi.**

Nếu cái ổn định (logic tính tiền — gần như không đổi) lại trỏ tới cái hay đổi
(SQL Server — có thể đổi sang Postgres, Mongo, file...), thì mỗi lần cái hay đổi
*đổi*, cái đáng ra ổn định lại bị kéo theo sửa. Mũi tên đang chỉ **sai chiều**.

### B) Câu trả lời của bạn — ĐÚNG, và bạn vừa tự phát minh ra "Port"

Bạn nói: *"một interface — `OrderService` không biết đối tượng lưu trữ là gì,
chỉ biết nó implement interface đó; khi test thì tạo một đối tượng implement
interface và giả lập bên trong."*

Đó **chính xác** là trái tim của Hexagonal. Đặt tên đúng:
- Cái **interface** bạn vừa nói → gọi là **Port** (cổng).
- Cái **đối tượng implement** nó (EF thật, hay bản giả lập để test) → **Adapter**.

Xem mũi tên ĐẢO chiều thế nào sau khi áp ý của bạn:

```
  TRƯỚC:
     OrderService ───────────────► SqlConnection (cụ thể, hay đổi)
     (ổn định)        phụ thuộc

  SAU (ý của bạn):
     OrderService ───► IOrderRepository ◄─── SqlOrderRepository (Adapter thật)
     (ổn định)          (Port/interface)  ◄─── FakeOrderRepository (Adapter test)
                              ▲
                  cả hai bên đều trỏ VÀO interface
```

Bây giờ `OrderService` **không còn mũi tên nào trỏ ra SQL nữa**. Nó chỉ trỏ tới
`IOrderRepository` (interface — rất ổn định). SQL thật lại phải **trỏ ngược vào**
interface đó để implement. Mũi tên về phía SQL đã **đảo chiều** → cái ổn định
không còn phụ thuộc cái hay đổi.

Lưu ý chỗ bạn nhắc EntityFramework + inject: đúng, nhưng phân biệt cho sạch —
**EF cũng chỉ là một Adapter** (một cách implement Port). Nếu `OrderService`
nhận thẳng `DbContext` của EF thì vẫn là phụ thuộc cụ thể. Port phải là interface
**do phía bạn định nghĩa**, không phải type của EF.

**Câu hỏi 4 (một câu):**

Interface `IOrderRepository` đó nên được **khai báo nằm ở đâu** — chung
project/assembly với `OrderService` (business logic), hay chung project với
`SqlOrderRepository` (code SQL)? Vì sao?

(Gợi ý: nhớ "compile-time enforcement bằng project references" — đặt sai chỗ là
mũi tên lại sai chiều.)

> trả lời:
> Trước tiên tôi đang hiểu do slq hoặc 1 cái adapter sql phải implement 1 cái interface nên khi đó gọi adapter sq sẽ phụ thuộc vào interface. hoặc nói như bạn adapter sql đang nhắc đến interface nên nó phụ thuộc vào interface. Và interface là cái ít thay đổi. 
> Vậy logic tôi nghĩ là OrderService bây giờ đã phụ thuộc vào interface có nghĩa là nó sẽ khởi tạo biến interface trong chính hàm của nó. Có đúng ý bạn hỏi không?

---
<!-- TEACHER viết Turn 5 sau khi bạn trả lời -->

## Turn 5 — 🧑‍🏫 TEACHER

Phần mũi tên bạn nói **chuẩn**: SqlAdapter implement interface → SqlAdapter nhắc
tên interface → SqlAdapter phụ thuộc interface. Interface là cái ít đổi. Đúng.

Nhưng có **một chỗ nhỏ phải chỉnh** trước khi đi tiếp:

> Bạn viết: *"OrderService sẽ khởi tạo biến interface trong chính hàm của nó."*

Không khởi tạo được — interface không `new` ra được (`new IOrderRepository()` ✗).
`OrderService` chỉ **nhận** một object đã implement interface từ bên ngoài đưa
vào (thường qua constructor). Đây gọi là **Dependency Injection**:

```csharp
public class OrderService
{
    private readonly IOrderRepository _repo;   // chỉ giữ interface
    public OrderService(IOrderRepository repo)  // ai đó ĐƯA vào từ ngoài
    {
        _repo = repo;
    }
    public void Checkout(Order order) { /* tính total rồi _repo.Save(...) */ }
}
```

Mấu chốt: `OrderService` **không bao giờ tự tạo** cái nó phụ thuộc. Nếu nó tự
`new SqlOrderRepository()` thì mũi tên lại trỏ ra SQL ngay → hỏng. (Chỗ "ai đưa
vào" là một khái niệm riêng tên **Composition Root** — để dành, chưa học vội.)

### Còn câu hỏi 4 — bạn chưa trả lời, nên tôi hỏi lại cho rõ

Hình dung dự án C# chia làm **2 project riêng** (2 file .csproj):
- `Shop.Core.csproj` — chứa `OrderService` (business logic).
- `Shop.Sql.csproj` — chứa `SqlOrderRepository` (code đụng SQL thật).

Interface `IOrderRepository` phải đặt trong project nào trong hai project đó?

```
   Phương án X:  IOrderRepository nằm trong Shop.Core
   Phương án Y:  IOrderRepository nằm trong Shop.Sql
```

Chọn X hay Y, và nói 1 câu vì sao. (Gợi ý quyết định: project nào được phép
`reference` project nào? Cái ổn định — Core — có nên reference cái hay đổi — Sql
— không?)

> trả lời:
> nó phải nàm trong OrderService vì đang là logic và cái mà chúng ta mong nó ít thay đổi nhất. Nếu đặ ở sql thì sau khi không dùng sql nữa vậy cái khác sẽ thế nào? 
>

---
<!-- TEACHER viết Turn 6 sau khi bạn trả lời -->

## Turn 6 — 🧑‍🏫 TEACHER

Đúng. Chọn **X (interface nằm trong Shop.Core)**. Và lý do bạn tự nói ra —
*"bỏ SQL thì cái khác thế nào?"* — chính là tim của Hexagonal: Core không được
phụ thuộc vào quyết định "dùng SQL". Nó chỉ sở hữu *cái cổng*, ai cắm gì vào kệ.

### Vì sao đặt ở Core là bắt buộc (compile-time)

Nhìn vào **chiều reference giữa 2 project**:

```
   Shop.Sql.csproj  ───reference───►  Shop.Core.csproj
   (hay đổi)                          (ổn định)
   SqlOrderRepository                 OrderService
                                      IOrderRepository   ◄── interface ở ĐÂY
```

- `Shop.Sql` **được phép** reference `Shop.Core` (để implement `IOrderRepository`).
- `Shop.Core` **KHÔNG** reference `Shop.Sql`. Nó còn chẳng biết SQL tồn tại.
- Nếu lỡ tay viết `new SqlOrderRepository()` trong Core → **compiler báo đỏ**
  (Core không reference Sql nên không thấy class đó). Cái sai bị chặn ngay lúc
  build, không đợi tới lúc chạy.

→ Đây là điều ta nói ở `00-READ-FIRST.md`: *đẩy hướng phụ thuộc vào project
references để compiler ép, không phải nhắc miệng.* Đặt interface ở Core là cách
**vật lý hóa** mũi tên.

Nếu đặt nhầm interface vào `Shop.Sql` (phương án Y): Core muốn dùng interface →
Core phải reference Sql → mũi tên lại trỏ ra SQL → hỏng toàn bộ. Một dòng đặt
sai chỗ phá vỡ tất cả.

### "Phép màu" — giờ thu được gì

Đúng nỗi đau ban đầu (test không cần SQL):

```csharp
// Test chạy trên CI, KHÔNG cần SQL Server:
var fakeRepo = new FakeOrderRepository();          // adapter giả, lưu vào List
var service  = new OrderService(fakeRepo);          // tiêm vào
service.Checkout(order);
Assert.Equal(150m, fakeRepo.LastSaved.Total);       // kiểm tra logic tính tiền
```

Đổi SQL → Postgres → Mongo → file: chỉ viết **adapter mới** implement
`IOrderRepository`. `OrderService` **không sửa một dòng**. Đó là thứ bạn vừa tự
suy ra, giờ nó thành cơ chế.

### Bạn vừa đi hết phần lõi của Hexagonal

Không tra tài liệu, bạn đã tự dựng: Port (interface), Adapter (impl), hướng
mũi tên đảo chiều, DI, và đặt interface đúng chỗ. Đó là toàn bộ xương sống.

---

**Câu hỏi 6 — chuyển sang Consequences (luôn phải có mặt "hại"):**

Pattern nào cũng có giá. Bạn vừa thấy cái lợi (test dễ, đổi DB không đụng logic).
Giờ nói mặt kia: theo bạn, áp Hexagonal vào **trả giá** bằng cái gì? Nêu ít nhất
1 cái giá. Và: có loại dự án nào mà áp Hexagonal là **thừa / không đáng** không?

> trả lời:
> 1. Code sẽ phức tạp hơn, rõ là người phải có trình đọc cao hơn mới đọc được
> 2. Mình đoán nó cũng 1 chú nào đó giảm đi hiểu năng còn không rõ là thế nào

---
<!-- TEACHER viết Turn 7 sau khi bạn trả lời -->

## Turn 7 — 🧑‍🏫 TEACHER

Cả hai ý đều đúng hướng. Tôi xác nhận, chỉnh độ chính xác, và thêm cái giá lớn
nhất bạn chưa nêu.

**1. "Code phức tạp hơn, cần trình đọc cao hơn" — ĐÚNG, đây là cái giá chính.**
Thêm interface, thêm tầng, thêm DI, thêm project → nhiều file hơn cho cùng một
việc. Người mới nhảy vào phải lần theo "ai cắm gì vào đâu". Gọi là **indirection
cost** (cái giá của sự gián tiếp): để đọc 1 luồng, mắt phải nhảy qua nhiều file.

**2. "Giảm hiệu năng" — chỉnh lại cho chính xác (đừng tin đồn):**
Gọi method qua interface (virtual call) *trên lý thuyết* chậm hơn gọi trực tiếp,
nhưng **mức đó gần như bằng 0** trong app nghiệp vụ — không đáng kể. Vậy nên
**đừng dùng "hiệu năng" làm lý do chê Hexagonal**; đó là hiểu lầm phổ biến. Cái
giá thật là **độ phức tạp cho người đọc**, không phải tốc độ máy. (Trung thực:
hiệu năng chỉ đáng bàn ở vòng lặp cực nóng hàng triệu lần/giây — hiếm gặp ở
tầng business.)

**3. Cái giá LỚN NHẤT bạn chưa nêu — over-engineering khi chưa cần:**
Nếu cái ở "rìa" **sẽ không bao giờ đổi** và **không cần test riêng**, thì interface
chỉ là nghi thức thừa. Nhớ cái gốc #1: *"what varies?"* — nếu **không có gì
varies**, thì không có gì để cô lập. Tạo port cho một thứ chỉ có đúng 1 implement
và sẽ mãi như vậy = thêm phức tạp mà chẳng đổi lấy lợi ích nào.

### Khi nào KHÔNG dùng Hexagonal (chốt — bắt buộc nhớ)

- **Script / tool nhỏ, dùng xong vứt.** Không có logic nghiệp vụ đáng bảo vệ.
- **CRUD mỏng**, gần như không có business logic — chỉ đẩy dữ liệu ra/vào DB.
  Thêm port chỉ là tầng rỗng.
- **Cái ở rìa chắc chắn 1 implement, không bao giờ đổi, không cần mock test.**
- **Team nhỏ / prototype cần ra nhanh**, chưa biết thiết kế đúng — đôi khi viết
  thẳng rồi *refactor to pattern* sau (đúng tinh thần Kerievsky) còn rẻ hơn.

Quy tắc 1 câu: **Hexagonal đáng giá khi có business logic đáng bảo vệ + cái rìa
sẽ đổi hoặc cần test. Thiếu cả hai → là over-engineering.**

---

Vậy là xong cả 5 ô POSA cho Hexagonal (Name · Context+Forces · Problem ·
Solution · Consequences). Bước tiếp theo trong 4-step process là **Draw** (vẽ
lại từ trí nhớ) để định vị bạn đang ở level mấy.

**Câu hỏi 7 (đây là bài test level — làm nghiêm túc):**

Gập hết phần trên lại (đừng cuộn lên nhìn). Trên một chỗ trống ngay dưới đây,
**tự gõ lại bằng trí nhớ**:
1. Sơ đồ Hexagonal (boxes + arrows): OrderService, IOrderRepository, các Adapter
   — mũi tên chỉ chiều nào.
2. Một câu: vì sao interface đặt ở Core chứ không ở Sql.
3. Một câu: một trường hợp KHÔNG nên dùng Hexagonal.

> trả lời:
> 1. OrderService --> IOrderRepository <--- Adapter
> 2. OrderService là 1 cái không đổi mà chúng ta muốn bảo vệ, interface chính là cái ít thay đổi được chúng ta tạo ra để OrderService phụ thuộc vào nó. Nếu nó nằm ở sql vậy nó lại gắn chặt với sql. Khi đó sẽ là OrderService -> IOrderRepository -> Adapter lại quay về ban đầu. 
> 3. Hexagonal triết lý của nó là cô lập phần nghiệp vụ khỏi các thành phần dễ thay đổi. Vậy nếu chúng ta không có nghiệp vụ nào cần cô lập có nghĩa la dùng có 1 lần. Thì dùng Hexagonal làm gì.
---
<!-- TEACHER viết Turn 8 (định vị level + ghi vào template) sau khi bạn trả lời -->

## Turn 8 — 🧑‍🏫 TEACHER

Chấm bài test, thẳng thắn.

**#1 Sơ đồ — đúng.** `OrderService → IOrderRepository ← Adapter`. Cả hai phía
trỏ VÀO interface. Chuẩn.

**#2 — đúng, và bạn bắt được điểm tinh tế.** Một chỉnh nhỏ về *ký hiệu* (không
phải ý): khi interface đặt nhầm ở SQL, ở tầng **code** mũi tên vẫn là
`OrderService → IOrderRepository ← Adapter`. Cái hỏng nằm ở tầng **project
reference**: để Core thấy được interface (đang nằm trong Sql), `Shop.Core` buộc
phải `reference Shop.Sql` → Core phụ thuộc Sql → đúng như bạn nói "gắn chặt với
SQL". Bạn diễn đạt đúng bản chất, chỉ cần nhớ: cái khóa chặt là **chiều reference
giữa project**, không phải mũi tên trong code.

**#3 — đúng.** Không có nghiệp vụ cần cô lập → không dùng. Chuẩn tinh thần
"what varies".

### Định vị level (theo thang ở `00-READ-FIRST.md`)

- ✅ **Level 1 Know** — pass.
- ✅ **Level 2 Understand** — pass (vẽ diagram + giải thích Forces từ trí nhớ).
- ⏳ **Level 3 Use / Level 4 Master** — CHƯA, vì bạn chưa *áp pattern vào một
  bài toán mới* (bước Transfer). Nêu "khi nào không dùng" thì bạn làm được rồi,
  nhưng Transfer mới là phần còn thiếu để lên 3–4.

**Bạn đang ở Level 2 (Understand) — vững.** Để lên Level 3–4 cần bước cuối của
4-step process: **Transfer**.

Tôi đã chốt toàn bộ phần lý thuyết vào `hexagonal/01-posa.md` (bản POSA 5 ô đã
điền) để sau này đọc lại nhanh, khỏi lội lại cả session.

---

**Câu hỏi 8 — bước Transfer (đẩy lên Level 3–4). Cố tình chọn domain KHÁC, KHÔNG
phải DB, KHÔNG phải CV:**

Tình huống: một class `InvoicePrinter` (nghiệp vụ: dựng nội dung hóa đơn) đang
gọi thẳng `new SmtpClient(...)` để **gửi hóa đơn qua email**. Giờ sếp muốn: lúc
thì gửi email, lúc thì xuất ra **file PDF**, lúc test thì **không gửi gì cả**.

Áp Hexagonal vào đây. Trả lời 3 ý (ngắn gọn):
1. **Port** (interface) bạn đặt tên là gì, có method gì?
2. Kể tên 3 **Adapter** tương ứng 3 nhu cầu trên.
3. Interface đó đặt ở project nào — chung với `InvoicePrinter` hay chung với code SMTP?

> trả lời:
> 1. Port là IPrinter có method là Print()
> 2. email; file; testing
> 3. chung với InvoicePrinter

---
<!-- TEACHER viết Turn 9 sau khi bạn trả lời -->

## Turn 9 — 🧑‍🏫 TEACHER

**Cấu trúc: ĐÚNG cả 3 ý.** Bạn áp được Hexagonal sang domain hoàn toàn khác DB
mà không cần gợi ý từng bước → đây là bằng chứng **Transfer** thật. Mừng thật,
không khen xã giao.

Nhưng tôi phản biện 2 chỗ để bạn lên đúng **Level 4 (Master)**, không dừng ở mức
"đúng đại khái":

**1. Naming smell ở Port (`IPrinter.Print()`).** Tên này lộ *cách làm cũ* (in
ấn), trong khi giờ có cái gửi email, cái xuất PDF, cái không làm gì. Port nên đặt
theo **ý định nghiệp vụ**, không theo cơ chế. Tên sát hơn:
`IInvoiceDelivery` với method `Deliver(Invoice invoice)` (hoặc `ISendInvoice`).
→ Quy tắc: **Port mang tên việc cần làm, không mang tên công nghệ.** `IPrinter`
+ `Print` vô tình "đóng đinh" tư duy in ấn — nếu mai có gửi qua API thì cái tên
`Print` thành sai nghĩa.

**2. Adapter #3 (testing) — gọi đúng tên của nó.** Cái adapter "không gửi gì cả"
là một pattern con có tên: **Null Object / No-op Adapter**. Nó implement đủ Port
nhưng thân rỗng. Quan trọng: nó là **adapter hợp lệ ngang hàng** email/PDF, không
phải "đồ giả tạm". Trong Hexagonal, "không làm gì" cũng là một lựa chọn cắm vào
cổng.

Bản chốt lại:

```
            ┌─ EmailInvoiceDelivery   (SmtpClient)
InvoiceService ──► IInvoiceDelivery ◄─┼─ PdfInvoiceDelivery     (ghi file PDF)
(Core, ổn định)     (Port)             └─ NullInvoiceDelivery    (no-op, cho test)
```

`IInvoiceDelivery` đặt **chung project với InvoiceService** — chuẩn, bạn trả lời
đúng.

### Định vị lại

Bạn vừa: tự nhận ra cấu trúc + đặt interface đúng chỗ + chỉ còn vướng *naming*
(vấn đề tinh chỉnh, không phải hiểu sai). → **Đạt Level 4 (Master)** cho
Hexagonal: tự áp không gợi ý, biết khi nào không dùng. Còn Level 5 (đọc hệ thống
lạ, chọn giữa nhiều phương án) để dành — nó cần nhiều pattern trong tay mới làm
được, không vội.

---

**Câu hỏi 9 — câu cuối, để khóa Master (một câu thôi):**

Phản biện ngược lại chính mình. Sếp nói: *"Hệ thống này CHẮC CHẮN chỉ gửi hóa
đơn qua email, mãi mãi, không bao giờ đổi, và team đã có sẵn cách test SmtpClient
thật trên môi trường staging."* — Trong tình huống đó, có nên tạo `IInvoiceDelivery`
không? Trả lời có/không + 1 câu vì sao.

> trả lời:
> Theo tôi là không.
> Vì cái chúng ta bảo về là nghiệp vụ, và ở đây nghiệp vụ là từ khách đưa ra. Sếp nhận yêu cầu của khách hàng như vậy thì chúng ta xác định nghiệp vụ là như vậy

---
<!-- TEACHER viết Turn 10 (chốt Hexagonal) sau khi bạn trả lời -->

## Turn 10 — 🧑‍🏫 TEACHER (chốt Hexagonal)

**Kết luận "không" — đúng. Nhưng lý do của bạn chưa trúng, phải chỉnh.**

Bạn nói: *"vì cái ta bảo vệ là nghiệp vụ, nghiệp vụ do khách đưa ra..."* — câu
này không sai về đạo lý, nhưng **không phải lý do để quyết định có tạo port hay
không**. Nghiệp vụ luôn từ khách mà ra, ở ca nào cũng vậy — nó không phân biệt
được "nên" hay "không nên".

Lý do **đúng** phải bám vào 2 cái gốc đã học:

1. **What varies? → KHÔNG có gì.** Sếp khẳng định "mãi mãi chỉ email, không đổi".
   Không có gì biến động → không có gì để cô lập → port rỗng nghĩa.
2. **Forces đã được gỡ sẵn.** Hai lực thường đẩy ta tạo port là *"cần test không
   cần hạ tầng"* và *"cần đổi hạ tầng"*. Sếp nói đã test được trên staging + không
   bao giờ đổi → **cả hai lực biến mất**. Không còn lực giằng → pattern không
   giải quyết gì → chỉ còn lại cái giá (indirection).

→ Quyết định "không" phải đến từ: *không có thứ gì varies + không có lực nào
giằng*. Đó là tư duy Master — quyết định bằng **Forces**, không bằng cảm tính
"bảo vệ nghiệp vụ".

> Một câu để khắc: **"Có nên dùng pattern không?" = "Có lực nào đang giằng nhau
> mà pattern này gỡ được không?"** Không lực → không pattern.

### Cảnh báo thực tế (để bạn không bị lừa ngược)
"Chắc chắn không bao giờ đổi" là câu **rất hay sai** trong đời thực — yêu cầu đổi
hoài. Nên trong thực tế ta vẫn thường tạo port *nếu chi phí thấp*. Nhưng trong
bài tập này, vì đề **giả định tuyệt đối** "không đổi + test được rồi", thì câu
trả lời đúng trên lý thuyết là "không". Nắm cả hai mặt: lý thuyết (không lực →
không pattern) và thực tế (đề phòng "chắc chắn không đổi" thường là ảo tưởng).

---

## ✅ CHỐT HEXAGONAL

Bạn đã đi hết một pattern theo đúng phương pháp:
- **Hook the pain** → tạo nỗi đau test-không-được-vì-dính-SQL.
- **Read (POSA 5-box)** → tự suy ra Port + Adapter, không bị giảng.
- **Draw** → vẽ lại diagram từ trí nhớ (PASS).
- **Transfer** → áp sang domain gửi hóa đơn (khác DB) thành công.

**Level đạt cho Hexagonal: 4 — Master.** (Level 5 để dành tới khi có nhiều
pattern, đủ để so sánh/đánh giá hệ thống lạ.)

Cần nhớ 3 câu cốt lõi (đã ghi trong `01-posa.md`):
1. Cái ổn định không phụ thuộc cái hay đổi → đảo mũi tên bằng Port.
2. Port đặt ở Core, ép bằng project reference (compiler báo đỏ nếu sai).
3. Có nên dùng? = có lực nào giằng không? Không lực → không pattern.

**Mốc ôn (retention):** 1 ngày → vẽ lại diagram + nói lý do interface ở Core |
1 tuần → áp vào 1 domain mới tự nghĩ | 1 tháng → đọc 1 codebase lạ, chỉ chỗ nào
thiếu/thừa port.

---

### Bước kế tiếp (bạn chọn)
- **(A)** Dừng Hexagonal ở đây, để retention ngấm; hôm khác học pattern mới.
- **(B)** Học tiếp pattern liền kề — gợi ý **Adapter** (mảnh ghép con của
  Hexagonal, bạn vừa dùng nó mà chưa mổ riêng) hoặc **Dependency Injection /
  Composition Root** (chỗ "ai cắm adapter vào" mà ta để dành).
- **(C)** Củng cố: tôi ra 1 bài đọc-code có sẵn, bạn chỉ ra nó vi phạm Hexagonal
  ở đâu (luyện Recognize — năng lực khó nhất).

Chọn A / B / C.

> trả lời:
> (1) Học nốt driving side trước — đóng cho tròn Hexagonal, rồi mới sang C
> (luyện Recognize trên code có cả hai phía).

---

## Turn 11 — 🧑‍🏫 TEACHER — Driving side (nửa còn thiếu của lục giác)

Tôi đã dạy thiếu một nửa. Bù lại đây. Nhớ lại `OrderService`: ta mới làm **một
phía** — nó gọi RA ngoài (DB). Giờ hỏi phía kia.

**Câu hỏi nền (chưa cần trả lời ngay, để dẫn):** *Ai gọi `OrderService.Checkout()`?*

Có thể là: một REST API controller, một màn hình desktop, một dòng lệnh CLI, một
con cron chạy nền, hay một **unit test**. Tất cả những thứ đó **gọi VÀO** app.

Vẽ ra để thấy **hai phía**:

```
   DRIVING side (gọi VÀO)            CORE              DRIVEN side (app gọi RA)
   ───────────────────────          ────              ───────────────────────
   RestController ─┐                                        ┌─► SqlOrderRepository
   CliCommand    ──┼─► [ICheckoutUseCase] ► OrderService ► [IOrderRepository] ─┤
   TestRunner    ─┘     (driving port)      (logic)         (driven port)      └─► FakeOrderRepository
```

Hai khác biệt cốt lõi giữa hai phía:

| | Driving side (trái) | Driven side (phải) |
|---|---|---|
| Ai gọi ai | bên ngoài **gọi vào** app | app **gọi ra** bên ngoài |
| Ai "cầm lái" | adapter điều khiển app | app điều khiển adapter |
| Port là gì | interface của **use-case** (app cung cấp) | interface của **hạ tầng** (app cần) |
| Ví dụ adapter | REST controller, CLI, test | SQL repo, email, file |

**Điểm mấu chốt (đây là cái làm Hexagonal KHÁC "Layered có interface"):**
Mũi tên phụ thuộc ở **CẢ HAI phía đều trỏ VÀO Core**.
- Driving: controller → `ICheckoutUseCase` (← Core sở hữu interface này).
- Driven: SQL repo → `IOrderRepository` (← Core cũng sở hữu).

Core ngồi giữa, **không trỏ ra phía nào**. Bên trái không biết bên phải là SQL
hay file. Bên phải không biết bên trái là web hay CLI. Đối xứng. Đó là lý do
Cockburn vẽ **lục giác** (cổng quanh mọi phía), không phải 2 lớp chồng.

**Câu hỏi 11 (một câu — suy nghĩ theo cái bạn đã nắm):**

Driving port (`ICheckoutUseCase`) và driven port (`IOrderRepository`) — theo bạn,
interface nào do **Core định nghĩa và sở hữu**? Một cái, hai cái, hay không cái
nào? Vì sao?

(Gợi ý: nhớ quy tắc "interface đặt ở Core". Áp nó cho CẢ hai phía xem sao.)

> trả lời:
> Core sử hữu cái bất biến đó là interface.
> Việc định nghĩa sẽ được nằm ở 2 side

---
<!-- TEACHER viết Turn 12 sau khi bạn trả lời -->

## Turn 12 — 🧑‍🏫 TEACHER

Bạn đúng vế đầu, nhưng vế sau lẫn — phải gỡ cho sạch, vì đây là chỗ tinh tế nhất.

Bạn viết: *"Việc định nghĩa sẽ nằm ở 2 side."* → **Sai.** Tách bạch 2 từ hay bị
nhầm:

- **Định nghĩa interface (definition)** = nơi khai báo `interface I... { ... }`.
- **Hiện thực interface (implementation)** = nơi viết class `class X : I...`.

Câu trả lời đúng:
> **CẢ HAI interface đều ĐỊNH NGHĨA trong Core.** Chỉ có **implementation (adapter)**
> mới nằm ở 2 side.

```
                 Shop.Core  (định nghĩa CẢ HAI port)
                 ┌─────────────────────────────────────┐
   driving side  │  interface ICheckoutUseCase   ◄──┐   │   driven side
   ──────────    │  class OrderService : ICheckout │  │   │   ──────────
   RestController│  interface IOrderRepository  ◄─┐ │   │
      │ implements                               │ │   │      SqlOrderRepository
      └───────────────────────────────────────┐ │ │   │         │ implements
                                               │ │ │   │         │
   (adapter ở ngoài, reference vào Core)  ─────┘ │ │   └─────────┘
                                                  ... cả 2 adapter đều trỏ VÀO Core
```

Vì sao cả hai phải ở Core? Áp đúng quy tắc đã học: **interface là cái ổn định →
ở Core; cái ổn định không phụ thuộc cái hay đổi.** Nếu để định nghĩa
`ICheckoutUseCase` bên project web, thì Core (chứa `OrderService` implement nó)
phải reference web → mũi tên trỏ ra ngoài → hỏng. Y hệt lý do với driven port.

**Một bất đối xứng tinh tế (điểm hay nhất, ít người nắm):**
- **Driven port** (`IOrderRepository`): Core **định nghĩa** + **gọi**, người ngoài
  **implement**. (Core nói "tôi cần ai đó làm việc này".)
- **Driving port** (`ICheckoutUseCase`): Core **định nghĩa** + **implement** (chính
  `OrderService`), người ngoài **gọi**. (Core nói "đây là việc tôi làm được, ai
  cần thì gọi".)

→ Cả hai interface đều ở Core, nhưng **Core implement driving port, còn người
ngoài implement driven port**. Đó là sự đối xứng + bất đối xứng đẹp của lục giác.

### Chốt: giờ bạn thấy trọn hình
Hexagonal KHÔNG chỉ là "tách bất biến/biến đổi" (đó là *cơ chế*). Cái *riêng* của
nó là: **app ngồi giữa, mọi giao tiếp 2 phía đều qua port do app sở hữu, nên app
độc lập hoàn toàn với cả phía gọi vào lẫn phía bị gọi ra.** Đổi web→CLI (trái)
hay SQL→file (phải) đều không đụng Core.

Tôi sẽ cập nhật `01-posa.md` thêm phần driving/driven cho đủ.

---

**Câu 12 (một câu, để chắc bạn nắm bất đối xứng):**

Trong 2 port đó, cái nào mà **`OrderService` (Core) tự viết class implement nó**,
cái nào mà **code bên ngoài Core viết class implement**? Ghép cho đúng.

> trả lời:
>  (Core) tự viết class implement có nghĩa là core đang dùng nó -> vậy nó là Driven port
>  cái kia ngược lại 


---
<!-- TEACHER viết Turn 13 sau khi bạn trả lời -->

## Turn 13 — 🧑‍🏫 TEACHER

Ghép **ngược rồi**. Và lỗi gốc là trộn hai từ: *"implement"* ≠ *"dùng (gọi)"*.
Tách ra là hết nhầm.

Một interface có **2 vai** tách rời:
- **Implement** = *viết class thân thịt* cho interface (`class X : I {...}`).
- **Call / use** = *gọi method* của interface (`i.DoSomething()`).

Hai vai này **ở hai người khác nhau**. Giờ soi từng port:

**Driven port — `IOrderRepository` (`.Save()`):**
- Ai **gọi** `.Save()`? → `OrderService` (Core gọi ra ngoài để lưu).
- Ai **implement** `.Save()`? → `SqlOrderRepository` (**bên ngoài** Core).
- → Core **GỌI**, ngoài **IMPLEMENT**.

**Driving port — `ICheckoutUseCase` (`.Checkout()`):**
- Ai **gọi** `.Checkout()`? → `RestController` (**bên ngoài** gọi vào app).
- Ai **implement** `.Checkout()`? → `OrderService` (**chính Core**).
- → Core **IMPLEMENT**, ngoài **GỌI**.

Vậy đáp án đúng (ngược với bạn ghép):

| | Core tự implement? | Ai gọi? |
|---|---|---|
| **Driving** (`ICheckoutUseCase`) | ✅ **Core implement** | bên ngoài gọi |
| **Driven** (`IOrderRepository`) | ❌ ngoài implement | Core gọi |

Câu hỏi của tôi là *"port nào Core tự viết class implement"* → đáp án là
**Driving port**. Bạn trả lời "Driven" → ngược.

**Vì sao bạn nhầm:** bạn suy *"Core đang dùng nó → Core implement nó"*. Nhưng
*dùng* (gọi) và *implement* (viết thân) là hai việc khác nhau. Với driven port,
Core **dùng** (gọi `.Save()`) nhưng **không implement** — nó nhờ adapter ngoài
implement. "Dùng" không kéo theo "implement".

> Mẹo nhớ chắc: nhìn chữ "DRIVE" (lái).
> - **Driving** = cái *lái* app từ ngoài vào → app (Core) là thứ *bị gọi* → nên
>   Core phải **có sẵn thân** để bị gọi → **Core implement**.
> - **Driven** = app *lái* ra ngoài → Core *gọi đi*, thứ ngoài *bị sai khiến* →
>   nên thứ ngoài phải **có thân** → **ngoài implement**.

Đọc lại 1 lần nữa cho ngấm, đây là phần dễ quên nhất của Hexagonal.

---

**Câu 13 (một câu — xác nhận lại cho chắc, đừng cuộn lên nhìn bảng):**

`RestController` và `SqlOrderRepository` — cái nào là **driving adapter**, cái
nào là **driven adapter**? Và mỗi cái *gọi* hay *bị gọi* bởi Core?

> trả lời:
> RestController gọi core -> RestController là Driving 
> và ngược lại 


---
<!-- TEACHER viết Turn 14 sau khi bạn trả lời -->

## Turn 14 — 🧑‍🏫 TEACHER

**Đúng.** `RestController` gọi vào Core → **driving adapter**.
`SqlOrderRepository` bị Core gọi ra → **driven adapter**. Bạn đã chỉnh lại được
sau cú nhầm — đúng cái quan trọng là *gỡ được*, không phải *không bao giờ sai*.

Giờ bạn nắm trọn lục giác: hai phía, hai loại port, ai implement/ai gọi. Tôi đã
ghi phần driving/driven vào `01-posa.md` để khỏi mất.

### Hexagonal — định vị lại sau khi học đủ 2 phía
- Driven side: **Master** (tự áp, transfer được, biết khi nào không dùng).
- Driving side: **Understand→Use** (vừa nắm, chưa tự áp lần nào).
- Cả hai phía nhập lại: bạn ở **Level 3–4**. Để chắc Level 4 trọn, cần một lần
  *nhận diện* (Recognize) — đó chính là bước C.

---

## Bước C — Recognize (năng lực khó nhất): đọc code, chỉ ra chỗ sai

Đây là bài SĂN LỖI. Dưới đây là code C# có thật-như-đời. Đừng sửa vội — chỉ
**chẩn đoán**.

```csharp
// ===== Project: Shop.Core =====
public class PricingService
{
    public Receipt Checkout(Cart cart)
    {
        decimal total = cart.Lines.Sum(l => l.Price * l.Qty);
        if (total > 1_000_000) total *= 0.9m;            // business rule: giảm 10%

        // gửi mail xác nhận
        var smtp = new SmtpClient("smtp.shop.com");       // (*)
        smtp.Send(new MailMessage("shop@x.com", cart.CustomerEmail,
                  "Hoá đơn", $"Tổng: {total}"));

        // ghi log ra file
        File.AppendAllText("C:\\logs\\checkout.txt",       // (**)
                           $"{DateTime.Now}: {cart.Id} = {total}\n");

        return new Receipt(cart.Id, total);
    }
}
```

`PricingService` nằm trong project **Shop.Core** (đáng lẽ là business logic thuần).

**Câu 14 (chẩn đoán — trả lời theo ý bạn, chưa cần sửa):**
1. Chỗ `(*)` và `(**)` vi phạm Hexagonal thế nào? (dùng từ "mũi tên" / "Core
   phụ thuộc cái gì").
2. Nếu sếp bảo "viết unit test kiểm tra luật giảm giá 10%", bạn vướng ở đâu?
3. Liệt kê các **driven port** bạn sẽ cần tách ra (đặt tên theo nghiệp vụ).

> trả lời:
> 1. Core -> (*) và (**); 
> 2. Vẫn làm bình thường nhỉ
> 3. send mail và log file  đều là driven port

---
<!-- TEACHER viết Turn 15 sau khi bạn trả lời -->

## Turn 15 — 🧑‍🏫 TEACHER

**Câu 1 — đúng.** `Core → (*) SmtpClient` và `Core → (**) File`. Core đang trỏ
mũi tên ra hạ tầng cụ thể (SMTP, file system). Cái ổn định phụ thuộc cái hay đổi.

**Câu 3 — đúng.** Hai driven port, đặt tên nghiệp vụ:
`IInvoiceNotifier.Notify(...)` (gửi mail) và `IAuditLog.Record(...)` (ghi log).

**Câu 2 — SAI, và đây là điểm đắt nhất.** Bạn nói *"vẫn làm bình thường"*. Thử
thật xem chuyện gì xảy ra khi viết test:

```csharp
[Fact]
public void Discount_10pct_when_over_1M()
{
    var svc = new PricingService();
    var receipt = svc.Checkout(cartWith(total: 2_000_000));
    Assert.Equal(1_800_000, receipt.Total);
}
```

Bạn gọi `Checkout` để kiểm tra **luật giảm giá**. Nhưng `Checkout` không chỉ
tính tiền — giữa chừng nó:
- `(*)` **mở SMTP thật** `smtp.shop.com` → trên máy CI không có mạng/SMTP →
  **test ném exception hoặc treo timeout**. Test giảm giá fail vì... lỗi mail.
- `(**)` **ghi file** `C:\logs\checkout.txt` → CI là Linux, hoặc không có quyền
  ghi → lại fail. Mà nếu chạy được thì mỗi lần test lại **gửi mail thật** cho
  khách + rác file.

→ Vướng ở chỗ: **không thể test luật giảm giá MÀ KHÔNG kích hoạt mail + file.**
Logic thuần (tính tiền) bị **trộn** với side-effect (I/O). Muốn chạm #1 thì #2,
#3 bị lôi theo — đúng y nỗi đau ban đầu của `OrderService`, chỉ khác vỏ.

Đây là **Recognize**: cùng một bệnh "I/O dính trong logic" nhưng lần này núp
dưới mail + file thay vì SQL. Nhận ra nó dù đổi vỏ = đúng năng lực khó nhất.

> Bài học: "test được không?" KHÔNG hỏi *"logic có đúng không"* mà hỏi *"chạy
> logic có kéo theo I/O thật không?"*. Có I/O thật xen vào = chưa test cô lập được.

### Định vị
Bạn nhận ra #1, #3 ngay (cấu trúc + tách port). Riêng #2 (hệ quả test) là chỗ
trượt — nhưng giờ đã thấy. → Recognize: **đạt mức Use, đang lên Master**. Cần
thêm vài lần săn lỗi ở pattern khác để chắc.

---

## ✅ HEXAGONAL — HOÀN TẤT VÒNG HỌC

Bạn đã đi đủ 4-step + cả 2 phía + 1 lần Recognize:
- Hook the pain → Read (POSA) → Draw → Transfer → (driving/driven) → Recognize.
- **Level tổng: 4 — Master** (driven vững; driving nắm; recognize đang lên).

**Câu 15 — chốt phiên (một câu, tự do):**
Sau cả buổi, viết lại bằng lời CỦA BẠN: *Hexagonal là gì, giải nỗi đau gì, và
1 dấu hiệu để nhận ra code đang vi phạm nó?* (Đây là test "dạy lại" — diễn đạt
được = hiểu thật.)

> trả lời:
>
>

---
<!-- TEACHER chốt + cập nhật retention sau khi bạn trả lời -->
