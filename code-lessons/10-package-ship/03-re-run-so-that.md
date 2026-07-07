# Mẩu 03 — Re-run full suite = DoD + dùng SỐ THẬT (không blueprint)

**(1) Thuộc về đâu:** bước re-run cuối + con số trong `README.md`/DoD. Bài học chống-bịa-số-liệu.

**(2) Cần biết trước:** full test suite; `lint-imports` (ép ranh giới layer); blueprint vs thực tế.

**(3) Bằng chứng thật (output đã chạy):**
```
======================= 290 passed, 1 skipped in 16.60s =======================
Contracts: 5 kept, 0 broken.
```
Design (blueprint `vision_demo`) lại ghi: "110 passed, 1 skipped".

**(4) Giải thích từng ý nhỏ:**
- Re-run TOÀN BỘ suite ở #10 = kiểm không có regression sau mọi thay đổi #01–#09. Đây là "chân lý hiện tại".
- **290 ≠ 110:** dự án THẬT đã tiến hoá vượt blueprint (production-hardening #05 + switchover #05b +
  #06 inference + #07 backpressure + #08 observability + #09 supervisor). README PHẢI ghi 290.
- `5 kept, 0 broken` → ranh giới 6 layer không bị rò rỉ (domain/kernel không import I/O ngoài...).
- `1 skipped` = có chủ đích (guard nền tảng ARM/POSIX skip trên Windows), không phải lỗi.

**(5) Là gì:** cổng kiểm cuối: chạy lại tất cả + báo số THẬT (không copy tài liệu nguồn).

**(6) Tại sao dùng số thật (không blueprint):** copy "110" vào README = **bịa** (số không khớp thực
tế). Tài liệu sai làm mất niềm tin + kiểm chứng sai về sau. Luật §5: khẳng định phải có bằng chứng
chạy thật. Số đúng = số `pytest` in ra.

**(7) Dùng ở đâu trong project:** README "Test count" + DoD ghi 290/1 + note "khác blueprint vì hardening".

**(8) Không re-run / dùng số bịa thì sao:** regression lọt lưới; hoặc README nói 110 trong khi thật
290 → người sau tưởng thiếu/ dư test → mất niềm tin tài liệu.

**(9) Ví von:** cân hàng THẬT trước khi dán nhãn khối lượng — không chép khối lượng "mẫu" trên tờ hướng
dẫn. Nhãn sai = khách mất tin.

**(10) Liên kết bức tranh lớn:** nối văn hoá dự án "không bịa, verify nhiều lần". Số thật đi vào README
+ DoD + journal (C-009). Là ví dụ sống của luật chống-hallucination.

**(11) Cạm bẫy:** đừng lấy số kỳ vọng/blueprint làm số báo cáo. Mỗi lần đổi code → re-run để số luôn
đúng. `1 skipped` phải giải thích (có chủ đích), không lờ đi.

**(12) Tự kiểm:**
- Vì sao README ghi 290 chứ không 110? Điều gì sai nếu copy 110?
- `5 kept, 0 broken` chứng minh điều gì về kiến trúc?

**(13) Mốc ôn:** 1 ngày / 1 tuần / 1 tháng.

**(14) Nguồn:** output `pytest`/`lint-imports` thật (LOG #166) · `README.md` · journal C-009. Độ chắc:
cao (số từ output chạy thật).
