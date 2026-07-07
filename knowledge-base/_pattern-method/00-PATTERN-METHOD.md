# 🧭 PATTERN-METHOD — Cách HỌC & DẠY một architecture/design pattern

> Áp dụng cho MỌI concept là **pattern / nguyên lý kiến trúc** trong `knowledge-base/`
> (hexagonal, bulkhead, backpressure, circuit-breaker, dependency-direction...).
> Concept "thường" (không phải pattern) vẫn dùng `../_templates/_TEMPLATE.md`. Pattern → dùng
> `_TEMPLATE-pattern.md` (cùng folder này) + tuân phương pháp dưới đây.
>
> Nguồn gốc: kết tinh từ thư mục `pattern-study/` của người dùng (đã dùng thật, học
> Hexagonal tới Level 4). File này là bản chính thức, ánh xạ sang ngữ cảnh repo (Python,
> 6 layer, import-linter). Bản gốc C# lưu ở `pattern-study/` để tham chiếu.

---

## 0. Đích & kim chỉ nam
**Mục tiêu cuối:** lên **Level 5** cho từng pattern để **dùng được trong dự án thật** —
KHÔNG học cho biết, KHÔNG thuộc tên. Đo bằng **hành động chứng minh**, không bằng cảm giác
"thấy quen".

**Hai câu hỏi gốc — hỏi cho MỌI pattern:**
1. **What varies?** (cái gì sẽ thay đổi) — tách vùng biến động sau một abstraction để khi
   nó đổi, code ổn định không phải sửa. (Mạnh nhất ở design tier / GoF.)
2. **Which way do dependencies point?** (mũi tên phụ thuộc chỉ hướng nào) — xếp sao cho cái
   *stable* KHÔNG phụ thuộc cái *volatile*. (Mạnh nhất ở architecture tier.)

> Hai nửa một đồng xu: #1 = tách CÁI GÌ, #2 = nối theo HƯỚNG NÀO. Bỏ nửa nào cũng què.
> ⚠️ Đừng ép mọi pattern về 2 câu này (Singleton/Facade/Iterator có gốc khác). Đừng dạy như
> danh mục rời rạc, cũng đừng nhồi mọi thứ vào một công thức.

---

## 1. Thang 5 cấp độ (đo TỪNG pattern) — có test chứng minh
> Bạn đang ở **cấp cao nhất mà còn PASS test**. Fail test cấp N → bạn ở N−1. KHÔNG có "gần đạt".

| Cấp | Tên | Làm được gì | Test chứng minh (làm được mới tính) |
|-----|-----|-------------|-------------------------------------|
| 1 | **Know** (Biết) | Biết nó tồn tại | Gập tài liệu, viết 1 câu: nó giải vấn đề gì |
| 2 | **Understand** (Hiểu) | Giải thích *vì sao* | Giấy trắng: vẽ diagram + nói 3 câu "lực A giằng lực B" |
| 3 | **Use** (Dùng) | Áp được KHI CÓ gợi ý | Cho bài toán + bảo trước "dùng pattern X" → áp đúng |
| 4 | **Master** (Thành thạo) | Tự áp KHÔNG gợi ý + xét 1 pattern | Bài toán không gợi ý → tự chọn đúng + nêu 1 ca KHÔNG nên dùng |
| 5 | **Analyze & Evaluate** | Đọc HỆ THỐNG lạ + ra quyết định | Review codebase/design lạ → chỉ pattern dùng/thiếu/sai, chọn giữa ≥2 phương án + bảo vệ bằng trade-off |

- **Xét MỘT pattern** (khi nào không dùng) = phân tích nhỏ → **cấp 4**.
- **Đọc CẢ hệ thống lạ + chọn phương án** = phân tích lớn + đánh giá → **cấp 5** (đỉnh).

**Liên kết cổng Feynman (AGENTS.md §1, §5):** chỉ đổi trạng thái concept sang **✅ = khi đạt
Level 4** (tự áp không gợi ý + biết khi nào KHÔNG dùng). Level 5 để dành tới khi có nhiều
pattern để so sánh. Dưới Level 4 → giữ 🔵 + chỉ rõ hổng đâu.

---

## 2. Học một pattern = luyện 4 NĂNG LỰC (không phải nạp thông tin)
1. **Recognize** (nhận diện) — nhìn tình huống → biết pattern nào hợp / code lạ vi phạm chỗ nào.
2. **Structure** (cấu trúc) — pattern hình dạng gì (boxes + arrows).
3. **Judge** (phán đoán) — nên dùng không, cái giá phải trả gì.
4. **Transfer** (chuyển giao) — áp được sang bài toán / ngôn ngữ / domain khác.

> POSA 5-box CHỈ dạy **#2 Structure**. **#1 Recognize** và **#4 Transfer** là phần khó nhất,
> tốn công thật — phải luyện riêng (xem bước 4 dưới). "Describing is not knowing."

