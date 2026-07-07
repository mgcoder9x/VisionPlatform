# 🧭 AI Decision Journal — Sổ quyết định AI (xuyên suốt, để kiểm chứng)

> **Mục đích (do người dùng yêu cầu):** một nơi cố định, xuyên suốt, ghi lại 4 thứ mà AI
> phải làm khi triển khai — để **sau này kiểm chứng lại được** (audit):
> 1. **Quyết định AI tự ra** mà spec/yêu cầu KHÔNG nói → `01-decisions.md` (ID `D-###`)
> 2. **Chỗ AI phải đổi** so với yêu cầu/thiết kế ban đầu → `02-requirement-changes.md` (ID `C-###`)
> 3. **Trade-off** AI phải cân nhắc → `03-tradeoffs.md` (ID `T-###`)
> 4. **Bất kỳ điều gì bạn nên biết** (rủi ro / giả định / nợ / phần CHƯA kiểm) → `04-things-to-know.md` (ID `K-###`)
>
> `00-INDEX.md` = bảng 1 trang gom mọi ID + trạng thái, dùng để **rà kiểm chứng nhanh**.

---

## 0. Vì sao có file này (khác gì `AI-IMPLEMENTATION-LOG.md`?)

| | `AI-IMPLEMENTATION-LOG.md` (gốc repo) | `ai-decision-journal/` (thư mục này) |
|---|---|---|
| Hình thức | Nhật ký **theo thời gian** (append-only, Entry #1→#N) | **View cắt ngang** theo 4 chủ đề, có **ID ổn định** |
| Trả lời câu hỏi | "Phiên đó làm gì, theo thứ tự nào?" | "Mọi quyết định tự-ra / mọi rủi ro CHƯA kiểm đang mở là gì?" |
| Vai trò | **Nguồn sự thật gốc** (canonical, không sửa) | **Chỉ mục kiểm chứng** — mỗi mục TRỎ NGƯỢC về Entry # của log |
| Khi kiểm chứng | Đọc tuần tự, khó tra chéo | Mở `00-INDEX.md` → lọc trạng thái 🔴 → truy nguồn |

→ **Không nhân đôi dữ liệu:** journal này là chỉ mục có ID; mỗi entry BẮT BUỘC ghi `Nguồn:`
trỏ về `AI-IMPLEMENTATION-LOG.md` Entry # / commit / file:line. Khi hai bên mâu thuẫn → **LOG THẮNG**
(nó là canonical); sửa journal cho khớp, đừng sửa log.

## 1. Định dạng 1 entry (tối ưu cho AI đọc — cố định, đừng đổi tuỳ tiện)

Mỗi entry là 1 block bắt đầu bằng heading `### <ID> — <ngày> — <tiêu đề 1 dòng>` rồi các trường
`Key: value` cố định (AI parse được, người đọc cũng được):

```
### D-001 — 2026-07-02 — Control-plane dùng segment tên-cố-định
Status: ✅            # ✅ đã verify · 🟡 đang chờ/đã làm chưa kiểm đủ · 🔴 CHƯA verify / rủi ro mở · ↩️ đã bị đảo
Scope: shm-ring-epoch-switchover / Task 1.1-1.2
Nguồn: LOG Entry #119, #121, #122 · design.md
Evidence: pytest 192 passed/1 skipped; lint 5 kept/0 broken (LOG #122)
Links: T-001, C-001
Nội dung: <mô tả ngắn, ĐỦ để hiểu mà không cần mở log>
Vì sao: <lý do bản chất, không phải cái ngọn>
```

**Quy tắc trường:**
- `Status` — chỉ đổi sang ✅ khi có **bằng chứng** (lệnh + output / nguồn đọc tận nơi). Không có bằng chứng = giữ 🟡/🔴.
- `Nguồn` — BẮT BUỘC. Không có nguồn kiểm được ⇒ không được viết chắc; gắn `[suy đoán]`/`[chưa kiểm]` inline.
- `Evidence` — với code: lệnh đã CHẠY + số thật (vd `pytest 200 passed/1 skipped`). Với kiến thức: link/độ chắc chắn.
- `Links` — ID liên quan (một quyết định thường kèm 1 trade-off + đôi khi 1 điều-nên-biết).
- `↩️` — nếu một entry bị đảo về sau: KHÔNG xoá; đổi `Status: ↩️` + thêm dòng `Đảo bởi: <ID/Entry>`.

## 2. Cách APPEND (mỗi lần AI triển khai có 1 trong 4 loại trên)
1. Chọn đúng file (01/02/03/04), cấp ID kế tiếp (D/C/T/K + số tăng dần, KHÔNG tái dùng số cũ).
2. Ghi entry theo định dạng §1, luôn kèm `Nguồn` + `Evidence`.
3. Thêm 1 dòng vào `00-INDEX.md` (ID · tiêu đề · Status · Nguồn).
4. Vẫn append `AI-IMPLEMENTATION-LOG.md` như luật §2 AGENTS.md (journal KHÔNG thay log).

## 3. Cách KIỂM CHỨNG về sau (audit checklist)
- Mở `00-INDEX.md`, lọc mọi dòng `🔴` và `🟡` → đó là danh sách "chưa chắc chắn" cần đối chiếu.
- Với mỗi entry: mở `Nguồn` (Entry # trong log) → nếu là code, **chạy lại** lệnh trong `Evidence`, so số.
- Nếu số không khớp / file/hàm đã đổi → hạ Status xuống 🔴 + ghi ngày phát hiện; điều tra **gốc** (không vá ngọn).
- Định kỳ (mỗi mốc lớn): rà `04-things-to-know.md` — món 🔴 nào đã đóng thì cập nhật; đừng để rủi ro cũ trôi mất.

## 4. Trạng thái nguồn tại thời điểm seed (2026-07-03, đã verify)
- Log gốc: `AI-IMPLEMENTATION-LOG.md` chạy tới **Entry #127** (grep xác nhận). Log KHỚP git (`b812071` = Entry #127) — **không lệch pha**.
- Nhánh `develop`, **ahead origin/develop 5 commit, CHƯA push** (`git status`).
- Baseline test mới nhất đọc từ LOG/end.md: **200 passed / 1 skipped**, `lint-imports` **5 kept / 0 broken** (commit `b812071`).
- Seed của journal này lấy từ **sub-spec `shm-ring-epoch-switchover`** (biên đang làm) + các rủi ro mở của `#05`.
  Các Entry cũ hơn (#1–#104: hạ tầng học/luật) vẫn nằm trong log canonical, chưa nhân vào đây (thêm khi cần).
