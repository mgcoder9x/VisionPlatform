# 📚 Knowledge Base — kiến thức sách vở TÁI DÙNG (học MỘT lần)

> Khu này KHÁC `lessons/`:
> - `lessons/` = trình tự + thực hành theo dự án (học theo buổi).
> - `knowledge-base/` = **kiến thức về 1 concept/pattern**, học MỘT lần, nhiều lesson **link tới**.
>
> Lý do: cùng 1 pattern có thể xuất hiện ở nhiều lesson — KHÔNG học lại mỗi lần. Học ở đây,
> đánh dấu "đã nắm", lesson chỉ tham chiếu.

## ⚖️ NHỎ hay LỚN? (luật định tuyến — quyết định để đúng chỗ)
| Loại | Định nghĩa | Để ở đâu |
|------|-----------|----------|
| **Kiến thức NHỎ** | thuật ngữ ngắn, tra là hiểu, không cần luyện (pip, venv, src layout...) | 1 mục trong `00-GLOSSARY.md` |
| **Kiến thức LỚN** | khái niệm cần HỌC SÂU + luyện (hexagonal, backpressure, GIL...) | **folder riêng** `<concept>/` |

- `_pattern-method/` = **bộ phương pháp + mẫu** (cách học + POSA + taxonomy + quiz) DÙNG ĐỂ học
  kiến thức lớn; **không phải nơi chứa** kiến thức lớn. Mỗi kiến thức lớn sống ở folder riêng của nó.
- Phân vân nhỏ/lớn? Hỏi: *"tra 1 dòng là xong, hay phải luyện tới Level 4?"* — luyện → LỚN → folder.
- Từ trong glossary nếu "phình" thành cần học sâu → nâng cấp: tạo folder `<concept>/`, glossary chỉ giữ 1 dòng + link "Học sâu".

## 📖 Thuật ngữ → `00-GLOSSARY.md`
Giải thích thuật ngữ (pip, venv...) ở `knowledge-base/00-GLOSSARY.md` (1 lần, dùng mọi bài).
Bài dạy chỉ LINK tới, không giải thích inline.

## 🧭 Học một PATTERN → `_pattern-method/`
Concept là **pattern/nguyên lý kiến trúc** (hexagonal, bulkhead, backpressure...) → tuân
`_pattern-method/00-PATTERN-METHOD.md` (5 cấp có test · 4 bước Hook→Read→Draw→Transfer · 2 câu hỏi gốc) và điền
theo `_pattern-method/_TEMPLATE-pattern.md` (POSA 5-box + Diagnostic + Recognize). Tier của pattern → `_pattern-method/00-TAXONOMY.md`.
Ôn tập → `_pattern-method/_TEMPLATE-quiz.md`. Concept "thường" (không phải pattern) vẫn dùng `_templates/_TEMPLATE.md`.

## Quy tắc (AI tuân — xem AGENTS.md §1.6)
1. Trước khi dạy 1 concept trong lesson → kiểm bảng dưới.
2. Concept đã ✅ nắm → lesson chỉ **link**, KHÔNG dạy lại.
3. Concept chưa có / chưa nắm → **học trong `knowledge-base/<concept>/` trước** (lesson dự án
   dừng lại, AI nói "ra đó học trước"), rồi quay lại lesson.
4. **Học 1 concept = tạo folder + chia buổi** (giống lessons):
   `<concept>/00-plan.md` (theo `_templates/_TEMPLATE-plan.md`) → mỗi buổi folder `<concept>/<kk>-<buổi>/lesson.md`
   (1 mẩu/1 câu hỏi, append-only, ô Hỏi/Đáp) → khi ĐẬU kết tinh vào `<concept>/README.md`
   (concept thường: `_templates/_TEMPLATE.md`; **pattern: `_pattern-method/_TEMPLATE-pattern.md` + tuân `_pattern-method/00-PATTERN-METHOD.md`**)
   + đổi trạng thái ✅ + back-link lesson dùng nó.
5. Folder concept tạo **khi bắt đầu học** (không tạo rỗng hàng loạt).

## Danh mục kiến thức (cập nhật trạng thái khi học)
Trạng thái: ⬜ chưa học · 🔵 đang học · ✅ đã nắm (= đạt **Level 4**). Cột **Level** = thang 5 cấp (`_pattern-method/00-PATTERN-METHOD.md`).

| Concept | Trạng thái | Level | Tier | Module gốc | Folder |
|---------|-----------|-------|------|------------|--------|
| Hexagonal / Ports & Adapters | ✅ | 4 — Master | Architectural pattern | 02 | `pattern-study/pattern-study/hexagonal/` (bản gốc, đã học thật) |
| Coupling & Cohesion | ⬜ | 1 | Principle | 01 | `coupling-cohesion/` |
| Dependency direction | ⬜ | 1 | Principle | 01 | `dependency-direction/` |
| Bulkhead | ⬜ | 1 | Resilience pattern | 02 | `bulkhead/` |
| Backpressure | ⬜ | 1 | Resilience pattern | 02 | `backpressure/` |
| Immutability & CoW | ⬜ | 1 | Mechanism | 02 | `immutability-cow/` |
| GIL | ⬜ | 1 | Mechanism | 04 | `gil/` |
| SHM atomicity | ⬜ | 1 | Mechanism | 04 | `shm-atomicity/` |
| ZMQ patterns | ⬜ | 1 | Mechanism | 04 | `zmq-patterns/` |
| Asyncio event loop | ⬜ | 1 | Mechanism | 04 | `asyncio-event-loop/` |
| Circuit breaker | ⬜ | 1 | Resilience pattern | 04 | `circuit-breaker/` |

> Thêm concept mới vào bảng khi gặp. Tier → `_pattern-method/00-TAXONOMY.md`.
> **Lưu ý Hexagonal:** đã học thật tới Level 4 trong `pattern-study/` (bản C#, có session + quiz + POSA điền đủ).
> Gộp "Hexagonal architecture" + "Ports & Adapters" làm MỘT (chúng là cùng pattern, tránh học 2 lần).
