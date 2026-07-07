# 🚀 BẮT ĐẦU TỪ ĐÂY

> Đây là **giáo trình tự học** để bạn hiểu Vision Platform Architecture đủ sâu để **tự code lại từ đầu**, không chỉ đọc cho biết.

> 📌 **Trước khi bắt đầu**, đọc lướt [`00-ERRATA.md`](00-ERRATA.md) — danh sách đính chính +
> cạm bẫy đa nền tảng (jitter `hash()`, MediaPacket không hashable, SHM trên Windows, số
> benchmark là kỳ vọng...). Tránh lặp các lỗi đã biết.

## Bạn đang ở đâu trong dự án này?

Có **4 thứ** trong workspace này, đừng nhầm:

| Thư mục | Vai trò | Khi nào động vào |
|---------|---------|------------------|
| `Vision_platform_architecture_design/` | **Bản thiết kế production đầy đủ** — nguồn tham chiếu khái niệm cho các mục "Production:" ở cuối mỗi step. **Lưu ý:** đây là tài liệu thiết kế tham chiếu, KHÔNG được đóng gói trong snapshot workspace này; nếu bạn không thấy folder này, hãy coi các link "Production:" là tham chiếu khái niệm. | Tham khảo (nếu có). KHÔNG sửa khi đang học. |
| `Learning_path/` (folder này) | **Giáo trình tự học** từ con số 0 → tự triển khai được. | Đọc theo thứ tự + làm bài tập + code along. |
| `vision_demo_workspace/` (bạn sẽ tạo ở Module 03 step 01) | **Project thật bạn sẽ code** trong khi học. Minimal. | Bạn gõ code vào đây mỗi ngày. |
| `_vision_demo_workspace/` | **Reference build** — phiên bản hoàn chỉnh mà bạn DỰNG RA khi gõ hết Module 03 (Step 01→10). **Không** được đóng gói sẵn trong snapshot này; bạn tự tạo `vision_demo_workspace/` theo các step. Nếu cần đối chiếu, so với code mẫu in trong từng step. | Tự build theo step; không có sẵn để peek. |

---

## 🎯 Mục tiêu cuối cùng

Sau khi hoàn thành Learning_path, bạn sẽ:

1. **Đọc** bản thiết kế production (`Vision_platform_architecture_design/`, nếu có trong môi trường của bạn) để hiểu **tại sao** mỗi quyết định, không chỉ "nó là gì". Nếu không có folder này, các mục "Production:" cuối mỗi step vẫn dùng được như tham chiếu khái niệm.
2. **Code lại** một phiên bản nhỏ (1 camera, 2 stage, 1 inference service) chạy được trên máy bạn — gọi là `vision_demo_workspace/`.
3. **Mở rộng** dần `vision_demo_workspace/` lên 4 camera, thêm SHM, thêm backpressure, thêm shutdown — gặp các bug thật và tự fix.
4. **Triển khai** một dự án thật (HeadDetect hoặc dự án khác) dùng cùng kiến trúc, có lý do để bảo vệ trong meeting.

**Không phải mục tiêu**: học cách dùng OpenCV/PyTorch/YOLO. Đây không phải khoá CV. Đây là khoá **kiến trúc phần mềm cho hệ thống CV**.

---

## 📚 Phương pháp học (đọc kỹ — quyết định 80% thành công)

### Nguyên tắc 1: Build-first, read-second

Đọc lý thuyết trước rồi code sau là **cách kém nhất**. Não cần "móc treo" để gắn kiến thức vào. Móc treo = trải nghiệm thực tế bạn vừa code xong 5 phút trước.

→ Mỗi module đều có phần **Code-along**. Đừng skip. Mở terminal, gõ thật.

### Nguyên tắc 2: Spiral curriculum — gặp lại 3 lần

Một concept (ví dụ: "Port") sẽ xuất hiện ở 3 độ sâu:

- **Lần 1** (Module 01-02): Nhận diện. "Port là interface mà adapter phải implement."
- **Lần 2** (Module 03): Dùng được. "Tôi vừa code 1 port `IDataSource` và 1 adapter `VideoFileSource`."
- **Lần 3** (Module 04-05): Hiểu trade-off. "Port có cost: thêm abstraction layer. Khi 1 implementation duy nhất tồn tại mãi → port có thể là over-engineering. Nhưng port giúp test dễ + đổi adapter."