---

## 3. Quy trình 4 BƯỚC / 1 pattern (process tuyến tính, chạy 1→4)
1. **Hook the pain** (khơi nỗi đau) — ưu tiên *tạo* nỗi đau hơn *nhớ*: viết (hoặc lấy) một
   đoạn code chạy được nhưng tệ (nested if, copy-paste, class ôm quá nhiều việc), thử thêm 1
   tính năng để tự thấy đau ở đâu. (Tinh thần *Refactoring to Patterns*, Kerievsky 2004.)
2. **Read** — đọc pattern theo **POSA 5-box** (`_TEMPLATE-pattern.md`).
3. **Draw** — gập tài liệu, vẽ lại diagram (boxes + arrows) từ trí nhớ.
4. **Transfer** — refactor đống code xấu ở bước 1 về pattern, RỒI áp pattern vào 1 bài toán
   **khác domain** nữa. (Bỏ bước 1 và 4 = biết tên mà không dùng được.)

> ⚖️ Cân bằng theo tier: *Refactoring to Patterns* (pattern lộ ra từ code xấu) hợp **design
> pattern (GoF)**. **Architecture pattern** (Hexagonal, Layers) thường phải *upfront* (thiết kế
> trước) — ít khi "refactor vô tình mà ra". Chọn cách theo tier, đừng máy móc. (Tier → `00-TAXONOMY.md`.)

---

## 4. Hai nguyên tắc grounding (khi xuống code thật)
- **Intent over ceremony** (ý định hơn nghi thức) — đạt *mục đích* pattern với ít code nhất.
  Một hàm / dataclass / Protocol đã đủ thì đừng dựng cây class đồ sộ. Pattern là *ý định*,
  không phải số lượng class.
- **Compile-time / tool enforcement** (ép bằng công cụ, không nhắc miệng) — "hướng phụ thuộc"
  đừng để trên giấy. Trong repo Python này, đẩy nó vào **import-linter** (luật 6 layer §4):
  `domain` không được import `adapters` → vi phạm là **linter báo đỏ**, không phải nhắc miệng.
  (Tương đương "project references" trong bản C# gốc của pattern-study.)

---

## 5. Đo tới đâu & chống quên (Retention)
- **Đo:** dùng thang 5 cấp + test ở §1. KHÔNG đo bằng cảm giác.
- **Chống quên (spaced repetition):** sau **1 ngày / 1 tuần / 1 tháng**, chạy lại test của cấp
  đang đứng — vẽ diagram + nói Forces từ trí nhớ, KHÔNG đọc lại tài liệu. Ghi mốc ôn trong
  `<concept>/README.md`. Dùng `_TEMPLATE-quiz.md` cho buổi ôn.

---

## 6. Giao kèo truyền đạt (AI tuân khi dạy pattern — siết theo AGENTS.md §1)
- **Không trả lời ngay** — dẫn bằng câu hỏi để người học TỰ tìm ra. Chốt sau khi họ tự nghĩ.
- **Một lần một thứ** — dạy 1 ý, kiểm tra hiểu, mới đi tiếp. Không đổ đống.
- **Bắt đầu từ nỗi đau thật**, không từ định nghĩa.
- **Vẽ sơ đồ trước**, code chỉ minh hoạ (ưu tiên pseudo / Python tối giản). Không biến buổi học
  thành dạy cú pháp.
- **Phản biện** — mỗi pattern PHẢI ép trả lời "khi nào KHÔNG dùng".
- **Nói thẳng, cô đọng** — sai thì nói sai kèm lý do. Không tâng bốc.
- **Mọi thông tin chốt phải kiểm chứng nguồn** (AGENTS.md §5 anti-hallucination). Không chắc →
  nói "CHƯA CHẮC", đừng bịa tác giả/nguồn.

> **Ranh giới:** người thầy không học thay được. Phần khó nhất (nhận ra lúc nào cần pattern, áp
> sang bài lạ) chỉ xây bằng chính số lần người học tự vấp. Việc của AI: rút ngắn đường, vẽ sơ đồ,
> phản biện, neo lý thuyết vào nỗi đau thật — đi cùng, không đi thay.

---

## 7. Câu khóa quyết định (in đậm, nhớ đời)
> **"Có nên dùng pattern không?" = "Có lực (force) nào đang giằng nhau mà pattern này gỡ được
> không?"** — Không lực → không pattern.

---

**Tóm 1 câu:** Học pattern = luyện *Recognize + Transfer* (không chỉ đọc Structure), đi qua
**Hook→Read→Draw→Transfer**, đo bằng **5 cấp có test**, luôn giữ **Forces + cái giá + khi nào
KHÔNG dùng**, ép hướng phụ thuộc bằng **import-linter**.
