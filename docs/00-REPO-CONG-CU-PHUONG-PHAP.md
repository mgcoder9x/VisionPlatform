# 🛠️ Hệ điều hành Học + Công cụ cho MỌI AI (FILE GỘP)

> Ba phần (file này gộp toàn bộ thiết kế công cụ; chỉ `AI-IMPLEMENTATION-LOG.md` để riêng):
> - **PHẦN A — Hệ điều hành học (dùng hằng ngày):** cách AI dạy bạn, tự chọn việc, lưu bài học, chống quên.
> - **PHẦN B — Catalog repo #1 theo lĩnh vực (tham chiếu):** chọn công cụ nào cho vấn đề nào.
> - **PHẦN C — Cài đặt + Tích hợp:** tải repo nào, đặt đâu, ráp lại thành một hệ thống ra sao.
>
> Mục tiêu tối thượng: **bạn hiểu hệ thống đủ sâu để TỰ VIẾT LẠI được từng dòng.**
> Triết lý nền: **luôn đưa MẨU NHỎ NHẤT — mỗi lần chỉ 1 ý hoặc 1 câu hỏi.** Không làm bạn ngợp.

---

# ⚡ PHẦN A — HỆ ĐIỀU HÀNH HỌC

## A1. Triết lý cốt lõi (luật bất biến cho AI)

1. **Nhỏ nhất mỗi lần.** Mỗi lượt CHỈ 1 mẩu kiến thức nhỏ nhất, HOẶC 1 câu hỏi. KHÔNG đổ một loạt.
2. **Hỏi rồi chờ.** Sau mỗi mẩu/câu hỏi, DỪNG, mở ô để bạn trả lời. Không tự đi tiếp.
3. **Không code hộ khi học.** AI giải thích + hỏi; bạn gõ. Sai → hỏi câu dẫn, không đưa đáp án.
4. **Không xóa, chỉ thêm.** Mọi thứ append vào file bài học → AI thấy được bạn học thế nào, ở level nào.
5. **Mọi thứ phải valid.** Đưa kiến thức → AI tự kiểm đúng/sai + độ chắc chắn. Code → chạy/test mới gọi "xong".

## A2. Luật ROUTER — AI tự chọn chế độ + skill (bạn KHÔNG phải tự chọn)

AI đọc câu của bạn, tự phân loại và tự áp đúng chế độ + skill agent-skills. Khi đoán sai,
bạn gõ **phím override** ở đầu câu: `[học]` `[xây]` `[ôn]` `[review]`.

| Tín hiệu trong câu của bạn | Chế độ AI tự bật | agent-skill dùng |
|---|---|---|
| "giải thích / tại sao / là gì / hiểu" | **HỌC** (Socratic, 1 câu hỏi/lần) | `interview-me`, `doubt-driven-development` |
| "làm / thêm / sửa / build / triển khai" | **XÂY** (spec → task nhỏ → diff → test) | `spec-driven` → `planning` → `incremental` → `tdd` |
| "review / kiểm tra code này" | **REVIEW** | `code-review-and-quality` |
| "ôn / tự viết lại / kiểm tra tôi" | **RECALL** (bắt bạn viết lại từ trí nhớ) | dùng luật dạy A4 |
| câu ngắn tra cứu | **HỎI NHANH** (≤3 câu) | — |
| lạc đề | đánh dấu **[ngoài lề]**, không ghi bài học | — |

> Đầu mỗi câu, AI nói 1 dòng: "→ Chế độ: HỌC" để bạn biết nó vào đúng chưa.

## A3. Hệ thống thư mục bài học

```
lessons/
├── 00-LEARNING-MAP.md              ← bản đồ: tôi đang ở đâu, level, cách học (append)
├── 01-<chu-de>/
│   ├── 00-plan.md                  ← KẾ HOẠCH bài: dạy gì, cần biết gì, tiêu chí đậu
│   ├── lesson_01.md                ← buổi dạy (append-only: mẩu nhỏ + câu hỏi + ô Hỏi-Đáp)
│   ├── lesson_02.md
│   └── ...
├── 02-<chu-de>/
│   └── ...
```

### Template `00-plan.md` (file đầu mỗi bài — AI tạo trước khi dạy)
```markdown
# Bài <NN>: <Tên> — KẾ HOẠCH

## Mục tiêu (học xong LÀM ĐƯỢC gì)
- ...

## Các vấn đề sẽ dạy (đã chia nhỏ, theo thứ tự)
1. ...
2. ...

## Cần biết trước (tiên quyết)
- ...

## Tiêu chí ĐẬU (làm được mới qua bài)
- [ ] Tự giải thích <X> bằng 3 câu không thuật ngữ
- [ ] Tự viết lại <Y> từ trí nhớ
- [ ] Test xanh cho <Z>

## Nguồn tham chiếu (AI đã tự valid)
- <nguồn> — độ chắc chắn: <cao/vừa/thấp>
```

