# 🧰 AI Learning OS Kit — bộ khởi tạo tái dùng cho dự án mới

> Đây là bản **trích + genericized** của "hệ điều hành học" mà ta đã xây trong VisionPlatform.
> Copy kit này vào dự án mới, điền placeholder `{{...}}`, là có ngay: luật chung cho mọi AI,
> bộ nhớ bền, log chống drift, quy trình học/triển khai.

## Kit gồm gì
| File template | Copy tới đâu trong dự án mới | Vai trò |
|---------------|------------------------------|---------|
| `AGENTS.template.md` | `AGENTS.md` (gốc repo) | Luật trung tâm, mọi AI đọc |
| `GEMINI.template.md` | `GEMINI.md` (gốc repo) | Mirror cho Gemini |
| `copilot-instructions.template.md` | `.github/copilot-instructions.md` | Mirror cho Copilot |
| `kiro-steering-core-rules.template.md` | `.kiro/steering/00-core-rules.md` | Mirror cho Kiro (always-load) |
| `AI-IMPLEMENTATION-LOG.template.md` | `AI-IMPLEMENTATION-LOG.md` | Hộp đen quyết định (4 mục) |
| `memory-bank/*.md` | `memory-bank/` | Bộ nhớ giữa phiên (chuẩn Cline) |
| `lessons/00-LEARNING-MAP.template.md` | `lessons/00-LEARNING-MAP.md` | Bản đồ học |
| `METHODOLOGY.md` | giữ làm tài liệu tham chiếu | Hệ điều hành học + catalog repo |

## Cách dùng (6 bước)
1. Copy toàn bộ template vào dự án mới (đổi tên `.template.md` → `.md`, đặt đúng chỗ ở bảng trên).
2. Tìm & thay mọi placeholder `{{PROJECT_NAME}}`, `{{PROJECT_DESC}}`, `{{ARCH_RULES}}`, `{{STACK}}`, `{{REVIEW_CHECKLIST}}`.
3. Cài agent-skills: `git clone https://github.com/addyosmani/agent-skills.git` → copy `skills/*` vào `.kiro/skills/` (Kiro) / theo lệnh từng tool.
4. Điền `memory-bank/projectbrief.md` + `productContext.md` cho dự án mới.
5. Mở phiên AI bất kỳ → nó đọc AGENTS.md → tự áp router/sư phạm/log/validate.
6. (Nhắc) sửa AGENTS.md thì đồng bộ tay GEMINI.md + copilot (mirror là bản tĩnh).

## Nguồn gốc (repo gốc của từng ý)
- Chuẩn AGENTS.md: `openai/agents.md` (Linux Foundation)
- Skill quy trình/kỷ luật: `addyosmani/agent-skills`
- Bộ nhớ markdown: `cline/cline` Memory Bank
- Bộ nhớ thông minh (nâng cấp): `mem0ai/mem0`
- Quy trình spec: `github/spec-kit`
→ Chi tiết "vấn đề nào dùng repo nào": xem `METHODOLOGY.md`.

## Giới hạn trung thực
- Luật = chỉ thị LLM đọc, KHÔNG cưỡng chế tuyệt đối; tải về giúp bền + tự nạp.
- Validate kiến thức là best-effort (không chặn 100% hallucination); chỉ code validate khách quan bằng test.
- Mirror (GEMINI/Copilot) là bản TĨNH — sửa AGENTS.md phải đồng bộ tay.
