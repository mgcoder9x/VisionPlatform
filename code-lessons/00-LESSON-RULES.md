# 📚 LESSON-RULES — Luật tạo bài giảng giải thích CODE (cho người mới hoàn toàn)

> File luật RIÊNG (không trộn vào AGENTS chính; AGENTS §1.8 chỉ trỏ tới đây).
> Áp dụng MỖI khi tạo/cập nhật bài giảng trong `code-lessons/`.
> Người học: **chưa biết Python, chưa biết kiến trúc tổng thể**. Mục tiêu tối thượng: hiểu mọi
> thứ dù nhỏ nhất → **tự viết lại được** vision-platform.

---

## 0. Ba khu học KHÁC nhau (đừng lẫn)
- `knowledge-base/` = **concept tái dùng** (hexagonal, pickle, CoW...) — học 1 lần, độc lập project.
- `lessons/` = (cũ, tạm dừng) lộ trình build-first.
- **`code-lessons/` (khu NÀY)** = **giải thích CHÍNH code đã build trong `vision-platform/`**, từng
  dòng/từng thứ nhỏ nhất, cho người mới. Bám file code thật.

---

## 1. LUẬT TỐI CAO — Bám sát code thật TUYỆT ĐỐI (chống bịa)
1. **Đọc trước khi giảng.** Trước khi viết/cập nhật 1 bài, PHẢI `read_file` chính file code trong
   `vision-platform/` đang giảng. KHÔNG giảng từ trí nhớ.
2. **Quote NGUYÊN VĂN.** Đoạn code trong bài phải **copy đúng từng ký tự** từ file thật + ghi
   **đường dẫn + (nếu được) số dòng**. KHÔNG sửa, KHÔNG "đại khái", KHÔNG bịa thêm dòng.
3. **Khẳng định hành vi = phải kiểm.** Nói "dòng này chạy ra X" → phải đã CHẠY thật (hoặc trích test
   đã pass / output thật). Suy đoán → nhãn **[suy đoán]**. (Theo AGENTS §5.)
4. **Lesson ↔ code đồng bộ.** Mỗi bài ghi rõ "Bám file: `<path>` (trạng thái lúc viết)". Nếu code đổi
   sau này → bài liên quan thành **[CẦN CẬP NHẬT]** (ghi vào INDEX). Không để bài lệch code.
5. **Tuyệt đối không tạo lesson trong câu trả lời chat.** Lesson sống trong file `code-lessons/`.
   Chat chỉ báo "đã tạo/cập nhật bài X".

---

## 2. Cơ chế học của con người (nền tảng — vì sao luật cấu trúc như §4)
> Khoa học học tập đã được công nhận (độ chắc: cao về nguyên lý, mình áp dụng có chọn lọc):
- **Cognitive Load Theory (Sweller):** não chứa được ít thứ mới/lần → **chia nhỏ nhất (chunking)** +
  **worked example trước** (xem code đã giải thích kỹ rồi mới tự làm). Bỏ chi tiết thừa gây nhiễu.
- **Retrieval practice / testing effect (Roediger):** **nhớ lại** (tự trả lời) khắc sâu hơn đọc lại
  → mỗi bài kết bằng câu hỏi tự kiểm.
- **Spaced repetition (đường quên Ebbinghaus):** ôn lại theo mốc 1 ngày / 1 tuần / 1 tháng.
- **Dual coding (Paivio):** chữ + **hình/ví von** → nhớ tốt hơn chữ đơn thuần.
- **Elaborative interrogation:** liên tục hỏi **"tại sao"** + nối với cái đã biết → hiểu sâu, không học vẹt.
- **Concreteness fading (Goldstone):** đi từ **cụ thể (dòng code thật) → trừu tượng (concept)** →
  ví von, KHÔNG bắt đầu bằng định nghĩa khô.
- **Feynman technique:** chỉ coi là "hiểu" khi **giải thích lại bằng lời mình** cho người không biết.
- **Zone of Proximal Development (Vygotsky):** bắc giàn (scaffold) ngay trên mức hiện tại — không quá dễ, không quá khó.

---

## 3. Quy tắc giảng (rút từ §2)
- **Một mẩu = một ý nhỏ nhất.** 1 dòng / 1 từ khóa / 1 ký hiệu / 1 hàm nhỏ. Không nhồi.
- **WHY trước WHAT.** Luôn trả lời: *Là gì? · Vấn đề nó giải / tại sao tồn tại? · Dùng ở đâu trong
  project (file/dòng/luồng cụ thể)? · Nếu KHÔNG có nó thì sao?*