### Template `lesson_<kk>.md` (buổi dạy — APPEND-ONLY)
```markdown
# Bài <NN> — Buổi <kk> (<ngày>)
> Quy tắc: mỗi lần CHỈ 1 mẩu nhỏ nhất + 1 câu hỏi. Không xóa, chỉ thêm.

## [AI] Mẩu #1 (nhỏ nhất)
<1 ý duy nhất, ngắn>
**Tự valid:** <đúng không / nguồn / độ chắc chắn>

## [AI] Câu hỏi #1
<chỉ 1 câu>

## [BẠN] Trả lời #1
<bạn gõ vào đây>

## [AI] Nhận xét #1
<đúng/sai chỗ nào; nếu sai → câu dẫn dắt, KHÔNG đưa đáp án>

---
<lặp lại Mẩu #2 / Câu hỏi #2 ... khi bạn đã trả lời #1>
```

### Template `00-LEARNING-MAP.md` (bản đồ — AI cập nhật, append)
```markdown
# 🗺️ Bản đồ học — tôi đang ở đâu

## Hồ sơ người học (AI tự quan sát + append, không xóa)
- Level hiện tại: <...>
- Cách học hợp: <thích ví dụ trước / hỏi nhiều / ...>
- Hay vướng ở: <...>

## Trạng thái bài học
| Bài | Chủ đề | Trạng thái | Buổi gần nhất |
|-----|--------|-----------|---------------|
| 01 | ... | đang học / ĐẬU | lesson_03 |

## Con trỏ HIỆN TẠI (chân lý)
- Bài <NN>, buổi <kk>, mẩu <#>. Bước kế: <...>
```

### Khu kiến thức tái dùng — `knowledge-base/`
Concept/pattern dùng nhiều lần học MỘT lần ở `knowledge-base/<concept>/`. **Học concept =
tạo folder + chia buổi** (giống lessons): `00-plan.md` + `lesson_kk.md` (1 mẩu/1 câu hỏi,
append-only) → kết tinh `README.md` khi ĐẬU → trạng thái ✅ trong `00-INDEX.md`. Lesson dự án
PHẢI nêu "cần học trước" + link knowledge-base; concept chưa nắm → **AI bảo ra đó học trước**;
đã nắm → chỉ LINK, không dạy lại. Mỗi concept: cần biết trước + cần gì để làm được.

## A4. Luật DẠY (chi tiết)
- Mỗi lượt: **1 mẩu HOẶC 1 câu hỏi** → rồi ô `[BẠN] Trả lời` → rồi `[AI] Nhận xét`.
- **Append-only:** không sửa/xóa mẩu cũ. Hiểu sai trước đó vẫn giữ lại (để thấy tiến bộ).
- Khi nêu "cần biết gì": cũng **chỉ nêu mẩu nhỏ nhất kế tiếp**, không liệt kê hết.
- Luôn có **chỗ cho bạn hỏi lại** ở cuối mỗi mẩu.

## A5. Luật VALIDATE (chống sai + chống nợ kỹ thuật)
- **Kiến thức:** trước khi đưa, AI tự kiểm bằng lý lẽ + nguồn chính thống (`source-driven`),
  ghi **độ chắc chắn**. Không chắc → nói rõ "chưa chắc", không bịa.
- **Code:** AI/bạn chạy + test trước khi gọi "xong". Báo rõ **ĐÃ verify gì / CHƯA gì + vì sao**.
- Nghi ngờ điểm quan trọng → dùng `doubt-driven-development` (tự phản biện trước khi chốt).

## A6. Luật HANDOFF (4 agent phối hợp) + CHECKPOINT (chống crash)

**Handoff — các tool cộng tác qua FILE chung, không chat trực tiếp:**
```
Gemini  → đọc/giải thích → ghi phát hiện vào lessons/.../lesson_kk.md + activeContext.md
Kiro    → đọc activeContext → tạo plan/spec + task nhỏ
Codex   → đọc plan → bạn gõ code → ghi AI-IMPLEMENTATION-LOG.md
Copilot → hỏi nhanh, không ghi
```

