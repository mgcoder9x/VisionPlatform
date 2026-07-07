# 02 — Pattern Template (POSA 5-box)

> Khuôn DÙNG CHUNG cho **mọi** pattern. Mỗi pattern copy khuôn này vào folder
> riêng của nó rồi điền. Đọc `00-READ-FIRST.md` + `01-method.md` trước.
>
> Quy tắc điền: **giữ đủ Forces và phần "hại"**; luôn trả lời "khi nào KHÔNG
> dùng"; mọi thông tin chốt phải kiểm chứng nguồn.

---

## 1. Name (Tên)
- **Tên chuẩn:** …
- **Tên khác / hay bị gọi nhầm:** …
- **Tier (tầng):** Principle / Architectural style / Architectural pattern /
  Design pattern / Resilience pattern / Mechanism — (xem `architecture-taxonomy-map.md`)
- **Một câu nó giải gì:** …

## 2. Context + Forces (Bối cảnh + Lực giằng nhau)
- **Context** — tình huống nào thì cân nhắc pattern này: …
- **Forces** — các lực ĐANG GIẰNG nhau (ít nhất 2, dạng "A ↔ B"):
  - … ↔ …
  - … ↔ …
- **What varies?** (cái gì sẽ thay đổi cần cô lập): …

## 3. Problem (Vấn đề)
- **Triệu chứng / nỗi đau cụ thể** khi không có pattern: …
- **Pain thật từ kinh nghiệm C#** (step "Hook the pain"): …

## 4. Solution (Giải pháp)
- **Diagram** (boxes + arrows — hướng phụ thuộc):

  ```
  (vẽ ở đây: hộp + mũi tên, ai phụ thuộc ai)
  ```

- **Các thành phần chính:** …
- **Hướng mũi tên phụ thuộc:** … (stable không phụ thuộc volatile)
- **Bản C# tối giản** (intent over ceremony — ít nghi thức nhất có thể): …
- **Ép bằng compiler?** (project references nào cấm reference nào): …

## 5. Consequences (Hệ quả — CẢ lợi VÀ hại)
- **Lợi (benefits):** …
- **Hại / cái giá (costs):** … ← KHÔNG được bỏ trống
- **Khi nào KHÔNG nên dùng (when NOT to use):** … ← bắt buộc

---

## Self-location (Định vị bản thân theo thang 5 level)
> Đánh dấu level cao nhất bạn còn PASS test (xem bảng test ở `00-READ-FIRST.md`).

- [ ] **1 Know** — viết 1 câu nó giải gì (không mở tài liệu)
- [ ] **2 Understand** — giấy trắng: vẽ diagram + nói Forces
- [ ] **3 Use** — áp được khi có gợi ý
- [ ] **4 Master** — tự áp không gợi ý + nêu 1 ca KHÔNG nên dùng
- [ ] **5 Analyze & Evaluate** — đọc hệ thống lạ, chọn phương án + bảo vệ trade-off

**Đang ở level:** …
**Mốc ôn (retention):** 1 ngày → … | 1 tuần → … | 1 tháng → …

## Sources (Nguồn — phải kiểm chứng)
- …
