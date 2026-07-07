# specs/ — Spec-Driven Development (GitHub spec-kit)

> Lấy từ `github/spec-kit` (clone ở `external/spec-kit/`). Đây là **template + command** dùng
> được NGAY bằng tay. CLI `specify` (cần `uv`) sẽ cài ở **bài hướng dẫn môi trường** sau.

## Có gì ở đây
- `templates/` — khung tài liệu: `constitution-template.md`, `spec-template.md`,
  `plan-template.md`, `tasks-template.md`, `checklist-template.md`.
- `commands/` — prompt quy trình spec-kit: `constitution`, `specify`, `clarify`, `plan`,
  `tasks`, `analyze`, `implement`, `checklist`, `taskstoissues`.

## Dùng thủ công (chưa cần CLI) — quy trình
```
constitution  → đặt nguyên tắc dự án (1 lần)
   ↓
specify        → viết spec (cái gì, cho ai, vì sao) → specs/<feature>/spec.md
   ↓
clarify        → AI hỏi lại chỗ mơ hồ trước khi plan
   ↓
plan           → thiết kế kỹ thuật → specs/<feature>/plan.md
   ↓
tasks          → chia task atomic → specs/<feature>/tasks.md
   ↓
analyze        → soát chéo spec↔plan↔tasks (nhất quán, đủ)
   ↓
implement      → làm từng task (theo luật sư phạm: bạn tự gõ khi học)
```
Cách dùng: mỗi feature tạo folder `specs/<feature>/`, copy template tương ứng vào rồi điền;
hoặc dán nội dung `commands/<bước>.md` cho AI để nó chạy đúng bước đó.

## Khi nào dùng cái gì
- **Spec-kit** = quy trình spec hình thức (cho mọi tool, gồm Codex/Gemini/Copilot).
- **Kiro** có Spec native riêng — có thể dùng thẳng trong IDE; spec-kit ở đây để các tool khác + để học tư duy SDD.
- **agent-skills** = kỷ luật/sư phạm bao trùm; spec-kit = khung tài liệu spec cụ thể. Hai cái bổ trợ.

## CHƯA làm (để bài môi trường)
- Cài `uv` + chạy `specify init` (tự sinh slash-command + scripts per tool). Hiện dùng template thủ công là đủ.