Nếu bạn chỉ đọc lần 1 → bạn nhớ tên. Nếu đọc cả 3 lần → bạn **hiểu**.

### Nguyên tắc 3: Worked examples first

Các nghiên cứu của John Sweller (Cognitive Load Theory) chứng minh:

- "Đọc lý thuyết → tự giải bài tập" — học sinh giải đúng ~30%, hiểu sâu thấp.
- "Đọc lời giải mẫu → tự giải bài tương tự" — đúng ~80%, hiểu sâu cao gấp 3.

→ Mỗi pattern, bạn sẽ đọc **1 ví dụ đã giải** trước, rồi tự làm bài tương tự.

### Nguyên tắc 4: Stop khi confused

Nếu một section đọc 2 lần không hiểu — DỪNG. Đừng cố đẩy. Quay lại module trước hoặc nhảy xuống "Trade-offs" để xem có context phụ không. Đẩy tiếp khi confused = chôn lỗ hổng kiến thức.

### Nguyên tắc 5: Ghi chú bằng cách viết lại

Cuối mỗi module có **Self-check** — 5-10 câu hỏi. KHÔNG chỉ trả lời trong đầu. **Mở file mới, viết câu trả lời ra**. Viết = ép bộ não compile lại từ memory thay vì nhận diện. Khác biệt rất lớn.

---

## 🗺️ Roadmap 7 module

| # | Module | Thời gian | Mục đích | Output |
|---|--------|-----------|----------|--------|
| 01 | **Foundations** | 3-5h | Hiểu các khái niệm cốt lõi: architecture là gì, coupling, dependency direction. | Trả lời được self-check. |
| 02 | **Core concepts** | 6-8h | 5 pattern lặp đi lặp lại trong dự án: hexagonal, ports&adapters, bulkhead, backpressure, immutability. | Vẽ diagram được. |
| 03 | **Build-along** | 15-25h | Code thật `vision_demo_workspace/` từ skeleton tới shutdown protocol. | Project chạy được trên máy bạn. |
| 04 | **Deep dives** | 8-12h | GIL, SHM atomicity, ZMQ patterns, asyncio loop, circuit breaker math. | Hiểu được why của các quyết định khó. |
| 05 | **Real bugs** | 5-8h | Walkthrough 12+ bug thật từ R1-R5 review. Học từ sai lầm. | Phát hiện được pattern bug khi review code. |
| 06 | **Implementation** | 4-6h | Plan 16 tuần triển khai thật. Definition of done. Testing. Risk register. | Roadmap + risk review dùng được trong dự án thật. |
| 07 | **Troubleshooting** | 3-5h | Khi production bug — pipeline stall, memory leak, shutdown hang. | Decision tree dùng được khi 3h sáng có incident. |

**Tổng**: 44-69 giờ (1-2 tháng nếu học 1-2h/ngày).

---

## 📖 Cách đọc giáo trình này

### Trước khi bắt đầu Module 01

1. Đọc hết file này (`00-START-HERE.md`) — đảm bảo bạn hiểu phương pháp.
2. Cài đặt môi trường:
   ```bash
   # Python 3.11+ (kiểm tra)
   py --version
   
   # Tạo venv riêng cho dự án học
   py -m venv .venv_learning
   .venv_learning\Scripts\activate     # Windows
   # source .venv_learning/bin/activate  # macOS/Linux
   
   pip install --upgrade pip
   ```
3. Mở 2 cửa sổ terminal: 1 để gõ code, 1 để chạy code.

### Trong mỗi module

1. Mở `00-index.md` của module đó.
2. Đọc theo **thứ tự đánh số** (`01-...md`, `02-...md`,...). KHÔNG nhảy.
3. Đến phần "Code-along" — gõ TỪNG dòng vào terminal/file. Đừng copy-paste.
4. Gặp "Checkpoint" — trả lời TRƯỚC khi xem đáp án.
5. Hết module — làm `99-self-check.md`. Pass mới qua module sau.

