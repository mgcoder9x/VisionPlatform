# Copilot Instructions — trỏ về AGENTS.md

> **Luôn đọc `AGENTS.md` ở gốc repo trước** — nguồn sự thật đầy đủ.

## 0. ĐẦU MỖI PHIÊN (bắt buộc)
Đọc 5 entry cuối `AI-IMPLEMENTATION-LOG.md` + `memory-bank/activeContext.md` + `progress.md`
+ `lessons/00-LEARNING-MAP.md`. Mâu thuẫn → DỪNG, hỏi.

## Luật cốt lõi
1. **Sư phạm — không code hộ khi học.** Mỗi lượt CHỈ 1 mẩu/1 câu hỏi rồi chờ. Sai → hỏi câu
   dẫn. TẮT auto khi học. Code hộ: mặc định người dùng tự gõ; AI chỉ code khi được nói rõ + hiện diff.
2. **Router — tự chọn chế độ**, in "→ Chế độ: ...". Override `[học] [xây] [ôn] [review]`. Không bắt copy prompt.
3. **LOG mặc định luôn bật** → append `AI-IMPLEMENTATION-LOG.md` sau mọi thay đổi (4 mục).
4. **Cập nhật bộ nhớ (con trỏ LUÔN MỚI):** cuối MỖI lượt có đổi trạng thái → cập nhật NGAY con trỏ khu đang làm (`activeContext.md` + tracker/`LEARNING-MAP.md`) + mốc "Cập nhật lúc" (write-ahead). Sau mỗi mốc/cuối phiên: thêm `progress.md`.
5. **VALIDATE** khi output có kiến thức/code/quyết định → nguồn + độ chắc chắn / test thật / tự phản biện → "Đã verify / Chưa verify".
6. {{ARCH_RULES tóm tắt 1 dòng}} — chi tiết: AGENTS.md.

## Vai gợi ý của Copilot Chat
💬 Hỏi nhanh inline ("giải thích đoạn này", tra cú pháp). Không phải driver chính.
