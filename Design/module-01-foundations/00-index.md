# Module 01 — Foundations

> **Mục đích**: Trước khi học pattern cụ thể (hexagonal, bulkhead...), bạn cần các khái niệm gốc. Module này dạy 4 thứ.

## Tại sao module này tồn tại?

Ngày 1 tôi cũng từng nghĩ "kiến trúc = vẽ box + arrow". Sai. Kiến trúc = **tập hợp các quyết định không thể đảo ngược dễ dàng**. Để ra quyết định ĐÚNG, bạn cần biết các đại lượng quan trọng để cân nhắc:

- **Coupling** & **cohesion** — đại lượng đo sự "vướng víu" giữa các phần.
- **Dependency direction** — ai phụ thuộc vào ai. Sai chỗ này → toàn bộ kiến trúc sụp.
- **Context** — không có "best architecture", chỉ có "phù hợp với context X".

Nếu bạn không hiểu 4 thứ trên, bạn sẽ đọc Hexagonal/Bulkhead/CQRS chỉ thấy "à thì box A có mũi tên đến box B" — không hiểu **tại sao**.

## Thời gian cần

3-5 giờ. Mỗi file 30-60 phút (đọc + ngẫm + làm checkpoint).

## Thứ tự đọc (không nhảy)

| # | File | Bạn sẽ học gì | Thời gian |
|---|------|---------------|-----------|
| 1 | [`01-what-is-software-architecture.md`](01-what-is-software-architecture.md) | Định nghĩa "kiến trúc phần mềm" theo cách dùng được — không phải định nghĩa từ điển. | 30' |
| 2 | [`02-coupling-cohesion-the-core-tradeoff.md`](02-coupling-cohesion-the-core-tradeoff.md) | 2 đại lượng quan trọng nhất bạn sẽ đo trong mọi quyết định kiến trúc. | 60' |
| 3 | [`03-dependency-direction.md`](03-dependency-direction.md) | Quy tắc vàng: **ai phụ thuộc ai?** Câu trả lời quyết định 70% kiến trúc của bạn. | 60' |
| 4 | [`04-context-matters-no-best-architecture.md`](04-context-matters-no-best-architecture.md) | Tại sao MVC tốt cho web nhưng tệ cho game. Tại sao microservices không phải lúc nào cũng đúng. | 45' |
| 5 | [`99-self-check.md`](99-self-check.md) | Tự kiểm tra. Pass mới qua Module 02. | 30' |

## Output sau module này

Bạn sẽ trả lời được (không tra cứu):

1. Phân biệt "code design" và "architecture design".
2. Đưa 1 đoạn code vào, đo coupling và cohesion ở mức nào, đề xuất cải thiện.
3. Vẽ đúng dependency direction giữa 4 layer (domain / kernel / runtime / application).
4. Đánh giá: "kiến trúc X có phù hợp với dự án Y không?" — không trả lời chung chung.

## Mẹo học hiệu quả

- **Đừng** đọc 1 lèo cả 4 file. Mỗi file → ngẫm 1 ngày → file tiếp theo.
- **Hãy** áp dụng vào codebase bạn đang có (HeadDetect/main_app/) — phát hiện coupling cao ở đâu.
- **Đừng** học thuộc định nghĩa. Học bằng cách trả lời "trong tình huống X, tôi sẽ làm Y vì Z".

---

➡️ Bắt đầu: [`01-what-is-software-architecture.md`](01-what-is-software-architecture.md)
