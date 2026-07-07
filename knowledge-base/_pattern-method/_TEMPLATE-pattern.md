# <Tên pattern> — POSA 5-box

> Khuôn cho **mọi pattern/nguyên lý kiến trúc**. Copy file này vào
> `knowledge-base/<concept>/README.md` (hoặc `01-posa.md`) rồi điền.
> Đọc `00-PATTERN-METHOD.md` + `00-TAXONOMY.md` (cùng folder `_pattern-method/`) trước.
> **Trạng thái:** ⬜ chưa học / 🔵 đang học / ✅ đã nắm (= đạt Level 4, xem cuối file)
>
> Quy tắc điền: **giữ ĐỦ Forces và phần "hại"**; LUÔN trả lời "khi nào KHÔNG dùng";
> mọi thông tin chốt phải kiểm chứng nguồn (AGENTS.md §5).

---

## 1. Name (Tên)
- **Tên chuẩn:** …
- **Tên khác / hay gọi nhầm:** …
- **Tier (tầng):** … — (xem `00-TAXONOMY.md`)
- **Một câu nó giải gì:** …

## 2. Context + Forces (Bối cảnh + Lực giằng nhau)
- **Context** — tình huống nào thì cân nhắc: …
- **Forces** — các lực ĐANG GIẰNG nhau (≥2, dạng "A ↔ B"): ← KHÔNG bỏ trống
  - … ↔ …
  - … ↔ …
- **What varies?** (cái cần cô lập): …

## 3. Problem (Vấn đề)
- **Triệu chứng / nỗi đau cụ thể** khi KHÔNG có pattern: …
- **Pain thật (bước "Hook the pain")** — đoạn code xấu gây đau: …

## 4. Solution (Giải pháp)
- **Diagram** (boxes + arrows — chỉ rõ hướng phụ thuộc):

  ```
  (vẽ ở đây: hộp + mũi tên, ai phụ thuộc ai)
  ```

- **Các thành phần chính:** …
- **Hướng mũi tên:** … (cái stable KHÔNG phụ thuộc cái volatile)
- **Bản tối giản (intent over ceremony)** — Python/pseudo, ít nghi thức nhất: …
- **Ép bằng công cụ?** — layer nào KHÔNG được import layer nào (import-linter, §4): …

## 5. Consequences (Hệ quả — CẢ lợi VÀ hại)
- **Lợi (benefits):** …
- **Hại / cái giá (costs):** … ← KHÔNG được bỏ trống
- **Khi nào KHÔNG nên dùng:** … ← BẮT BUỘC

---

## Câu hỏi chẩn đoán (DIAGNOSTIC — gặp tình huống thì hỏi tuần tự)
> 2 câu gốc mọi pattern (`00-PATTERN-METHOD.md`): *What varies?* · *Which way do deps point?*

**Nhóm A — CÓ NÊN dùng? (sàng lọc)**
1. …?
2. …?
   → tất cả "không" → KHÔNG dùng (over-engineering). Có ≥1 "có" → cân nhắc.

**Nhóm B — ÁP THẾ NÀO? (sau khi quyết dùng)**
3. **What varies** ở đây là gì → thứ cần giấu sau abstraction.
4. Đặt tên theo **ý định nghiệp vụ** hay công nghệ? (phải theo nghiệp vụ)
5. **Mũi tên** sau khi tách: cái stable còn trỏ ra cái volatile không? (phải KHÔNG)
6. Đặt ở **layer nào**? (import-linter có chặn được vi phạm không?)

**Câu khóa:** *"Có lực nào đang giằng mà pattern này gỡ được không?"* — Không lực → không pattern.

## Dấu hiệu NHẬN BIẾT vi phạm (RECOGNIZE — đọc code lạ, năng lực khó nhất)
> Cùng một bệnh, khác lớp sơn. Tập "ngửi" ra chỗ sai dù nó núp dưới vỏ nào.

- **Smell chính:** … (vd: class logic lại `new <hạ tầng cụ thể>` / gọi thẳng I/O)
- **Phép thử quyết định:** … (vd: "chạy logic có kéo theo I/O thật không?")
- **Bẫy hay trượt:** "chạy được" ≠ "test cô lập được" — đừng thấy code chạy là cho qua.

---

## Self-location (định vị theo thang 5 cấp — `00-PATTERN-METHOD.md` §1)
> Tick cấp cao nhất CÒN PASS test. ✅ trạng thái concept = đạt **Level 4**.

- [ ] **1 Know** — viết 1 câu nó giải gì (không mở tài liệu)
- [ ] **2 Understand** — giấy trắng: vẽ diagram + nói Forces
- [ ] **3 Use** — áp được khi CÓ gợi ý
- [ ] **4 Master** — tự áp KHÔNG gợi ý + nêu 1 ca KHÔNG nên dùng
- [ ] **5 Analyze & Evaluate** — đọc hệ thống lạ, chọn phương án + bảo vệ trade-off

**Đang ở Level:** …
**Mốc ôn (retention):** 1 ngày → … | 1 tuần → … | 1 tháng → …

## Lesson dùng pattern này (back-links)
- …

## Sources (Nguồn — đã validate) + độ chắc chắn
- … — độ chắc chắn: <cao/vừa/thấp>