### Khi bị stuck

- **Confused 5 phút** → đọc lại section đó 1 lần nữa.
- **Confused 15 phút** → quay về module trước, đọc lại "Liên kết".
- **Confused 30 phút** → ghi câu hỏi cụ thể vào file `_questions.md` riêng. Đẩy tiếp module sau, quay lại sau.

---

## 🚧 Những gì giáo trình này KHÔNG dạy

Đặt expectation trước:

❌ Cách dùng OpenCV / PyTorch / YOLO — đã có khoá riêng.
❌ Linux/Docker basics — bạn cần đã biết cơ bản.
❌ Python language basics — assumption: bạn biết class, function, decorator, context manager, asyncio cơ bản.
❌ Best practices "tổng quát" — chỉ tập trung vào kiến trúc CV multi-camera real-time.

Nếu bạn yếu Python, đọc thử file `module-01-foundations/01-what-is-software-architecture.md` trước — nếu code mẫu không hiểu thì tạm dừng học **Effective Python** rồi quay lại.

---

## 🤝 Mong đợi từ bạn

Học kiến trúc khác học framework. Framework: 1 tuần thuộc API. Kiến trúc: bạn hiểu **tradeoff** sau khi tự đập đi xây lại 3-4 lần. Hãy đặt kỳ vọng đúng:

- Module 01-02: cảm giác "lý thuyết suông" — KHỚP. Cứ đẩy tiếp, sẽ thấy ích lợi ở Module 03.
- Module 03: sẽ FRUSTRATING. Code không chạy, refactor 3 lần. Đó là **chỗ học thật sự xảy ra**.
- Module 04-05: thấy "à thì ra vậy" — concept ban đầu kết tinh thành intuition.
- Module 06-07: dùng được trong production thật.

Đừng kỳ vọng "đọc xong là làm được". Học kiến trúc là **xây cơ bắp, không phải nhồi RAM**.

---

## 🏁 Sẵn sàng?

Mở [`module-01-foundations/00-index.md`](module-01-foundations/00-index.md) và bắt đầu.

---

## Phụ lục: Cấu trúc folder Learning_path

```
Learning_path/
├── 00-START-HERE.md                    ← bạn đang đọc
├── module-01-foundations/              ← nền tảng. KHÔNG skip.
│   ├── 00-index.md
│   ├── 01-what-is-software-architecture.md
│   ├── 02-coupling-cohesion-the-core-tradeoff.md
│   ├── 03-dependency-direction.md
│   ├── 04-context-matters-no-best-architecture.md
│   └── 99-self-check.md
├── module-02-core-concepts/            ← 5 pattern xuất hiện đi lặp lại
│   ├── 00-index.md
│   ├── 01-hexagonal-architecture-from-scratch.md
│   ├── 02-ports-and-adapters-build-one.md
│   ├── 03-bulkhead-pattern.md
│   ├── 04-backpressure-why-it-matters.md
│   ├── 05-immutability-and-cow.md
│   └── 99-self-check.md
├── module-03-build-along/              ← code vision_demo_workspace/
│   ├── 00-overview.md
│   └── step-01..step-10-*.md
├── module-04-deep-dives/               ← hiểu sâu các quyết định (GIL, SHM, ZMQ, asyncio, circuit breaker, traceback)
├── module-05-real-bugs/                ← case studies bug thật từ R1-R5
├── module-06-implementation/           ← plan triển khai 16 tuần
├── module-07-troubleshooting/          ← khi production có bug
└── reference-cards/                    ← cheat sheets in được
```

**Trạng thái giáo trình**: ✅ Tất cả 7 module đã hoàn thành, có self-check. Module 03 (build-along) in đầy đủ code mẫu từng step để bạn tự dựng `vision_demo_workspace/` đạt **110 passed + 1 skipped** (111 test collected — xem Step 10). Module 06 có thêm risk register để review thiết kế bằng score + evidence + mitigation. Các con số test/benchmark trong giáo trình là *mục tiêu kỳ vọng* khi bạn gõ đúng theo step, không phải artifact đóng gói sẵn trong snapshot này.
