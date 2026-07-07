# Mẩu 01 — Ship = gói phân phối + Definition of Done

**(1) Thuộc về đâu:** bức tranh #10 + phần DoD trong `vision-platform/README.md`.

**(2) Cần biết trước:** "chạy trên máy tôi" ≠ "giao được"; DoD (Definition of Done — tiêu chí "xong");
luật §5 (code = chạy test thật mới gọi xong).

**(3) Bằng chứng thật (quote DoD `README.md`):**
```markdown
## Definition of Done (#10)
- [x] Tests pass: `pytest` → 290 passed, 1 skipped (verify thật).
- [x] No deps leak: `lint-imports` → 5 kept, 0 broken (domain/kernel không import I/O ngoài).
- [x] End-to-end demo chạy (`--source noise` processed 10; `--source fake` skipped 5).
- [x] Package builds: `python -m build` → wheel + sdist; fresh-install `__version__` = 0.1.0.
- [x] README ... kiến trúc + quick start + số thật + trade-offs.
```

**(4) Giải thích từng ý nhỏ:**
- Mỗi mục DoD `[x]` phải kèm **bằng chứng chạy thật** (lệnh + output), không phải "chắc ổn".
- "Tests pass" = số THẬT đã chạy; "No deps leak" = lint gate; "demo chạy" = smoke thật; "builds" = wheel dựng được + cài được.

**(5) Là gì:** DoD = danh sách kiểm đóng, mỗi mục chứng minh bằng lệnh chạy thật, quyết định "đủ điều kiện giao".

**(6) Tại sao tồn tại / vấn đề nó giải:** chống "xong" mơ hồ. Không có DoD → mỗi người hiểu "xong" khác
nhau → vỡ lúc giao/vận hành. DoD biến "xong" thành **kiểm được**.

**(7) Dùng ở đâu trong project:** cuối #10 (README). Mỗi mục neo lệnh: `pytest`, `lint-imports`,
`demo_pipeline`, `python -m build`.

**(8) Không có DoD thì sao:** giao code chưa test đủ / rò rỉ layer / không cài được → sự cố lúc deploy.

**(9) Ví von:** checklist trước khi máy bay cất cánh — từng mục phi công phải xác nhận THẬT (nhìn đồng
hồ), không "chắc ổn". Thiếu 1 mục = không cất cánh.

**(10) Liên kết bức tranh lớn:** DoD là cổng cuối của vòng đời DEFINE→...→SHIP. Nối luật §5 (verify
bằng chạy thật) — mỗi `[x]` là 1 bằng chứng.

**(11) Cạm bẫy:** đừng tick `[x]` khi chưa chạy (dối chính mình). "Type hints" / "idempotent" cần
kiểm thật, không tự tin.

**(12) Tự kiểm:**
- Vì sao "chạy trên máy tôi" chưa phải "ship được"?
- Mỗi mục DoD cần gì để được tick `[x]`?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** `vision-platform/README.md` (DoD) · Design step-10 (Phần 6). Độ chắc: cao (DoD neo lệnh đã chạy thật).