- **Không thuật ngữ inline.** Từ lạ → link `knowledge-base/00-GLOSSARY.md#<từ>`; concept lớn →
  `knowledge-base/<concept>/`. Người mới click là hiểu, không kẹt.
- **Cụ thể → trừu tượng → ví von.** Bắt đầu từ dòng code thật, rồi mới khái niệm, rồi ví von đời thường.
- **Nối bức tranh lớn.** Mỗi thứ phải chỉ rõ nằm ở layer nào (domain/kernel/runtime/application/
  adapters/profiles) + phục vụ luồng pipeline nào.
- **Người học chủ động.** Xen câu "đoán thử trước khi xem" + ô tự kiểm.
- **KHÔNG name-drop để treo.** Bất kỳ khái niệm/thuật ngữ nhắc trong `00-cau-chuyen.md` (vd "6 layer",
  "port", "CoW") PHẢI kèm **gloss 1 dòng** hoặc **link glossary/knowledge-base** NGAY tại chỗ — đào sâu
  để dành mẩu sau. Người mới đọc cau-chuyen phải hiểu được bức tranh, không bị kẹt ở 1 từ lạ.
- **Giọng cho người mới.** Câu ngắn, không hù dọa, không từ to tát chưa giải thích.

---

## 3.5 🌀 VÒNG CUNG DẠY (bắt buộc — tầng CHỦ ĐỀ, đi từ VẤN ĐỀ tới giải pháp)
> Đây là cái còn thiếu nếu chỉ có template 14 mục. MỖI chủ đề (`<NN>-.../00-cau-chuyen.md`) PHẢI
> kể theo 6 nhịp dưới — TẠO "tension" (vấn đề) TRƯỚC khi "resolution" (giải pháp). Sau đó mới tới
> các file mẩu chi tiết (14 mục). Người học phải hiểu *tại sao cần*, không chỉ *cái gì*.

1. **Tổng quan (Big picture trước):** thứ này nằm ở đâu trong hệ (layer/pipeline), phục vụ gì, vẽ
   sơ đồ hộp+mũi tên → tạo "móc treo" gắn kiến thức (chống quá tải).
2. **Vấn đề & TẠI SAO nó là vấn đề (Forces):** nỗi đau cụ thể; các **lực giằng nhau** (A↔B); làm
   kiểu ngây thơ (naive) thì HỎNG ở đâu — cho người học *thấy đau* trước. Đặt ≥1 câu để họ tự đoán.
3. **Khám phá NHIỀU hướng/góc nhìn:** nêu **≥2 cách giải**, ưu/nhược + vì sao loại từng cách. Dẫn
   người học tự nghĩ hướng trước khi lộ đáp án (generation effect — tự vật lộn rồi mới xem).
4. **Chốt giải pháp + TẠI SAO nó thắng:** phương án chọn + lý do thắng các phương án kia (trade-off,
   không "đúng tuyệt đối"). Nếu là pattern: nối 2 câu gốc (what varies / hướng phụ thuộc).
5. **Dạy TRIỂN KHAI (code thật):** giờ mới vào code — qua các file mẩu nhỏ nhất (template 14 mục §4).
6. **NÊN LÀM / NÊN TRÁNH:** do's & don'ts cụ thể, anti-pattern, cạm bẫy (+link ERRATA), "khi nào KHÔNG dùng".

> Map khung sư phạm (§8): nhịp 1–3 ≈ Engage/Explore (5E) + "Hook the pain" + Forces; nhịp 4 ≈
> Explain + trade-off; nhịp 5 ≈ Elaborate (worked example); nhịp 6 + tự kiểm ≈ Evaluate.

## 4. CẤU TRÚC BẮT BUỘC mỗi file lesson (`_TEMPLATE-lesson.md`)
> Mỗi mục ghi RÕ "thông tin gì được phép vào" — để đúng thứ vào đúng chỗ. Xem template kèm.
Thứ tự cố định: (1) Thuộc về đâu → (2) Cần biết trước → (3) Code thật (quote) → (4) Giải thích
từng-dòng-nhỏ-nhất → (5) Là gì (1–2 câu) → (6) Tại sao tồn tại / vấn đề nó giải → (7) Dùng ở đâu
trong project → (8) Không có nó thì sao → (9) Ví von → (10) Liên kết bức tranh lớn → (11) Cạm bẫy
(+errata) → (12) Tự kiểm (retrieval + Feynman) → (13) Mốc ôn → (14) Nguồn (file code + Design step + độ chắc).

---

