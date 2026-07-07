# Bài 01 — Buổi 01 (2026-06-13): Kiểm môi trường + tạo workspace
> Quy tắc: mỗi lượt CHỈ 1 mẩu nhỏ nhất HOẶC 1 câu hỏi. Không xóa, chỉ thêm.

## [AI] Mẩu #1 — Mục tiêu + tình trạng môi trường
Bài 1 = dựng `vision_demo_workspace/` (project con CHẠY ĐƯỢC). Môi trường của bạn (đã kiểm
bằng lệnh trước đó): **Python 3.12 ✓ · git ✓ · pip ✓**. Project chỉ cần `numpy`, `pytest`,
`import-linter` (cài qua pip khi tới bước đó). `uv` **KHÔNG cần** cho project này.
→ Không thiếu gì để bắt đầu.

**Tự valid:** Python/git/pip đã verify bằng lệnh thật (cao). "uv không cần" vì project dùng
pip deps thuần (cao).

## [AI] Câu hỏi #1
Trước khi gõ lệnh nào — nghĩ thử: **vì sao nên đặt `vision_demo_workspace/` thành project
TÁCH RIÊNG**, thay vì code thẳng vào repo VisionPlatform này?
(Gợi ý: liên quan "tách biệt để lỗi không lan" + tránh lẫn *luật/giáo trình* với *code dự án*.)

## [BẠN] Trả lời #1
- Tôi chưa rõ thư mục sẽ chứa code chính là gì? vision_demo_workspace/ ? rõ rằng tôi không phải làm demo mà làm dự án thật. Nên cần có 1 cái tên hợp lý; Cái khác tôi biết nhưng pip ✓* dùng làm gì tôi không biết. Bạn cần xem lại việc giải thích. Bạn cần có 1 cái file kiến thức phải biết

## [AI] Nhận xét #1
Cảm ơn — phản hồi của bạn đúng, và lỗi là ở TÔI: Mẩu #1 dùng từ chưa giải thích (`pip`...) và
tên `vision_demo_workspace` không hợp. Đã sửa:

1. **Từ lạ (pip, venv...):** đã tạo file `00-can-biet-truoc.md` (cùng folder Bài 1) — giải
   thích plain, không thuật ngữ. `pip` = công cụ tải/cài thư viện Python về máy.
2. **Tên dự án:** bạn đúng — ta làm **dự án thật**, không phải demo. Nên KHÔNG dùng tên
   `vision_demo_workspace`. → Câu hỏi chốt cho bạn (mục dưới).

**Đáp án Câu hỏi #1 (vì sao project TÁCH RIÊNG):** để code dự án **không lẫn** với repo
luật/giáo trình (VisionPlatform) này; và nếu code lỗi/rối thì **chỉ hỏng trong "hộp" riêng**,
không làm hỏng tài liệu + luật. (Đây chính là tinh thần "bulkhead" — vách ngăn.)

## [AI] Câu hỏi #2 (chốt tên dự án)
Dự án THẬT của bạn nên đặt tên thư mục là gì? (vd `headdetect/`, hay tên khác bạn muốn).
Cho tôi tên → ta tạo thư mục đó + venv ở buổi này.

## [BẠN] Trả lời #2
hiện tại để làm thì tôi làm cho về detect nhưng sau này tôi sẽ cho nhiều bài con hiện tại vừa làm nhưng cũng nhằm tới xây base. bạn nghĩ tên gì? 

## [AI] Nhận xét #2 + đề xuất tên
Ý bạn ("1 base, nhiều bài con") KHỚP đúng kiến trúc 6 layer: **base** = phần dùng chung
(domain/kernel/runtime/application/adapters); mỗi **bài con** (detect, sau này thêm) = một
`profiles/<app>` (composition root) cắm vào base. → KHÔNG đặt tên project theo "detect", vì
detect chỉ là 1 app con. Đặt tên theo **base/nền tảng**.

**Đề xuất (chọn 1, đều hợp lệ làm package Python — chữ thường, không gạch ngang):**
- `visionkit/` ← mình KHUYÊN: đọc là "bộ nền tảng thị giác dùng chung"; detect nằm trong `profiles/detect`.
- `visioncore/` — nhấn "lõi/base".
- `visionlab/` — nhấn "nhiều thí nghiệm/bài con".

Cấu trúc hình dung (tên ví dụ `visionkit`):
```
visionkit/                ← project THẬT (base)
  src/visionkit/
    domain/ kernel/ runtime/ application/ adapters/
    profiles/
      detect/             ← bài con #1 (app đầu tiên)
      <bài con sau>/       ← thêm sau, KHÔNG đụng base
```

→ Gõ tên bạn chọn (hoặc "ok" để dùng `visionkit`). Chốt xong mình hướng dẫn bạn **tự gõ** lệnh
tạo thư mục + venv.

## [BẠN] Trả lời #2b (chốt tên)
<gõ tên hoặc "ok">

