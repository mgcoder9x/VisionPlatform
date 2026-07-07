# systemPatterns.md — Kiến trúc & quyết định (đổi khi có quyết định mới)

## Pattern cốt lõi (Module 02)
- Hexagonal / Ports & Adapters
- Bulkhead (1 camera/process — lỗi không lan)
- Backpressure (hàng đợi có giới hạn, 4 policy: DROP_OLDEST/DROP_NEWEST/BLOCK/REJECT)
- Immutability + Copy-on-Write

## Quy tắc import 6 layer (KHÔNG vi phạm)
- **domain**: Python thuần + numpy. KHÔNG cv2/torch/ZMQ.
- **kernel**: ports + DTOs. KHÔNG adapter cụ thể.
- **runtime**: chỉ phụ thuộc kernel.
- **application**: phụ thuộc kernel + runtime.
- **adapters**: phụ thuộc kernel.
- **profiles**: composition root, phụ thuộc mọi thứ.

## Quyết định công cụ (hệ điều hành học)
- AGENTS.md = luật trung tâm; mirror sang GEMINI.md + .github/copilot-instructions.md + .kiro/steering.
- agent-skills (22 skill) cài tại .kiro/skills/ — quy trình + kỷ luật + sư phạm.
- Bộ nhớ = Cline Memory Bank (folder này). Log quyết định = AI-IMPLEMENTATION-LOG.md.

## Quyết định: agent-skills làm XƯƠNG SỐNG (chốt 2026-06-13)
- Mảng quy trình/kỷ luật/sư phạm → dùng **agent-skills** (gộp), KHÔNG lắp best-of-breed từng cái.
- Lý do: 1 người học cần nhất quán + ít bảo trì + chống rác > độ sâu chuyên biệt.
- Nguyên tắc: "khởi đầu gộp, chỉ chuyên biệt khi chạm trần".
- spec-kit: **ĐÃ lấy template về `specs/`** (dùng thủ công); CLI `specify` (cần uv) chờ bài môi trường. task-master/BMAD/cc-sdd: bỏ (trùng).
  mem0/MCP memory: chờ khi project lớn (markdown đủ).

## Definition of Done — khi viết code (Module 03+)
- Bắt buộc tích hợp **Architecture Linter** (import-linter hoặc `tests/test_architecture_layers.py`
  bằng AST) kiểm import 6 layer; pass linter mới tính "xong" buổi code. Dựng KHI có code thật (chưa làm).