## 5. Cấu trúc thư mục `code-lessons/`
- `00-LESSON-RULES.md` — file này.
- `00-INDEX.md` — bản đồ: bài ↔ vấn đề #NN ↔ file code thật ↔ trạng thái.
- `_TEMPLATE-lesson.md` — khuôn bắt buộc.
- `<NN>-<chủ-đề>/` — 1 folder/chủ đề (bám vấn đề #NN trong implement). Trong đó nhiều file md nhỏ:
  `<kk>-<mẩu>.md` — mỗi file giảng 1 mẩu nhỏ nhất (1 file/1 dòng-hoặc-ý). Đánh số để đọc tuần tự.

---

## 6. Quy trình tạo 1 bài (AI tuân)
1. Đọc file code thật trong `vision-platform/` + Design step liên quan.
2. Chia chủ đề thành các mẩu nhỏ nhất → liệt kê trong `<NN>-.../00-muc-luc.md`.
3. Mỗi mẩu = 1 file md theo template §4, quote code đúng + cite path.
4. (Nếu có khẳng định hành vi) chạy thật / trích test đã pass.
5. Cập nhật `00-INDEX.md` (bài mới + trạng thái) + ghi log.
6. Báo trong chat NGẮN GỌN (không dán nội dung lesson vào chat).

## 7. Cổng "đã hiểu" (Feynman, theo AGENTS §1/§5)
Chỉ đánh dấu 1 mẩu ✅ khi người học **tự giải thích bằng lời mình** + trả lời được câu retrieval.
Chưa đạt → giữ 🔵 + chỉ rõ hổng. AI đóng vai người không biết gì, hỏi tới khi thông.

---
**Một câu:** Bài giảng = giải thích code THẬT (quote đúng, cite path, không bịa) từ mẩu nhỏ nhất,
luôn nói *tại sao tồn tại / dùng ở đâu / không có thì sao*, theo cơ chế học của não (chunk + why +
retrieval + ví von + ôn lại), kết bằng tự-giải-thích-lại.


---

## 8. Nguồn khung sư phạm (neo vào cái có thật — đã có công cụ web)
> Phiên này ĐÃ bật MCP `fetch` → verify được nguồn online. Độ tin: cao về *tên/khung* (có nguồn),
> vừa về *chi tiết áp dụng* (mình diễn giải lại, không trích nguyên văn).

- **Problem-Based Learning (PBL)** — ✅ verify qua web ([Wikipedia: Problem-based learning](https://en.wikipedia.org/wiki/Problem-based_learning)):
  học qua việc **giải một vấn đề mở**, không bắt đầu bằng bài giảng lý thuyết. **Quy trình Maastricht
  7 bước** khớp đúng "Vòng cung dạy" §3.5: làm rõ thuật ngữ → **định nghĩa vấn đề** → brainstorm
  (nhiều hướng) → cấu trúc/giả thuyết → mục tiêu học → tự nghiên cứu → **tổng hợp**. (Nội dung đã rephrase cho tuân thủ bản quyền.)
- **5E Instructional Model** (BSCS, Rodger Bybee): Engage → Explore → Explain → Elaborate → Evaluate.
  → khung gốc cho "Vòng cung dạy" §3.5.
- **"Make It Stick"** (Brown, Roediger, McDaniel 2014): retrieval practice, spaced repetition,
  interleaving, **generation effect** (tự vật lộn trước khi xem đáp án). → §2, §3.5 nhịp 3.
- **"Understanding by Design" / Backward Design** (Wiggins & McTighe): bắt đầu từ "hiểu để làm gì"
  + essential questions. → "WHY trước WHAT".
- **Cognitive Apprenticeship** (Collins, Brown, Newman): modeling → coaching → scaffolding →
  articulation → reflection → exploration.
- **Cognitive Load Theory** (Sweller) + **worked examples**. **Dual coding** (Paivio). **Feynman technique**.
- Sư phạm kỹ thuật phần mềm: **"Refactoring to Patterns"** (Kerievsky 2004 — "Hook the pain"),
  **POSA** (Buschmann — "Forces"), **"A Philosophy of Software Design"** (Ousterhout — *design it
  twice*, cân nhắc nhiều phương án), **"Clean Architecture"** (R.C. Martin). → §3.5 nhịp 2–4.
- Repo/tài liệu dạy nổi tiếng (tham chiếu khái niệm; fetch khi cần qua MCP `fetch`): system-design-primer,
  build-your-own-x, cosmicpython ("Architecture Patterns with Python").

> Có MCP `fetch`: khi đưa kiến thức/nguồn cụ thể → nên FETCH + gắn link thật trước khi coi là "đã verify nguồn" (AGENTS §5).
