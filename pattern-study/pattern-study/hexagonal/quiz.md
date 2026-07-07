# Hexagonal — Quiz ôn tập (10 câu)

> Gập `01-posa.md` và `session.md` lại. Trả lời từ trí nhớ. Viết vào `> đáp án:`
> bên dưới mỗi câu, rồi bảo tôi "chấm".

---

**Q1.** Hexagonal / Ports & Adapters giải nỗi đau gì — nói bằng 1 câu.

> đáp án: bảo vệ nghiệp vụ ít thay đổi ra khỏi các phần hạ tầng thường dễ thay đổi

---

**Q2.** Hai câu hỏi gốc (áp cho mọi pattern) là gì?

> đáp án: Cái gì thay đổi? lực nào đang rằng nó?

---

**Q3.** Port là gì? Adapter là gì? Mỗi cái 1 câu.

> đáp án:
> Port là các interface ít thay đổi nằm ở core
> Port chính là hạ tầng hoặc phần từ bên ngoài gọi nó

---

**Q4.** Interface (Port) phải được **định nghĩa** ở project nào — Core hay
Infrastructure? Vì sao (1 câu)?

> đáp án:
> Core; nếu ở Infrastructure thì khi core dùng tới sẽ phải referent với Infrastructure gây ra hướng mũi tên hướng ra ngoài
---

**Q5.** Driving adapter vs Driven adapter: cái nào *gọi vào* Core, cái nào *bị
Core gọi ra*? Cho 1 ví dụ mỗi loại.

> đáp án: Tôi hiểu từ ngoài vào thì core phải implement còn những cái như sql và core gọi thì sql phải tự implement

---

**Q6.** Driving port — Core **implement** hay **gọi**?
Driven port — Core **implement** hay **gọi**?

> đáp án: thương nhầm lẫn giữa Driving và Driven do là tiềng anh

---

**Q7.** Nếu `OrderService` tự `new SqlOrderRepository()` bên trong constructor —
vi phạm nguyên tắc nào? Hậu quả là gì?

> đáp án: Vì phạm hướng mũi tên hướng vào trong; gây ra việc orderServices gắn chặt với adapter sẽ không thể mock test 

---

**Q8.** Phép thử nhanh nhất để nhận ra một class *đang vi phạm* Hexagonal là gì?
(1 câu, nhớ bài săn lỗi Turn 15.)

> đáp án:

---

**Q9.** Nêu 2 trường hợp KHÔNG nên áp Hexagonal (over-engineering).

> đáp án:

---

**Q10.** Hexagonal, Clean Architecture, Onion Architecture — khác nhau ở đâu?
Giống nhau ở đâu? (2–3 câu là đủ.)

> đáp án:

---

<!-- Trả lời xong 10 câu, bảo tôi "chấm" — tôi sẽ chấm + ghi level mới. -->
