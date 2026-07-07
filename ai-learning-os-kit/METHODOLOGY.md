# 📐 METHODOLOGY — Hệ điều hành Học + Công cụ cho mọi AI (bản tái dùng)

> Genericized từ dự án gốc. Ba phần: A (cách AI dạy/làm), B (repo #1 mỗi lĩnh vực), C (cài đặt + tích hợp).
> Triết lý nền: **mẩu nhỏ nhất — mỗi lượt 1 ý hoặc 1 câu hỏi.** Không làm người học ngợp.

---

## PHẦN A — Hệ điều hành học

**A1. Triết lý (luật bất biến):** (1) nhỏ nhất mỗi lần; (2) hỏi rồi chờ; (3) không code hộ
khi học; (4) không xóa, chỉ thêm vào file học; (5) mọi thứ phải validate.

**A2. Router** — AI tự phân loại câu hỏi → tự áp chế độ + skill, in "→ Chế độ: X":
| Tín hiệu | Chế độ | skill |
|---|---|---|
| giải thích / tại sao / là gì | HỌC (Socratic, 1 câu hỏi) | `interview-me`, `doubt-driven-development` |
| làm / sửa / build | XÂY (spec → task nhỏ → diff → test) | `spec-driven`→`planning`→`incremental`→`tdd` |
| review code | REVIEW | `code-review-and-quality` |
| ôn / tự viết lại | RECALL | luật dạy A4 |
| lạc đề | [ngoài lề], không ghi | — |
Override: `[học] [xây] [ôn] [review]`.

**A3. Thư mục bài học:**
```
lessons/
├── 00-LEARNING-MAP.md     ← bản đồ: đang ở đâu, level, cách học
└── <NN>-<chủ-đề>/
    ├── 00-plan.md         ← dạy gì, cần biết gì, tiêu chí đậu
    └── lesson_<kk>.md     ← buổi dạy (append-only: mẩu nhỏ + câu hỏi + ô [BẠN] Trả lời + [AI] Nhận xét)
```

**A3.5. Khu kiến thức tái dùng `knowledge-base/`:** concept tái dùng học MỘT lần. **Học concept
= tạo folder + chia buổi** (`00-plan.md` + `lesson_kk.md`, 1 câu hỏi/lần) → kết tinh `README.md`
khi ĐẬU. Lesson dự án nêu "cần học trước" + link; chưa nắm → ra knowledge-base học trước; đã nắm → chỉ LINK.

**A4. Luật dạy:** mỗi lượt 1 mẩu HOẶC 1 câu hỏi → ô trả lời → nhận xét. Append-only. Luôn có chỗ hỏi lại.

**A4.5. Cập nhật bộ nhớ (chống dữ liệu cũ):** sau mỗi mốc/cuối phiên → cập nhật
`memory-bank/activeContext.md` + `progress.md` (chân lý hiện tại); học tiến triển → `LEARNING-MAP.md`.
File nền chỉ đổi khi thay đổi lớn; mâu thuẫn thì activeContext/progress THẮNG.

**A5. Validate:** kiến thức (nguồn + độ chắc chắn) · code (test thật) · quyết định (doubt-driven).
Mọi phản hồi kết "Đã verify / Chưa verify". Không khẳng định nào thiếu cách-đã-kiểm.

**A6. Handoff + Checkpoint:** các tool cộng tác qua FILE chung (không chat trực tiếp). Ghi
"con trỏ hiện tại" ở đầu mỗi mẩu + git commit mỗi task → chống mất khi app tắt giữa chừng.

---

## PHẦN B — Catalog repo #1 theo lĩnh vực (chọn theo merit, không ép một repo làm tất cả)

| Vấn đề | Repo #1 | Ai làm |
|--------|---------|--------|
| Chuẩn ngữ cảnh portable | [openai/agents.md](https://github.com/openai/agents.md) | OpenAI / Linux Foundation |
| Quy trình spec-driven | [github/spec-kit](https://github.com/github/spec-kit) | GitHub |
| Kỷ luật + chống drift + sư phạm | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Addy Osmani (Google) |
| Bộ nhớ markdown | [cline/cline](https://github.com/cline/cline) Memory Bank | Cline team |
| Bộ nhớ thông minh (chống dữ liệu cũ) | [mem0ai/mem0](https://github.com/mem0ai/mem0) | Mem0 |
| Hiểu codebase (tùy chọn) | [PocketFlow-Tutorial-Codebase-Knowledge](https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge) | Zachary Huang |
| Nguyên lý agent đáng tin cậy | [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) | HumanLayer |
| Học cách hỏi AI | [anthropics/courses](https://github.com/anthropics/courses) | Anthropic |

❌ KHÔNG cần: framework PocketFlow (xây LLM app); nhiều memory tool song song; trùng vai.

---

## PHẦN C — Cài đặt + Tích hợp

**Kiến trúc:** `AGENTS.md` là trung tâm → trỏ tới `.kiro/skills/` (agent-skills), `memory-bank/`
(Cline), `lessons/`, `AI-IMPLEMENTATION-LOG.md`. Các tool ráp qua các file này, không chat trực tiếp.

**Bộ nhớ Cline (6 file `memory-bank/`):** projectbrief · productContext · systemPatterns ·
techContext · **activeContext** (chân lý hiện tại) · **progress** (chân lý hiện tại). Đọc
activeContext/progress trước để chống dữ liệu cũ.

**Cài theo tool:** Codex đọc AGENTS.md native; Kiro `.kiro/steering/` + `.kiro/skills/`;
Gemini `GEMINI.md` + `gemini skills install`; Copilot `.github/copilot-instructions.md`.

**Lộ trình:** (0) luật + skill + log → (1) memory-bank + lessons + mirror → (2) spec-kit khi
xây code → (3) mem0/MCP khi project lớn.

**Giới hạn trung thực:** luật = chỉ thị (không cưỡng chế tuyệt đối); validate kiến thức là
best-effort; mirror là bản tĩnh (sửa AGENTS.md phải đồng bộ tay).
