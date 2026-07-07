# 🧭 PATTERN-METHOD — Cách HỌC & DẠY một architecture/design pattern (portable)

> Áp dụng cho mọi concept là **pattern/nguyên lý kiến trúc** trong `knowledge-base/`.
> Concept "thường" → `../_templates/_TEMPLATE.md`. Pattern → `_TEMPLATE-pattern.md` (cùng folder) + phương pháp dưới đây.
> Language-independent (đo ở tầng sơ đồ, không phải cú pháp).

## 0. Đích & 2 câu hỏi gốc
Mục tiêu: lên **Level 5** để DÙNG được trong dự án thật. Đo bằng **hành động chứng minh**.
1. **What varies?** — tách vùng biến động sau abstraction.
2. **Which way do dependencies point?** — cái *stable* không phụ thuộc cái *volatile*.
> Đừng ép MỌI pattern về 2 câu này (Singleton/Facade/Iterator có gốc khác).

## 1. Thang 5 cấp (đo từng pattern) — có test
| Cấp | Tên | Test chứng minh |
|-----|-----|-----------------|
| 1 | Know | Gập tài liệu, viết 1 câu nó giải gì |
| 2 | Understand | Giấy trắng: vẽ diagram + nói Forces |
| 3 | Use | Áp được KHI CÓ gợi ý |
| 4 | Master | Tự áp KHÔNG gợi ý + nêu 1 ca KHÔNG nên dùng |
| 5 | Analyze & Evaluate | Đọc hệ thống lạ → chọn phương án + bảo vệ trade-off |
**✅ trạng thái concept = đạt Level 4.** Dưới đó giữ 🔵 + chỉ rõ hổng.

## 2. Học pattern = luyện 4 năng lực
Recognize · Structure · Judge · Transfer. POSA 5-box CHỈ dạy Structure; Recognize + Transfer
là phần khó nhất, luyện riêng.

## 3. Quy trình 4 bước / pattern
1. **Hook the pain** — tạo/lấy đoạn code xấu, thử thêm tính năng để thấy đau.
2. **Read** — POSA 5-box (`_TEMPLATE-pattern.md`).
3. **Draw** — gập tài liệu, vẽ lại diagram từ trí nhớ.
4. **Transfer** — refactor code xấu về pattern + áp sang 1 domain KHÁC.
> Design pattern (GoF) hợp refactor-to-pattern; architectural pattern thường upfront. Theo tier (`00-TAXONOMY.md`).

## 4. Grounding
- **Intent over ceremony** — đạt mục đích với ít code nhất.
- **Tool enforcement** — ép hướng phụ thuộc bằng công cụ của dự án (vd **import-linter** cho
  Python, **project references** cho C#), không nhắc miệng.

## 5. Retention
Ôn lại test của cấp đang đứng sau **1 ngày / 1 tuần / 1 tháng**. Dùng `_TEMPLATE-quiz.md`.

## 6. Giao kèo dạy
Không trả lời ngay (dẫn bằng câu hỏi) · một lần một thứ · bắt đầu từ nỗi đau thật · vẽ sơ đồ
trước · ép trả lời "khi nào KHÔNG dùng" · nói thẳng cô đọng · chốt phải kiểm chứng nguồn.

## 7. Câu khóa
> "Có nên dùng pattern không?" = "Có lực nào đang giằng mà pattern này gỡ được không?" — Không lực → không pattern.