**Checkpoint — nếu app tắt giữa chừng:**
- Câu trả lời đang dở (chưa ghi file) = mất. File đã ghi = an toàn.
- Vì vậy: AI ghi `Con trỏ HIỆN TẠI` trong LEARNING-MAP **ở ĐẦU mỗi mẩu** (không đợi cuối).
- Mỗi task code xong → `git commit` (save-point). Crash → đọc MAP + log + `git log` để tiếp.
- Mở phiên mới: AI đọc `LEARNING-MAP.md` + `memory-bank/activeContext.md` + 5 entry log cuối TRƯỚC khi làm.

---

# 📚 PHẦN B — Catalog repo #1 theo lĩnh vực (tham chiếu)

> Không có repo "#1 tổng thể". Mỗi vấn đề chọn cái #1 của lĩnh vực đó.

| # | Vấn đề / Lĩnh vực | Repo #1 | 🏛️ Ai làm |
|---|-------------------|---------|-----------|
| A | Chuẩn ngữ cảnh portable | [openai/agents.md](https://github.com/openai/agents.md) | OpenAI / Linux Foundation |
| B | Quy trình spec-driven | [github/spec-kit](https://github.com/github/spec-kit) | GitHub/Microsoft |
| C | Kỷ luật + chống drift + sư phạm | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Addy Osmani (Google) |
| D | Bộ nhớ markdown | [cline/cline](https://github.com/cline/cline) "Memory Bank" | Cline team |
| D'| Bộ nhớ "thông minh" (chống dữ liệu cũ) | [mem0ai/mem0](https://github.com/mem0ai/mem0) | Mem0 |
| E | Hiểu codebase nhanh (tùy chọn) | [PocketFlow-Tutorial-Codebase-Knowledge](https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge) | Zachary Huang |
| F | Nguyên lý xây agent | [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) | HumanLayer |
| G | Học cách hỏi AI / prompt | [anthropics/courses](https://github.com/anthropics/courses) | Anthropic |
| H | Học nội dung kiến trúc | → `00-COMPANION-REPO-VA-LO-TRINH.md` | cosmicpython... |

**Vì sao #1 (gọn):**
- **A** — chuẩn mở duy nhất nhiều tool đọc native. *(đã tạo `AGENTS.md`)*
- **B** — chính chủ GitHub, chuẩn mực nhất về quy trình spec. Á quân: `gotalab/cc-sdd`.
- **C** — duy nhất có *anti-rationalization tables* + *verification gates* (chống AI đi đường tắt) + skill sư phạm. ⚠️ **TẮT `/build auto` khi học.** #1 ở lĩnh vực này, KHÔNG phải tổng thể.
- **D** — chuẩn markdown-memory có tên; `activeContext`+`progress` là "sự thật hiện tại" (chống dữ liệu cũ). 6 file: Phần C.
- **D'** — tự update/xoá/hợp nhất ký ức mâu thuẫn (markdown không làm được). Dùng khi project lớn.
- **E** — auto-sinh tutorial từ repo. *Tùy chọn.* Framework PocketFlow thì **KHÔNG cần**.
- **F/G** — nguyên lý agent + cách hỏi; tham khảo theo nhu cầu.

---

# 🔧 PHẦN C — Cài đặt + Tích hợp

## C0. Vì sao phải tải thật (không dựa vào luật AI tự bịa)
Luật AI gõ trong chat = mong manh: phiên sau / tool khác không chắc tuân. **Repo tải về =
artifact trong ổ đĩa, tool tự nạp, không phụ thuộc trí nhớ AI.** → Thứ gì muốn AI *luôn*
tuân phải thành **file thật** (skill/rule/memory) trong repo.

## C1. Kiến trúc tích hợp — `AGENTS.md` là trung tâm
```
                         ┌─────────────────┐
                         │   AGENTS.md      │  ← trung tâm: index + luật, mọi tool đọc
                         └────────┬─────────┘
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
     ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
     │ .kiro/skills/   │  │  memory-bank/   │  │    specs/       │
     │ (agent-skills)  │  │ (Cline pattern) │  │  (spec-kit)     │
     └────────────────┘  └────────────────┘  └────────────────┘
              │                   │                   │
              └─ lessons/ + AI-IMPLEMENTATION-LOG.md (học + hộp đen) ─┘
```
Các tool **không chat trực tiếp** — chúng cùng đọc/ghi các file trên. `AGENTS.md` trỏ tới tất cả.

## C2. Bảng tải/cài + trạng thái thật
| Repo | Lệnh tải/cài | Đặt vào | Ai cài | Trạng thái |
|------|--------------|---------|--------|-----------|
| AGENTS.md (chuẩn) | (tự viết) | gốc repo | — | ✅ Đã có |
| **agent-skills** | `git clone https://github.com/addyosmani/agent-skills.git` | `.kiro/skills/` | Kiro (tôi) | ✅ Đã cài (22 skill; gốc ở `external/`) |
| Cline Memory Bank | (tạo folder + 6 file) | `memory-bank/` | Kiro (tôi) | ⏳ |
| lessons | (tạo folder) | `lessons/` | Kiro (tôi) | ⏳ |
| spec-kit | `specify init` | `specs/` | bạn (CLI) | ⏳ |
| mem0 / MCP memory | cấu hình `mcp.json` | `.kiro/settings/` | Kiro (tôi) | ⏳ (khi cần) |

**Giới hạn thật:** trong workspace tôi (Kiro) cài được `.kiro/skills/`, `memory-bank/`, MCP,
AGENTS.md. **Tôi KHÔNG vào app Codex/Gemini/Copilot của bạn được** — 3 tool đó bạn tự cài,
nhưng đều trỏ về cùng `AGENTS.md` + đọc cùng `memory-bank/`, `lessons/`.

## C3. Cấu trúc bộ nhớ Cline Memory Bank (`memory-bank/`, 6 file)
| File | Nội dung | Đổi |
|------|----------|-----|
| `projectbrief.md` | Mục tiêu, phạm vi | Hiếm |
| `productContext.md` | Vì sao học/xây | Hiếm |
| `systemPatterns.md` | Kiến trúc, import 6 layer | Khi có quyết định |
| `techContext.md` | Stack, ràng buộc | Khi đổi công cụ |
| **`activeContext.md`** | ĐANG làm gì, bước kế | **Mỗi phiên** (chân lý) |
| **`progress.md`** | Xong gì / còn gì / bug | **Mỗi phiên** (chân lý) |

> `lessons/00-LEARNING-MAP.md` = trục **HỌC**; `memory-bank/progress.md` = trục **XÂY**. AI đọc cả hai đầu phiên.

## C4. Cài theo 4 tool của bạn
| Tool | File luật | Làm | agent-skills |
|------|-----------|-----|--------------|
| Codex | `AGENTS.md` | đọc native — xong | tham chiếu trong AGENTS.md |
| Kiro | `.kiro/steering/` | ✅ `00-core-rules.md` trỏ về AGENTS.md | ✅ `.kiro/skills/` (đã cài) |
| Gemini | `GEMINI.md` | tạo: "Follow AGENTS.md" + luật A1/A2 | `gemini skills install <repo> --path skills` |
| Copilot | `.github/copilot-instructions.md` | tạo: "Follow AGENTS.md" + luật A1/A2 | persona trong `agents/` |

- **spec-kit:** `specify init` (hoặc đọc `spec-driven.md` lấy tư duy). **Tắt `/build auto` khi học.**

## C5. Lộ trình kích hoạt
| Phase | Làm | Trạng thái |
|-------|-----|-----------|
| 0 | `AGENTS.md` + log + Kiro steering + cài agent-skills vào Kiro | ✅ |
| 1 | Tạo `lessons/` + `memory-bank/` + mirror Gemini/Copilot | ✅ |
| 2 | Xây thật: Spec đầu tiên theo module `Design/` (spec-kit) | ⏳ kế tiếp |
| 3 | Project lớn: nâng `mem0`/MCP memory | ⏳ |

## C6. Bộ tối thiểu (đừng ôm hết)
`AGENTS.md` + Cline Memory Bank + `lessons/` + `AI-IMPLEMENTATION-LOG.md` + agent-skills (đã cài, tắt auto) + spec-kit (đọc 1 lần). Còn lại: tham khảo theo nhu cầu.

## C7. ❌ KHÔNG thêm
Framework PocketFlow · repo code dự án mẫu · nhiều memory tool song song · trùng vai (đã có agent-skills thì khỏi đọc sâu task-master/BMAD).

---

## 📋 Ghi chú Triển khai
> File này chỉ tóm tắt. Hộp đen đầy đủ (4 mục bắt buộc + lịch sử) ở `AI-IMPLEMENTATION-LOG.md`.
- **Đã gộp** `00-INTEGRATION-SETUP.md` vào Phần C (xóa file đó).
- **Đã làm thật:** agent-skills cài vào `.kiro/skills/` (22 skill), validated.
- **CHƯA tạo (Phase 1):** `lessons/`, `memory-bank/`, `GEMINI.md`, `.github/copilot-instructions.md`.
